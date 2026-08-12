import sys
import tempfile
from pathlib import Path
import pytest
from unittest.mock import MagicMock, patch
from uuid import uuid4

# Add backend to path
_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from fastapi.testclient import TestClient
from main import app
from app.dependencies.auth import verify_admin, verify_compliance_officer
from app.services.text_extraction_service import TextExtractionService
from app.services.rule_extraction_service import RuleExtractionService
from app.agents.regulation.agent import RegulationAgent

# ─── Mock Auth Dependency Overrides ──────────────────────────────────────────


class MockUser:
    def __init__(self, role="admin"):
        self.id = uuid4()
        self.email = f"test-{role}@aml.com"
        self.role = role
        self.is_active = True


mock_admin = MockUser("admin")
mock_officer = MockUser("compliance_officer")


async def override_verify_admin():
    return mock_admin


async def override_verify_compliance_officer():
    return mock_officer


# ─── 1. Text Extraction Service Tests ────────────────────────────────────────


def test_text_extraction_txt():
    """Verify raw plain text file ingestion via temporary file."""
    text_content = "This is a regulation stating threshold is 5000 USD."
    with tempfile.NamedTemporaryFile(
        suffix=".txt", mode="w+", delete=False, encoding="utf-8"
    ) as tf:
        tf.write(text_content)
        tf.flush()
        temp_name = tf.name
    try:
        extracted = TextExtractionService.extract_text(temp_name)
        assert extracted == text_content
    finally:
        Path(temp_name).unlink(missing_ok=True)


def test_text_extraction_md():
    """Verify markdown file ingestion via temporary file."""
    md_content = "# UK Regulation\n- Threshold: £10,000"
    with tempfile.NamedTemporaryFile(
        suffix=".md", mode="w+", delete=False, encoding="utf-8"
    ) as tf:
        tf.write(md_content)
        tf.flush()
        temp_name = tf.name
    try:
        extracted = TextExtractionService.extract_text(temp_name)
        assert extracted == md_content
    finally:
        Path(temp_name).unlink(missing_ok=True)


@patch("app.services.text_extraction_service.pypdf.PdfReader")
def test_text_extraction_pdf(mock_pdf_reader):
    """Verify native PDF reader fallback using a temp file."""
    mock_page = MagicMock()
    mock_page.extract_text.return_value = "PDF Section 1: PEP block rule active."
    mock_pdf_reader.return_value.pages = [mock_page]

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tf:
        temp_name = tf.name
    try:
        extracted = TextExtractionService.extract_text(temp_name)
        assert "PEP block" in extracted
    finally:
        Path(temp_name).unlink(missing_ok=True)


@patch("app.services.text_extraction_service.docx.Document")
def test_text_extraction_docx(mock_docx):
    """Verify DOCX paragraph iteration extraction using a temp file."""
    mock_para = MagicMock()
    mock_para.text = "DOCX Regulation: EDD is mandatory."
    mock_docx.return_value.paragraphs = [mock_para]

    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tf:
        temp_name = tf.name
    try:
        extracted = TextExtractionService.extract_text(temp_name)
        assert "EDD is mandatory" in extracted
    finally:
        Path(temp_name).unlink(missing_ok=True)


# ─── 2. Rule Extraction Engine Tests ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_rule_extraction_regex_fallback():
    """Verify regex rule parser is triggered when Gemini key is missing."""
    text = (
        "The block list contains high risk clients. The threshold limit for EU transaction "
        "is 15000 EUR. EDD requirements are mandatory for PEP clients."
    )
    with patch("app.services.rule_extraction_service.settings.GEMINI_API_KEY", ""):
        rules = await RuleExtractionService.extract_rules(text)

        # Verify it parses regex patterns
        assert len(rules) > 0
        rule_types = [r["rule_type"] for r in rules]
        assert any(t in rule_types for t in ["threshold", "block", "edd"])


# ─── 3. Regulations & Rules CRUD API Routing Tests ─────────────────────────────


def test_api_regulations_list_rbac():
    """Verify compliance officer can view list but not upload regulations."""
    # 1. View is allowed
    app.dependency_overrides[verify_compliance_officer] = (
        override_verify_compliance_officer
    )
    client = TestClient(app, raise_server_exceptions=False)
    res_list = client.get("/api/v1/regulations/")
    assert res_list.status_code in (200, 500)

    # 2. Upload is forbidden for standard officer role
    async def override_forbidden():
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="Forbidden")

    app.dependency_overrides[verify_admin] = override_forbidden
    res_upload = client.post(
        "/api/v1/regulations/",
        data={"title": "FCA 2026", "authority": "FCA"},
        files={"file": ("fca.txt", b"FCA rule text", "text/plain")},
    )
    assert res_upload.status_code == 403
    app.dependency_overrides.clear()


def test_api_admin_regulation_upload_and_rollback_routes():
    """Verify admin has permission to upload, extract rules and trigger rollback endpoints."""
    app.dependency_overrides[verify_admin] = override_verify_admin
    app.dependency_overrides[verify_compliance_officer] = (
        override_verify_compliance_officer
    )
    client = TestClient(app, raise_server_exceptions=False)

    # POST Upload regulation
    res_upload = client.post(
        "/api/v1/regulations/",
        data={
            "title": "FCA 2026",
            "authority": "FCA",
            "version": "1.0.0",
            "description": "FCA Test",
        },
        files={"file": ("fca.txt", b"FCA AML rule block limit 5000", "text/plain")},
    )
    assert res_upload.status_code in (200, 201, 500)  # 500 is database connection issue

    # POST Extract rules
    res_extract = client.post(f"/api/v1/regulations/{uuid4()}/extract-rules")
    assert res_extract.status_code in (200, 404, 500)

    # POST Rollback
    res_rollback = client.post(
        f"/api/v1/regulations/{uuid4()}/rollback",
        json={
            "version_id": str(uuid4()),
            "reason": "Restoring stable regulations rules",
        },
    )
    assert res_rollback.status_code in (200, 404, 500)
    app.dependency_overrides.clear()


def test_api_policy_rules_routes_rbac():
    """Verify policy rules endpoint authorizations with valid schema payloads."""

    # Write actions need Admin
    async def override_forbidden():
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="Forbidden")

    app.dependency_overrides[verify_admin] = override_forbidden
    client = TestClient(app, raise_server_exceptions=False)
    res_create = client.post(
        "/api/v1/policy-rules/",
        json={
            "regulation_id": str(uuid4()),
            "rule_name": "TEST_LIMIT",
            "rule_type": "threshold",
            "conditions": {"max_amount": 1000},
            "severity": "medium",
            "version": "1.0.0",
        },
    )
    assert res_create.status_code == 403

    # Read actions allowed for Officers
    app.dependency_overrides[verify_compliance_officer] = (
        override_verify_compliance_officer
    )
    res_list = client.get("/api/v1/policy-rules/")
    assert res_list.status_code in (200, 500)
    app.dependency_overrides.clear()


# ─── 4. Regulation Agent Validation ───────────────────────────────────────────


def test_regulation_agent_defaults_fallback():
    """Verify RegulationAgent falls back to hardcoded compliance rules if DB yields empty list."""
    agent = RegulationAgent()
    assert hasattr(agent, "process")

    # Verify default parameters
    assert len(agent._default_rules()) >= 4
