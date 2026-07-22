"""
Sanctions Agent Test Suite
===========================

Covers:
  1. Individual customer screening (no match)
  2. Business customer screening (no match)
  3. Possible Match (SAN002)
  4. Confirmed Individual Match (SAN003)
  5. Confirmed Company Match (SAN004)
  6. Passport Match (SAN009)
  7. Registration Number Match (SAN010)
  8. Terrorist Financing Match (SAN005)
  9. Asset Freeze Match (SAN006)
 10. Travel Ban Match (SAN007)
 11. Multiple Matches (SAN008)
 12. Provider Failure (Graceful degradation)
 13. Duplicate Screening Subjects (Deduplication)
 14. Validation Errors (Empty lists/inputs)
"""

import pytest
from typing import List, Optional, Dict, Any

from app.agents.base.agent_state import AgentState
from app.agents.base.exceptions import AgentValidationError
from app.agents.screening.models import ScreeningSubject, CompanyScreeningSubject
from app.agents.screening.constants import (
    MATCH_CONFIRMED,
    MATCH_POSSIBLE,
    MATCH_NONE,
    RISK_LOW,
    RISK_MEDIUM,
    RISK_HIGH,
    RISK_CRITICAL,
    ROLE_CUSTOMER,
    ROLE_DIRECTOR,
    ROLE_UBO,
    ROLE_COMPANY,
)
from app.agents.sanctions.agent import SanctionsAgent
from app.agents.sanctions.models import SanctionRecord, SanctionMatchResult
from app.agents.sanctions.provider import BaseSanctionsProvider
from app.agents.sanctions.constants import (
    SANCTIONS_STATUS_CLEAR,
    SANCTIONS_STATUS_POSSIBLE,
    SANCTIONS_STATUS_CONFIRMED,
    SANCTION_CATEGORY_INDIVIDUAL,
    SANCTION_CATEGORY_COMPANY,
    SANCTION_CATEGORY_ASSET_FREEZE,
    SANCTION_CATEGORY_TRAVEL_BAN,
    SANCTION_CATEGORY_TERRORIST,
    LIST_OFAC,
    LIST_UK_SANCTIONS,
    LIST_UN,
)


# ─── Test Providers ───────────────────────────────────────────────────────────
class EmptySanctionsProvider(BaseSanctionsProvider):
    @property
    def provider_name(self) -> str:
        return "EmptySanctionsProvider"

    async def search_individuals(
        self, subject: ScreeningSubject
    ) -> List[SanctionRecord]:
        return []

    async def search_companies(
        self, subject: CompanyScreeningSubject
    ) -> List[SanctionRecord]:
        return []


class FailingSanctionsProvider(BaseSanctionsProvider):
    @property
    def provider_name(self) -> str:
        return "FailingSanctionsProvider"

    async def search_individuals(
        self, subject: ScreeningSubject
    ) -> List[SanctionRecord]:
        raise ConnectionError("Sanctions watchlists lookup timeout")

    async def search_companies(
        self, subject: CompanyScreeningSubject
    ) -> List[SanctionRecord]:
        raise ConnectionError("Sanctions watchlists lookup timeout")


class CustomSanctionsProvider(BaseSanctionsProvider):
    def __init__(self, records: List[SanctionRecord]):
        self._records = records

    @property
    def provider_name(self) -> str:
        return "CustomSanctionsProvider"

    async def search_individuals(
        self, subject: ScreeningSubject
    ) -> List[SanctionRecord]:
        return [r for r in self._records if r.entity_type == "INDIVIDUAL"]

    async def search_companies(
        self, subject: CompanyScreeningSubject
    ) -> List[SanctionRecord]:
        return [r for r in self._records if r.entity_type == "COMPANY"]


# ─── Payload Helpers ──────────────────────────────────────────────────────────
def individual_customer(name: str = "Ahmed Al-Masri") -> Dict[str, Any]:
    first, *rest = name.split()
    return {
        "first_name": first,
        "last_name": rest[0] if rest else "Unknown",
        "dob": "1978-11-12",
        "nationality": "Syria",
        "customer_type": "individual",
        "passport_number": "SYR-987654-A",
    }


def business_customer() -> Dict[str, Any]:
    return {"first_name": "Acme", "last_name": "Ltd", "customer_type": "business"}


def make_state(
    customer: Optional[Dict[str, Any]] = None,
    directors: Optional[List] = None,
    ubos: Optional[List] = None,
    customer_profile: Optional[Dict] = None,
    companies: Optional[List] = None,
    use_empty_customer: bool = False,
) -> AgentState:
    resolved = (
        {}
        if use_empty_customer
        else (customer if customer is not None else individual_customer())
    )
    return AgentState(
        customer_id="test-cust-123",
        case_id="case-sanc-123",
        customer=resolved,
        directors=directors or [],
        ubos=ubos or [],
        customer_profile=customer_profile or {},
        companies=companies or [],
    )


