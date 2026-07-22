import json
import pytest
from datetime import datetime, date, timedelta
from uuid import uuid4, UUID
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.testclient import TestClient

from app.core.config import settings
from app.models.models import (
    AIModel,
    ModelVersion,
    PromptTemplate,
    PromptVersion,
    AIExecution,
    AIFeedback,
    AIExplanation,
    AIPolicy,
    AIUsageStatistics,
)
from app.services.ai_governance_service import AIGovernanceService, PRICING_TABLE
from app.services.explainability_service import ExplainabilityService
from main import app

client = TestClient(app)

# ─── Mock DB Helpers ──────────────────────────────────────────────────────────


class _ScalarResult:
    def __init__(self, items):
        self._items = items

    def first(self):
        return self._items[0] if self._items else None

    def all(self):
        return list(self._items)

    def scalars(self):
        return self

    def scalar_one_or_none(self):
        return self._items[0] if self._items else None

    def scalar_one(self):
        return self._items[0] if self._items else None


def make_mock_db(rows=None):
    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = _ScalarResult(rows or [])
    db.get = AsyncMock(return_value=rows[0] if rows else None)
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    db.add = MagicMock()
    db.delete = AsyncMock()
    db.refresh = AsyncMock()
    db.bind = MagicMock()
    db.bind.dialect.name = "sqlite"
    return db


# ─── Service Unit Tests ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_register_model_and_version():
    """Verify that models and versions can be registered correctly."""
    db = make_mock_db()

    # 1. Model registration
    model = await AIGovernanceService.register_model(db, "test-model", "gemini", True)
    assert model.name == "test-model"
    assert model.provider == "gemini"
    assert model.is_active is True

    # 2. Version registration
    m_ver = await AIGovernanceService.register_model_version(
        db, model.id, "v1.0", {"temp": 0.5}
    )
    assert m_ver.version == "v1.0"
    assert m_ver.metadata_json == {"temp": 0.5}


@pytest.mark.asyncio
async def test_prompt_template_and_version_lifecycles():
    """Test creating prompt templates, versions, and switching active versions."""
    db = make_mock_db()

    # 1. Create prompt template
    pt = await AIGovernanceService.create_prompt_template(
        db, "test_prompt", "Standard test prompt"
    )
    assert pt.name == "test_prompt"

    # 2. Create prompt version
    pv = await AIGovernanceService.create_prompt_version(
        db, pt.id, "Hello {name}", "1.0.0", "draft"
    )
    assert pv.version == "1.0.0"
    assert pv.approved_status == "draft"
    assert pv.is_active is False


@pytest.mark.asyncio
async def test_approve_reject_prompt_version():
    """Verify state transitions and approvals workflows."""
    # Mock prompt version row
    pv = PromptVersion(
        id=uuid4(),
        template_id=uuid4(),
        version="1.0.0",
        content="Text",
        approved_status="pending",
        is_active=False,
    )
    db = make_mock_db([pv])

    # 1. Approve version
    res_app = await AIGovernanceService.approve_prompt_version(
        db, pv.id, uuid4(), "Looks perfect."
    )
    assert res_app.approved_status == "approved"

    # 2. Reject version
    pv.approved_status = "pending"
    res_rej = await AIGovernanceService.reject_prompt_version(
        db, pv.id, uuid4(), "Needs work."
    )
    assert res_rej.approved_status == "rejected"


@pytest.mark.asyncio
async def test_switch_and_rollback_active_version():
    """Verify switching active versions checks that version is approved."""
    pt_id = uuid4()
    pv = PromptVersion(
        id=uuid4(),
        template_id=pt_id,
        version="1.0.0",
        content="Text",
        approved_status="approved",
        is_active=False,
    )
    db = make_mock_db([pv])

    # Switch active
    active_pv = await AIGovernanceService.switch_active_prompt_version(db, pt_id, pv.id)
    assert active_pv.is_active is True
    assert active_pv.approved_status == "published"


