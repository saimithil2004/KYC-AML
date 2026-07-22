"""
Dashboard API — Phase 9
=======================
Exposes endpoints for overview stats, charts, recent activities,
high-risk customer widgets, alert/case dashboards, and global search.
Only accessible to compliance officers and admins.
"""

import logging
from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies.auth import verify_compliance_officer
from app.models.models import User
from app.services.dashboard_service import DashboardService

logger = logging.getLogger(__name__)
router = APIRouter()


# ── GET /dashboard/overview ───────────────────────────────────────────────────


@router.get("/overview", response_model=Dict[str, Any])
async def get_overview(
    current_user: User = Depends(verify_compliance_officer),
    db: AsyncSession = Depends(get_db),
):
    """Get overall dashboard KPIs."""
    try:
        return await DashboardService.get_overview(db)
    except Exception as exc:
        logger.error(f"Failed to fetch overview: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch overview: {str(exc)}",
        )


# ── GET /dashboard/charts ─────────────────────────────────────────────────────


@router.get("/charts", response_model=Dict[str, Any])
async def get_charts(
    current_user: User = Depends(verify_compliance_officer),
    db: AsyncSession = Depends(get_db),
):
    """Get all dashboard chart datasets."""
    try:
        return await DashboardService.get_charts(db)
    except Exception as exc:
        logger.error(f"Failed to fetch charts: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch charts: {str(exc)}",
        )


# ── GET /dashboard/activity ───────────────────────────────────────────────────


@router.get("/activity", response_model=List[Dict[str, Any]])
async def get_activity(
    limit: int = Query(30, ge=1, le=100),
    current_user: User = Depends(verify_compliance_officer),
    db: AsyncSession = Depends(get_db),
):
    """Get live audit activity feed."""
    try:
        return await DashboardService.get_activity(db, limit)
    except Exception as exc:
        logger.error(f"Failed to fetch activity: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch activity: {str(exc)}",
        )


# ── GET /dashboard/risk ───────────────────────────────────────────────────────


@router.get("/risk", response_model=List[Dict[str, Any]])
async def get_risk(
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(verify_compliance_officer),
    db: AsyncSession = Depends(get_db),
):
    """Get high-risk customer widget list."""
    try:
        return await DashboardService.get_high_risk(db, limit)
    except Exception as exc:
        logger.error(f"Failed to fetch high risk: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch high risk: {str(exc)}",
        )


# ── GET /dashboard/alerts ─────────────────────────────────────────────────────


@router.get("/alerts", response_model=Dict[str, Any])
async def get_alerts_summary(
    current_user: User = Depends(verify_compliance_officer),
    db: AsyncSession = Depends(get_db),
):
    """Get alert summary metrics."""
    try:
        return await DashboardService.get_alerts_summary(db)
    except Exception as exc:
        logger.error(f"Failed to fetch alerts summary: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch alerts summary: {str(exc)}",
        )


# ── GET /dashboard/cases ──────────────────────────────────────────────────────


@router.get("/cases", response_model=Dict[str, Any])
async def get_cases_summary(
    current_user: User = Depends(verify_compliance_officer),
    db: AsyncSession = Depends(get_db),
):
    """Get case workload and summary metrics."""
    try:
        return await DashboardService.get_cases_summary(db)
    except Exception as exc:
        logger.error(f"Failed to fetch cases summary: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch cases summary: {str(exc)}",
        )


# ── GET /dashboard/monitoring ─────────────────────────────────────────────────


@router.get("/monitoring", response_model=Dict[str, Any])
async def get_monitoring(
    current_user: User = Depends(verify_compliance_officer),
    db: AsyncSession = Depends(get_db),
):
    """Get monitoring schedules and due/upcoming reviews."""
    try:
        return await DashboardService.get_monitoring(db)
    except Exception as exc:
        logger.error(f"Failed to fetch monitoring: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch monitoring: {str(exc)}",
        )


# ── GET /dashboard/search ─────────────────────────────────────────────────────


@router.get("/search", response_model=Dict[str, Any])
async def search(
    q: str = Query(..., min_length=2),
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(verify_compliance_officer),
    db: AsyncSession = Depends(get_db),
):
    """Global search across entities."""
    try:
        return await DashboardService.search(db, q, limit)
    except Exception as exc:
        logger.error(f"Failed to search: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to search: {str(exc)}",
        )


# ── GET /dashboard/ai ─────────────────────────────────────────────────────────


@router.get("/ai", response_model=Dict[str, Any])
async def get_ai_summary(
    current_user: User = Depends(verify_compliance_officer),
    db: AsyncSession = Depends(get_db),
):
    """Get AI Agent frameworks execution summary."""
    try:
        return await DashboardService.get_ai_summary(db)
    except Exception as exc:
        logger.error(f"Failed to fetch AI summary: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch AI summary: {str(exc)}",
        )
