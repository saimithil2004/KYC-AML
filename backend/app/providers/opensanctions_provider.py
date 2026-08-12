"""
OpenSanctions Provider
======================
Production-grade PEP and Sanctions screening via the OpenSanctions REST API.
https://api.opensanctions.org/

Features:
  - Async HTTP via httpx.AsyncClient
  - Exponential backoff retry (tenacity)
  - Configurable timeout
  - Per-request Redis caching (TTL-based)
  - Rate-limit header awareness (Retry-After)
  - Structured logging
  - Response validation via Pydantic
  - Graceful degradation (empty list on fatal error)

Environment Variables:
  OPEN_SANCTIONS_API_KEY   : API key from opensanctions.org (required in production)
  OPEN_SANCTIONS_BASE_URL  : Base URL (default: https://api.opensanctions.org)
  OPEN_SANCTIONS_TIMEOUT   : Request timeout in seconds (default: 10)
  OPEN_SANCTIONS_CACHE_TTL : Redis cache TTL in seconds (default: 3600)
"""

import hashlib
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

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
from app.agents.pep.constants import (
    PEP_CATEGORY_DOMESTIC,
    PEP_CATEGORY_FOREIGN,
    PEP_CATEGORY_INTERNATIONAL_ORG,
    PEP_CATEGORY_FAMILY_MEMBER,
    PEP_CATEGORY_CLOSE_ASSOCIATE,
    PEP_CATEGORY_FORMER_PEP,
)
from app.agents.sanctions.constants import (
    SANCTION_CATEGORY_INDIVIDUAL,
    SANCTION_CATEGORY_COMPANY,
    SANCTION_CATEGORY_TERRORIST,
    SANCTION_CATEGORY_FINANCIAL,
    LIST_UN,
    LIST_OFAC,
    LIST_EU,
    LIST_UK_SANCTIONS,
)
from app.agents.screening.constants import ENTITY_INDIVIDUAL, ENTITY_COMPANY

logger = logging.getLogger(__name__)

# ─── Configuration ────────────────────────────────────────────────────────────
_BASE_URL = os.getenv("OPEN_SANCTIONS_BASE_URL", "https://api.opensanctions.org")
_API_KEY = os.getenv("OPEN_SANCTIONS_API_KEY", "")
_TIMEOUT = float(os.getenv("OPEN_SANCTIONS_TIMEOUT", "10"))
_CACHE_TTL = int(os.getenv("OPEN_SANCTIONS_CACHE_TTL", "3600"))
_MAX_RETRIES = 3
_PROVIDER_NAME = "opensanctions"

# Mapping OpenSanctions topic strings → internal constants
_TOPIC_TO_PEP_CATEGORY = {
    "role.pep": PEP_CATEGORY_DOMESTIC,
    "role.pep.domestic": PEP_CATEGORY_DOMESTIC,
    "role.pep.foreign": PEP_CATEGORY_FOREIGN,
    "role.pep.international": PEP_CATEGORY_INTERNATIONAL_ORG,
    "role.rca": PEP_CATEGORY_FAMILY_MEMBER,
    "role.associate": PEP_CATEGORY_CLOSE_ASSOCIATE,
    "role.pep.former": PEP_CATEGORY_FORMER_PEP,
}

_DATASET_TO_SANCTION_LIST = {
    "us_ofac_sdn": LIST_OFAC,
    "us_ofac_cons": LIST_OFAC,
    "un_sc_sanctions": LIST_UN,
    "eu_fsf": LIST_EU,
    "gb_hmt_sanctions": LIST_UK_SANCTIONS,
}


def _cache_key(prefix: str, query: str) -> str:
    """Generates a deterministic Redis cache key from a query string."""
    digest = hashlib.sha256(query.encode()).hexdigest()[:16]
    return f"opensanctions:{prefix}:{digest}"


def _get_redis():
    """Lazy-loads Redis client. Returns None if unavailable."""
    try:
        from app.core.cache import cache
        return cache
    except Exception:
        return None


async def _cached_get(cache_key: str) -> Optional[List[Dict]]:
    """Returns cached result list or None."""
    r = _get_redis()
    if not r:
        return None
    try:
        raw = await r.get(cache_key)
        if raw:
            return json.loads(raw)
    except Exception as exc:
        logger.debug(f"OpenSanctions: Cache read failed: {exc}")
    return None


async def _cache_set(cache_key: str, data: List[Dict]) -> None:
    """Writes a result list to Redis with TTL."""
    r = _get_redis()
    if not r:
        return
    try:
        await r.set(cache_key, json.dumps(data), ex=_CACHE_TTL)
    except Exception as exc:
        logger.debug(f"OpenSanctions: Cache write failed: {exc}")


