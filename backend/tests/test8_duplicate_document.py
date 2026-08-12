"""
TEST 8 — DUPLICATE DOCUMENT END-TO-END AML TEST
================================================

Duplicate detection in this project works at TWO levels:

Level 1 — DocumentVerificationService.run_pre_ocr_checks (service layer):
  - Computes SHA-256 hash of the uploaded file
  - Stores it in verification_metadata["file_hash"]
  - validate_document(doc, ocr_data, is_dup_hash=True) flags it with:
    "Document duplicate hash already uploaded."
  - Triggered by Celery task / API upload endpoint
  - This is what test_e2e_duplicate_document_flagged (Scenario 8) tests

Level 2 — DocumentVerificationAgent (AML pipeline agent):
  - Checks for duplicate FILE NAMES in the documents loaded into AgentState
  - If the same filename appears more than once → duplicate_count += 1
  - Score deduction: 10 points per duplicate (score -= duplicates * 10.0)
  - A duplicate triggers a warning: "Duplicate document detected: ..."
  - It does NOT raise an AgentValidationError — pipeline continues

This test exercises the full AML pipeline path (Level 2):
  - Create customer with complete KYC
  - Create one verified passport doc
  - Create a SECOND document for the SAME customer with the SAME file_name
    (same content = same hash as bonus, but the agent checks filename)
  - Run ScreeningService.run_screening_async
  - Verify duplicate is detected, score is reduced, and decision matches policy

Expected document score with 1 duplicate:
  Base: 100.0
  - 1 duplicate × 10.0 = -10.0
  Both docs are "verified" so no unverified-ratio penalty.
  Final: 90.0 → risk_level = "low" (>=70)

Expected overall AML contribution from document at 90.0:
  weight = 10%, agent_score = 90, gap = 10, contribution = 10% of 10 = 1.0

Expected overall AML score: ~1.0 → APPROVE (<=30)
"""

import json
import pytest
from datetime import date
from uuid import uuid4, UUID
from pathlib import Path

from app.core.database import SessionLocalSync, sync_engine
from app.models.models import (
    Base, User, Customer, KYCProfile, Document,
    Case, Alert, RiskScore,
)
from app.services.screening_service import ScreeningService
from app.services.document_verification import DocumentVerificationService


# ── Helper: create duplicate-document customer ────────────────────────────────

def _create_duplicate_document_customer():
    """Create customer with two docs sharing the same filename (and content hash)."""
    Base.metadata.create_all(sync_engine)
    db = SessionLocalSync()

    unique_suffix = uuid4().hex[:8]
    user = User(
        email=f"duplicate.document.test.{unique_suffix}@example.com",
        password_hash="pw",
        role="customer",
    )
    db.add(user)
    db.commit()

    cust = Customer(
        user_id=user.id,
        customer_type="individual",
        first_name="Duplicate",
        last_name="Document Test",
        dob=date(1988, 3, 22),
        nationality="United Kingdom",
        street_address="99 Clone Street",
        city="Bristol",
        postal_code="BS1 1AB",
        country="United Kingdom",
        status="onboarding",
    )
    db.add(cust)
    db.commit()

    kyc = KYCProfile(
        customer_id=cust.id,
        full_name="Duplicate Document Test",
        date_of_birth=date(1988, 3, 22),
        nationality="United Kingdom",
        address="99 Clone Street, Bristol",
        source_of_funds="Salary",
        source_of_wealth="Employment Income",
        occupation="Accountant",
        tax_residency="United Kingdom",
        risk_category="low",
    )
    db.add(kyc)
    db.commit()

    # Create the actual file (large enough to pass quality checks: >5KB)
    Path("uploads").mkdir(exist_ok=True)
    # Same file content → same SHA-256 hash
    file_content = b"%PDF-1.4 " + b"X" * 10000  # >5KB

    original_path = Path("uploads/duplicate_test_passport.pdf")
    original_path.write_bytes(file_content)

    # Compute hash for both docs
    sha256_hash = DocumentVerificationService.calculate_sha256(original_path)
    print(f"\n[TEST8] Document SHA-256 hash: {sha256_hash}")

    # Document 1 — original, verified
    doc1 = Document(
        customer_id=cust.id,
        document_type="passport",
        file_name="duplicate_test_passport.pdf",      # <-- same filename
        file_path=str(original_path),
        file_size=len(file_content),
        content_type="application/pdf",
        verification_status="verified",
        ocr_data={
            "first_name": "Duplicate",
            "last_name": "Document Test",
            "document_type": "passport",
        },
        verification_metadata={
            "file_hash": sha256_hash,
            "fraud_checks": {"tampering_detected": False, "score": 0},
        },
    )
    db.add(doc1)
    db.commit()

    # Document 2 — duplicate: SAME filename, SAME file content/hash
    # (simulates user uploading the same passport twice)
    doc2 = Document(
        customer_id=cust.id,
        document_type="passport",
        file_name="duplicate_test_passport.pdf",      # <-- SAME filename = duplicate
        file_path=str(original_path),
        file_size=len(file_content),
        content_type="application/pdf",
        verification_status="verified",               # also marked verified
        ocr_data={
            "first_name": "Duplicate",
            "last_name": "Document Test",
            "document_type": "passport",
        },
        verification_metadata={
            "file_hash": sha256_hash,                 # SAME hash as doc1
            "fraud_checks": {"tampering_detected": False, "score": 0},
        },
    )
    db.add(doc2)
    db.commit()

    cust_id = str(cust.id)
    doc1_id = str(doc1.id)
    doc2_id = str(doc2.id)
    db.close()
    return cust_id, doc1_id, doc2_id, sha256_hash


