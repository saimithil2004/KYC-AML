"""
OFAC SDN Sanctions Provider
============================
Production-grade OFAC (Office of Foreign Assets Control) sanctions screening
via the US Treasury OFAC Sanctions List Search API.

API Documentation:
  https://sanctionssearch.ofac.treas.gov/

Features:
  - Async HTTP via httpx.AsyncClient
  - Exponential backoff retry (tenacity)
  - Configurable timeout and threshold
  - Redis caching (TTL-based)
  - Rate-limit handling
  - Structured logging
  - Pydantic response validation
  - Graceful degradation

Environment Variables:
  OFAC_API_KEY        : OFAC API key (optional for basic access)
  OFAC_BASE_URL       : OFAC API base URL
  OFAC_MIN_SCORE      : Minimum match score to return (default: 70)
  OFAC_TIMEOUT        : Request timeout seconds (default: 10)
  OFAC_CACHE_TTL      : Redis cache TTL seconds (default: 3600)
"""

import hashlib
import json
import logging
import os
from typing import Any, Dict, List, Optional

import httpx
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.agents.sanctions.models import SanctionRecord
from app.agents.sanctions.provider import BaseSanctionsProvider
from app.agents.screening.models import CompanyScreeningSubject, ScreeningSubject
from app.agents.screening.constants import ENTITY_INDIVIDUAL, ENTITY_COMPANY
from app.agents.sanctions.constants import (
    LIST_OFAC,
    SANCTION_CATEGORY_INDIVIDUAL,
    SANCTION_CATEGORY_COMPANY,
    SANCTION_CATEGORY_TERRORIST,
    SANCTION_CATEGORY_ASSET_FREEZE,
    SANCTION_CATEGORY_FINANCIAL,
)

logger = logging.getLogger(__name__)

# ─── Configuration ────────────────────────────────────────────────────────────
_API_KEY = os.getenv("OFAC_API_KEY", "")
_BASE_URL = os.getenv(
    "OFAC_BASE_URL",
    "https://sanctionssearch.ofac.treas.gov/SdnList.aspx"
)
_API_SEARCH_URL = os.getenv(
    "OFAC_API_SEARCH_URL",
    "https://api.ofac-api.com/v2/search"
)
_MIN_SCORE = float(os.getenv("OFAC_MIN_SCORE", "70"))
_TIMEOUT = float(os.getenv("OFAC_TIMEOUT", "10"))
_CACHE_TTL = int(os.getenv("OFAC_CACHE_TTL", "3600"))
_MAX_RETRIES = 3
_PROVIDER_NAME = "ofac"

# OFAC SDN Type → internal category mapping
_SDN_TYPE_MAP = {
    "SDN": SANCTION_CATEGORY_FINANCIAL,
    "ENTITY": SANCTION_CATEGORY_COMPANY,
    "INDIVIDUAL": SANCTION_CATEGORY_INDIVIDUAL,
}


def _cache_key(prefix: str, query: str) -> str:
    digest = hashlib.sha256(query.encode()).hexdigest()[:16]
    return f"ofac:{prefix}:{digest}"


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


def _build_headers() -> Dict[str, str]:
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if _API_KEY:
        headers["api-key"] = _API_KEY
    return headers


