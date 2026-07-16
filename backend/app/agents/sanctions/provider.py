"""
Sanctions Provider Architecture
===============================

BaseSanctionsProvider
    Abstract interface that decouples the Sanctions Agent from any specific data
    source (OFAC, UK List, UN, EU, OpenSanctions, etc.).

MockSanctionsProvider
    Deterministic mock provider for development and testing. Returns realistic
    sanctions records matching all test case requirements.
"""

import abc
from typing import List, Union

from app.agents.screening.models import ScreeningSubject, CompanyScreeningSubject
from app.agents.sanctions.models import SanctionRecord
from app.agents.screening.constants import ENTITY_INDIVIDUAL, ENTITY_COMPANY
from app.agents.sanctions.constants import (
    LIST_OFAC, LIST_UK_SANCTIONS, LIST_UN, LIST_EU, LIST_INTERNAL,
    SANCTION_CATEGORY_INDIVIDUAL, SANCTION_CATEGORY_COMPANY,
    SANCTION_CATEGORY_ASSET_FREEZE, SANCTION_CATEGORY_TRAVEL_BAN,
    SANCTION_CATEGORY_FINANCIAL, SANCTION_CATEGORY_TERRORIST,
    PROVIDER_MOCK
)


class BaseSanctionsProvider(abc.ABC):
    """
    Abstract interface for all sanctions screening providers.
    """

    @property
    @abc.abstractmethod
    def provider_name(self) -> str:
        """Name of the sanctions provider."""

    @abc.abstractmethod
    async def search_individuals(self, subject: ScreeningSubject) -> List[SanctionRecord]:
        """Search sanctions database for candidate individual records."""

    @abc.abstractmethod
    async def search_companies(self, subject: CompanyScreeningSubject) -> List[SanctionRecord]:
        """Search sanctions database for candidate company records."""


# ─── Mock Database ───────────────────────────────────────────────────────────
_MOCK_SANCTIONS_DATABASE: List[SanctionRecord] = [
    # 1. Exact Name/DOB/Nationality/Passport Individual Match (Terrorist Financing)
    SanctionRecord(
        record_id="SANC-IND-001",
        entity_type=ENTITY_INDIVIDUAL,
        full_name="Ahmed Al-Masri",
        aliases=["Ahmed Masri", "Abu Hamza"],
        dob="1978-11-12",
        nationality="Syria",
        passport_number="SYR-987654-A",
        sanction_category=SANCTION_CATEGORY_TERRORIST,
        sanction_list=LIST_UN,
        is_active=True,
        source=PROVIDER_MOCK
    ),
    
    # 2. Asset Freeze Individual Match
    SanctionRecord(
        record_id="SANC-IND-002",
        entity_type=ENTITY_INDIVIDUAL,
        full_name="Vladimir Petrov",
        dob="1963-04-05",
        nationality="Russia",
        passport_number="RUS-442299",
        sanction_category=SANCTION_CATEGORY_ASSET_FREEZE,
        sanction_list=LIST_EU,
        is_active=True,
        source=PROVIDER_MOCK
    ),

    # 3. Travel Ban Individual Match
    SanctionRecord(
        record_id="SANC-IND-003",
        entity_type=ENTITY_INDIVIDUAL,
        full_name="Robert Mugabe Jr",
        dob="1980-09-20",
        nationality="Zimbabwe",
        sanction_category=SANCTION_CATEGORY_TRAVEL_BAN,
        sanction_list=LIST_UK_SANCTIONS,
        is_active=True,
        source=PROVIDER_MOCK
    ),

    # 4. Confirmed Company Sanction (Registration Number Match + Asset Freeze)
    SanctionRecord(
        record_id="SANC-COM-001",
        entity_type=ENTITY_COMPANY,
        full_name="North Star Shipping Ltd",
        registration_number="REG-991188",
        country="North Korea",
        business_address="12 Juche Tower Rd, Pyongyang",
        sanction_category=SANCTION_CATEGORY_ASSET_FREEZE,
        sanction_list=LIST_OFAC,
        is_active=True,
        source=PROVIDER_MOCK
    ),

    # 5. Fuzzy Match Candidate (Individual)
    SanctionRecord(
        record_id="SANC-IND-004",
        entity_type=ENTITY_INDIVIDUAL,
        full_name="Mikhail Danilov",
        dob="1970-01-15",
        nationality="Russia",
        sanction_category=SANCTION_CATEGORY_FINANCIAL,
        sanction_list=LIST_UK_SANCTIONS,
        is_active=True,
        source=PROVIDER_MOCK
    ),

    # 6. Sanctioned Company (by Name match)
    SanctionRecord(
        record_id="SANC-COM-002",
        entity_type=ENTITY_COMPANY,
        full_name="Cyber Threat Holdings Inc",
        country="Iran",
        sanction_category=SANCTION_CATEGORY_COMPANY,
        sanction_list=LIST_INTERNAL,
        is_active=True,
        source=PROVIDER_MOCK
    )
]


class MockSanctionsProvider(BaseSanctionsProvider):
    """
    In-memory sanctions provider returning realistic candidate records.
    """

    @property
    def provider_name(self) -> str:
        return PROVIDER_MOCK

    async def search_individuals(self, subject: ScreeningSubject) -> List[SanctionRecord]:
        """Returns all individual records in the mock database."""
        return [r for r in _MOCK_SANCTIONS_DATABASE if r.entity_type == ENTITY_INDIVIDUAL]

    async def search_companies(self, subject: CompanyScreeningSubject) -> List[SanctionRecord]:
        """Returns all company records in the mock database."""
        return [r for r in _MOCK_SANCTIONS_DATABASE if r.entity_type == ENTITY_COMPANY]