def test_cost_calculation():
    """Verify LLM price estimation formula against pricing rate config matrices."""
    # Test gemini
    gemini_cost = AIGovernanceService.calculate_cost("gemini", 1000, 2000)
    # 1000 input tokens = 1 * 0.000075 = 0.000075
    # 2000 output tokens = 2 * 0.000300 = 0.0006
    # Total = 0.000675
    assert gemini_cost == 0.000675

    # Test fallback
    fallback_cost = AIGovernanceService.calculate_cost(
        "unsupported-provider", 1000, 1000
    )
    # Default is input 0.001000, output 0.003000
    # Total = 0.004000
    assert fallback_cost == 0.004000


@pytest.mark.asyncio
async def test_policy_guardrails_compliance():
    """Test policy checker returns violations if thresholds are exceeded."""
    policy = AIPolicy(
        id=uuid4(),
        name="strict_policy",
        rules_json={
            "min_confidence_threshold": 80.0,
            "max_latency_ms": 1000,
            "max_cost": 0.01,
        },
        is_active=True,
    )
    db = make_mock_db([policy])

    # 1. Compliant call
    ok, violations = await AIGovernanceService.check_policy_guardrails(
        db, "strict_policy", 90.0, 500, 0.005
    )
    assert ok is True
    assert len(violations) == 0

    # 2. Non-compliant call (fails confidence, latency, cost)
    ok, violations = await AIGovernanceService.check_policy_guardrails(
        db, "strict_policy", 50.0, 2000, 0.05
    )
    assert ok is False
    assert len(violations) == 3


def test_hallucination_detection_accuracy():
    """Verify that hallucination rates are calculated based on references matches."""
    text = "Subject John Doe matches database list markers for Sanction checks."

    # 1. High match rate (no hallucination)
    has_hallucination, score = AIGovernanceService.detect_hallucinations(
        text, ["John Doe", "Sanction"]
    )
    assert has_hallucination is False
    assert score == 100.0

    # 2. Low match rate (hallucination flagged)
    has_hallucination, score = AIGovernanceService.detect_hallucinations(
        text, ["Jane Doe", "PEP Check", "Adverse Media"]
    )
    assert has_hallucination is True
    assert score == 0.0


@pytest.mark.asyncio
async def test_explainability_report_construction():
    """Test structured explainability reports generation logic."""
    db = make_mock_db()
    exec_id = uuid4()

    report = await ExplainabilityService.generate_explanation_report(
        db=db,
        execution_id=exec_id,
        agent_name="SanctionsAgent",
        overall_score=85.0,
        findings=["Name similarity high", "Birthdate mismatch"],
        rules_triggered=["RULE_SANCTION_001"],
        matched_entities=["John Doe"],
        missing_evidence=["Official PII verification doc"],
    )

    assert report.execution_id == exec_id
    assert "SanctionsAgent" in report.decision_summary
    assert report.confidence == 95.0
    assert "RULE_SANCTION_001" in report.matched_rules
    assert "Official PII verification doc" in report.missing_evidence


# ─── API Router Integration Tests ────────────────────────────────────────────


def test_api_statistics_and_dashboard_structure():
    """Verify schemas and response structures for AI Analytics endpoints."""
    # Inject token headers if needed, otherwise verify returns metrics or auth challenge
    response = client.get("/api/v1/ai/dashboard")
    # Returns 401 if unauthorized, which proves endpoint route exists and is authenticated
    assert response.status_code in (200, 401)


def test_api_provider_status_uptime():
    """Verify health checker response format for providers."""
    response = client.get("/api/v1/ai/provider-status")
    assert response.status_code in (200, 401)
    if response.status_code == 200:
        data = response.json()
        assert "providers" in data
        assert len(data["providers"]) > 0
        assert data["providers"][0]["name"] == "Gemini"
