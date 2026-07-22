"""
Country Risk Agent — Risk Matrix
=================================

Stateless country risk lookup matrix that maps countries to their classifications.
"""

from typing import Optional

from app.agents.country.provider import BaseCountryRiskProvider
from app.agents.country.constants import (
    RISK_LOW,
    RISK_MEDIUM,
    RISK_HIGH,
    RISK_PROHIBITED,
)


class RiskMatrix:
    """
    Business logic helper for performing country risk evaluations using an injected provider.
    """

    def __init__(self, provider: BaseCountryRiskProvider):
        self._provider = provider

    def get_risk_level(self, country_name: str) -> str:
        """
        Retrieves the risk level of the country. Defaults to RISK_LOW if not found
        or if the provider fails.
        """
        try:
            profile = self._provider.get_country_profile(country_name)
            if profile:
                return profile.risk_level
        except Exception:
            # Graceful degradation on provider failure
            pass
        return RISK_LOW

    def is_prohibited(self, country_name: str) -> bool:
        return self.get_risk_level(country_name) == RISK_PROHIBITED

    def is_high(self, country_name: str) -> bool:
        return self.get_risk_level(country_name) == RISK_HIGH

    def is_medium(self, country_name: str) -> bool:
        return self.get_risk_level(country_name) == RISK_MEDIUM

    def is_fatf_listed(self, country_name: str) -> bool:
        profile = self._provider.get_country_profile(country_name)
        return profile.is_fatf_listed if profile else False
