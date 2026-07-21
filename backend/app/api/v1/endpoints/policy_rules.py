"""
Policy Rules CRUD API — Phase 10
================================
Supports manual creation, updating, disabling/enabling,
archiving, and deletion of custom PolicyRules.
Only accessible to compliance officers and admins.
"""

import logging
from typing import Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.schema_helpers import ensure_phase10_schema
from app.dependencies.auth import get_current_user, verify_compliance_officer, verify_admin
from app.models.models import User, PolicyRule, Regulation
from app.schemas.schemas import PolicyRuleResponse, PaginatedPolicyRules, PolicyRuleCreate, PolicyRuleUpdate
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)
router = APIRouter()


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    return forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "unknown")


# ── GET /policy-rules ─────────────────────────────────────────────────────────

@router.get("/", response_model=PaginatedPolicyRules)
async def list_policy_rules(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    rule_type: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    country: Optional[str] = Query(None),
    current_user: User = Depends(verify_compliance_officer),
    db: AsyncSession = Depends(get_db),
):
    """List policy rules with pagination and filters."""
    await ensure_phase10_schema(db)
    
    q = select(PolicyRule)
    if rule_type:
        q = q.where(PolicyRule.rule_type == rule_type)
    if is_active is not None:
        q = q.where(PolicyRule.is_active == is_active)
    if country:
        q = q.where(PolicyRule.country == country)

    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
    items = (await db.execute(
        q.order_by(PolicyRule.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()

    return PaginatedPolicyRules(total=total, page=page, page_size=page_size, items=items)


# ── POST /policy-rules ────────────────────────────────────────────────────────

@router.post("/", response_model=PolicyRuleResponse, status_code=201)
async def create_policy_rule(
    rule_in: PolicyRuleCreate,
    request: Request,
    current_user: User = Depends(verify_admin),  # Only admin can create manually
    db: AsyncSession = Depends(get_db),
):
    """Creates a custom policy rule manually."""
    await ensure_phase10_schema(db)

    # Verify source regulation exists
    reg_result = await db.execute(select(Regulation).where(Regulation.id == rule_in.regulation_id))
    regulation = reg_result.scalars().first()
    if not regulation:
        raise HTTPException(
            status_code=404,
            detail=f"Source regulation {rule_in.regulation_id} not found."
        )

    rule = PolicyRule(
        id=uuid4(),
        regulation_id=rule_in.regulation_id,
        rule_name=rule_in.rule_name,
        rule_type=rule_in.rule_type,
        conditions=rule_in.conditions,
        is_active=True,
        severity=rule_in.severity,
        description=rule_in.description,
        expression=rule_in.expression,
        threshold=rule_in.threshold,
        country=rule_in.country or regulation.country,
        version=rule_in.version
    )
    db.add(rule)
    await db.flush()

    await AuditService.log(
        db=db,
        user_id=current_user.id,
        action="CREATE_POLICY_RULE",
        entity_name="policy_rule",
        entity_id=rule.id,
        new_values=rule_in.model_dump(),
        ip_address=_get_client_ip(request),
    )

    await db.commit()
    await db.refresh(rule)
    return rule


# ── PUT /policy-rules/{id} ────────────────────────────────────────────────────

@router.put("/{rule_id}", response_model=PolicyRuleResponse)
async def update_policy_rule(
    rule_id: UUID,
    rule_in: PolicyRuleUpdate,
    request: Request,
    current_user: User = Depends(verify_admin),  # Only admin can edit policy rules
    db: AsyncSession = Depends(get_db),
):
    """Updates fields or toggles active status of a policy rule."""
    await ensure_phase10_schema(db)

    result = await db.execute(select(PolicyRule).where(PolicyRule.id == rule_id))
    rule = result.scalars().first()
    if not rule:
        raise HTTPException(status_code=404, detail="Policy rule not found.")

    old_values = {
        "rule_name": rule.rule_name,
        "is_active": rule.is_active,
        "conditions": rule.conditions,
    }
    update_data = rule_in.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(rule, field, value)

    await AuditService.log(
        db=db,
        user_id=current_user.id,
        action="UPDATE_POLICY_RULE",
        entity_name="policy_rule",
        entity_id=rule_id,
        old_values=old_values,
        new_values=update_data,
        ip_address=_get_client_ip(request),
    )

    await db.commit()
    await db.refresh(rule)
    return rule


# ── DELETE /policy-rules/{id} ─────────────────────────────────────────────────

@router.delete("/{rule_id}", status_code=204)
async def delete_policy_rule(
    rule_id: UUID,
    request: Request,
    current_user: User = Depends(verify_admin),  # Only admin can delete policy rules
    db: AsyncSession = Depends(get_db),
):
    await ensure_phase10_schema(db)

    result = await db.execute(select(PolicyRule).where(PolicyRule.id == rule_id))
    rule = result.scalars().first()
    if not rule:
        raise HTTPException(status_code=404, detail="Policy rule not found.")

    await AuditService.log(
        db=db,
        user_id=current_user.id,
        action="DELETE_POLICY_RULE",
        entity_name="policy_rule",
        entity_id=rule_id,
        old_values={"rule_name": rule.rule_name},
        ip_address=_get_client_ip(request),
    )

    await db.delete(rule)
    await db.commit()
    return None
