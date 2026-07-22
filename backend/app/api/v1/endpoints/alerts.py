"""
Alerts API — Phase 8
=====================
Full CRUD for AML alerts with filtering, pagination, and audit logging.
Compliance officers can triage, escalate, dismiss, and close alerts.
"""

import logging
from datetime import datetime, date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.database import get_db
from app.dependencies.auth import get_current_user, verify_compliance_officer
from app.models.models import Alert, Customer, User
from app.schemas.schemas import (
    AlertCreate,
    AlertUpdate,
    AlertResponse,
    PaginatedAlerts,
)
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)
router = APIRouter()

VALID_STATUSES = {"open", "under_review", "dismissed", "escalated", "closed"}


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    return (
        forwarded.split(",")[0].strip()
        if forwarded
        else (request.client.host if request.client else "unknown")
    )


# ── GET /alerts ───────────────────────────────────────────────────────────────


@router.get("/", response_model=PaginatedAlerts)
async def list_alerts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    customer_id: Optional[UUID] = Query(None),
    status: Optional[str] = Query(None),
    alert_type: Optional[str] = Query(None),
    min_risk_score: Optional[float] = Query(None),
    max_risk_score: Optional[float] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    search: Optional[str] = Query(None),
    sort_by: str = Query("created_at"),
    sort_dir: str = Query("desc"),
    current_user: User = Depends(verify_compliance_officer),
    db: AsyncSession = Depends(get_db),
):
    q = select(Alert)

    if customer_id:
        q = q.where(Alert.customer_id == customer_id)
    if status:
        q = q.where(Alert.status == status)
    if alert_type:
        q = q.where(Alert.alert_type == alert_type)
    if min_risk_score is not None:
        q = q.where(Alert.risk_score >= min_risk_score)
    if max_risk_score is not None:
        q = q.where(Alert.risk_score <= max_risk_score)
    if date_from:
        q = q.where(
            Alert.created_at >= datetime.combine(date_from, datetime.min.time())
        )
    if date_to:
        q = q.where(Alert.created_at <= datetime.combine(date_to, datetime.max.time()))

    total = (
        await db.execute(select(func.count()).select_from(q.subquery()))
    ).scalar_one()

    sort_col = getattr(Alert, sort_by, Alert.created_at)
    q = q.order_by(sort_col.asc() if sort_dir == "asc" else sort_col.desc())
    q = q.offset((page - 1) * page_size).limit(page_size)
    items = (await db.execute(q)).scalars().all()

    return PaginatedAlerts(total=total, page=page, page_size=page_size, items=items)


# ── GET /alerts/{id} ─────────────────────────────────────────────────────────


@router.get("/{alert_id}", response_model=AlertResponse)
async def get_alert(
    alert_id: UUID,
    current_user: User = Depends(verify_compliance_officer),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalars().first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found.")
    return alert


# ── POST /alerts ──────────────────────────────────────────────────────────────


@router.post("/", response_model=AlertResponse, status_code=201)
async def create_alert(
    alert_in: AlertCreate,
    request: Request,
    current_user: User = Depends(verify_compliance_officer),
    db: AsyncSession = Depends(get_db),
):
    # Verify customer exists
    result = await db.execute(
        select(Customer).where(Customer.id == alert_in.customer_id)
    )
    if not result.scalars().first():
        raise HTTPException(status_code=404, detail="Customer not found.")

    alert = Alert(
        customer_id=alert_in.customer_id,
        transaction_id=alert_in.transaction_id,
        alert_type=alert_in.alert_type,
        risk_score=alert_in.risk_score,
        status=alert_in.status,
        alert_metadata=alert_in.alert_metadata or {},
    )
    db.add(alert)
    await db.flush()

    await AuditService.log(
        db=db,
        user_id=current_user.id,
        action="CREATE_ALERT",
        entity_name="alert",
        entity_id=alert.id,
        new_values={
            "alert_type": alert_in.alert_type,
            "risk_score": alert_in.risk_score,
            "status": alert_in.status,
        },
        ip_address=_get_client_ip(request),
    )

    await db.commit()
    await db.refresh(alert)
    return alert


# ── PUT /alerts/{id} ─────────────────────────────────────────────────────────


@router.put("/{alert_id}", response_model=AlertResponse)
async def update_alert(
    alert_id: UUID,
    alert_in: AlertUpdate,
    request: Request,
    current_user: User = Depends(verify_compliance_officer),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalars().first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found.")

    if alert_in.status and alert_in.status not in VALID_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Must be one of: {', '.join(VALID_STATUSES)}",
        )

    old_values = {"status": alert.status}
    update_data = alert_in.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(alert, field, value)
    alert.updated_at = datetime.utcnow()

    await AuditService.log(
        db=db,
        user_id=current_user.id,
        action="UPDATE_ALERT",
        entity_name="alert",
        entity_id=alert.id,
        old_values=old_values,
        new_values=update_data,
        ip_address=_get_client_ip(request),
    )

    await db.commit()
    await db.refresh(alert)
    return alert


# ── DELETE /alerts/{id} ───────────────────────────────────────────────────────


@router.delete("/{alert_id}", status_code=204)
async def delete_alert(
    alert_id: UUID,
    request: Request,
    current_user: User = Depends(verify_compliance_officer),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalars().first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found.")

    await AuditService.log(
        db=db,
        user_id=current_user.id,
        action="DELETE_ALERT",
        entity_name="alert",
        entity_id=alert.id,
        old_values={"alert_type": alert.alert_type, "status": alert.status},
        ip_address=_get_client_ip(request),
    )

    await db.delete(alert)
    await db.commit()
    return None


# ── GET /alerts/customer/{customer_id} ────────────────────────────────────────


@router.get("/customer/{customer_id}", response_model=PaginatedAlerts)
async def get_customer_alerts(
    customer_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    current_user: User = Depends(verify_compliance_officer),
    db: AsyncSession = Depends(get_db),
):
    q = select(Alert).where(Alert.customer_id == customer_id)
    if status:
        q = q.where(Alert.status == status)

    total = (
        await db.execute(select(func.count()).select_from(q.subquery()))
    ).scalar_one()
    items = (
        (
            await db.execute(
                q.order_by(Alert.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .scalars()
        .all()
    )

    return PaginatedAlerts(total=total, page=page, page_size=page_size, items=items)
