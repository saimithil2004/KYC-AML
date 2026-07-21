"""
Screening (Re-screening) API — Phase 8
========================================
POST /screening/{customer_id}/run — triggers a full OrchestratorAgent screening
for the customer and returns the results immediately.

Also exposes:
  GET /screening/{customer_id}/status — latest risk score + case info
  GET /screening/{customer_id}/history — all historical risk scores
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.database import get_db
from app.dependencies.auth import get_current_user, verify_compliance_officer
from app.models.models import Case, Customer, RiskScore, User
from app.schemas.schemas import RescreeningResponse
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)
router = APIRouter()


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    return forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "unknown")


# ── POST /screening/{customer_id}/run ─────────────────────────────────────────

@router.post("/{customer_id}/run", response_model=RescreeningResponse)
async def run_screening(
    customer_id: UUID,
    request: Request,
    current_user: User = Depends(verify_compliance_officer),
    db: AsyncSession = Depends(get_db),
):
    """
    Trigger a full AML/KYC compliance re-screening for a customer.
    Runs all 16 AI agents via OrchestratorAgent, updates risk score,
    creates/updates alerts and cases, and returns results.
    """
    # Verify customer exists
    result = await db.execute(select(Customer).where(Customer.id == customer_id))
    customer = result.scalars().first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found.")

    # Audit: log rescreening initiation
    await AuditService.log(
        db=db,
        user_id=current_user.id,
        action="INITIATE_RESCREENING",
        entity_name="customer",
        entity_id=customer_id,
        new_values={"initiated_by": current_user.email},
        ip_address=_get_client_ip(request),
        reason="Manual re-screening triggered by compliance officer",
    )
    await db.commit()

    # Run screening (synchronous call — ScreeningService handles async internally)
    try:
        from app.services.screening_service import ScreeningService
        screening_result = await ScreeningService.run_screening_async(str(customer_id))

        # Audit: log result
        await AuditService.log(
            db=db,
            user_id=current_user.id,
            action="RESCREENING_COMPLETE",
            entity_name="customer",
            entity_id=customer_id,
            new_values={
                "score": screening_result.get("score"),
                "tier": screening_result.get("tier"),
                "decision": screening_result.get("decision"),
            },
            ip_address=_get_client_ip(request),
        )
        await db.commit()

        return RescreeningResponse(
            status="completed",
            customer_id=str(customer_id),
            case_id=screening_result.get("case_id"),
            score=screening_result.get("score"),
            tier=screening_result.get("tier"),
            decision=screening_result.get("decision"),
            message=f"Re-screening complete. Decision: {screening_result.get('decision')}. Score: {screening_result.get('score', 0):.1f}/100.",
        )

    except Exception as exc:
        logger.error(f"Re-screening failed for customer {customer_id}: {exc}")
        raise HTTPException(
            status_code=500,
            detail=f"Re-screening failed: {str(exc)[:200]}",
        )


# ── GET /screening/{customer_id}/status ───────────────────────────────────────

@router.get("/{customer_id}/status")
async def get_screening_status(
    customer_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the latest risk score and open case for a customer."""
    # RBAC
    if current_user.role == "customer":
        result = await db.execute(select(Customer).where(Customer.id == customer_id))
        customer = result.scalars().first()
        if not customer or customer.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized.")

    # Latest risk score
    risk_result = await db.execute(
        select(RiskScore)
        .where(RiskScore.customer_id == customer_id)
        .order_by(RiskScore.created_at.desc())
        .limit(1)
    )
    risk = risk_result.scalars().first()

    # Latest case
    case_result = await db.execute(
        select(Case)
        .where(Case.customer_id == customer_id)
        .order_by(Case.created_at.desc())
        .limit(1)
    )
    case = case_result.scalars().first()

    return {
        "customer_id": str(customer_id),
        "risk_score": {
            "overall_score": float(risk.overall_score),
            "risk_tier": risk.risk_tier,
            "breakdown": risk.breakdown,
            "assessed_at": risk.created_at.isoformat(),
        } if risk else None,
        "latest_case": {
            "id": str(case.id),
            "status": case.status,
            "priority": case.priority,
            "sar_filed": case.sar_filed,
            "created_at": case.created_at.isoformat(),
        } if case else None,
    }


# ── GET /screening/{customer_id}/history ─────────────────────────────────────

@router.get("/{customer_id}/history")
async def get_screening_history(
    customer_id: UUID,
    current_user: User = Depends(verify_compliance_officer),
    db: AsyncSession = Depends(get_db),
):
    """Get all historical risk scores for a customer."""
    result = await db.execute(
        select(RiskScore)
        .where(RiskScore.customer_id == customer_id)
        .order_by(RiskScore.created_at.desc())
    )
    scores = result.scalars().all()

    return {
        "customer_id": str(customer_id),
        "total": len(scores),
        "history": [
            {
                "id": str(r.id),
                "overall_score": float(r.overall_score),
                "risk_tier": r.risk_tier,
                "breakdown": r.breakdown,
                "created_at": r.created_at.isoformat(),
            }
            for r in scores
        ],
    }
