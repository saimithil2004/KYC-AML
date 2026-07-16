"""
Country Risk Agent — Provider Architecture
===========================================

BaseCountryRiskProvider
    Abstract interface for all country risk providers.

MockCountryRiskProvider
    Deterministic in-memory country risk rating database for testing and development.
"""

import abc
from typing import Dict, Optional

from app.agents.country.models import CountryRiskProfile
from app.agents.country.constants import (
    RISK_LOW, RISK_MEDIUM, RISK_HIGH, RISK_PROHIBITED, PROVIDER_MOCK
)


class BaseCountryRiskProvider(abc.ABC):
    """
    Abstract Base Provider for jurisdictional risk data.
    """

    @property
    @abc.abstractmethod
    def provider_name(self) -> str:
        """Name of the country risk provider."""

    @abc.abstractmethod
    def get_country_profile(self, country_name: str) -> Optional[CountryRiskProfile]:
        """
        Retrieves the risk profile for the standardized country name.
        """


# ─── Mock Database ───────────────────────────────────────────────────────────
_MOCK_COUNTRY_PROFILES: Dict[str, CountryRiskProfile] = {
    "Iran": CountryRiskProfile(
        country_name="Iran",
        iso_alpha2="IR",
        iso_alpha3="IRN",
        risk_level=RISK_PROHIBITED,
        is_fatf_listed=True,
        is_sanctioned=True,
        source=PROVIDER_MOCK
    ),
    "North Korea": CountryRiskProfile(
        country_name="North Korea",
        iso_alpha2="KP",
        iso_alpha3="PRK",
        risk_level=RISK_PROHIBITED,
        is_fatf_listed=True,
        is_sanctioned=True,
        source=PROVIDER_MOCK
    ),
    "Russia": CountryRiskProfile(
        country_name="Russia",
        iso_alpha2="RU",
        iso_alpha3="RUS",
        risk_level=RISK_HIGH,
        is_fatf_listed=False,
        is_sanctioned=True,
        source=PROVIDER_MOCK
    ),
    "Syria": CountryRiskProfile(
        country_name="Syria",
        iso_alpha2="SY",
        iso_alpha3="SYR",
        risk_level=RISK_HIGH,
        is_fatf_listed=True,
        is_sanctioned=True,
        source=PROVIDER_MOCK
    ),
    "Cayman Islands": CountryRiskProfile(
        country_name="Cayman Islands",
        iso_alpha2="KY",
        iso_alpha3="CYM",
        risk_level=RISK_MEDIUM,
        is_fatf_listed=True,
        is_sanctioned=False,
        source=PROVIDER_MOCK
    ),
    "Panama": CountryRiskProfile(
        country_name="Panama",
        iso_alpha2="PA",
        iso_alpha3="PAN",
        risk_level=RISK_MEDIUM,
        is_fatf_listed=True,
        is_sanctioned=False,
        source=PROVIDER_MOCK
    ),
    "United Kingdom": CountryRiskProfile(
        country_name="United Kingdom",
        iso_alpha2="GB",
        iso_alpha3="GBR",
        risk_level=RISK_LOW,
        source=PROVIDER_MOCK
    ),
    "United States": CountryRiskProfile(
        country_name="United States",
        iso_alpha2="US",
        iso_alpha3="USA",
        risk_level=RISK_LOW,
        source=PROVIDER_MOCK
    ),
    "Germany": CountryRiskProfile(
        country_name="Germany",
        iso_alpha2="DE",
        iso_alpha3="DEU",
        risk_level=RISK_LOW,
        source=PROVIDER_MOCK
    ),
    "France": CountryRiskProfile(
        country_name="France",
        iso_alpha2="FR",
        iso_alpha3="FRA",
        risk_level=RISK_LOW,
        source=PROVIDER_MOCK
    ),
    "Singapore": CountryRiskProfile(
        country_name="Singapore",
        iso_alpha2="SG",
        iso_alpha3="SGP",
        risk_level=RISK_LOW,
        source=PROVIDER_MOCK
    ),
    "Switzerland": CountryRiskProfile(
        country_name="Switzerland",
        iso_alpha2="CH",
        iso_alpha3="CHE",
        risk_level=RISK_LOW,
        source=PROVIDER_MOCK
    ),
    "Canada": CountryRiskProfile(
        country_name="Canada",
        iso_alpha2="CA",
        iso_alpha3="CAN",
        risk_level=RISK_LOW,
        source=PROVIDER_MOCK
    ),
    "Japan": CountryRiskProfile(
        country_name="Japan",
        iso_alpha2="JP",
        iso_alpha3="JPN",
        risk_level=RISK_LOW,
        source=PROVIDER_MOCK
    ),
    "Australia": CountryRiskProfile(
        country_name="Australia",
        iso_alpha2="AU",
        iso_alpha3="AUS",
        risk_level=RISK_LOW,
        source=PROVIDER_MOCK
    ),
    "Belgium": CountryRiskProfile(
        country_name="Belgium",
        iso_alpha2="BE",
        iso_alpha3="BEL",
        risk_level=RISK_LOW,
        source=PROVIDER_MOCK
    ),
    "China": CountryRiskProfile(
        country_name="China",
        iso_alpha2="CN",
        iso_alpha3="CHN",
        risk_level=RISK_LOW,
        source=PROVIDER_MOCK
    ),
}


class MockCountryRiskProvider(BaseCountryRiskProvider):
    """
    Mock rating provider using an in-memory database of standard AML classifications.
    """

    @property
    def provider_name(self) -> str:
        return PROVIDER_MOCK

    def get_country_profile(self, country_name: str) -> Optional[CountryRiskProfile]:
        return _MOCK_COUNTRY_PROFILES.get(country_name)
