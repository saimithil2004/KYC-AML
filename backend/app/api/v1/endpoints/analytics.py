"""
Analytics API Router — Phase 13
===============================
Provides REST endpoints for compliance statistics, rolling period KPIs,
risk averages, and case workload balancing.
Only accessible to compliance officers and administrators.
"""

from typing import Any, Dict
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.schema_helpers import ensure_phase13_schema
from app.dependencies.auth import verify_compliance_officer
from app.models.models import User
from app.services.analytics_service import AnalyticsService

router = APIRouter()


@router.get("/")
async def get_kpis(
    period: str = Query("monthly", regex="^(daily|weekly|monthly|quarterly|yearly)$"),
    current_user: User = Depends(verify_compliance_officer),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve generic compliance KPIs for the period."""
    await ensure_phase13_schema(db)
    return await AnalyticsService.get_kpi_metrics(db, period)


@router.get("/dashboard")
async def get_dashboard_summary(
    current_user: User = Depends(verify_compliance_officer),
    db: AsyncSession = Depends(get_db),
):
    """Get high-level dashboard KPIs for charts and metrics list."""
    await ensure_phase13_schema(db)
    return await AnalyticsService.get_kpi_metrics(db, "monthly")


@router.get("/risk")
async def get_risk_metrics(
    current_user: User = Depends(verify_compliance_officer),
    db: AsyncSession = Depends(get_db),
):
    """Get risk score averages and tier distributions."""
    await ensure_phase13_schema(db)
    return await AnalyticsService.get_risk_analytics(db)


@router.get("/cases")
async def get_case_metrics(
    current_user: User = Depends(verify_compliance_officer),
    db: AsyncSession = Depends(get_db),
):
    """Get case status statistics and investigator workloads."""
    await ensure_phase13_schema(db)
    return await AnalyticsService.get_case_analytics(db)


@router.get("/investigations")
async def get_investigation_metrics(
    current_user: User = Depends(verify_compliance_officer),
    db: AsyncSession = Depends(get_db),
):
    """Get active investigation workload logs (reusing workspace service if needed)."""
    await ensure_phase13_schema(db)
    from app.services.investigation_service import InvestigationService

    return await InvestigationService.get_dashboard_metrics(db)


@router.get("/transactions")
async def get_transaction_metrics(
    current_user: User = Depends(verify_compliance_officer),
    db: AsyncSession = Depends(get_db),
):
    """Get transactions statistics for line chart volumes."""
    await ensure_phase13_schema(db)
    # Return quick analytics transaction KPIs
    return await AnalyticsService.get_kpi_metrics(db, "monthly")
