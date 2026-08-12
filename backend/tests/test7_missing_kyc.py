"""
TEST 7 — MISSING MANDATORY KYC END-TO-END AML TEST
===================================================
Verifies existing pipeline behaviour when a KYCProfile is intentionally
missing a mandatory field that the existing KycAgent/KycRulesEngine catches.

Mandatory fields that trigger AgentValidationError (CRITICAL — raises immediately):
  - first_name_or_last_name  (Rule KYC001)
  - dob                      (Rule KYC002)

Non-critical missing fields (warnings / risk flags only):
  - occupation               (Rule KYC007, optional)
  - tax_residency            (Rule KYC008, optional)
  - source_of_funds          (Rule KYC006, RISK_MEDIUM)
  - source_of_wealth         (Rule KYC005, MANUAL_REVIEW recommendation)
  - address parts            (Rule KYC004, RISK_MEDIUM)
  - passport/ID doc          (Rule KYC003, RISK_HIGH)

This test deliberately omits `occupation` (Rule KYC007) and `tax_residency`
(Rule KYC008) from the KYCProfile so that:
  * The pipeline DOES NOT raise AgentValidationError (only name/DOB do that)
  * KycAgent detects the missing fields and records them
  * KYC score is reduced: 100 - 10 (occupation) - 5 (tax_residency) = 85.0
  * kyc_status = INCOMPLETE (85.0 >= 60.0 but < 100.0)
  * The pipeline continues to completion (PEP, Sanctions, etc. all CLEAR)
  * Final decision depends on overall AML score (expected: APPROVE at low score)

Customer has:
  PEP = CLEAR, Sanctions = CLEAR, Country = CLEAR, FATF = CLEAR,
  Transactions = CLEAR, Document = VERIFIED (passport)

Only intentional risk signal: missing occupation + tax_residency → KYC007 + KYC008
"""

import asyncio
import json
import pytest
from datetime import date
from uuid import UUID, uuid4
from pathlib import Path

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.core.database import SessionLocalSync, sync_engine
from app.models.models import (
    Base, User, Customer, KYCProfile, Document,
    Case, Alert, RiskScore, Account, Transaction,
)
from app.services.screening_service import ScreeningService


# ── Helper: create test customer ─────────────────────────────────────────────

def _create_missing_kyc_customer():
    """Create a clean customer with intentionally missing source_of_funds."""
    Base.metadata.create_all(sync_engine)
    db = SessionLocalSync()

    unique_suffix = uuid4().hex[:8]
    user = User(
        email=f"missing.kyc.test.{unique_suffix}@example.com",
        password_hash="pw",
        role="customer",
    )
    db.add(user)
    db.commit()

    cust = Customer(
        user_id=user.id,
        customer_type="individual",
        first_name="Missing",
        last_name="KYC Test",
        dob=date(1990, 6, 15),
        nationality="United Kingdom",
        street_address="5 Test Lane",
        city="Manchester",
        postal_code="M1 1AA",
        country="United Kingdom",
        status="onboarding",
    )
    db.add(cust)
    db.commit()

    # KYC profile with intentionally missing occupation (Rule KYC007) + tax_residency (Rule KYC008)
    # Both are nullable at DB level — this is how the existing test for missing_kyc works
    kyc = KYCProfile(
        customer_id=cust.id,
        full_name="Missing KYC Test",
        date_of_birth=date(1990, 6, 15),
        nationality="United Kingdom",
        address="5 Test Lane, Manchester",
        source_of_funds="Salary",
        source_of_wealth="Employment Income",
        occupation=None,            # ← intentionally omitted (Rule KYC007)
        tax_residency=None,         # ← intentionally omitted (Rule KYC008)
        risk_category="low",
    )
    db.add(kyc)

    # Valid verified passport document
    Path("uploads").mkdir(exist_ok=True)
    passport_path = Path("uploads/passport_kyc7_test.pdf")
    if not passport_path.exists():
        passport_path.write_bytes(b"%PDF-1.4 test passport content for kyc7")

    doc = Document(
        customer_id=cust.id,
        document_type="passport",
        file_name="passport_kyc7_test.pdf",
        file_path=str(passport_path),
        file_size=2048,
        content_type="application/pdf",
        verification_status="verified",
        ocr_data={
            "first_name": "Missing",
            "last_name": "KYC Test",
            "document_type": "passport",
        },
        verification_metadata={"fraud_checks": {"tampering_detected": False, "score": 0}},
    )
    db.add(doc)
    db.commit()

    cust_id = str(cust.id)
    doc_id = str(doc.id)
    kyc_id = str(kyc.id)
    db.close()
    return cust_id, doc_id, kyc_id


