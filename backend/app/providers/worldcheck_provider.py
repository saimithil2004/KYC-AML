"""
World-Check One Provider (Refinitiv / LSEG)
============================================
Production PEP and Sanctions screening via the Refinitiv World-Check One REST API.
https://developers.refinitiv.com/en/api-catalog/world-check-one/world-check-one-api

Features:
  - Async HTTP via httpx.AsyncClient
  - HMAC-SHA256 request signing (World-Check authentication scheme)
  - Exponential backoff retry (tenacity)
  - Configurable timeout
  - Redis caching (TTL-based)
  - Rate-limit handling
  - Structured logging
  - Pydantic-compatible response parsing
  - Graceful degradation to empty list on failure

Environment Variables:
  WORLD_CHECK_API_KEY     : World-Check API key (Gateway ID)
  WORLD_CHECK_API_SECRET  : World-Check API secret (for HMAC signing)
  WORLD_CHECK_BASE_URL    : API base URL (default prod URL)
  WORLD_CHECK_GROUP_ID    : Your organisation group ID
  WORLD_CHECK_TIMEOUT     : Request timeout in seconds (default: 15)
  WORLD_CHECK_CACHE_TTL   : Redis cache TTL in seconds (default: 3600)
"""

import hashlib
import hmac
import json
import logging
import os
import time
from base64 import b64encode
from typing import Any, Dict, List, Optional
from uuid import uuid4

import httpx
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.agents.pep.models import PepRecord, ScreeningSubject
from app.agents.pep.provider import BasePepProvider
from app.agents.sanctions.models import SanctionRecord
from app.agents.sanctions.provider import BaseSanctionsProvider
from app.agents.screening.models import CompanyScreeningSubject
from app.agents.screening.constants import ENTITY_INDIVIDUAL, ENTITY_COMPANY
from app.agents.pep.constants import (
    PEP_CATEGORY_DOMESTIC,
    PEP_CATEGORY_FOREIGN,
    PEP_CATEGORY_FAMILY_MEMBER,
    PEP_CATEGORY_CLOSE_ASSOCIATE,
    PEP_CATEGORY_FORMER_PEP,
    PEP_CATEGORY_INTERNATIONAL_ORG,
)
from app.agents.sanctions.constants import (
    SANCTION_CATEGORY_INDIVIDUAL,
    SANCTION_CATEGORY_COMPANY,
    SANCTION_CATEGORY_TERRORIST,
    SANCTION_CATEGORY_ASSET_FREEZE,
    SANCTION_CATEGORY_FINANCIAL,
    LIST_OFAC,
    LIST_UN,
    LIST_EU,
    LIST_UK_SANCTIONS,
)

logger = logging.getLogger(__name__)

# ─── Configuration ────────────────────────────────────────────────────────────
_API_KEY = os.getenv("WORLD_CHECK_API_KEY", "")
_API_SECRET = os.getenv("WORLD_CHECK_API_SECRET", "")
_BASE_URL = os.getenv(
    "WORLD_CHECK_BASE_URL",
    "https://rms-world-check-one-api-pilot.thomsonreuters.com/v2"
)
_GROUP_ID = os.getenv("WORLD_CHECK_GROUP_ID", "")
_TIMEOUT = float(os.getenv("WORLD_CHECK_TIMEOUT", "15"))
_CACHE_TTL = int(os.getenv("WORLD_CHECK_CACHE_TTL", "3600"))
_MAX_RETRIES = 3
_PROVIDER_NAME = "worldcheck"

# World-Check category codes → internal PEP category
_WC_CATEGORY_TO_PEP = {
    "PEP": PEP_CATEGORY_DOMESTIC,
    "PEP-CLASS-1": PEP_CATEGORY_DOMESTIC,
    "PEP-CLASS-2": PEP_CATEGORY_FOREIGN,
    "PEP-CLASS-3": PEP_CATEGORY_INTERNATIONAL_ORG,
    "PEP-CLASS-4": PEP_CATEGORY_FAMILY_MEMBER,
    "RCA": PEP_CATEGORY_CLOSE_ASSOCIATE,
    "PREV-PEP": PEP_CATEGORY_FORMER_PEP,
}

