"""
Dow Jones Risk & Compliance Provider
======================================
Production PEP and Sanctions screening via the Dow Jones Risk & Compliance API.
https://developer.dowjones.com/risk-and-compliance

Features:
  - Async HTTP via httpx.AsyncClient
  - Bearer token authentication
  - Exponential backoff retry (tenacity)
  - Redis caching (TTL-based)
  - Rate-limit handling
  - Structured logging
  - Response validation
  - Graceful degradation

Environment Variables:
  DOW_JONES_API_KEY     : Dow Jones API credentials (client ID or key)
  DOW_JONES_API_SECRET  : Dow Jones API secret (for OAuth token endpoint)
  DOW_JONES_BASE_URL    : API base URL
  DOW_JONES_TIMEOUT     : Request timeout in seconds (default: 15)
  DOW_JONES_CACHE_TTL   : Redis cache TTL in seconds (default: 3600)
"""

import hashlib
import json
import logging
import os
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
    SANCTION_CATEGORY_FINANCIAL,
    LIST_OFAC,
    LIST_UN,
    LIST_EU,
    LIST_UK_SANCTIONS,
)

logger = logging.getLogger(__name__)

# ─── Configuration ────────────────────────────────────────────────────────────
_API_KEY = os.getenv("DOW_JONES_API_KEY", "")
_API_SECRET = os.getenv("DOW_JONES_API_SECRET", "")
_BASE_URL = os.getenv(
    "DOW_JONES_BASE_URL",
    "https://api.dowjones.com/risk-and-compliance/v1"
)
_TOKEN_URL = os.getenv(
    "DOW_JONES_TOKEN_URL",
    "https://accounts.dowjones.com/oauth2/v1/token"
)
_TIMEOUT = float(os.getenv("DOW_JONES_TIMEOUT", "15"))
_CACHE_TTL = int(os.getenv("DOW_JONES_CACHE_TTL", "3600"))
_MAX_RETRIES = 3
_PROVIDER_NAME = "dowjones"

# Dow Jones category strings → internal PEP categories
_DJ_CATEGORY_MAP = {
    "PEP": PEP_CATEGORY_DOMESTIC,
    "Domestic PEP": PEP_CATEGORY_DOMESTIC,
    "Foreign PEP": PEP_CATEGORY_FOREIGN,
    "International Organisation": PEP_CATEGORY_INTERNATIONAL_ORG,
    "Family Member": PEP_CATEGORY_FAMILY_MEMBER,
    "Close Associate": PEP_CATEGORY_CLOSE_ASSOCIATE,
    "Former PEP": PEP_CATEGORY_FORMER_PEP,
}

_DJ_SOURCE_MAP = {
    "OFAC": LIST_OFAC,
    "UN": LIST_UN,
    "EU": LIST_EU,
    "HMT": LIST_UK_SANCTIONS,
    "UK": LIST_UK_SANCTIONS,
}

# In-process token cache (avoids re-authentication on every call)
_token_cache: Dict[str, Any] = {"token": None, "expires_at": 0}


def _cache_key(prefix: str, query: str) -> str:
    digest = hashlib.sha256(query.encode()).hexdigest()[:16]
    return f"dowjones:{prefix}:{digest}"


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


async def _get_access_token() -> Optional[str]:
    """
    Obtains a Bearer token from Dow Jones OAuth2 endpoint.
    Caches the token in-process until expiry.
    """
    import time
    if not _API_KEY or not _API_SECRET:
        return None

    now = time.time()
    if _token_cache["token"] and now < _token_cache["expires_at"] - 60:
        return _token_cache["token"]

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                _TOKEN_URL,
                data={
                    "grant_type": "client_credentials",
                    "client_id": _API_KEY,
                    "client_secret": _API_SECRET,
                    "scope": "compliance",
                },
            )
            resp.raise_for_status()
            token_data = resp.json()
            _token_cache["token"] = token_data.get("access_token")
            _token_cache["expires_at"] = now + int(token_data.get("expires_in", 3600))
            return _token_cache["token"]
    except Exception as exc:
        logger.error(f"Dow Jones: Token acquisition failed: {exc}")
        return None


