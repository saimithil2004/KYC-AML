"""
Trace KYC agent metadata for TEST 7 customer to verify kyc_status, missing_fields, failed_rules.
"""
import asyncio
import json
from app.agents.base.agent_state import AgentState
from app.agents.kyc.agent import KycAgent
from app.agents.kyc.validator import KycValidator
from app.agents.kyc.rules import KycRulesEngine

# Simulate the same input that ScreeningService builds
customer_dict = {
    "id": "test-kyc7",
    "customer_type": "individual",
    "first_name": "Missing",
    "last_name": "KYC Test",
    "dob": "1990-06-15",
    "nationality": "United Kingdom",
    "street_address": "5 Test Lane",
    "city": "Manchester",
    "postal_code": "M1 1AA",
    "country": "United Kingdom",
    "status": "onboarding",
}

kyc_dict = {
    "full_name": "Missing KYC Test",
    "date_of_birth": "1990-06-15",
    "nationality": "United Kingdom",
    "address": "5 Test Lane, Manchester",
    "source_of_funds": "Salary",
    "source_of_wealth": "Employment Income",
    "occupation": None,       # intentionally missing — KYC007
    "tax_residency": None,    # intentionally missing — KYC008
    "risk_category": "low",
    "annual_income_range": None,
    "expected_activity_desc": None,
    "notes": None,
}

docs_list = [
    {
        "id": "doc-1",
        "document_type": "passport",
        "file_name": "passport_kyc7_test.pdf",
        "file_path": "uploads/passport_kyc7_test.pdf",
        "content_type": "application/pdf",
        "file_size": 2048,
        "ocr_data": {"first_name": "Missing", "last_name": "KYC Test", "document_type": "passport"},
        "verification_status": "verified",
        "verification_metadata": {"fraud_checks": {"tampering_detected": False, "score": 0}},
    }
]

state = AgentState(
    customer_id="test-kyc7",
    case_id="test-case-7",
    customer=customer_dict,
    kyc_profile=kyc_dict,
    uploaded_documents=docs_list,
)


async def trace_kyc():
    agent = KycAgent()
    result = await agent.process(state)
    print("=== KYC AGENT TRACE ===")
    print(f"kyc_status    : {state.shared_metadata.get('kyc_status')}")
    print(f"kyc_score     : {state.shared_metadata.get('kyc_score')}")
    print(f"missing_fields: {state.shared_metadata.get('missing_fields')}")
    print(f"next_agent    : {state.shared_metadata.get('next_agent')}")
    print()
    audit = state.shared_metadata.get("kyc_audit_trail", {})
    print(f"passed_rules  : {audit.get('passed_rules', [])}")
    print(f"failed_rules  : {audit.get('failed_rules', [])}")
    print()
    print(f"warnings      : {result.get('warnings', [])}")
    print(f"recommendations: {result.get('recommendations', [])}")
    print(f"risk_level    : {result.get('risk_level')}")
    print(f"findings      : {result.get('findings', [])}")


asyncio.run(trace_kyc())
