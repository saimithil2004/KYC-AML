"""
Unit tests for CompanyAgent.

Coverage
--------
1.  Individual customer  → agent SKIPS, returns success, status=SKIPPED
2.  Individual customer  → next_agent always "pep_agent"
3.  Individual customer  → routing object has company_agent_executed=False
4.  Business customer (complete profile)  → STATUS_COMPLETE, score=100
5.  Business customer (complete profile)  → next_agent = "pep_agent"
6.  Business customer (complete profile)  → routing has company_agent_executed=True
7.  Business customer — missing reg number  → CO001 in failed_rules, HIGH risk
8.  Business customer — dissolved status   → CO010 in failed_rules, HIGH risk
9.  Business customer — missing directors  → CO006 warning, HIGH risk
10. Business customer — missing UBOs       → CO008 recommendation (EDD)
11. Business customer — missing company docs → CO009 recommendation
12. Business customer — all missing (empty state) → STATUS_FAILED
13. Missing customer_type                  → AgentValidationError raised
14. Missing customer dict entirely         → AgentValidationError raised
"""

import pytest
from app.agents.base.agent_state import AgentState
from app.agents.base.exceptions import AgentValidationError
from app.agents.company.agent import CompanyAgent
from app.agents.company.constants import (
    STATUS_COMPLETE,
    STATUS_INCOMPLETE,
    STATUS_FAILED,
    STATUS_SKIPPED,
    RISK_HIGH,
    RISK_MEDIUM,
    RISK_LOW,
    RULE_MISSING_REG_NUMBER,
    RULE_NO_DIRECTORS,
    RULE_NO_UBOS,
    RULE_NO_COMPANY_DOCS,
    RULE_DISSOLVED_COMPANY,
)

# ─────────────────────────────────────────────────────────────
# Fixtures / payload builders
# ─────────────────────────────────────────────────────────────


def individual_customer():
    return {
        "first_name": "Alice",
        "last_name": "Smith",
        "dob": "1985-06-15",
        "customer_type": "individual",
    }


def business_customer():
    return {
        "first_name": "Acme",
        "last_name": "Ltd",
        "customer_type": "business",
    }


def complete_company():
    return {
        "company_registration_number": "12345678",
        "incorporation_date": "2010-01-01",
        "company_status": "active",
        "registered_street": "1 Fleet Street",
        "registered_city": "London",
        "registered_postcode": "EC4Y 1AA",
        "registered_country": "United Kingdom",
        "industry_code": "6419",
    }


def directors():
    return [{"name": "John Director", "role": "CEO"}]


def shareholders():
    return [{"name": "Acme Holdings", "shareholder_name": "Acme Holdings"}]


def qualifying_ubos():
    return [{"name": "Big Owner", "ownership_percentage": 51.0}]


def company_documents():
    return [{"document_type": "certificate_of_incorporation", "status": "verified"}]


def complete_state(customer=None, companies=None, dirs=None, ubos=None, docs=None):
    """Helper that builds a fully-populated business AgentState."""
    return AgentState(
        customer_id="biz-001",
        case_id="case-200",
        customer=customer or business_customer(),
        customer_profile={"shareholders": shareholders()},
        companies=companies if companies is not None else [complete_company()],
        directors=dirs if dirs is not None else directors(),
        ubos=ubos if ubos is not None else qualifying_ubos(),
        uploaded_documents=docs if docs is not None else company_documents(),
    )


# ─────────────────────────────────────────────────────────────
# Test Group A — Individual Customer (SKIP path)
# ─────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_individual_customer_returns_success():
    """SKIP path must succeed — it is NOT an error."""
    state = AgentState(
        customer_id="ind-001",
        case_id="case-100",
        customer=individual_customer(),
    )
    agent = CompanyAgent()
    result = await agent.execute(state)

    assert result.success is True
    assert result.metadata["company_status"] == STATUS_SKIPPED


@pytest.mark.anyio
async def test_individual_customer_routes_to_pep_agent():
    state = AgentState(
        customer_id="ind-002",
        case_id="case-101",
        customer=individual_customer(),
    )
    agent = CompanyAgent()
    result = await agent.execute(state)

    assert result.metadata["next_agent"] == "pep_agent"
    assert state.shared_metadata["next_agent"] == "pep_agent"


@pytest.mark.anyio
async def test_individual_customer_routing_object():
    """The AgentRoutingInfo object must signal company_agent_executed=False."""
    state = AgentState(
        customer_id="ind-003",
        case_id="case-102",
        customer=individual_customer(),
    )
    agent = CompanyAgent()
    result = await agent.execute(state)

    routing = result.metadata["routing"]
    assert routing["customer_type"] == "INDIVIDUAL"
    assert routing["current_agent"] == "company_agent"
    assert routing["next_agent"] == "pep_agent"
    assert routing["company_agent_executed"] is False
    assert routing["skip_reason"] is not None


