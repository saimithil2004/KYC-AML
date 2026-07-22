"""
PEP Agent Test Suite
=====================

Groups
------
A — Individual customer: no-match → CLEAR, subject extraction
B — Business customer: multiple subjects, deduplication
C — Match scenarios: confirmed, fuzzy, no-match
D — PEP categories: foreign (PEP004), current domestic (PEP006),
                    family (PEP005), former (PEP007)
E — Edge cases: provider failure, validation errors, AgentState, audit trail
"""

import pytest
from typing import List, Optional, Dict, Any

from app.agents.base.agent_state import AgentState
from app.agents.base.exceptions import AgentValidationError
from app.agents.pep.agent import PepAgent
from app.agents.pep.models import ScreeningSubject, PepRecord
from app.agents.pep.provider import BasePepProvider
from app.agents.pep.constants import (
    PEP_STATUS_CLEAR,
    PEP_STATUS_POSSIBLE,
    PEP_STATUS_CONFIRMED,
    RISK_LOW,
    RISK_MEDIUM,
    RISK_HIGH,
    RISK_CRITICAL,
    PEP_CATEGORY_DOMESTIC,
    PEP_CATEGORY_FOREIGN,
    PEP_CATEGORY_FAMILY_MEMBER,
    PEP_CATEGORY_FORMER_PEP,
)

# ─────────────────────────────────────────────────────────────────────────────
# Test providers
# ─────────────────────────────────────────────────────────────────────────────


class EmptyProvider(BasePepProvider):
    @property
    def provider_name(self) -> str:
        return "EmptyProvider"

    async def search(self, subject: ScreeningSubject) -> List[PepRecord]:
        return []


class FailingProvider(BasePepProvider):
    @property
    def provider_name(self) -> str:
        return "FailingProvider"

    async def search(self, subject: ScreeningSubject) -> List[PepRecord]:
        raise ConnectionError("PEP provider timeout")


class ExactMatchProvider(BasePepProvider):
    def __init__(self, record: PepRecord):
        self._record = record

    @property
    def provider_name(self) -> str:
        return "ExactMatchProvider"

    async def search(self, subject: ScreeningSubject) -> List[PepRecord]:
        return [self._record]


# ─────────────────────────────────────────────────────────────────────────────
# Helpers — single canonical definition
# ─────────────────────────────────────────────────────────────────────────────


