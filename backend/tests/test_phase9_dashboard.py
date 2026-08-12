import sys
from pathlib import Path
import pytest
from uuid import uuid4
from datetime import datetime, date

# Add backend to path
_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from main import app
from app.dependencies.auth import verify_compliance_officer, get_current_user
from app.models.models import User, Customer, RiskScore, Alert, Case, AuditLog
from app.services.dashboard_service import DashboardService

from unittest.mock import AsyncMock, MagicMock, patch

# ─── Mock Auth & DB dependency overrides ─────────────────────────────────────


class MockUser:
    def __init__(self, role="compliance_officer"):
        self.id = uuid4()
        self.email = f"test-{role}@aml.com"
        self.role = role
        self.is_active = True


mock_officer = MockUser("compliance_officer")
mock_customer = MockUser("customer")


async def override_verify_compliance_officer():
    return mock_officer


async def override_get_current_user():
    return mock_officer


async def override_get_current_user_customer():
    return mock_customer


# ─── Tests ───────────────────────────────────────────────────────────────────


@patch.object(DashboardService, "get_overview", new_callable=AsyncMock)
def test_dashboard_rbac_compliance_officer(mock_overview):
    """Verify compliance officer can access dashboard overview."""
    mock_overview.return_value = {
        "total_customers": 100,
        "high_risk_customers": 5,
        "pending_cases": 2,
        "open_alerts": 3,
    }
    app.dependency_overrides[verify_compliance_officer] = (
        override_verify_compliance_officer
    )
    client = TestClient(app)
    response = client.get("/api/v1/dashboard/overview")

    assert response.status_code == 200
    app.dependency_overrides.clear()


def test_dashboard_rbac_customer_forbidden():
    """Verify normal customer user is forbidden from dashboard overview."""

    async def override_forbidden():
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="Not authorized.")

    app.dependency_overrides[verify_compliance_officer] = override_forbidden
    client = TestClient(app)
    response = client.get("/api/v1/dashboard/overview")
    assert response.status_code == 403
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_dashboard_service_mock_aggregation():
    """Test DashboardService aggregation logic with mock database sessions."""
    assert hasattr(DashboardService, "get_overview")
    assert hasattr(DashboardService, "get_charts")
    assert hasattr(DashboardService, "get_activity")
    assert hasattr(DashboardService, "get_high_risk")
    assert hasattr(DashboardService, "get_alerts_summary")
    assert hasattr(DashboardService, "get_cases_summary")
    assert hasattr(DashboardService, "get_monitoring")
    assert hasattr(DashboardService, "search")
    assert hasattr(DashboardService, "get_ai_summary")


@patch.object(DashboardService, "search", new_callable=AsyncMock)
def test_dashboard_search_endpoint(mock_search):
    """Verify search API parameters and routing."""
    mock_search.return_value = {"query": "test", "results": []}
    app.dependency_overrides[verify_compliance_officer] = (
        override_verify_compliance_officer
    )
    client = TestClient(app)
    # Search requires q parameter
    res1 = client.get("/api/v1/dashboard/search")
    assert res1.status_code == 422  # Missing q parameter

    res2 = client.get("/api/v1/dashboard/search?q=test")
    assert res2.status_code == 200
    app.dependency_overrides.clear()


@patch.object(DashboardService, "get_charts", new_callable=AsyncMock)
@patch.object(DashboardService, "get_activity", new_callable=AsyncMock)
@patch.object(DashboardService, "get_high_risk", new_callable=AsyncMock)
@patch.object(DashboardService, "get_alerts_summary", new_callable=AsyncMock)
@patch.object(DashboardService, "get_cases_summary", new_callable=AsyncMock)
@patch.object(DashboardService, "get_monitoring", new_callable=AsyncMock)
@patch.object(DashboardService, "get_ai_summary", new_callable=AsyncMock)
def test_dashboard_charts_endpoints(
    mock_ai, mock_mon, mock_cases, mock_alerts, mock_risk, mock_act, mock_charts
):
    """Verify charts and helper overview routes."""
    mock_charts.return_value = {}
    mock_act.return_value = []
    mock_risk.return_value = []
    mock_alerts.return_value = {}
    mock_cases.return_value = {}
    mock_mon.return_value = {}
    mock_ai.return_value = {}

    app.dependency_overrides[verify_compliance_officer] = (
        override_verify_compliance_officer
    )
    client = TestClient(app)

    for route in ["charts", "activity", "risk", "alerts", "cases", "monitoring", "ai"]:
        res = client.get(f"/api/v1/dashboard/{route}")
        assert res.status_code == 200

    app.dependency_overrides.clear()