def _build_headers() -> Dict[str, str]:
    """Builds request headers including API key if configured."""
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    api_key = os.getenv("OPEN_SANCTIONS_API_KEY", "") or _API_KEY
    if api_key:
        headers["Authorization"] = f"ApiKey {api_key}"
    return headers


async def _search_entities(
    query: str,
    schema: str = "Person",
    datasets: Optional[str] = None,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """
    Core HTTP call to OpenSanctions /match endpoint.
    Uses tenacity for exponential-backoff retry.

    Parameters
    ----------
    query   : Full name to search
    schema  : "Person" or "Company" (OpenSanctions entity types)
    datasets: Comma-separated dataset IDs (None = all datasets)
    limit   : Max results to return

    Returns
    -------
    List of raw result dicts from OpenSanctions API.
    """
    ck = _cache_key(schema.lower(), query)
    cached = await _cached_get(ck)
    if cached is not None:
        logger.debug(f"OpenSanctions: Cache hit for '{query}'")
        return cached

    payload: Dict[str, Any] = {
        "queries": {
            "entity": {
                "schema": schema,
                "properties": {"name": [query]},
            }
        },
        "limit": limit,
    }

    params: Dict[str, str] = {}
    if datasets:
        params["dataset"] = datasets

    url = f"{_BASE_URL}/match"
    results: List[Dict] = []

    try:
        async for attempt in AsyncRetrying(
            retry=retry_if_exception_type((httpx.TransportError, httpx.TimeoutException)),
            stop=stop_after_attempt(_MAX_RETRIES),
            wait=wait_exponential(multiplier=1, min=1, max=8),
            reraise=True,
        ):
            with attempt:
                async with httpx.AsyncClient(timeout=_TIMEOUT, headers=_build_headers()) as client:
                    resp = await client.post(url, json=payload, params=params)

                    # Rate limit handling
                    if resp.status_code == 429:
                        retry_after = float(resp.headers.get("Retry-After", "5"))
                        logger.warning(
                            f"OpenSanctions: Rate limited. Retry-After={retry_after}s"
                        )
                        time.sleep(retry_after)
                        raise httpx.TransportError("Rate limited")

                    if resp.status_code == 401:
                        logger.error(
                            "OpenSanctions: Unauthorized — check OPEN_SANCTIONS_API_KEY"
                        )
                        return []

                    resp.raise_for_status()
                    data = resp.json()
                    responses = data.get("responses", {})
                    entity_hits = responses.get("entity", {})
                    results = entity_hits.get("results", [])

    except httpx.HTTPStatusError as exc:
        logger.error(
            f"OpenSanctions: HTTP error {exc.response.status_code} for query '{query}': {exc}"
        )
        return []
    except Exception as exc:
        logger.error(f"OpenSanctions: Unexpected error for query '{query}': {exc}")
        return []

    await _cache_set(ck, results)
    return results


def _result_to_pep_record(result: Dict[str, Any]) -> Optional[PepRecord]:
    """Maps a raw OpenSanctions result dict → PepRecord."""
    try:
        props = result.get("properties", {})
        topics = result.get("topics", [])

        # Determine PEP category from topics
        category = PEP_CATEGORY_DOMESTIC
        for topic in topics:
            if topic in _TOPIC_TO_PEP_CATEGORY:
                category = _TOPIC_TO_PEP_CATEGORY[topic]
                break

        # Extract dates — OpenSanctions uses array properties
        dob_list = props.get("birthDate", [])
        dob = dob_list[0] if dob_list else None

        nationality_list = props.get("nationality", []) or props.get("country", [])
        nationality = nationality_list[0] if nationality_list else None

        names = props.get("name", [])
        full_name = names[0] if names else result.get("caption", "Unknown")

        position_list = props.get("position", [])
        position = position_list[0] if position_list else None

        is_current = "role.pep.former" not in topics

        last_updated = result.get("last_seen", None)

        return PepRecord(
            record_id=result.get("id", "UNKNOWN"),
            full_name=full_name,
            dob=dob,
            nationality=nationality,
            country=nationality,
            category=category,
            position=position,
            is_current=is_current,
            source=_PROVIDER_NAME,
            last_updated=last_updated,
        )
    except Exception as exc:
        logger.warning(f"OpenSanctions: Failed to parse PEP record: {exc}")
        return None


def _result_to_sanction_record(result: Dict[str, Any], entity_type: str) -> Optional[SanctionRecord]:
    """Maps a raw OpenSanctions result dict → SanctionRecord."""
    try:
        props = result.get("properties", {})
        datasets = result.get("datasets", [])

        # Determine sanction list
        sanction_list = LIST_UN  # default
        for ds in datasets:
            if ds in _DATASET_TO_SANCTION_LIST:
                sanction_list = _DATASET_TO_SANCTION_LIST[ds]
                break

        # Determine category from topics
        topics = result.get("topics", [])
        if "sanction.terrorist" in topics:
            sanction_category = SANCTION_CATEGORY_TERRORIST
        elif entity_type == ENTITY_COMPANY:
            sanction_category = SANCTION_CATEGORY_COMPANY
        else:
            sanction_category = SANCTION_CATEGORY_FINANCIAL

        names = props.get("name", [])
        full_name = names[0] if names else result.get("caption", "Unknown")

        aliases = names[1:] if len(names) > 1 else []

        dob_list = props.get("birthDate", [])
        dob = dob_list[0] if dob_list else None

        nationality_list = props.get("nationality", []) or props.get("country", [])
        nationality = nationality_list[0] if nationality_list else None

        passport_list = props.get("passportNumber", [])
        passport_number = passport_list[0] if passport_list else None

        reg_list = props.get("registrationNumber", [])
        registration_number = reg_list[0] if reg_list else None

        address_list = props.get("address", [])
        business_address = address_list[0] if address_list else None

        return SanctionRecord(
            record_id=result.get("id", "UNKNOWN"),
            entity_type=entity_type,
            full_name=full_name,
            aliases=aliases,
            dob=dob,
            nationality=nationality,
            passport_number=passport_number,
            registration_number=registration_number,
            country=nationality,
            business_address=business_address,
            sanction_category=sanction_category,
            sanction_list=sanction_list,
            is_active=True,
            source=_PROVIDER_NAME,
            last_updated=result.get("last_seen"),
        )
    except Exception as exc:
        logger.warning(f"OpenSanctions: Failed to parse Sanction record: {exc}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# OpenSanctions PEP Provider
# ─────────────────────────────────────────────────────────────────────────────
class OpenSanctionsPepProvider(BasePepProvider):
    """
    Production PEP screening via OpenSanctions REST API.
    Searches the 'peps' dataset by default for politically exposed persons.
    """

    @property
    def provider_name(self) -> str:
        return _PROVIDER_NAME

    async def search(self, subject: ScreeningSubject) -> List[PepRecord]:
        logger.info(
            f"OpenSanctions[PEP]: Searching for '{subject.full_name}' "
            f"(DOB={subject.dob}, NAT={subject.nationality})"
        )
        raw_results = await _search_entities(
            query=subject.full_name,
            schema="Person",
            datasets="peps",
            limit=20,
        )
        records: List[PepRecord] = []
        for r in raw_results:
            record = _result_to_pep_record(r)
            if record:
                records.append(record)
        logger.info(
            f"OpenSanctions[PEP]: Found {len(records)} candidates for '{subject.full_name}'"
        )
        return records


# ─────────────────────────────────────────────────────────────────────────────
# OpenSanctions Sanctions Provider
# ─────────────────────────────────────────────────────────────────────────────
class OpenSanctionsSanctionsProvider(BaseSanctionsProvider):
    """
    Production sanctions screening via OpenSanctions REST API.
    Covers OFAC SDN, UN, EU, UK HMT, and 50+ other lists.
    """

    @property
    def provider_name(self) -> str:
        return _PROVIDER_NAME

    async def search_individuals(
        self, subject: ScreeningSubject
    ) -> List[SanctionRecord]:
        logger.info(
            f"OpenSanctions[Sanctions]: Searching individual '{subject.full_name}'"
        )
        raw_results = await _search_entities(
            query=subject.full_name,
            schema="Person",
            datasets="sanctions",
            limit=20,
        )
        records: List[SanctionRecord] = []
        for r in raw_results:
            record = _result_to_sanction_record(r, ENTITY_INDIVIDUAL)
            if record:
                records.append(record)
        logger.info(
            f"OpenSanctions[Sanctions]: Found {len(records)} individual hits for '{subject.full_name}'"
        )
        return records

    async def search_companies(
        self, subject: CompanyScreeningSubject
    ) -> List[SanctionRecord]:
        logger.info(
            f"OpenSanctions[Sanctions]: Searching company '{subject.company_name}'"
        )
        raw_results = await _search_entities(
            query=subject.company_name,
            schema="Company",
            datasets="sanctions",
            limit=20,
        )
        records: List[SanctionRecord] = []
        for r in raw_results:
            record = _result_to_sanction_record(r, ENTITY_COMPANY)
            if record:
                records.append(record)
        logger.info(
            f"OpenSanctions[Sanctions]: Found {len(records)} company hits for '{subject.company_name}'"
        )
        return records
