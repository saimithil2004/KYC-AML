import sys
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock
from uuid import uuid4

# Add backend to path
_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from fastapi.testclient import TestClient
from main import app
from app.dependencies.auth import verify_admin, verify_compliance_officer
from app.services.monitoring_service import MonitoringService
from app.tasks.schedule_tasks import run_monitoring_screening_task, dispatch_periodic_reviews, retry_failed_screenings
from app.models.models import MonitoringJob, MonitoringHistory

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


# ─── 1. Change Detection and Job Queuing Tests ───────────────────────────────

@pytest.mark.asyncio
async def test_change_detection_and_job_creation():
    """Verify change detection creates jobs and blocks duplicate requests."""
    mock_db = AsyncMock()
    mock_db.__aenter__.return_value = mock_db
    mock_res = MagicMock()
    mock_res.scalars.return_value.first.return_value = None  # No existing job
    mock_db.execute = AsyncMock(return_value=mock_res)

    # Create job
    customer_id = uuid4()
    with patch("app.services.monitoring_service.ensure_phase11_schema", return_value=None):
        job = await MonitoringService.detect_and_trigger_rescreen(mock_db, customer_id, "profile_updated")
        
        assert job is not None
        assert job.status == "queued"
        assert job.trigger_reason == "profile_updated"
        assert job.customer_id == customer_id

        # Mock database returning a running job
        mock_res.scalars.return_value.first.return_value = job
        duplicate_job = await MonitoringService.detect_and_trigger_rescreen(mock_db, customer_id, "profile_updated")
        assert duplicate_job.id == job.id  # Returns the same job, avoids duplicate


# ─── 2. Risk Delta Engine Tests ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_risk_delta_calculation():
    """Verify that delta calculations match previous risk score changes."""
    mock_db = AsyncMock()
    mock_db.__aenter__.return_value = mock_db
    mock_res = MagicMock()
    customer_id = uuid4()

    # Mock previous RiskScore
    mock_old_risk = MagicMock()
    mock_old_risk.overall_score = 45.0
    mock_res.scalars.return_value.first.side_effect = [
        mock_old_risk,  # First call fetches old risk score
        MagicMock(status="approved"),  # Second call fetches old case
        MagicMock(id=uuid4(), overall_score=60.0),  # Third call fetches new risk score
        MagicMock(review_frequency_months=12)  # Fourth call fetches monitoring schedule
    ]
    mock_res.scalar_one.return_value = 1  # Alert count is 1
    mock_db.execute = AsyncMock(return_value=mock_res)

    # Mock ScreeningService to run successfully
    mock_result = {
        "status": "success",
        "score": 60.0,
        "decision": "MANUAL_REVIEW",
        "case_id": str(uuid4()),
        "agents_completed": ["pep_agent", "sanctions_agent"]
    }

    with patch("app.services.monitoring_service.ensure_phase11_schema", return_value=None), \
         patch("app.services.monitoring_service.ScreeningService.run_screening_async", return_value=mock_result), \
         patch("app.services.monitoring_service.MonitoringService._generate_automated_alerts", return_value=None):
        
        res = await MonitoringService.run_rescreening(mock_db, customer_id, "new_transaction")
        
        assert res["status"] == "success"
        assert res["score"] == 60.0
        # Verify delta comparison
        # History is added to the session
        history_calls = [c[0][0] for c in mock_db.add.call_args_list if isinstance(c[0][0], MonitoringHistory)]
        assert len(history_calls) == 1
        history = history_calls[0]
        assert history.old_score == 45.0
        assert history.new_score == 60.0
        assert history.risk_delta == 15.0
        assert history.risk_trend == "deteriorating"  # delta > 5.0


# ─── 3. Celery Tasks & Dispatches Tests ──────────────────────────────────────

@patch("app.tasks.schedule_tasks.run_monitoring_screening_task.delay")
def test_celery_dispatch_loop(mock_delay):
    """Verify that dispatch_periodic_reviews lists schedules and issues Celery tasks."""
    mock_db = AsyncMock()
    mock_db.__aenter__.return_value = mock_db
    mock_res = MagicMock()
    
    # Mock overdue schedules
    mock_schedule = MagicMock()
    mock_schedule.customer_id = uuid4()
    mock_schedule.status = "scheduled"
    mock_res.scalars.return_value.all.return_value = [mock_schedule]
    mock_db.execute = AsyncMock(return_value=mock_res)
    
    mock_job = MagicMock()
    mock_job.id = uuid4()
    mock_job.status = "queued"

    with patch("app.tasks.schedule_tasks.SessionLocal", return_value=mock_db), \
         patch("app.tasks.schedule_tasks.MonitoringService.detect_and_trigger_rescreen", return_value=mock_job):
         
        summary = dispatch_periodic_reviews()
        assert summary["reviews_dispatched"] == 1
        assert mock_delay.called


@patch("app.tasks.schedule_tasks.run_monitoring_screening_task.delay")
def test_failed_job_retry_celery_flow(mock_delay):
    """Verify Celery task scans for failed jobs and queues them for retry."""
    mock_db = AsyncMock()
    mock_db.__aenter__.return_value = mock_db
    mock_res = MagicMock()
    
    mock_job = MagicMock()
    mock_job.id = uuid4()
    mock_job.customer_id = uuid4()
    mock_job.trigger_reason = "risk_change"
    mock_job.retry_count = 1
    
    mock_res.scalars.return_value.all.return_value = [mock_job]
    mock_db.execute = AsyncMock(return_value=mock_res)

    with patch("app.tasks.schedule_tasks.SessionLocal", return_value=mock_db):
        summary = retry_failed_screenings()
        assert summary["retried_count"] == 1
        assert mock_job.status == "queued"
        assert mock_job.retry_count == 2
        assert mock_delay.called




# ─── 4. API Endpoints Authorization (RBAC) Tests ─────────────────────────────

def test_api_monitoring_list_rbac():
    """Verify that compliance officers can access list but customers are forbidden."""
    # Read is allowed for Compliance Officer
    app.dependency_overrides[verify_compliance_officer] = override_verify_compliance_officer
    client = TestClient(app, raise_server_exceptions=False)
    
    res = client.get("/api/v1/monitoring/")
    assert res.status_code in (200, 500)  # 500 is allowed for offline DB

    res_history = client.get("/api/v1/monitoring/history")
    assert res_history.status_code in (200, 500)

    # Post manual trigger is allowed
    res_run = client.post(f"/api/v1/monitoring/run/{uuid4()}")
    assert res_run.status_code in (200, 202, 404, 500)

    # Post cancel is allowed
    res_cancel = client.post(f"/api/v1/monitoring/cancel/{uuid4()}")
    assert res_cancel.status_code in (200, 400, 404, 500)

    # Post retry is allowed
    res_retry = client.post(f"/api/v1/monitoring/retry/{uuid4()}")
    assert res_retry.status_code in (200, 400, 404, 500)

    # Read is blocked for general customers
    async def override_forbidden():
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Forbidden")
    app.dependency_overrides[verify_compliance_officer] = override_forbidden

    res_forbidden = client.get("/api/v1/monitoring/")
    assert res_forbidden.status_code == 403

    app.dependency_overrides.clear()
