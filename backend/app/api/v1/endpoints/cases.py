"""
Cases API — Phase 8
====================
Full CRUD for investigation cases.
Supports:
  - Create / list / get / update / delete cases
  - POST /cases/{id}/decision — record compliance officer decision
  - GET /cases/{id}/full — full case view (customer + KYC + alerts + risk + agents)
  - Audit logging on every mutation
"""

import logging
from datetime import datetime, date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.database import get_db
from app.dependencies.auth import get_current_user, verify_compliance_officer
from app.models.models import (
    AgentLog,
    Alert,
    Case,
    Customer,
    Document,
    KYCProfile,
    RiskScore,
    User,
)
from app.schemas.schemas import (
    CaseCreate,
    CaseDecision,
    CaseResponse,
    CaseUpdate,
    PaginatedCases,
)
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)
router = APIRouter()


def _flatten_breakdown(raw: dict | None) -> dict:
    """
    Normalise the risk breakdown dict.
    The risk agent stores each signal as {weight, agent_score, contribution}.
    `contribution` is already in 0–100 point space (weights sum to 100),
    so it is returned directly without further scaling.
    Plain floats are returned as-is.
    """
    if not raw:
        return {}
    result: dict = {}
    for key, val in raw.items():
        if isinstance(val, dict):
            result[key] = round(float(val.get("contribution", 0)), 1)
        elif val is not None:
            result[key] = float(val)
        else:
            result[key] = 0.0
    return result


VALID_STATUSES = {
    "open",
    "under_review",
    "waiting_info",
    "escalated",
    "approved",
    "rejected",
    "closed",
    "investigating",
    "new",
}
VALID_DECISIONS = {"APPROVE", "REJECT", "EDD_REQUIRED", "MANUAL_REVIEW"}


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    return (
        forwarded.split(",")[0].strip()
        if forwarded
        else (request.client.host if request.client else "unknown")
    )


# ── GET /cases ────────────────────────────────────────────────────────────────


@router.get("/", response_model=PaginatedCases)
async def list_cases(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    customer_id: Optional[UUID] = Query(None),
    status: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    assigned_to: Optional[UUID] = Query(None),
    sar_filed: Optional[bool] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    sort_by: str = Query("created_at"),
    sort_dir: str = Query("desc"),
    current_user: User = Depends(verify_compliance_officer),
    db: AsyncSession = Depends(get_db),
):
    q = select(Case)

    if customer_id:
        q = q.where(Case.customer_id == customer_id)
    if status:
        q = q.where(Case.status == status)
    if priority:
        q = q.where(Case.priority == priority)
    if assigned_to:
        q = q.where(Case.assigned_to == assigned_to)
    if sar_filed is not None:
        q = q.where(Case.sar_filed == sar_filed)
    if date_from:
        q = q.where(Case.created_at >= datetime.combine(date_from, datetime.min.time()))
    if date_to:
        q = q.where(Case.created_at <= datetime.combine(date_to, datetime.max.time()))

    total = (
        await db.execute(select(func.count()).select_from(q.subquery()))
    ).scalar_one()

    sort_col = getattr(Case, sort_by, Case.created_at)
    q = q.order_by(sort_col.asc() if sort_dir == "asc" else sort_col.desc())
    q = q.offset((page - 1) * page_size).limit(page_size)
    items = (await db.execute(q)).scalars().all()

    return PaginatedCases(total=total, page=page, page_size=page_size, items=items)


# ── GET /cases/customer/{customer_id} ────────────────────────────────────────