# ─────────────────────────────────────────────────────────────────────────────
# Group A — Individual Customer screening (No Match)
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.anyio
async def test_individual_no_match_is_clear():
    agent = SanctionsAgent(provider=EmptySanctionsProvider())
    result = await agent.execute(make_state())

    assert result.success is True
    assert result.metadata["sanctions_status"] == SANCTIONS_STATUS_CLEAR
    assert result.risk_level == RISK_LOW
    assert result.metadata["next_agent"] == "country_risk_agent"


# ─────────────────────────────────────────────────────────────────────────────
# Group B — Business Customer screening (No Match)
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.anyio
async def test_business_no_match_is_clear():
    state = make_state(
        customer=business_customer(),
        companies=[
            {
                "name": "Safe Shipping Corp",
                "registration_number": "REG-123",
                "country": "UK",
            }
        ],
        directors=[
            {"name": "John Doe", "dob": "1970-01-01", "passport_number": "UK-1122"}
        ],
    )
    agent = SanctionsAgent(provider=EmptySanctionsProvider())
    result = await agent.execute(state)

    assert result.success is True
    assert result.metadata["sanctions_status"] == SANCTIONS_STATUS_CLEAR
    assert len(result.metadata["audit_trail"]["matched_lists"]) == 0


# ─────────────────────────────────────────────────────────────────────────────
# Group C — Match Scenarios
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.anyio
async def test_possible_match_manual_review():
    """Fuzzy name match, no DOB/nationality match -> POSSIBLE_MATCH -> MANUAL_REVIEW."""
    record = SanctionRecord(
        record_id="SANC-123",
        entity_type="INDIVIDUAL",
        full_name="Ahmeeed Al-Masssri",  # Fuzzy name similarity
        dob="1960-01-01",
        nationality="Egypt",
        sanction_category=SANCTION_CATEGORY_INDIVIDUAL,
        sanction_list=LIST_OFAC,
        is_active=True,
    )
    agent = SanctionsAgent(provider=CustomSanctionsProvider([record]))
    result = await agent.execute(
        make_state(customer=individual_customer("Ahmed Al-Masri"))
    )

    assert result.metadata["sanctions_status"] == SANCTIONS_STATUS_POSSIBLE
    assert result.risk_level == RISK_MEDIUM
    assert "SAN002" in result.metadata["rules_triggered"]


@pytest.mark.anyio
async def test_confirmed_individual_match():
    """Exact Name + DOB + Nationality -> CONFIRMED -> CRITICAL."""
    record = SanctionRecord(
        record_id="SANC-123",
        entity_type="INDIVIDUAL",
        full_name="Ahmed Al-Masri",
        dob="1978-11-12",
        nationality="Syria",
        sanction_category=SANCTION_CATEGORY_INDIVIDUAL,
        sanction_list=LIST_UN,
        is_active=True,
    )
    agent = SanctionsAgent(provider=CustomSanctionsProvider([record]))
    result = await agent.execute(
        make_state(customer=individual_customer("Ahmed Al-Masri"))
    )

    assert result.metadata["sanctions_status"] == SANCTIONS_STATUS_CONFIRMED
    assert result.risk_level == RISK_CRITICAL
    assert "SAN003" in result.metadata["rules_triggered"]


@pytest.mark.anyio
async def test_confirmed_company_match():
    """Company name match -> CONFIRMED -> CRITICAL."""
    record = SanctionRecord(
        record_id="SANC-COM-123",
        entity_type="COMPANY",
        full_name="Target Shipping Corp",
        country="Iran",
        sanction_category=SANCTION_CATEGORY_COMPANY,
        sanction_list=LIST_OFAC,
        is_active=True,
    )
    state = make_state(
        customer=business_customer(),
        companies=[{"name": "Target Shipping Corp", "country": "Iran"}],
    )
    agent = SanctionsAgent(provider=CustomSanctionsProvider([record]))
    result = await agent.execute(state)

    assert result.metadata["sanctions_status"] == SANCTIONS_STATUS_CONFIRMED
    assert result.risk_level == RISK_CRITICAL
    assert "SAN004" in result.metadata["rules_triggered"]


@pytest.mark.anyio
async def test_passport_match():
    """Exact Passport match -> Confirmed Individual Match via SAN009."""
    record = SanctionRecord(
        record_id="SANC-123",
        entity_type="INDIVIDUAL",
        full_name="Ahmed Al-Masri",
        passport_number="SYR-987654-A",
        sanction_category=SANCTION_CATEGORY_INDIVIDUAL,
        sanction_list=LIST_UN,
        is_active=True,
    )
    agent = SanctionsAgent(provider=CustomSanctionsProvider([record]))
    result = await agent.execute(make_state(customer=individual_customer()))

    assert "SAN009" in result.metadata["rules_triggered"]
    assert result.risk_level == RISK_CRITICAL


