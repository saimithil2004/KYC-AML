"""
Executive BI & Reports Unit Tests — Phase 13
=============================================
Tests report templates CRUD, report byte stream exports, periodic scheduled crons,
dashboard KPI analytics calculators, RBAC endpoint security rules, and audit log entries.
"""

import pytest
import io
from uuid import uuid4
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, AsyncMock

from fastapi import status
from app.models.models import User, Report, ReportTemplate, ScheduledReport, ReportExecution
from app.services.report_service import ReportService
from app.services.analytics_service import AnalyticsService
from app.api.v1.endpoints.reports import verify_compliance_officer, verify_admin


def test_verify_rbac_checks():
    """Verify compliance officer and admin access rules."""
    cust_user = User(id=uuid4(), email="cust@test.com", role="customer")
    with pytest.raises(Exception):
        verify_compliance_officer(cust_user)

    officer = User(id=uuid4(), email="officer@test.com", role="compliance_officer")
    verify_compliance_officer(officer)  # Should pass

    admin = User(id=uuid4(), email="admin@test.com", role="admin")
    verify_admin(admin)  # Should pass


@pytest.mark.asyncio
async def test_report_service_compile_and_export():
    """Verify ReportService data compilation and format export methods."""
    mock_db = AsyncMock()
    mock_db.__aenter__.return_value = mock_db

    # Setup mock query results for distributions/counts
    mock_res = MagicMock()
    mock_res.all.return_value = [("low", 12), ("medium", 45)]
    mock_db.execute = AsyncMock(return_value=mock_res)

    with patch("app.services.report_service.ensure_phase13_schema", return_value=None):
        # 1. Compile Risk Distribution
        data = await ReportService.compile_report_data(mock_db, "risk_distribution", {})
        assert len(data) == 2
        assert data[0]["risk_category"] == "low"
        assert data[0]["count"] == 12

        # 2. Test Export Bytes
        csv_bytes = ReportService.generate_csv_bytes(data)
        assert b"risk_category,count" in csv_bytes

        json_bytes = ReportService.generate_json_bytes(data)
        assert b'"risk_category": "low"' in json_bytes

        excel_bytes = ReportService.generate_excel_bytes(data, "Test Report")
        assert len(excel_bytes) > 0

        pdf_bytes = ReportService.generate_pdf_bytes(data, "Test Report", {})
        assert len(pdf_bytes) > 0


@pytest.mark.asyncio
async def test_analytics_service_kpis():
    """Verify AnalyticsService compiles KPIs and risk trends successfully."""
    mock_db = AsyncMock()
    mock_db.__aenter__.return_value = mock_db

    mock_res = MagicMock()
    mock_res.scalar_one.return_value = 10
    mock_res.scalar.return_value = 10
    mock_res.first.return_value = (45.5, 100)
    mock_res.all.return_value = [("low", 12), ("medium", 45)]
    mock_db.execute = AsyncMock(return_value=mock_res)

    with patch("app.services.analytics_service.ensure_phase13_schema", return_value=None):
        res = await AnalyticsService.get_kpi_metrics(mock_db, "monthly")
        assert res["period"] == "monthly"
        assert "metrics" in res
        assert "distributions" in res


@pytest.mark.asyncio
async def test_celery_report_execution_task():
    """Verify Celery task execute_scheduled_reports queries due schedules."""
    from app.tasks.schedule_tasks import execute_scheduled_reports
    
    mock_db = AsyncMock()
    mock_db.__aenter__.return_value = mock_db

    mock_schedule = MagicMock()
    mock_schedule.id = uuid4()
    mock_schedule.name = "Weekly AML Run"
    mock_schedule.cron_expression = "weekly"
    mock_schedule.next_run = datetime.utcnow() - timedelta(hours=1)
    mock_schedule.status = "active"
    mock_schedule.template = MagicMock()
    mock_schedule.template.config = {"format": "csv", "filters": {"report_type": "risk_distribution"}}

    mock_res = MagicMock()
    mock_res.scalars.return_value.all.return_value = [mock_schedule]
    mock_db.execute = AsyncMock(return_value=mock_res)

    with patch("app.tasks.schedule_tasks.SessionLocal", return_value=mock_db), \
         patch("app.services.report_service.ReportService.compile_report_data", return_value=[{"col": 1}]), \
         patch("app.services.report_service.ReportService.generate_csv_bytes", return_value=b"col\n1"), \
         patch("app.services.audit_service.AuditService.log", return_value=None), \
         patch("builtins.open", MagicMock()), \
         patch("os.makedirs", return_value=None):
        
        status = execute_scheduled_reports()
        assert status["executed_count"] == 1
        assert mock_schedule.status == "active"