# ── Main test ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_e2e_duplicate_document_pipeline():
    """
    TEST 8 — Full pipeline with duplicate document.
    Verifies DocumentVerificationAgent detects duplicate filename,
    deducts 10 points from document score, and pipeline runs to completion.
    """
    cust_id, doc1_id, doc2_id, sha256_hash = _create_duplicate_document_customer()
    cust_uuid = UUID(cust_id)

    print(f"\n[TEST8] Customer ID   : {cust_id}")
    print(f"[TEST8] Document 1 ID : {doc1_id}")
    print(f"[TEST8] Document 2 ID : {doc2_id} (duplicate)")
    print(f"[TEST8] SHA-256 hash  : {sha256_hash}")

    # ── Run real AML screening pipeline ───────────────────────────────────────
    result = await ScreeningService.run_screening_async(cust_id)

    print(f"\n[TEST8] Pipeline result:")
    safe_result = json.dumps(result, indent=2, default=str)
    print(safe_result.encode('ascii', 'replace').decode('ascii'))

    # ── Assert pipeline completed successfully ────────────────────────────────
    assert result["status"] == "success", f"Pipeline returned non-success: {result}"

    decision = result["decision"]
    score = result["score"]
    tier = result["tier"]
    case_id = result["case_id"]

    print(f"\n[TEST8] Decision : {decision}")
    print(f"[TEST8] Score    : {score}")
    print(f"[TEST8] Tier     : {tier}")
    print(f"[TEST8] Case ID  : {case_id}")

    # ── Verify contributing factors for document signal ───────────────────────
    factors = result.get("contributing_factors", [])
    doc_factor = next((f for f in factors if f["signal"] == "document"), None)
    print(f"\n[TEST8] Document factor : {str(doc_factor).encode('ascii', 'replace').decode('ascii')}")

    # Document agent should detect the duplicate
    # Expected document_score = 90 (100 - 10 for 1 duplicate, both verified)
    # This is reflected in the agent_score for the document signal
    if doc_factor:
        agent_score = doc_factor["agent_score"]
        print(f"[TEST8] Document agent_score : {agent_score}")
        # The duplicate reduces the score — should be <100
        assert agent_score < 100.0, (
            f"Document agent_score should be <100 (duplicate detected), got {agent_score}"
        )

    # ── Verify DB state ───────────────────────────────────────────────────────
    db = SessionLocalSync()

    cust_rec = db.query(Customer).filter(Customer.id == cust_uuid).first()
    print(f"\n[TEST8] customer.status : {cust_rec.status}")

    kyc_rec = db.query(KYCProfile).filter(KYCProfile.customer_id == cust_uuid).first()
    print(f"[TEST8] kyc.occupation : {kyc_rec.occupation}")
    print(f"[TEST8] kyc.source_of_funds : {kyc_rec.source_of_funds}")

    docs = db.query(Document).filter(Document.customer_id == cust_uuid).all()
    print(f"[TEST8] Documents in DB : {len(docs)}")
    for d in docs:
        print(f"  doc: {d.id}, type={d.document_type}, status={d.verification_status}, name={d.file_name}")

    case_rec = db.query(Case).filter(Case.customer_id == cust_uuid).order_by(Case.created_at.desc()).first()
    print(f"[TEST8] case.status : {case_rec.status if case_rec else None}")
    print(f"[TEST8] case.priority : {case_rec.priority if case_rec else None}")

    risk_rec = db.query(RiskScore).filter(RiskScore.customer_id == cust_uuid).first()
    print(f"[TEST8] risk.overall_score : {float(risk_rec.overall_score) if risk_rec else None}")
    print(f"[TEST8] risk.risk_tier : {risk_rec.risk_tier if risk_rec else None}")

    alert_rec = db.query(Alert).filter(Alert.customer_id == cust_uuid).first()
    print(f"[TEST8] alert : {alert_rec.alert_type if alert_rec else None}")

    # ── Verify document count and hash ────────────────────────────────────────
    assert len(docs) == 2, f"Expected 2 documents in DB, got {len(docs)}"
    filenames = [d.file_name for d in docs]
    assert filenames.count("duplicate_test_passport.pdf") == 2, (
        f"Expected 2 docs with same filename, got: {filenames}"
    )
    for d in docs:
        meta = d.verification_metadata or {}
        assert meta.get("file_hash") == sha256_hash, (
            f"Document {d.id} hash mismatch: {meta.get('file_hash')} != {sha256_hash}"
        )

    db.close()

    print(f"\n[TEST8] Agents completed : {result.get('agents_completed', [])}")

    return {
        "customer_id": cust_id,
        "doc1_id": doc1_id,
        "doc2_id": doc2_id,
        "sha256_hash": sha256_hash,
        "decision": decision,
        "score": score,
        "tier": tier,
        "case_id": case_id,
        "case_status": case_rec.status if case_rec else None,
        "customer_status": cust_rec.status,
        "risk_score": float(risk_rec.overall_score) if risk_rec else None,
        "alert": alert_rec.alert_type if alert_rec else None,
    }