def individual_customer(name: str = "Alice Smith") -> Dict[str, Any]:
    first, *rest = name.split()
    return {
        "first_name": first,
        "last_name": rest[0] if rest else "Unknown",
        "dob": "1985-06-15",
        "nationality": "United Kingdom",
        "customer_type": "individual",
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
    """
    use_empty_customer=True passes {} as customer, bypassing the `or` fallback,
    for validation-error test paths.
    """
    resolved = (
        {}
        if use_empty_customer
        else (customer if customer is not None else individual_customer())
    )
    return AgentState(
        customer_id="test-001",
        case_id="case-pep-001",
        customer=resolved,
        directors=directors or [],
        ubos=ubos or [],
        customer_profile=customer_profile or {},
        companies=companies or [],
    )


def uk_pep_record(
    name: str = "Alice Smith",
    category: str = PEP_CATEGORY_DOMESTIC,
    is_current: bool = True,
    position: str = "Member of Parliament",
) -> PepRecord:
    return PepRecord(
        record_id="PEP-T-001",
        full_name=name,
        dob="1985-06-15",
        nationality="United Kingdom",
        country="United Kingdom",
        category=category,
        position=position,
        is_current=is_current,
        source="test",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Group A — Individual customer
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_individual_no_match_is_clear():
    agent = PepAgent(provider=EmptyProvider())
    result = await agent.execute(make_state())

    assert result.success is True
    assert result.metadata["pep_status"] == PEP_STATUS_CLEAR
    assert result.risk_level == RISK_LOW
    assert result.metadata["next_agent"] == "sanctions_agent"


@pytest.mark.anyio
async def test_individual_subject_extracted():
    agent = PepAgent(provider=EmptyProvider())
    result = await agent.execute(make_state())

    screened = result.metadata["screened_subjects"]
    assert len(screened) >= 1
    assert screened[0]["full_name"] == "Alice Smith"
    assert screened[0]["role"] == "CUSTOMER"


# ─────────────────────────────────────────────────────────────────────────────
# Group B — Business customer
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_business_multiple_subjects_extracted():
    state = make_state(
        customer=business_customer(),
        directors=[{"name": "John Director", "dob": "1970-01-01"}],
        ubos=[{"name": "Big Owner", "dob": "1965-05-20", "ownership_percentage": 51.0}],
    )
    result = await PepAgent(provider=EmptyProvider()).execute(state)

    roles = {s["role"] for s in result.metadata["screened_subjects"]}
    assert "CUSTOMER" in roles
    assert "DIRECTOR" in roles
    assert "UBO" in roles


@pytest.mark.anyio
async def test_deduplication_same_person_two_roles():
    same = {"name": "Duplicate Person", "dob": "1975-03-10"}
    state = make_state(customer=business_customer(), directors=[same], ubos=[same])
    result = await PepAgent(provider=EmptyProvider()).execute(state)

    names = [s["full_name"] for s in result.metadata["screened_subjects"]]
    assert names.count("Duplicate Person") == 1


# ─────────────────────────────────────────────────────────────────────────────
# Group C — Match scenarios
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_exact_match_confirmed_edd_required():
    """Name + DOB + nationality all match → CONFIRMED, EDD required."""
    record = uk_pep_record("Alice Smith", PEP_CATEGORY_DOMESTIC)
    result = await PepAgent(provider=ExactMatchProvider(record)).execute(make_state())

    assert result.metadata["pep_status"] == PEP_STATUS_CONFIRMED
    assert result.metadata["edd_required"] is True
    assert result.metadata["next_agent"] == "sanctions_agent"


@pytest.mark.anyio
async def test_fuzzy_name_only_possible_or_clear():
    """Similar but wrong name, DOB and nationality mismatch → at most POSSIBLE."""
    record = PepRecord(
        record_id="PEP-FUZ-001",
        full_name="Alicia Smyth",
        dob="1990-01-01",
        nationality="Australia",
        country="Australia",
        category=PEP_CATEGORY_FOREIGN,
        is_current=True,
        source="test",
    )
    result = await PepAgent(provider=ExactMatchProvider(record)).execute(make_state())
    assert result.metadata["pep_status"] in (PEP_STATUS_POSSIBLE, PEP_STATUS_CLEAR)


@pytest.mark.anyio
async def test_completely_different_name_is_clear():
    record = PepRecord(
        record_id="PEP-DIF-001",
        full_name="Zhuang Wei Kai Xin Foo",
        dob="1950-01-01",
        nationality="Singapore",
        country="Singapore",
        category=PEP_CATEGORY_FOREIGN,
        is_current=True,
        source="test",
    )
    result = await PepAgent(provider=ExactMatchProvider(record)).execute(make_state())
    assert result.metadata["pep_status"] == PEP_STATUS_CLEAR


# ─────────────────────────────────────────────────────────────────────────────
# Group D — PEP category rules
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_foreign_pep_triggers_pep004():
    record = PepRecord(
        record_id="PEP-FR-001",
        full_name="Alice Smith",
        dob="1985-06-15",
        nationality="France",
        country="France",
        category=PEP_CATEGORY_FOREIGN,
        position="Minister",
        is_current=True,
        source="test",
    )
    state = make_state(customer={**individual_customer(), "nationality": "France"})
    result = await PepAgent(provider=ExactMatchProvider(record)).execute(state)

    assert "PEP004" in result.metadata["rules_triggered"]
    assert result.risk_level in (RISK_HIGH, RISK_CRITICAL)


@pytest.mark.anyio
async def test_domestic_current_pep_triggers_pep006_critical():
    """Current domestic PEP → PEP003 + PEP006 → CRITICAL, pep_score stored in metadata = 0."""
    record = uk_pep_record(
        "Alice Smith",
        PEP_CATEGORY_DOMESTIC,
        is_current=True,
        position="Secretary of State",
    )
    result = await PepAgent(provider=ExactMatchProvider(record)).execute(make_state())

    assert "PEP006" in result.metadata["rules_triggered"]
    assert result.risk_level == RISK_CRITICAL
    assert result.metadata["pep_score"] == 0.0


@pytest.mark.anyio
async def test_family_member_triggers_pep005():
    record = uk_pep_record(
        "Alice Smith", PEP_CATEGORY_FAMILY_MEMBER, position="Spouse of Minister"
    )
    result = await PepAgent(provider=ExactMatchProvider(record)).execute(make_state())

    assert "PEP005" in result.metadata["rules_triggered"]
    assert result.risk_level in (RISK_HIGH, RISK_CRITICAL)


@pytest.mark.anyio
async def test_former_pep_triggers_pep007_monitoring_recommendation():
    record = uk_pep_record(
        "Alice Smith",
        PEP_CATEGORY_FORMER_PEP,
        is_current=False,
        position="Former Minister",
    )
    result = await PepAgent(provider=ExactMatchProvider(record)).execute(make_state())

    assert "PEP007" in result.metadata["rules_triggered"]
    assert any("monitoring" in r.lower() for r in result.recommendations)


# ─────────────────────────────────────────────────────────────────────────────
# Group E — Edge cases
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_provider_failure_graceful_degradation():
    result = await PepAgent(provider=FailingProvider()).execute(make_state())

    assert result.success is True
    all_issues = result.warnings + result.errors
    assert any(
        "provider" in w.lower() or "timeout" in w.lower() or "error" in w.lower()
        for w in all_issues
    )


@pytest.mark.anyio
async def test_missing_customer_name_raises_validation_error():
    state = make_state(customer={"customer_type": "individual"})
    with pytest.raises(AgentValidationError) as exc_info:
        await PepAgent(provider=EmptyProvider()).execute(state)
    assert "name" in str(exc_info.value).lower()


@pytest.mark.anyio
async def test_missing_customer_dict_raises_validation_error():
    state = make_state(use_empty_customer=True)
    with pytest.raises(AgentValidationError):
        await PepAgent(provider=EmptyProvider()).execute(state)


@pytest.mark.anyio
async def test_next_agent_always_sanctions_agent():
    state = make_state()
    result = await PepAgent(provider=EmptyProvider()).execute(state)

    assert result.metadata["next_agent"] == "sanctions_agent"
    assert state.shared_metadata["next_agent"] == "sanctions_agent"


@pytest.mark.anyio
async def test_agent_state_has_all_required_keys():
    state = make_state()
    await PepAgent(provider=EmptyProvider()).execute(state)

    for key in [
        "pep_status",
        "pep_score",
        "pep_risk",
        "screened_subjects",
        "matched_subjects",
        "pep_findings",
        "pep_recommendations",
        "pep_audit_trail",
        "next_agent",
        "edd_required",
        "manual_review_required",
    ]:
        assert key in state.shared_metadata, f"Missing key: {key}"


@pytest.mark.anyio
async def test_audit_trail_populated():
    result = await PepAgent(provider=EmptyProvider()).execute(make_state())

    audit = result.metadata["audit_trail"]
    assert audit["provider_used"] == "EmptyProvider"
    assert audit["subjects_screened"] >= 1
    assert "validation_timestamp" in audit
