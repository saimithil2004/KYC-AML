"""
Monitoring API Router — Phase 11
===============================
Provides REST endpoints for compliance monitoring schedules, Celery jobs, history,
triage operations, and risk delta aggregations.
Only accessible to compliance officers and administrators.
"""

import logging
from typing import Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select, desc, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.schema_helpers import ensure_phase11_schema
from app.dependencies.auth import verify_compliance_officer, verify_admin
from app.models.models import (
    User,
    Customer,
    MonitoringSchedule,
    MonitoringJob,
    MonitoringHistory,
    RiskScore,
    Case,
)
from app.schemas.schemas import (
    PaginatedMonitoringSchedules,
    MonitoringScheduleResponse,
    PaginatedMonitoringJobs,
    MonitoringJobResponse,
    PaginatedMonitoringHistory,
    MonitoringHistoryResponse,
    MonitoringStatistics,
    RiskDeltaResponse,
)
from app.services.monitoring_service import MonitoringService
from app.services.audit_service import AuditService
from app.tasks.schedule_tasks import run_monitoring_screening_task

logger = logging.getLogger(__name__)
router = APIRouter()


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    return (
        forwarded.split(",")[0].strip()
        if forwarded
        else (request.client.host if request.client else "unknown")
    )


# ── GET /monitoring ──────────────────────────────────────────────────────────
@router.get("/", response_model=PaginatedMonitoringSchedules)
async def list_monitoring_schedules(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    current_user: User = Depends(verify_compliance_officer),
    db: AsyncSession = Depends(get_db),
):
    """List customer monitoring review schedules."""
    await ensure_phase11_schema(db)

    q = select(MonitoringSchedule)
    if status:
        q = q.where(MonitoringSchedule.status == status)

    total = (
        await db.execute(select(func.count()).select_from(q.subquery()))
    ).scalar_one()
    items = (
        (
            await db.execute(
                q.order_by(MonitoringSchedule.next_review_date.asc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .scalars()
        .all()
    )

    return PaginatedMonitoringSchedules(
        total=total, page=page, page_size=page_size, items=items
    )


# ── GET /monitoring/history ───────────────────────────────────────────────────
@router.get("/history", response_model=PaginatedMonitoringHistory)
async def list_monitoring_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    customer_id: Optional[UUID] = Query(None),
    current_user: User = Depends(verify_compliance_officer),
    db: AsyncSession = Depends(get_db),
):
    """Fetch history logs of re-screening executions."""
    await ensure_phase11_schema(db)

    q = select(MonitoringHistory)
    if customer_id:
        q = q.where(MonitoringHistory.customer_id == customer_id)

    total = (
        await db.execute(select(func.count()).select_from(q.subquery()))
    ).scalar_one()
    items = (
        (
            await db.execute(
                q.order_by(MonitoringHistory.screening_date.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .scalars()
        .all()
    )

    return PaginatedMonitoringHistory(
        total=total, page=page, page_size=page_size, items=items
    )


# ── GET /monitoring/jobs ──────────────────────────────────────────────────────
@router.get("/jobs", response_model=PaginatedMonitoringJobs)
async def list_monitoring_jobs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    current_user: User = Depends(verify_compliance_officer),
    db: AsyncSession = Depends(get_db),
):
    """Fetch queued, running, completed, or failed background jobs."""
    await ensure_phase11_schema(db)

    q = select(MonitoringJob)
    if status:
        q = q.where(MonitoringJob.status == status)

    total = (
        await db.execute(select(func.count()).select_from(q.subquery()))
    ).scalar_one()
    items = (
        (
            await db.execute(
                q.order_by(MonitoringJob.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .scalars()
        .all()
    )

    return PaginatedMonitoringJobs(
        total=total, page=page, page_size=page_size, items=items
    )


# ── POST /monitoring/run/{customer_id} ───────────────────────────────────────
@router.post(
    "/run/{customer_id}", response_model=MonitoringJobResponse, status_code=202
)
async def trigger_manual_rescreen(
    customer_id: UUID,
    request: Request,
    current_user: User = Depends(verify_compliance_officer),
    db: AsyncSession = Depends(get_db),
):
    """Trigger manual re-screening and run LangGraph compliance pipeline in background."""
    await ensure_phase11_schema(db)

    res = await db.execute(select(Customer).where(Customer.id == customer_id))
    customer = res.scalars().first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found.")

    # Detect duplicate queued/running jobs
    job = await MonitoringService.detect_and_trigger_rescreen(
        db, customer_id, "manual_rescreen"
    )
    if job.status == "queued":
        # Dispatch Celery background worker
        run_monitoring_screening_task.delay(
            str(job.id), str(customer_id), "manual_rescreen"
        )

        await AuditService.log(
            db=db,
            user_id=current_user.id,
            action="TRIGGER_MANUAL_RESCREEN",
            entity_name="monitoring_job",
            entity_id=job.id,
            new_values={"customer_id": str(customer_id), "trigger": "manual"},
            ip_address=_get_client_ip(request),
        )
        await db.commit()

    return job


# ── POST /monitoring/retry/{job_id} ──────────────────────────────────────────
@router.post("/retry/{job_id}", status_code=200)
async def retry_failed_job(
    job_id: UUID,
    request: Request,
    current_user: User = Depends(verify_compliance_officer),
    db: AsyncSession = Depends(get_db),
):
    """Retry a failed screening job."""
    await ensure_phase11_schema(db)

    res = await db.execute(select(MonitoringJob).where(MonitoringJob.id == job_id))
    job = res.scalars().first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    if job.status != "failed":
        raise HTTPException(status_code=400, detail="Only failed jobs can be retried.")

    success = await MonitoringService.retry_job(db, job_id)
    if success:
        # Dispatch Celery task
        run_monitoring_screening_task.delay(
            str(job.id), str(job.customer_id), job.trigger_reason
        )

        await AuditService.log(
            db=db,
            user_id=current_user.id,
            action="RETRY_MONITORING_JOB",
            entity_name="monitoring_job",
            entity_id=job_id,
            ip_address=_get_client_ip(request),
        )
        return {"status": "success", "message": "Failed job dispatched for retry."}

    return {"status": "error", "message": "Could not retry job."}


# ── POST /monitoring/cancel/{job_id} ─────────────────────────────────────────
@router.post("/cancel/{job_id}", status_code=200)
async def cancel_job(
    job_id: UUID,
    request: Request,
    current_user: User = Depends(verify_compliance_officer),
    db: AsyncSession = Depends(get_db),
):
    """Cancel a queued or running job."""
    await ensure_phase11_schema(db)

    res = await db.execute(select(MonitoringJob).where(MonitoringJob.id == job_id))
    job = res.scalars().first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    success = await MonitoringService.cancel_job(db, job_id)
    if success:
        await AuditService.log(
            db=db,
            user_id=current_user.id,
            action="CANCEL_MONITORING_JOB",
            entity_name="monitoring_job",
            entity_id=job_id,
            ip_address=_get_client_ip(request),
        )
        return {"status": "success", "message": "Job cancelled successfully."}

    raise HTTPException(status_code=400, detail="Cannot cancel job in current state.")


# ── GET /monitoring/reviews ───────────────────────────────────────────────────
@router.get("/reviews", response_model=PaginatedMonitoringSchedules)
async def list_pending_reviews(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(verify_compliance_officer),
    db: AsyncSession = Depends(get_db),
):
    """Fetch overdue and immediate review targets."""
    await ensure_phase11_schema(db)

    q = select(MonitoringSchedule).where(
        and_(
            MonitoringSchedule.next_review_date <= func.current_date(),
            MonitoringSchedule.status == "scheduled",
        )
    )

    total = (
        await db.execute(select(func.count()).select_from(q.subquery()))
    ).scalar_one()
    items = (
        (
            await db.execute(
                q.order_by(MonitoringSchedule.next_review_date.asc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .scalars()
        .all()
    )

    return PaginatedMonitoringSchedules(
        total=total, page=page, page_size=page_size, items=items
    )


# ── GET /monitoring/statistics ────────────────────────────────────────────────
@router.get("/statistics", response_model=MonitoringStatistics)
async def get_monitoring_stats(
    current_user: User = Depends(verify_compliance_officer),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve aggregations for widgets dashboard views."""
    return await MonitoringService.get_statistics(db)


# ── GET /monitoring/risk-delta/{customer_id} ──────────────────────────────────
@router.get("/risk-delta/{customer_id}", response_model=RiskDeltaResponse)
async def get_risk_delta(
    customer_id: UUID,
    current_user: User = Depends(verify_compliance_officer),
    db: AsyncSession = Depends(get_db),
):
    """Calculate and return score trends for the client."""
    await ensure_phase11_schema(db)

    # Fetch 2 latest risk scores
    scores_res = await db.execute(
        select(RiskScore)
        .where(RiskScore.customer_id == customer_id)
        .order_by(desc(RiskScore.created_at))
        .limit(2)
    )
    scores = scores_res.scalars().all()

    if not scores:
        raise HTTPException(
            status_code=404, detail="No risk score history found for customer."
        )

    latest_score = float(scores[0].overall_score)
    previous_score = float(scores[1].overall_score) if len(scores) > 1 else latest_score
    delta = latest_score - previous_score

    if delta > 5.0:
        trend = "deteriorating"
    elif delta < -5.0:
        trend = "improving"
    else:
        trend = "stable"

    # Query Alerts count for latest case
    new_alerts = 0
    case_res = await db.execute(
        select(Case)
        .where(Case.customer_id == customer_id)
        .order_by(desc(Case.created_at))
        .limit(1)
    )
    latest_case = case_res.scalars().first()
    if latest_case:
        alerts_res = await db.execute(
            select(func.count(Alert.id)).where(Alert.case_id == latest_case.id)
        )
        new_alerts = alerts_res.scalar_one() or 0

    return RiskDeltaResponse(
        customer_id=customer_id,
        latest_score=latest_score,
        previous_score=previous_score,
        delta=delta,
        risk_trend=trend,
        new_alerts_count=new_alerts,
    )