@pytest.mark.anyio
async def test_registration_number_match():
    """Exact Registration Number match -> Confirmed Company Match via SAN010."""
    record = SanctionRecord(
        record_id="SANC-COM-123",
        entity_type="COMPANY",
        full_name="Target Shipping Corp",
        registration_number="REG-991188",
        sanction_category=SANCTION_CATEGORY_COMPANY,
        sanction_list=LIST_OFAC,
        is_active=True,
    )
    state = make_state(
        customer=business_customer(),
        companies=[
            {"name": "Target Shipping Corp", "registration_number": "REG-991188"}
        ],
    )
    agent = SanctionsAgent(provider=CustomSanctionsProvider([record]))
    result = await agent.execute(state)

    assert "SAN010" in result.metadata["rules_triggered"]
    assert result.risk_level == RISK_CRITICAL


# ─────────────────────────────────────────────────────────────────────────────
# Group D — Sanctions Categories / Rules
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.anyio
async def test_terrorist_financing_match_immediate_escalation():
    record = SanctionRecord(
        record_id="SANC-123",
        entity_type="INDIVIDUAL",
        full_name="Ahmed Al-Masri",
        dob="1978-11-12",
        sanction_category=SANCTION_CATEGORY_TERRORIST,
        sanction_list=LIST_UN,
        is_active=True,
    )
    agent = SanctionsAgent(provider=CustomSanctionsProvider([record]))
    result = await agent.execute(make_state())

    assert "SAN005" in result.metadata["rules_triggered"]
    assert result.risk_level == RISK_CRITICAL
    assert any(
        "escalate to compliance officer" in r.lower() for r in result.recommendations
    )


@pytest.mark.anyio
async def test_asset_freeze_match():
    record = SanctionRecord(
        record_id="SANC-123",
        entity_type="INDIVIDUAL",
        full_name="Ahmed Al-Masri",
        dob="1978-11-12",
        sanction_category=SANCTION_CATEGORY_ASSET_FREEZE,
        sanction_list=LIST_UK_SANCTIONS,
        is_active=True,
    )
    agent = SanctionsAgent(provider=CustomSanctionsProvider([record]))
    result = await agent.execute(make_state())

    assert "SAN006" in result.metadata["rules_triggered"]
    assert any("asset freeze" in w.lower() for w in result.warnings)


@pytest.mark.anyio
async def test_travel_ban_match():
    record = SanctionRecord(
        record_id="SANC-123",
        entity_type="INDIVIDUAL",
        full_name="Ahmed Al-Masri",
        dob="1978-11-12",
        sanction_category=SANCTION_CATEGORY_TRAVEL_BAN,
        sanction_list=LIST_UK_SANCTIONS,
        is_active=True,
    )
    agent = SanctionsAgent(provider=CustomSanctionsProvider([record]))
    result = await agent.execute(make_state())

    assert "SAN007" in result.metadata["rules_triggered"]
    assert any("travel ban" in w.lower() for w in result.warnings)


@pytest.mark.anyio
async def test_multiple_matches():
    """Multiple matched subjects triggers SAN008 -> CRITICAL."""
    record1 = SanctionRecord(
        record_id="SANC-123",
        entity_type="INDIVIDUAL",
        full_name="Ahmed Al-Masri",
        dob="1978-11-12",
        sanction_category=SANCTION_CATEGORY_INDIVIDUAL,
        sanction_list=LIST_UN,
        is_active=True,
    )
    record2 = SanctionRecord(
        record_id="SANC-456",
        entity_type="INDIVIDUAL",
        full_name="John Director",
        dob="1970-01-01",
        sanction_category=SANCTION_CATEGORY_INDIVIDUAL,
        sanction_list=LIST_OFAC,
        is_active=True,
    )
    state = make_state(
        customer=individual_customer("Ahmed Al-Masri"),
        directors=[{"name": "John Director", "dob": "1970-01-01"}],
    )
    # We want both to match
    agent = SanctionsAgent(provider=CustomSanctionsProvider([record1, record2]))
    result = await agent.execute(state)

    assert "SAN008" in result.metadata["rules_triggered"]
    assert result.risk_level == RISK_CRITICAL


# ─────────────────────────────────────────────────────────────────────────────
# Group E — Edge Cases & Errors
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.anyio
async def test_provider_failure_graceful_degradation():
    state = make_state()
    agent = SanctionsAgent(provider=FailingSanctionsProvider())
    result = await agent.execute(state)

    assert result.success is True
    assert any(
        "provider failure" in w.lower() or "timeout" in w.lower()
        for w in result.warnings
    )


@pytest.mark.anyio
async def test_duplicate_screening_subjects():
    """Director listed twice should only be screened once."""
    same = {"name": "Duplicate Director", "dob": "1970-01-01"}
    state = make_state(customer=business_customer(), directors=[same, same])
    agent = SanctionsAgent(provider=EmptySanctionsProvider())
    result = await agent.execute(state)

    # 1 customer + 1 director = 2 screened individuals
    assert result.metadata["audit_trail"]["subjects_screened"] == 2


@pytest.mark.anyio
async def test_empty_customer_dict_raises_validation_error():
    state = make_state(use_empty_customer=True)
    agent = SanctionsAgent(provider=EmptySanctionsProvider())
    with pytest.raises(AgentValidationError):
        await agent.execute(state)
