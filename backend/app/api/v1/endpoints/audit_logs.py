"""
Audit Logs API — Phase 8
=========================
Read-only access to audit log entries for compliance officers and admins.
Supports pagination and filtering by user, entity, action, and date range.
"""

import logging
from datetime import datetime, date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.database import get_db
from app.dependencies.auth import verify_compliance_officer
from app.models.models import AuditLog, User
from app.schemas.schemas import AuditLogResponse, PaginatedAuditLogs

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/", response_model=PaginatedAuditLogs)
async def list_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
    user_id: Optional[UUID] = Query(None),
    action: Optional[str] = Query(None),
    entity_name: Optional[str] = Query(None),
    entity_id: Optional[UUID] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    current_user: User = Depends(verify_compliance_officer),
    db: AsyncSession = Depends(get_db),
):
    q = select(AuditLog)

    if user_id:
        q = q.where(AuditLog.user_id == user_id)
    if action:
        q = q.where(AuditLog.action.ilike(f"%{action}%"))
    if entity_name:
        q = q.where(AuditLog.entity_name == entity_name)
    if entity_id:
        q = q.where(AuditLog.entity_id == entity_id)
    if date_from:
        q = q.where(AuditLog.created_at >= datetime.combine(date_from, datetime.min.time()))
    if date_to:
        q = q.where(AuditLog.created_at <= datetime.combine(date_to, datetime.max.time()))

    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
    q = q.order_by(AuditLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    items = (await db.execute(q)).scalars().all()

    return PaginatedAuditLogs(total=total, page=page, page_size=page_size, items=items)


@router.get("/{entity_name}/{entity_id}", response_model=PaginatedAuditLogs)
async def get_entity_audit_trail(
    entity_name: str,
    entity_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(verify_compliance_officer),
    db: AsyncSession = Depends(get_db),
):
    """Get the full audit trail for a specific entity (e.g. case, alert, transaction)."""
    q = select(AuditLog).where(
        AuditLog.entity_name == entity_name,
        AuditLog.entity_id == entity_id,
    )
    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
    items = (await db.execute(
        q.order_by(AuditLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()

    return PaginatedAuditLogs(total=total, page=page, page_size=page_size, items=items)