# World-Check source codes → internal list
_WC_SOURCE_TO_LIST = {
    "OFAC": LIST_OFAC,
    "UN": LIST_UN,
    "EU": LIST_EU,
    "UK-HMT": LIST_UK_SANCTIONS,
}


def _sign_request(method: str, path: str, body: str = "") -> Dict[str, str]:
    """
    Generates HMAC-SHA256 signed headers for World-Check One API.
    Reference: https://developers.refinitiv.com/en/api-catalog/world-check-one
    """
    if not _API_KEY or not _API_SECRET:
        return {"Authorization": "", "Date": ""}

    date = time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime())
    request_id = str(uuid4())

    body_hash = ""
    if body:
        body_bytes = body.encode("utf-8")
        body_hash = b64encode(hashlib.sha256(body_bytes).digest()).decode()

    string_to_sign = (
        f"date: {date}\n"
        f"(request-target): {method.lower()} {path}\n"
        f"x-request-id: {request_id}\n"
        f"content-type: application/json\n"
    )
    if body_hash:
        string_to_sign += f"digest: SHA-256={body_hash}\n"

    signature = b64encode(
        hmac.new(
            _API_SECRET.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            hashlib.sha256,
        ).digest()
    ).decode()

    auth_header = (
        f'Signature keyId="{_API_KEY}",'
        f'algorithm="hmac-sha256",'
        f'headers="date (request-target) x-request-id content-type{"" if not body else " digest"}",'
        f'signature="{signature}"'
    )
    headers = {
        "Authorization": auth_header,
        "Date": date,
        "X-Request-Id": request_id,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if body_hash:
        headers["Digest"] = f"SHA-256={body_hash}"
    return headers


def _cache_key(prefix: str, query: str) -> str:
    digest = hashlib.sha256(query.encode()).hexdigest()[:16]
    return f"worldcheck:{prefix}:{digest}"


def _get_redis():
    try:
        from app.core.cache import cache
        return cache
    except Exception:
        return None


async def _cached_get(key: str) -> Optional[List[Dict]]:
    r = _get_redis()
    if not r:
        return None
    try:
        raw = await r.get(key)
        if raw:
            return json.loads(raw)
    except Exception:
        pass
    return None


async def _cache_set(key: str, data: List[Dict]) -> None:
    r = _get_redis()
    if not r:
        return
    try:
        await r.set(key, json.dumps(data), ex=_CACHE_TTL)
    except Exception:
        pass


async def _wc_search(
    name: str,
    entity_type: str = "INDIVIDUAL",
    dob: Optional[str] = None,
    country_code: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Performs a World-Check One case screening via the REST API.
    Uses POST /cases endpoint to create a case, then reads results.

    Falls back to empty list on any API key misconfiguration or failure.
    """
    if not _API_KEY or not _API_SECRET or not _GROUP_ID:
        logger.warning(
            "World-Check: Missing WORLD_CHECK_API_KEY/SECRET/GROUP_ID — "
            "screening unavailable. Set environment variables."
        )
        return []

    ck = _cache_key(entity_type.lower(), f"{name}:{dob}:{country_code}")
    cached = await _cached_get(ck)
    if cached is not None:
        logger.debug(f"World-Check: Cache hit for '{name}'")
        return cached

    # Build search payload
    primary_name = {
        "givenNames": name.split()[:-1] if " " in name else [name],
        "surname": name.split()[-1] if " " in name else "",
    }
    entity = {
        "entityType": entity_type,
        "primaryName": primary_name,
    }
    if entity_type == "INDIVIDUAL":
        if dob:
            entity["dateOfBirth"] = {"dateOfBirth": dob, "approximate": False}
        if country_code:
            entity["nationalities"] = [{"countryCode": country_code}]
    elif entity_type == "ORGANISATION":
        entity["primaryName"] = {"organisationName": name}
        if country_code:
            entity["incorporationCountries"] = [{"countryCode": country_code}]

    payload_dict = {
        "groupId": _GROUP_ID,
        "entityType": entity_type,
        "primaryName": primary_name if entity_type == "INDIVIDUAL" else {"organisationName": name},
    }
    payload = json.dumps(payload_dict)
    path = "/v2/cases"
    headers = _sign_request("POST", path, payload)

    results: List[Dict] = []
    try:
        async for attempt in AsyncRetrying(
            retry=retry_if_exception_type((httpx.TransportError, httpx.TimeoutException)),
            stop=stop_after_attempt(_MAX_RETRIES),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            reraise=True,
        ):
            with attempt:
                async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                    resp = await client.post(
                        f"{_BASE_URL}/cases",
                        content=payload,
                        headers=headers,
                    )
                    if resp.status_code == 429:
                        retry_after = float(resp.headers.get("Retry-After", "5"))
                        logger.warning(
                            f"World-Check: Rate limited. Retry-After={retry_after}s"
                        )
                        raise httpx.TransportError("Rate limited")
                    if resp.status_code in (401, 403):
                        logger.error(
                            "World-Check: Authentication failed — check WORLD_CHECK credentials"
                        )
                        return []
                    resp.raise_for_status()
                    data = resp.json()
                    results = data.get("results", [])

    except httpx.HTTPStatusError as exc:
        logger.error(
            f"World-Check: HTTP {exc.response.status_code} for '{name}': {exc}"
        )
        return []
    except Exception as exc:
        logger.error(f"World-Check: Search failed for '{name}': {exc}")
        return []

    await _cache_set(ck, results)
    return results


def _parse_pep_record(result: Dict[str, Any]) -> Optional[PepRecord]:
    """Maps a World-Check result → PepRecord."""
    try:
        categories = result.get("categories", [])
        category = PEP_CATEGORY_DOMESTIC
        for cat in categories:
            mapped = _WC_CATEGORY_TO_PEP.get(cat)
            if mapped:
                category = mapped
                break

        name = result.get("primaryName", {})
        given_names = " ".join(name.get("givenNames", []))
        surname = name.get("surname", "")
        full_name = f"{given_names} {surname}".strip() or result.get("name", "Unknown")

        dob_info = result.get("dateOfBirth", {})
        dob = dob_info.get("dateOfBirth")

        nats = result.get("nationalities", [])
        nationality = nats[0].get("countryCode") if nats else None

        position_list = result.get("positions", [])
        position = position_list[0].get("title") if position_list else None

        is_current = "PREV-PEP" not in categories and "FORMER" not in " ".join(categories)

        return PepRecord(
            record_id=result.get("id", f"WC-{uuid4().hex[:8]}"),
            full_name=full_name,
            dob=dob,
            nationality=nationality,
            country=nationality,
            category=category,
            position=position,
            is_current=is_current,
            source=_PROVIDER_NAME,
            last_updated=result.get("lastUpdated"),
        )
    except Exception as exc:
        logger.warning(f"World-Check: Failed to parse PEP record: {exc}")
        return None


def _parse_sanction_record(
    result: Dict[str, Any], entity_type: str
) -> Optional[SanctionRecord]:
    """Maps a World-Check result → SanctionRecord."""
    try:
        sources = result.get("sources", [])
        sanction_list = LIST_UN  # default
        for src in sources:
            src_id = src.get("sourceId", "")
            for prefix, lst in _WC_SOURCE_TO_LIST.items():
                if prefix in src_id.upper():
                    sanction_list = lst
                    break

        categories = result.get("categories", [])
        sanction_category = SANCTION_CATEGORY_FINANCIAL
        if any("TERRORIST" in c.upper() or "TERROR" in c.upper() for c in categories):
            sanction_category = SANCTION_CATEGORY_TERRORIST
        elif entity_type == ENTITY_COMPANY:
            sanction_category = SANCTION_CATEGORY_COMPANY

        name = result.get("primaryName", {})
        if entity_type == ENTITY_INDIVIDUAL:
            given_names = " ".join(name.get("givenNames", []))
            surname = name.get("surname", "")
            full_name = f"{given_names} {surname}".strip()
        else:
            full_name = name.get("organisationName", result.get("name", "Unknown"))

        aliases = [
            a.get("primaryName", {}).get("organisationName", "")
            or " ".join(
                a.get("primaryName", {}).get("givenNames", []) +
                [a.get("primaryName", {}).get("surname", "")]
            )
            for a in result.get("altNames", [])
        ]
        aliases = [a.strip() for a in aliases if a.strip()]

        dob_info = result.get("dateOfBirth", {})
        dob = dob_info.get("dateOfBirth")

        nats = result.get("nationalities", [])
        nationality = nats[0].get("countryCode") if nats else None

        ids = result.get("identities", [])
        passport_number = None
        reg_number = None
        for id_doc in ids:
            doc_type = id_doc.get("identityType", "")
            if "PASSPORT" in doc_type.upper():
                passport_number = id_doc.get("identityValue")
            elif "REG" in doc_type.upper() or "COMPANY" in doc_type.upper():
                reg_number = id_doc.get("identityValue")

        return SanctionRecord(
            record_id=result.get("id", f"WC-{uuid4().hex[:8]}"),
            entity_type=entity_type,
            full_name=full_name,
            aliases=aliases,
            dob=dob,
            nationality=nationality,
            passport_number=passport_number,
            registration_number=reg_number,
            country=nationality,
            sanction_category=sanction_category,
            sanction_list=sanction_list,
            is_active=True,
            source=_PROVIDER_NAME,
        )
    except Exception as exc:
        logger.warning(f"World-Check: Failed to parse sanction record: {exc}")
        return None


class WorldCheckPepProvider(BasePepProvider):
    """Production PEP screening via Refinitiv World-Check One."""

    @property
    def provider_name(self) -> str:
        return _PROVIDER_NAME

    async def search(self, subject: ScreeningSubject) -> List[PepRecord]:
        logger.info(f"World-Check[PEP]: Screening '{subject.full_name}'")
        raw = await _wc_search(
            name=subject.full_name,
            entity_type="INDIVIDUAL",
            dob=subject.dob,
            country_code=subject.nationality,
        )
        records = []
        for r in raw:
            # Only return PEP-category results
            if any(c in r.get("categories", []) for c in _WC_CATEGORY_TO_PEP):
                rec = _parse_pep_record(r)
                if rec:
                    records.append(rec)
        logger.info(f"World-Check[PEP]: {len(records)} PEP hits for '{subject.full_name}'")
        return records


class WorldCheckSanctionsProvider(BaseSanctionsProvider):
    """Production Sanctions screening via Refinitiv World-Check One."""

    @property
    def provider_name(self) -> str:
        return _PROVIDER_NAME

    async def search_individuals(
        self, subject: ScreeningSubject
    ) -> List[SanctionRecord]:
        logger.info(f"World-Check[Sanctions]: Screening individual '{subject.full_name}'")
        raw = await _wc_search(
            name=subject.full_name,
            entity_type="INDIVIDUAL",
            dob=subject.dob,
            country_code=subject.nationality,
        )
        records = []
        for r in raw:
            if r.get("isSanctioned") or any(
                "SANCTION" in c.upper() for c in r.get("categories", [])
            ):
                rec = _parse_sanction_record(r, ENTITY_INDIVIDUAL)
                if rec:
                    records.append(rec)
        logger.info(
            f"World-Check[Sanctions]: {len(records)} hits for '{subject.full_name}'"
        )
        return records

    async def search_companies(
        self, subject: CompanyScreeningSubject
    ) -> List[SanctionRecord]:
        logger.info(f"World-Check[Sanctions]: Screening company '{subject.company_name}'")
        raw = await _wc_search(
            name=subject.company_name,
            entity_type="ORGANISATION",
            country_code=subject.country,
        )
        records = []
        for r in raw:
            if r.get("isSanctioned") or any(
                "SANCTION" in c.upper() for c in r.get("categories", [])
            ):
                rec = _parse_sanction_record(r, ENTITY_COMPANY)
                if rec:
                    records.append(rec)
        logger.info(
            f"World-Check[Sanctions]: {len(records)} hits for '{subject.company_name}'"
        )
        return records