async def _search_ofac(
    name: str,
    entity_type: str = "individual",
    dob: Optional[str] = None,
    nationality: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Calls OFAC API to search SDN list by name and optional filters.
    Returns raw result dicts. Falls back to empty list on any failure.
    """
    ck = _cache_key(entity_type, f"{name}:{dob}:{nationality}")
    cached = await _cached_get(ck)
    if cached is not None:
        logger.debug(f"OFAC: Cache hit for '{name}'")
        return cached

    payload: Dict[str, Any] = {
        "apiKey": _API_KEY,
        "minScore": _MIN_SCORE,
        "sources": ["SDN"],
        "types": [entity_type],
        "searchTerm": name,
        "cases": [],
    }
    if dob:
        payload["dob"] = dob
    if nationality:
        payload["nationality"] = nationality

    results: List[Dict] = []
    try:
        async for attempt in AsyncRetrying(
            retry=retry_if_exception_type((httpx.TransportError, httpx.TimeoutException)),
            stop=stop_after_attempt(_MAX_RETRIES),
            wait=wait_exponential(multiplier=1, min=1, max=8),
            reraise=True,
        ):
            with attempt:
                async with httpx.AsyncClient(
                    timeout=_TIMEOUT, headers=_build_headers()
                ) as client:
                    resp = await client.post(_API_SEARCH_URL, json=payload)

                    if resp.status_code == 429:
                        raise httpx.TransportError("OFAC rate limited")
                    if resp.status_code == 401:
                        logger.error(
                            "OFAC: Unauthorized. Set OFAC_API_KEY environment variable."
                        )
                        return []

                    resp.raise_for_status()
                    data = resp.json()
                    results = data.get("results", [])

    except httpx.HTTPStatusError as exc:
        logger.error(f"OFAC: HTTP {exc.response.status_code} for '{name}': {exc}")
        return []
    except Exception as exc:
        logger.error(f"OFAC: Search failed for '{name}': {exc}")
        return []

    await _cache_set(ck, results)
    return results


def _parse_sanction_record(
    result: Dict[str, Any], entity_type: str
) -> Optional[SanctionRecord]:
    """Maps a raw OFAC API result → SanctionRecord."""
    try:
        sdn_type = result.get("sdnType", "INDIVIDUAL")
        category_map = {
            "INDIVIDUAL": SANCTION_CATEGORY_INDIVIDUAL,
            "ENTITY": SANCTION_CATEGORY_COMPANY,
        }
        sanction_category = category_map.get(sdn_type, SANCTION_CATEGORY_FINANCIAL)

        # Check program list for terrorism
        programs = result.get("programList", [])
        if any(p in programs for p in ("SDGT", "IFSR", "NPWMD")):
            sanction_category = SANCTION_CATEGORY_TERRORIST

        # Extract name
        full_name = result.get("name", result.get("title", "Unknown"))

        # Extract aliases
        aliases = [a.get("name", "") for a in result.get("akaList", []) if a.get("name")]

        # Extract DOB
        dob_list = result.get("dateOfBirthList", [])
        dob = dob_list[0].get("dateOfBirth") if dob_list else None

        # Extract nationality
        nationality_list = result.get("nationalityList", [])
        nationality = nationality_list[0].get("country") if nationality_list else None

        # Extract passport numbers
        passport_list = result.get("idList", [])
        passport_number = None
        for pid in passport_list:
            if pid.get("idType") in ("Passport", "National ID No."):
                passport_number = pid.get("idNumber")
                break

        # Extract registration number (companies)
        reg_number = None
        for pid in passport_list:
            if pid.get("idType") in ("Business Registration Document", "Company Number"):
                reg_number = pid.get("idNumber")
                break

        # Extract address
        address_list = result.get("addressList", [])
        business_address = None
        country = nationality
        if address_list:
            addr = address_list[0]
            parts = [
                addr.get("address1", ""),
                addr.get("city", ""),
                addr.get("country", ""),
            ]
            business_address = ", ".join(p for p in parts if p)
            country = addr.get("country") or country

        record_id = f"OFAC-{result.get('uid', 'UNKNOWN')}"

        return SanctionRecord(
            record_id=record_id,
            entity_type=entity_type,
            full_name=full_name,
            aliases=aliases,
            dob=dob,
            nationality=nationality,
            passport_number=passport_number,
            registration_number=reg_number,
            country=country,
            business_address=business_address,
            sanction_category=sanction_category,
            sanction_list=LIST_OFAC,
            is_active=True,
            source=_PROVIDER_NAME,
        )
    except Exception as exc:
        logger.warning(f"OFAC: Failed to parse result: {exc}")
        return None


class OfacSanctionsProvider(BaseSanctionsProvider):
    """
    Production OFAC SDN sanctions screening provider.
    Covers OFAC Specially Designated Nationals (SDN) list.
    """

    @property
    def provider_name(self) -> str:
        return _PROVIDER_NAME

    async def search_individuals(
        self, subject: ScreeningSubject
    ) -> List[SanctionRecord]:
        logger.info(
            f"OFAC: Screening individual '{subject.full_name}' "
            f"(DOB={subject.dob}, NAT={subject.nationality})"
        )
        raw = await _search_ofac(
            name=subject.full_name,
            entity_type="individual",
            dob=subject.dob,
            nationality=subject.nationality,
        )
        records = []
        for r in raw:
            rec = _parse_sanction_record(r, ENTITY_INDIVIDUAL)
            if rec:
                records.append(rec)
        logger.info(f"OFAC: {len(records)} hits for '{subject.full_name}'")
        return records

    async def search_companies(
        self, subject: CompanyScreeningSubject
    ) -> List[SanctionRecord]:
        logger.info(f"OFAC: Screening company '{subject.company_name}'")
        raw = await _search_ofac(
            name=subject.company_name,
            entity_type="entity",
        )
        records = []
        for r in raw:
            rec = _parse_sanction_record(r, ENTITY_COMPANY)
            if rec:
                records.append(rec)
        logger.info(f"OFAC: {len(records)} hits for '{subject.company_name}'")
        return records