@pytest.mark.anyio
async def test_individual_customer_no_warnings():
    """A skipped individual run must not produce any warnings."""
    state = AgentState(
        customer_id="ind-004",
        case_id="case-103",
        customer=individual_customer(),
    )
    agent = CompanyAgent()
    result = await agent.execute(state)

    assert result.warnings == []
    assert result.errors == []


# ─────────────────────────────────────────────────────────────
# Test Group B — Business Customer (full verification path)
# ─────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_business_complete_profile_returns_complete():
    state = complete_state()
    agent = CompanyAgent()
    result = await agent.execute(state)

    assert result.success is True
    assert result.metadata["company_status"] == STATUS_COMPLETE
    assert result.risk_score == 100.0


@pytest.mark.anyio
async def test_business_complete_profile_routes_to_pep_agent():
    state = complete_state()
    agent = CompanyAgent()
    result = await agent.execute(state)

    assert result.metadata["next_agent"] == "pep_agent"
    assert state.shared_metadata["next_agent"] == "pep_agent"


@pytest.mark.anyio
async def test_business_routing_object_executed_true():
    state = complete_state()
    agent = CompanyAgent()
    result = await agent.execute(state)

    routing = result.metadata["routing"]
    assert routing["company_agent_executed"] is True
    assert routing["customer_type"] == "BUSINESS"
    assert routing["skip_reason"] is None


@pytest.mark.anyio
async def test_business_missing_registration_number():
    """CO001 — Missing reg number → HIGH risk, CO001 in failed_rules."""
    company = complete_company()
    company.pop("company_registration_number")
    state = complete_state(companies=[company])
    agent = CompanyAgent()
    result = await agent.execute(state)

    assert result.risk_level == RISK_HIGH
    assert RULE_MISSING_REG_NUMBER in result.metadata["audit_trail"]["failed_rules"]
    assert result.metadata["company_status"] in (STATUS_INCOMPLETE, STATUS_FAILED)


@pytest.mark.anyio
async def test_business_dissolved_company_high_risk():
    """CO010 — Dissolved/inactive status → HIGH risk."""
    company = complete_company()
    company["company_status"] = "dissolved"
    state = complete_state(companies=[company])
    agent = CompanyAgent()
    result = await agent.execute(state)

    assert result.risk_level == RISK_HIGH
    assert RULE_DISSOLVED_COMPANY in result.metadata["audit_trail"]["failed_rules"]


@pytest.mark.anyio
async def test_business_no_directors_high_risk():
    """CO006 — No directors → HIGH risk, CO006 in failed_rules."""
    state = complete_state(dirs=[])
    agent = CompanyAgent()
    result = await agent.execute(state)

    assert result.risk_level == RISK_HIGH
    assert RULE_NO_DIRECTORS in result.metadata["audit_trail"]["failed_rules"]
    assert any("director" in w.lower() for w in result.warnings)


@pytest.mark.anyio
async def test_business_no_ubos_triggers_edd_recommendation():
    """CO008 — No qualifying UBOs → EDD recommendation."""
    state = complete_state(ubos=[])
    agent = CompanyAgent()
    result = await agent.execute(state)

    assert RULE_NO_UBOS in result.metadata["audit_trail"]["failed_rules"]
    assert any(
        "EDD" in r or "Enhanced Due Diligence" in r for r in result.recommendations
    )


@pytest.mark.anyio
async def test_business_no_company_documents_recommendation():
    """CO009 — No company docs → recommendation raised."""
    state = complete_state(docs=[])
    agent = CompanyAgent()
    result = await agent.execute(state)

    assert RULE_NO_COMPANY_DOCS in result.metadata["audit_trail"]["failed_rules"]
    assert any(
        "Incorporation" in r or "incorporation" in r for r in result.recommendations
    )


@pytest.mark.anyio
async def test_business_all_missing_returns_failed():
    """Empty company data → STATUS_FAILED, multiple warnings."""
    state = AgentState(
        customer_id="biz-999",
        case_id="case-999",
        customer=business_customer(),
        companies=[],
        directors=[],
        ubos=[],
        uploaded_documents=[],
    )
    agent = CompanyAgent()
    result = await agent.execute(state)

    assert result.metadata["company_status"] == STATUS_FAILED
    assert result.risk_level == RISK_HIGH
    assert len(result.warnings) >= 1


# ─────────────────────────────────────────────────────────────
# Test Group C — Validation Errors
# ─────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_missing_customer_type_raises_validation_error():
    state = AgentState(
        customer_id="err-001",
        case_id="case-err",
        customer={"first_name": "Bob"},  # no customer_type
    )
    agent = CompanyAgent()
    with pytest.raises(AgentValidationError) as exc_info:
        await agent.execute(state)
    assert "customer_type" in str(exc_info.value).lower()


@pytest.mark.anyio
async def test_missing_customer_dict_raises_validation_error():
    state = AgentState(
        customer_id="err-002",
        case_id="case-err-2",
        customer={},
    )
    agent = CompanyAgent()
    with pytest.raises(AgentValidationError):
        await agent.execute(state)