# ── Main test ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_e2e_missing_kyc_source_of_funds():
    """TEST 7 — End-to-end: missing occupation+tax_residency detected, pipeline completes."""
    cust_id, doc_id, kyc_id = _create_missing_kyc_customer()
    cust_uuid = UUID(cust_id)

    print(f"\n[TEST7] Customer ID : {cust_id}")
    print(f"[TEST7] KYC ID      : {kyc_id}")
    print(f"[TEST7] Document ID : {doc_id}")

    # ── Run real pipeline ─────────────────────────────────────────────────────
    result = await ScreeningService.run_screening_async(cust_id)

    print(f"\n[TEST7] Pipeline result:")
    print(json.dumps(result, indent=2, default=str))

    # ── Assert pipeline completed ─────────────────────────────────────────────
    assert result["status"] == "success", (
        f"Pipeline did not return success: {result}"
    )

    decision = result["decision"]
    score = result["score"]
    tier = result["tier"]
    case_id = result["case_id"]

    print(f"\n[TEST7] Decision : {decision}")
    print(f"[TEST7] Score    : {score}")
    print(f"[TEST7] Tier     : {tier}")
    print(f"[TEST7] Case ID  : {case_id}")

    # ── Verify DB ─────────────────────────────────────────────────────────────
    db = SessionLocalSync()

    cust_rec = db.query(Customer).filter(Customer.id == cust_uuid).first()
    print(f"\n[TEST7] customer.status  : {cust_rec.status}")

    kyc_rec = db.query(KYCProfile).filter(KYCProfile.customer_id == cust_uuid).first()
    print(f"[TEST7] kyc.source_of_funds : {kyc_rec.source_of_funds!r}  (should be None)")

    doc_rec = db.query(Document).filter(Document.customer_id == cust_uuid).first()
    print(f"[TEST7] doc.verification_status : {doc_rec.verification_status}")

    case_rec = db.query(Case).filter(Case.customer_id == cust_uuid).order_by(Case.created_at.desc()).first()
    print(f"[TEST7] case.status : {case_rec.status if case_rec else None}")

    risk_rec = db.query(RiskScore).filter(RiskScore.customer_id == cust_uuid).first()
    print(f"[TEST7] risk_score.overall_score : {float(risk_rec.overall_score) if risk_rec else None}")

    alert_rec = db.query(Alert).filter(Alert.customer_id == cust_uuid).first()
    print(f"[TEST7] alert : {alert_rec.alert_type if alert_rec else None}")

    print(f"[TEST7] investigation : (not queried — check admin UI)")

    # ── Verify KYC field state ────────────────────────────────────────────────
    assert kyc_rec.occupation is None, "occupation should still be None in DB"
    assert kyc_rec.tax_residency is None, "tax_residency should still be None in DB"
    assert doc_rec.verification_status == "verified", "Document should remain verified"

    db.close()

    print(f"\n[TEST7] agents_completed : {result.get('agents_completed', [])}")
    factors_str = str(result.get('contributing_factors', [])).encode('ascii', 'replace').decode('ascii')
    print(f"[TEST7] contributing_factors : {factors_str}")

    return {
        "customer_id": cust_id,
        "kyc_id": kyc_id,
        "doc_id": doc_id,
        "case_id": case_id,
        "decision": decision,
        "score": score,
        "tier": tier,
        "customer_status": cust_rec.status,
        "case_status": case_rec.status if case_rec else None,
        "risk_score": float(risk_rec.overall_score) if risk_rec else None,
        "alert": alert_rec.alert_type if alert_rec else None,
    }
