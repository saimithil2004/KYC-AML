"""
Companies House UK Provider
============================
Production company verification via the UK Companies House REST API.
https://developer.company-information.service.gov.uk/

Features:
  - Async HTTP via httpx.AsyncClient
  - Basic Auth (API key as username, no password)
  - Exponential backoff retry (tenacity)
  - Redis caching (TTL-based)
  - Rate-limit handling (429 responses)
  - Structured logging
  - Response validation
  - Graceful degradation

Used by:
  - CompanyAgent (verifies company registration)
  - UboAgent (verifies UBO company associations)
  - DirectorAgent (verifies directorship records)

Environment Variables:
  COMPANIES_HOUSE_API_KEY   : API key from Companies House developer portal
  COMPANIES_HOUSE_BASE_URL  : API base URL (default: https://api.company-information.service.gov.uk)
  COMPANIES_HOUSE_TIMEOUT   : Request timeout in seconds (default: 10)
  COMPANIES_HOUSE_CACHE_TTL : Redis cache TTL in seconds (default: 1800)
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

logger = logging.getLogger(__name__)

# ─── Configuration ────────────────────────────────────────────────────────────
_API_KEY = os.getenv("COMPANIES_HOUSE_API_KEY", "")
_BASE_URL = os.getenv(
    "COMPANIES_HOUSE_BASE_URL",
    "https://api.company-information.service.gov.uk"
)
_TIMEOUT = float(os.getenv("COMPANIES_HOUSE_TIMEOUT", "10"))
_CACHE_TTL = int(os.getenv("COMPANIES_HOUSE_CACHE_TTL", "1800"))
_MAX_RETRIES = 3
_PROVIDER_NAME = "companies_house"


def _cache_key(prefix: str, query: str) -> str:
    digest = hashlib.sha256(query.encode()).hexdigest()[:16]
    return f"companieshouse:{prefix}:{digest}"


def _get_redis():
    try:
        from app.core.cache import cache
        return cache
    except Exception:
        return None


async def _cached_get(key: str) -> Optional[Any]:
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


async def _cache_set(key: str, data: Any) -> None:
    r = _get_redis()
    if not r:
        return
    try:
        await r.set(key, json.dumps(data), ex=_CACHE_TTL)
    except Exception:
        pass


def _build_auth() -> httpx.BasicAuth:
    """Companies House uses API key as Basic Auth username with empty password."""
    return httpx.BasicAuth(username=_API_KEY, password="")


async def _make_request(path: str) -> Optional[Dict[str, Any]]:
    """
    Makes an authenticated GET request to Companies House API.
    Returns parsed JSON or None on failure.
    """
    if not _API_KEY:
        logger.warning(
            "Companies House: COMPANIES_HOUSE_API_KEY not set — provider unavailable"
        )
        return None

    ck = _cache_key("req", path)
    cached = await _cached_get(ck)
    if cached is not None:
        return cached

    url = f"{_BASE_URL}{path}"
    try:
        async for attempt in AsyncRetrying(
            retry=retry_if_exception_type((httpx.TransportError, httpx.TimeoutException)),
            stop=stop_after_attempt(_MAX_RETRIES),
            wait=wait_exponential(multiplier=1, min=1, max=8),
            reraise=True,
        ):
            with attempt:
                async with httpx.AsyncClient(
                    timeout=_TIMEOUT, auth=_build_auth()
                ) as client:
                    resp = await client.get(
                        url,
                        headers={"Accept": "application/json"},
                    )

                    if resp.status_code == 429:
                        logger.warning("Companies House: Rate limited (429)")
                        raise httpx.TransportError("Rate limited")
                    if resp.status_code == 401:
                        logger.error(
                            "Companies House: Unauthorized — check COMPANIES_HOUSE_API_KEY"
                        )
                        return None
                    if resp.status_code == 404:
                        logger.debug(f"Companies House: Not found — {path}")
                        return None
                    resp.raise_for_status()
                    data = resp.json()

    except httpx.HTTPStatusError as exc:
        logger.error(
            f"Companies House: HTTP {exc.response.status_code} for {path}: {exc}"
        )
        return None
    except Exception as exc:
        logger.error(f"Companies House: Request failed for {path}: {exc}")
        return None

    await _cache_set(ck, data)
    return data


class CompaniesHouseProvider:
    """
    Production Companies House UK verification provider.

    Provides:
      - Company lookup by registration number
      - Company search by name
      - Director/officer list retrieval
      - Registered address verification
      - Company status and filing history
    """

    @property
    def provider_name(self) -> str:
        return _PROVIDER_NAME

    async def get_company(self, registration_number: str) -> Optional[Dict[str, Any]]:
        """
        Looks up a company by its registration number.

        Returns a normalised company dict with:
          - company_name, company_number, status, type
          - registered_office_address
          - date_of_creation, date_of_cessation
          - jurisdiction, accounts

        Returns None if not found or on error.
        """
        logger.info(f"Companies House: Lookup company '{registration_number}'")
        path = f"/company/{registration_number.upper().strip()}"
        raw = await _make_request(path)
        if not raw:
            return None
        return self._parse_company(raw)

    async def search_companies(
        self, company_name: str, items_per_page: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Searches companies by name.
        Returns a list of normalised company dicts.
        """
        logger.info(f"Companies House: Searching for company '{company_name}'")
        path = f"/search/companies?q={httpx.QueryParams({'q': company_name, 'items_per_page': items_per_page})}"

        # Use dedicated search path without double-encoding
        ck = _cache_key("search", company_name)
        cached = await _cached_get(ck)
        if cached is not None:
            return cached

        if not _API_KEY:
            logger.warning("Companies House: API key not set")
            return []

        url = f"{_BASE_URL}/search/companies"
        params = {"q": company_name, "items_per_page": items_per_page}

        results = []
        try:
            async for attempt in AsyncRetrying(
                retry=retry_if_exception_type(
                    (httpx.TransportError, httpx.TimeoutException)
                ),
                stop=stop_after_attempt(_MAX_RETRIES),
                wait=wait_exponential(multiplier=1, min=1, max=8),
                reraise=True,
            ):
                with attempt:
                    async with httpx.AsyncClient(
                        timeout=_TIMEOUT, auth=_build_auth()
                    ) as client:
                        resp = await client.get(
                            url,
                            params=params,
                            headers={"Accept": "application/json"},
                        )
                        if resp.status_code == 429:
                            raise httpx.TransportError("Rate limited")
                        if resp.status_code == 401:
                            logger.error("Companies House: Unauthorized")
                            return []
                        resp.raise_for_status()
                        data = resp.json()
                        items = data.get("items", [])
                        results = [self._parse_company(i) for i in items]

        except Exception as exc:
            logger.error(
                f"Companies House: Search failed for '{company_name}': {exc}"
            )
            return []

        await _cache_set(ck, results)
        return results

    async def get_officers(self, registration_number: str) -> List[Dict[str, Any]]:
        """
        Returns a list of current company officers (directors, secretaries).
        Each dict contains: name, role, appointed_on, resigned_on, nationality, dob
        """
        logger.info(
            f"Companies House: Getting officers for '{registration_number}'"
        )
        path = f"/company/{registration_number.upper().strip()}/officers"
        raw = await _make_request(path)
        if not raw:
            return []

        officers = []
        for item in raw.get("items", []):
            officer = {
                "name": item.get("name", ""),
                "role": item.get("officer_role", ""),
                "appointed_on": item.get("appointed_on"),
                "resigned_on": item.get("resigned_on"),
                "nationality": item.get("nationality"),
                "date_of_birth": self._parse_dob(item.get("date_of_birth")),
                "is_current": not item.get("resigned_on"),
                "occupation": item.get("occupation"),
                "address": self._parse_address(item.get("address", {})),
            }
            officers.append(officer)

        logger.info(
            f"Companies House: {len(officers)} officers for '{registration_number}'"
        )
        return officers

    async def get_beneficial_owners(
        self, registration_number: str
    ) -> List[Dict[str, Any]]:
        """
        Returns Persons of Significant Control (PSC) for a company.
        Each dict contains: name, nationality, country_of_residence,
        natures_of_control, notified_on, ceased_on
        """
        logger.info(
            f"Companies House: Getting PSC for '{registration_number}'"
        )
        path = f"/company/{registration_number.upper().strip()}/persons-with-significant-control"
        raw = await _make_request(path)
        if not raw:
            return []

        ubos = []
        for item in raw.get("items", []):
            ubo = {
                "name": item.get("name", ""),
                "nationality": item.get("nationality"),
                "country_of_residence": item.get("country_of_residence"),
                "natures_of_control": item.get("natures_of_control", []),
                "notified_on": item.get("notified_on"),
                "ceased_on": item.get("ceased_on"),
                "is_active": not item.get("ceased_on"),
                "date_of_birth": self._parse_dob(item.get("date_of_birth")),
                "address": self._parse_address(item.get("address", {})),
            }
            ubos.append(ubo)

        logger.info(
            f"Companies House: {len(ubos)} PSC records for '{registration_number}'"
        )
        return ubos

    async def verify_company_registration(
        self, registration_number: str, company_name: str
    ) -> Dict[str, Any]:
        """
        Verifies a company's registration number and name match.
        Returns a verification result dict with:
          - verified: bool
          - status: 'active' | 'dissolved' | 'not_found'
          - name_match: bool
          - company_data: dict (full company info if found)
        """
        company = await self.get_company(registration_number)
        if not company:
            return {
                "verified": False,
                "status": "not_found",
                "name_match": False,
                "company_data": None,
            }

        registered_name = (company.get("company_name") or "").upper().strip()
        provided_name = (company_name or "").upper().strip()
        name_match = (
            registered_name == provided_name
            or provided_name in registered_name
            or registered_name in provided_name
        )

        return {
            "verified": company.get("status") == "active",
            "status": company.get("status", "unknown"),
            "name_match": name_match,
            "company_data": company,
            "provider": _PROVIDER_NAME,
        }

    # ── Private helpers ───────────────────────────────────────────────────────
    @staticmethod
    def _parse_company(raw: Dict[str, Any]) -> Dict[str, Any]:
        """Normalises a raw Companies House company dict."""
        address = raw.get("registered_office_address", {})
        return {
            "company_name": raw.get("company_name"),
            "company_number": raw.get("company_number"),
            "status": raw.get("company_status"),
            "type": raw.get("type"),
            "date_of_creation": raw.get("date_of_creation"),
            "date_of_cessation": raw.get("date_of_cessation"),
            "jurisdiction": raw.get("jurisdiction"),
            "registered_office_address": {
                "address_line_1": address.get("address_line_1"),
                "address_line_2": address.get("address_line_2"),
                "locality": address.get("locality"),
                "postal_code": address.get("postal_code"),
                "country": address.get("country"),
            },
            "sic_codes": raw.get("sic_codes", []),
            "has_charges": raw.get("has_charges", False),
            "has_insolvency_history": raw.get("has_insolvency_history", False),
            "source": _PROVIDER_NAME,
        }

    @staticmethod
    def _parse_dob(dob_raw: Optional[Dict]) -> Optional[str]:
        """Parses Companies House partial DOB (year+month only) to ISO-like string."""
        if not dob_raw:
            return None
        year = dob_raw.get("year")
        month = dob_raw.get("month")
        if year and month:
            return f"{year}-{month:02d}"
        return str(year) if year else None

    @staticmethod
    def _parse_address(addr: Dict[str, Any]) -> Optional[str]:
        """Converts address dict to a single string."""
        parts = [
            addr.get("address_line_1", ""),
            addr.get("address_line_2", ""),
            addr.get("locality", ""),
            addr.get("postal_code", ""),
            addr.get("country", ""),
        ]
        return ", ".join(p for p in parts if p) or None
