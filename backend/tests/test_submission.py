"""
Application Submission Endpoint Tests — Priority 2
===================================================
Tests POST /api/v1/kyc/{customer_id}/submit for:
  1. First valid submission
  2. Repeated submission prevention
  3. Incomplete KYC profile validation
  4. Missing document upload validation
  5. Already approved customer submission prevention
"""

import pytest
from datetime import date
from uuid import uuid4
from fastapi.testclient import TestClient

from main import app
from app.core.database import SessionLocalSync, sync_engine
from app.models.models import Base, User, Customer, KYCProfile, Document
from app.core.security import create_access_token

client = TestClient(app)


def _setup_submission_test_data(
    customer_status="onboarding",
    has_kyc=True,
    has_doc=True,
    kyc_incomplete=False,
):
    """Helper to provision test user, customer, KYC, and document records."""
    Base.metadata.create_all(sync_engine)
    db = SessionLocalSync()

    email = f"test_sub_{uuid4().hex[:8]}@example.com"
    user = User(
        email=email,
        password_hash="hashed_test_password",
        role="customer",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    customer = Customer(
        user_id=user.id,
        customer_type="individual",
        first_name="Submission",
        last_name="Tester",
        dob=date(1990, 5, 15),
        nationality="United Kingdom",
        street_address="10 Downing Street",
        city="London",
        postal_code="SW1A 2AA",
        country="United Kingdom",
        status=customer_status,
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)

    if has_kyc:
        kyc = KYCProfile(
            customer_id=customer.id,
            full_name="" if kyc_incomplete else "Submission Tester",
            date_of_birth=date(1990, 5, 15),
            nationality="" if kyc_incomplete else "United Kingdom",
            address="10 Downing Street",
            source_of_funds="Employment Salary",
            source_of_wealth="Accumulated Savings",
            occupation="Software Engineer",
            risk_category="low",
        )
        db.add(kyc)
        db.commit()

    if has_doc:
        doc = Document(
            customer_id=customer.id,
            document_type="passport",
            file_name="passport.pdf",
            file_path="uploads/passport.pdf",
            file_size=1024,
            content_type="application/pdf",
            verification_status="verified",
        )
        db.add(doc)
        db.commit()

    token = create_access_token(subject=str(user.id), role=user.role)
    db.close()

    return user.id, customer.id, token


def test_first_submission_success():
    """Verify first valid application submission succeeds and updates status to pending_verification."""
    user_id, cust_id, token = _setup_submission_test_data(customer_status="onboarding")
    headers = {"Authorization": f"Bearer {token}"}

    res = client.post(f"/api/v1/kyc/{cust_id}/submit", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "submitted"
    assert data["customer_id"] == str(cust_id)

    db = SessionLocalSync()
    cust = db.query(Customer).filter(Customer.id == cust_id).first()
    assert cust.status in ("pending_verification", "approved")
    db.close()


def test_repeated_submission_blocked():
    """Verify repeated submission when status is pending_verification returns 400 Bad Request."""
    user_id, cust_id, token = _setup_submission_test_data(customer_status="pending_verification")
    headers = {"Authorization": f"Bearer {token}"}

    res = client.post(f"/api/v1/kyc/{cust_id}/submit", headers=headers)
    assert res.status_code == 400
    assert "already been submitted" in res.json()["detail"]


def test_incomplete_kyc_submission_blocked():
    """Verify submitting with missing or incomplete KYC declaration returns 400 Bad Request."""
    user_id, cust_id, token = _setup_submission_test_data(
        customer_status="onboarding", kyc_incomplete=True
    )
    headers = {"Authorization": f"Bearer {token}"}

    res = client.post(f"/api/v1/kyc/{cust_id}/submit", headers=headers)
    assert res.status_code == 400
    assert "KYC declaration is incomplete" in res.json()["detail"]


def test_missing_document_submission_blocked():
    """Verify submitting with no uploaded identity document returns 400 Bad Request."""
    user_id, cust_id, token = _setup_submission_test_data(
        customer_status="onboarding", has_doc=False
    )
    headers = {"Authorization": f"Bearer {token}"}

    res = client.post(f"/api/v1/kyc/{cust_id}/submit", headers=headers)
    assert res.status_code == 400
    assert "No identity document uploaded" in res.json()["detail"]


def test_already_approved_customer_submission_blocked():
    """Verify submitting an already approved customer application returns 400 Bad Request."""
    user_id, cust_id, token = _setup_submission_test_data(customer_status="approved")
    headers = {"Authorization": f"Bearer {token}"}

    res = client.post(f"/api/v1/kyc/{cust_id}/submit", headers=headers)
    assert res.status_code == 400
    assert "already approved" in res.json()["detail"]