@router.get("/customer/{customer_id}", response_model=list[CaseResponse])
async def get_cases_by_customer(
    customer_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Return all cases for a given customer.
    Customers may only retrieve their own cases; compliance officers
    and admins may access any customer's cases.
    """
    if current_user.role == "customer":
        # Verify the requesting customer owns this customer_id
        cust_result = await db.execute(
            select(Customer).where(Customer.user_id == current_user.id)
        )
        customer = cust_result.scalars().first()
        if not customer or customer.id != customer_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorised to view cases for this customer.",
            )

    cases_result = await db.execute(
        select(Case)
        .where(Case.customer_id == customer_id)
        .order_by(Case.created_at.desc())
        .limit(25)
    )
    return cases_result.scalars().all()


# ── GET /cases/{id} ───────────────────────────────────────────────────────────


@router.get("/{case_id}", response_model=CaseResponse)
async def get_case(
    case_id: UUID,
    current_user: User = Depends(verify_compliance_officer),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Case).where(Case.id == case_id))
    case = result.scalars().first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found.")
    return case


# ── GET /cases/{id}/full ──────────────────────────────────────────────────────


@router.get("/{case_id}/full")
async def get_case_full(
    case_id: UUID,
    current_user: User = Depends(verify_compliance_officer),
    db: AsyncSession = Depends(get_db),
):
    """
    Full case view for compliance officer — returns:
    - Case details
    - Customer profile
    - KYC profile
    - Documents
    - Risk scores
    - Alerts
    - Agent logs
    """
    result = await db.execute(select(Case).where(Case.id == case_id))
    case = result.scalars().first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found.")

    # Customer
    cust_result = await db.execute(
        select(Customer).where(Customer.id == case.customer_id)
    )
    customer = cust_result.scalars().first()

    # KYC
    kyc_result = await db.execute(
        select(KYCProfile).where(KYCProfile.customer_id == case.customer_id)
    )
    kyc = kyc_result.scalars().first()

    # Documents
    doc_result = await db.execute(
        select(Document).where(Document.customer_id == case.customer_id)
    )
    documents = doc_result.scalars().all()

    # Risk Scores (latest 3)
    risk_result = await db.execute(
        select(RiskScore)
        .where(RiskScore.customer_id == case.customer_id)
        .order_by(RiskScore.created_at.desc())
        .limit(3)
    )
    risk_scores = risk_result.scalars().all()

    # Alerts
    alert_result = await db.execute(
        select(Alert)
        .where(Alert.customer_id == case.customer_id)
        .order_by(Alert.created_at.desc())
        .limit(20)
    )
    alerts = alert_result.scalars().all()

    # Agent logs
    agent_log_result = await db.execute(
        select(AgentLog)
        .where(AgentLog.case_id == case.id)
        .order_by(AgentLog.created_at.asc())
    )
    agent_logs = agent_log_result.scalars().all()

    return {
        "case": {
            "id": str(case.id),
            "customer_id": str(case.customer_id),
            "assigned_to": str(case.assigned_to) if case.assigned_to else None,
            "priority": case.priority,
            "status": case.status,
            "investigation_notes": case.investigation_notes,
            "sar_filed": case.sar_filed,
            "created_at": case.created_at.isoformat(),
            "updated_at": case.updated_at.isoformat(),
        },
        "customer": (
            {
                "id": str(customer.id),
                "customer_type": customer.customer_type,
                "first_name": customer.first_name,
                "last_name": customer.last_name,
                "nationality": customer.nationality,
                "country": customer.country,
                "status": customer.status,
            }
            if customer
            else None
        ),
        "kyc_profile": (
            {
                "full_name": kyc.full_name,
                "date_of_birth": (
                    kyc.date_of_birth.isoformat() if kyc.date_of_birth else None
                ),
                "nationality": kyc.nationality,
                "address": kyc.address,
                "source_of_funds": kyc.source_of_funds,
                "source_of_wealth": kyc.source_of_wealth,
                "occupation": kyc.occupation,
                "risk_category": kyc.risk_category,
                "annual_income_range": kyc.annual_income_range,
                "tax_residency": kyc.tax_residency,
            }
            if kyc
            else None
        ),
        "documents": [
            {
                "id": str(d.id),
                "document_type": d.document_type,
                "file_name": d.file_name,
                "verification_status": d.verification_status,
                "created_at": d.created_at.isoformat(),
            }
            for d in documents
        ],
        "risk_scores": [
            {
                "id": str(r.id),
                "overall_score": float(r.overall_score),
                "risk_tier": r.risk_tier,
                "breakdown": _flatten_breakdown(r.breakdown),
                "created_at": r.created_at.isoformat(),
            }
            for r in risk_scores
        ],
        "alerts": [
            {
                "id": str(a.id),
                "alert_type": a.alert_type,
                "risk_score": float(a.risk_score),
                "status": a.status,
                "alert_metadata": a.alert_metadata,
                "created_at": a.created_at.isoformat(),
            }
            for a in alerts
        ],
        "agent_logs": [
            {
                "agent_name": l.agent_name,
                "step_name": l.step_name,
                "output_state": l.output_state,
                "execution_time_ms": l.execution_time_ms,
                "created_at": l.created_at.isoformat(),
            }
            for l in agent_logs
        ],
    }


# ── POST /cases ───────────────────────────────────────────────────────────────


@router.post("/", response_model=CaseResponse, status_code=201)
async def create_case(
    case_in: CaseCreate,
    request: Request,
    current_user: User = Depends(verify_compliance_officer),
    db: AsyncSession = Depends(get_db),
):
    # Verify customer exists
    result = await db.execute(
        select(Customer).where(Customer.id == case_in.customer_id)
    )
    if not result.scalars().first():
        raise HTTPException(status_code=404, detail="Customer not found.")

    case = Case(
        customer_id=case_in.customer_id,
        priority=case_in.priority,
        status=case_in.status,
        investigation_notes=case_in.investigation_notes,
        assigned_to=case_in.assigned_to or current_user.id,
        sar_filed=False,
    )
    db.add(case)
    await db.flush()

    await AuditService.log(
        db=db,
        user_id=current_user.id,
        action="CREATE_CASE",
        entity_name="case",
        entity_id=case.id,
        new_values={
            "customer_id": str(case_in.customer_id),
            "priority": case_in.priority,
            "status": case_in.status,
        },
        ip_address=_get_client_ip(request),
    )

    await db.commit()
    await db.refresh(case)
    return case


# ── PUT /cases/{id} ───────────────────────────────────────────────────────────


@router.put("/{case_id}", response_model=CaseResponse)
async def update_case(
    case_id: UUID,
    case_in: CaseUpdate,
    request: Request,
    current_user: User = Depends(verify_compliance_officer),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Case).where(Case.id == case_id))
    case = result.scalars().first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found.")

    if case_in.status and case_in.status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status.")

    old_values = {
        "status": case.status,
        "priority": case.priority,
        "investigation_notes": (case.investigation_notes or "")[:100],
    }

    update_data = case_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(case, field, value)
    case.updated_at = datetime.utcnow()

    await AuditService.log(
        db=db,
        user_id=current_user.id,
        action="UPDATE_CASE",
        entity_name="case",
        entity_id=case.id,
        old_values=old_values,
        new_values=update_data,
        ip_address=_get_client_ip(request),
    )

    await db.commit()
    await db.refresh(case)
    return case


# ── POST /cases/{id}/decision ─────────────────────────────────────────────────


@router.post("/{case_id}/decision", response_model=CaseResponse)
async def record_case_decision(
    case_id: UUID,
    decision_in: CaseDecision,
    request: Request,
    current_user: User = Depends(verify_compliance_officer),
    db: AsyncSession = Depends(get_db),
):
    """
    Record a compliance officer's decision on a case.
    Decision: APPROVE | REJECT | EDD_REQUIRED | MANUAL_REVIEW
    """
    if decision_in.decision not in VALID_DECISIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid decision. Must be one of: {', '.join(VALID_DECISIONS)}",
        )

    result = await db.execute(select(Case).where(Case.id == case_id))
    case = result.scalars().first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found.")

    old_status = case.status

    # Map decision to case status
    decision_to_status = {
        "APPROVE": "approved",
        "REJECT": "rejected",
        "EDD_REQUIRED": "under_review",
        "MANUAL_REVIEW": "under_review",
    }
    case.status = decision_to_status[decision_in.decision]

    # Append decision notes
    officer_email = current_user.email
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    note_block = (
        f"\n\n[DECISION — {timestamp}]\n"
        f"Officer: {officer_email}\n"
        f"Decision: {decision_in.decision}\n"
        f"Notes: {decision_in.notes}"
    )
    if decision_in.reason:
        note_block += f"\nReason: {decision_in.reason}"

    case.investigation_notes = (case.investigation_notes or "") + note_block

    if decision_in.sar_filed:
        case.sar_filed = True

    case.updated_at = datetime.utcnow()

    # Update customer status based on decision
    cust_result = await db.execute(
        select(Customer).where(Customer.id == case.customer_id)
    )
    customer = cust_result.scalars().first()
    if customer:
        if decision_in.decision == "APPROVE":
            customer.status = "approved"
        elif decision_in.decision == "REJECT":
            customer.status = "rejected"
        elif decision_in.decision == "EDD_REQUIRED":
            customer.status = "edd_required"

    await AuditService.log(
        db=db,
        user_id=current_user.id,
        action="CASE_DECISION",
        entity_name="case",
        entity_id=case.id,
        old_values={"status": old_status},
        new_values={
            "decision": decision_in.decision,
            "new_status": case.status,
            "sar_filed": decision_in.sar_filed,
            "notes_preview": decision_in.notes[:200],
        },
        ip_address=_get_client_ip(request),
        reason=decision_in.reason,
    )

    await db.commit()
    await db.refresh(case)
    return case


# ── DELETE /cases/{id} ────────────────────────────────────────────────────────


@router.delete("/{case_id}", status_code=204)
async def delete_case(
    case_id: UUID,
    request: Request,
    current_user: User = Depends(verify_compliance_officer),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Case).where(Case.id == case_id))
    case = result.scalars().first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found.")

    await AuditService.log(
        db=db,
        user_id=current_user.id,
        action="DELETE_CASE",
        entity_name="case",
        entity_id=case.id,
        old_values={"status": case.status, "priority": case.priority},
        ip_address=_get_client_ip(request),
    )

    await db.delete(case)
    await db.commit()
    return None
