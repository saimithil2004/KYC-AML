import pytest
from app.agents.base.agent_state import AgentState
from app.agents.base.exceptions import AgentValidationError
from app.agents.kyc.agent import KycAgent
from app.agents.kyc.constants import STATUS_COMPLETE, STATUS_INCOMPLETE, STATUS_FAILED


# Helper payload generators
def get_complete_customer():
    return {
        "first_name": "Alexander",
        "last_name": "Hamilton",
        "dob": "1990-01-11",
        "gender": "male",
        "nationality": "United Kingdom",
        "street_address": "12 Broadway",
        "city": "London",
        "postal_code": "SW11 1AA",
        "country": "United Kingdom",
        "customer_type": "individual",
    }


def get_complete_kyc_profile():
    return {
        "occupation": "Statesman",
        "source_of_funds": "Salaried savings",
        "source_of_wealth": "Investments",
        "tax_residency": "United Kingdom",
    }


def get_complete_documents():
    return [{"document_type": "passport", "status": "verified"}]


@pytest.mark.anyio
async def test_kyc_agent_complete_profile():
    state = AgentState(
        customer_id="cust-001",
        case_id="case-100",
        customer=get_complete_customer(),
        kyc_profile=get_complete_kyc_profile(),
        uploaded_documents=get_complete_documents(),
    )

    agent = KycAgent()
    res = await agent.execute(state)

    assert res.success is True
    assert res.risk_score == 100.0
    assert res.risk_level == "low"
    assert res.metadata["kyc_status"] == STATUS_COMPLETE
    assert res.metadata["next_agent"] == "pep_agent"
    assert not res.warnings
    assert not res.errors


@pytest.mark.anyio
async def test_kyc_agent_missing_name():
    cust = get_complete_customer()
    cust["first_name"] = None

    state = AgentState(
        customer_id="cust-002",
        case_id="case-101",
        customer=cust,
        kyc_profile=get_complete_kyc_profile(),
        uploaded_documents=get_complete_documents(),
    )

    agent = KycAgent()
    with pytest.raises(AgentValidationError) as exc_info:
        await agent.execute(state)
    assert "Full Name is missing" in str(exc_info.value)


@pytest.mark.anyio
async def test_kyc_agent_missing_dob():
    cust = get_complete_customer()
    cust["dob"] = None

    state = AgentState(
        customer_id="cust-003",
        case_id="case-102",
        customer=cust,
        kyc_profile=get_complete_kyc_profile(),
        uploaded_documents=get_complete_documents(),
    )

    agent = KycAgent()
    with pytest.raises(AgentValidationError) as exc_info:
        await agent.execute(state)
    assert "Date of Birth is missing" in str(exc_info.value)


@pytest.mark.anyio
async def test_kyc_agent_missing_address():
    cust = get_complete_customer()
    cust["street_address"] = None  # costs 5 points

    state = AgentState(
        customer_id="cust-004",
        case_id="case-103",
        customer=cust,
        kyc_profile=get_complete_kyc_profile(),
        uploaded_documents=get_complete_documents(),
    )

    agent = KycAgent()
    res = await agent.execute(state)

    assert res.success is True
    assert res.risk_score == 95.0
    assert res.risk_level == "medium"  # Rule 7 triggers Medium Risk
    assert res.metadata["kyc_status"] == STATUS_INCOMPLETE
    assert any("address" in w.lower() for w in res.warnings)


@pytest.mark.anyio
async def test_kyc_agent_missing_identity_document():
    state = AgentState(
        customer_id="cust-005",
        case_id="case-104",
        customer=get_complete_customer(),
        kyc_profile=get_complete_kyc_profile(),
        uploaded_documents=[],  # Missing identity document (passport/ID/licence)
    )

    agent = KycAgent()
    res = await agent.execute(state)

    assert res.success is True
    assert res.risk_score == 80.0  # costs 20 points
    assert res.risk_level == "high"  # Rule 4 triggers High Risk
    assert res.metadata["kyc_status"] == STATUS_INCOMPLETE
    assert any("verification document" in w.lower() for w in res.warnings)


@pytest.mark.anyio
async def test_kyc_agent_missing_source_of_wealth():
    prof = get_complete_kyc_profile()
    prof["source_of_wealth"] = None  # costs 10 points

    state = AgentState(
        customer_id="cust-006",
        case_id="case-105",
        customer=get_complete_customer(),
        kyc_profile=prof,
        uploaded_documents=get_complete_documents(),
    )

    agent = KycAgent()
    res = await agent.execute(state)

    assert res.success is True
    assert res.risk_score == 90.0
    assert res.metadata["kyc_status"] == STATUS_INCOMPLETE
    # Rule 5: Manual Review recommendation
    assert any("Manual Review" in r for r in res.recommendations)


@pytest.mark.anyio
async def test_kyc_agent_business_customer():
    cust = get_complete_customer()
    cust["customer_type"] = "business"

    state = AgentState(
        customer_id="cust-007",
        case_id="case-106",
        customer=cust,
        kyc_profile=get_complete_kyc_profile(),
        uploaded_documents=get_complete_documents(),
    )

    agent = KycAgent()
    res = await agent.execute(state)

    assert res.success is True
    assert res.metadata["next_agent"] == "company_agent"
    assert any("Forwarding workflow to Company Agent" in r for r in res.recommendations)


@pytest.mark.anyio
async def test_kyc_agent_invalid_customer():
    state = AgentState(
        customer_id="cust-008",
        case_id="case-107",
        customer={},  # Empty dictionary
        kyc_profile=get_complete_kyc_profile(),
        uploaded_documents=get_complete_documents(),
    )

    agent = KycAgent()
    with pytest.raises(AgentValidationError):
        await agent.execute(state)