async def _dj_search(
    name: str,
    entity_type: str = "person",
    dob: Optional[str] = None,
    country: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Calls Dow Jones Risk & Compliance API to search by name.
    Returns raw result dicts. Falls back to empty list on failure.
    """
    if not _API_KEY:
        logger.warning(
            "Dow Jones: DOW_JONES_API_KEY not set — provider unavailable"
        )
        return []

    ck = _cache_key(entity_type, f"{name}:{dob}:{country}")
    cached = await _cached_get(ck)
    if cached is not None:
        logger.debug(f"Dow Jones: Cache hit for '{name}'")
        return cached

    token = await _get_access_token()
    if not token:
        logger.error("Dow Jones: Cannot authenticate — check DOW_JONES credentials")
        return []

    params: Dict[str, str] = {
        "name": name,
        "entityType": entity_type,
        "limit": "20",
    }
    if dob:
        params["dateOfBirth"] = dob
    if country:
        params["countryCode"] = country

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }

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
                    resp = await client.get(
                        f"{_BASE_URL}/search",
                        params=params,
                        headers=headers,
                    )
                    if resp.status_code == 429:
                        raise httpx.TransportError("Dow Jones rate limited")
                    if resp.status_code in (401, 403):
                        logger.error(
                            "Dow Jones: Auth failed — token may be expired or invalid"
                        )
                        _token_cache["token"] = None  # Force re-auth next call
                        return []
                    resp.raise_for_status()
                    data = resp.json()
                    results = data.get("entities", data.get("results", []))

    except httpx.HTTPStatusError as exc:
        logger.error(f"Dow Jones: HTTP {exc.response.status_code} for '{name}': {exc}")
        return []
    except Exception as exc:
        logger.error(f"Dow Jones: Search failed for '{name}': {exc}")
        return []

    await _cache_set(ck, results)
    return results


def _parse_pep_record(result: Dict[str, Any]) -> Optional[PepRecord]:
    """Maps a Dow Jones result → PepRecord."""
    try:
        categories = result.get("categories", [])
        category = PEP_CATEGORY_DOMESTIC
        for cat_name, mapped in _DJ_CATEGORY_MAP.items():
            if any(cat_name.lower() in c.lower() for c in categories):
                category = mapped
                break

        full_name = (
            result.get("name")
            or result.get("displayName")
            or result.get("primaryName", "Unknown")
        )

        dob = result.get("dateOfBirth") or result.get("birthDate")
        nationality = result.get("nationality") or result.get("countryOfBirth")
        position = result.get("position") or result.get("title")

        positions_list = result.get("positions", [])
        if positions_list and not position:
            position = positions_list[0].get("title") if positions_list else None

        is_current = not any(
            "former" in c.lower() or "prev" in c.lower() for c in categories
        )

        return PepRecord(
            record_id=result.get("id", f"DJ-{uuid4().hex[:8]}"),
            full_name=full_name,
            dob=dob,
            nationality=nationality,
            country=nationality,
            category=category,
            position=position,
            is_current=is_current,
            source=_PROVIDER_NAME,
            last_updated=result.get("lastUpdated") or result.get("updatedDate"),
        )
    except Exception as exc:
        logger.warning(f"Dow Jones: Failed to parse PEP record: {exc}")
        return None


def _parse_sanction_record(
    result: Dict[str, Any], entity_type: str
) -> Optional[SanctionRecord]:
    """Maps a Dow Jones result → SanctionRecord."""
    try:
        sources = result.get("sources", result.get("sanctionLists", []))
        sanction_list = LIST_UN
        for src in sources:
            src_str = str(src).upper()
            for prefix, lst in _DJ_SOURCE_MAP.items():
                if prefix in src_str:
                    sanction_list = lst
                    break

        categories = result.get("categories", [])
        sanction_category = SANCTION_CATEGORY_FINANCIAL
        if any("terror" in c.lower() for c in categories):
            sanction_category = SANCTION_CATEGORY_TERRORIST
        elif entity_type == ENTITY_COMPANY:
            sanction_category = SANCTION_CATEGORY_COMPANY

        full_name = (
            result.get("name")
            or result.get("displayName")
            or result.get("primaryName", "Unknown")
        )

        aliases = result.get("aliases", result.get("altNames", []))
        if isinstance(aliases, list):
            aliases = [a if isinstance(a, str) else a.get("name", "") for a in aliases]
        else:
            aliases = []

        dob = result.get("dateOfBirth") or result.get("birthDate")
        nationality = result.get("nationality") or result.get("countryCode")
        passport_number = result.get("passportNumber")
        reg_number = result.get("registrationNumber") or result.get("companyNumber")
        business_address = result.get("address") or result.get("registeredAddress")

        return SanctionRecord(
            record_id=result.get("id", f"DJ-{uuid4().hex[:8]}"),
            entity_type=entity_type,
            full_name=full_name,
            aliases=[a for a in aliases if a],
            dob=dob,
            nationality=nationality,
            passport_number=passport_number,
            registration_number=reg_number,
            country=nationality,
            business_address=business_address,
            sanction_category=sanction_category,
            sanction_list=sanction_list,
            is_active=True,
            source=_PROVIDER_NAME,
        )
    except Exception as exc:
        logger.warning(f"Dow Jones: Failed to parse sanction record: {exc}")
        return None


class DowJonesPepProvider(BasePepProvider):
    """Production PEP screening via Dow Jones Risk & Compliance API."""

    @property
    def provider_name(self) -> str:
        return _PROVIDER_NAME

    async def search(self, subject: ScreeningSubject) -> List[PepRecord]:
        logger.info(f"Dow Jones[PEP]: Screening '{subject.full_name}'")
        raw = await _dj_search(
            name=subject.full_name,
            entity_type="person",
            dob=subject.dob,
            country=subject.nationality,
        )
        records = []
        for r in raw:
            cats = r.get("categories", [])
            if any("pep" in c.lower() for c in cats):
                rec = _parse_pep_record(r)
                if rec:
                    records.append(rec)
        logger.info(f"Dow Jones[PEP]: {len(records)} hits for '{subject.full_name}'")
        return records


class DowJonesSanctionsProvider(BaseSanctionsProvider):
    """Production Sanctions screening via Dow Jones Risk & Compliance API."""

    @property
    def provider_name(self) -> str:
        return _PROVIDER_NAME

    async def search_individuals(
        self, subject: ScreeningSubject
    ) -> List[SanctionRecord]:
        logger.info(f"Dow Jones[Sanctions]: Screening individual '{subject.full_name}'")
        raw = await _dj_search(
            name=subject.full_name,
            entity_type="person",
            dob=subject.dob,
            country=subject.nationality,
        )
        records = []
        for r in raw:
            cats = r.get("categories", [])
            if any("sanction" in c.lower() for c in cats):
                rec = _parse_sanction_record(r, ENTITY_INDIVIDUAL)
                if rec:
                    records.append(rec)
        logger.info(
            f"Dow Jones[Sanctions]: {len(records)} hits for '{subject.full_name}'"
        )
        return records

    async def search_companies(
        self, subject: CompanyScreeningSubject
    ) -> List[SanctionRecord]:
        logger.info(f"Dow Jones[Sanctions]: Screening company '{subject.company_name}'")
        raw = await _dj_search(
            name=subject.company_name,
            entity_type="company",
            country=subject.country,
        )
        records = []
        for r in raw:
            cats = r.get("categories", [])
            if any("sanction" in c.lower() for c in cats):
                rec = _parse_sanction_record(r, ENTITY_COMPANY)
                if rec:
                    records.append(rec)
        logger.info(
            f"Dow Jones[Sanctions]: {len(records)} hits for '{subject.company_name}'"
        )
        return records
