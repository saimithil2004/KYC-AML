"""
Risk Scores API
===============
Exposes risk-score records for a customer.

  GET /risk-scores/customer/{customer_id}
      — return all historical risk scores for the customer, newest first.
        Customers may only access their own scores; compliance officers
        and admins may access any customer's scores.
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.models import Customer, RiskScore, User

logger = logging.getLogger(__name__)
router = APIRouter()


def _flatten_breakdown(raw: dict | None) -> dict:
    """
    Normalise the breakdown dict coming from the DB.

    The risk agent stores each signal as:
      {weight: float, agent_score: float, contribution: float}

    The frontend expects:
      {signal: float}   # risk point contribution 0–max_pts

    contribution × 100 converts the fractional weight contribution back to
    a points value (0–35 for sanctions, 0–25 for PEP, etc.).
    If the value is already a number it is returned as-is.
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


# ── GET /risk-scores/customer/{customer_id} ───────────────────────────────────


@router.get("/customer/{customer_id}")
async def get_risk_scores_by_customer(
    customer_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Return all risk scores for a given customer, newest first.
    Customers may only view their own risk scores.
    """
    if current_user.role == "customer":
        cust_result = await db.execute(
            select(Customer).where(Customer.user_id == current_user.id)
        )
        customer = cust_result.scalars().first()
        if not customer or customer.id != customer_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorised to view risk scores for this customer.",
            )

    scores_result = await db.execute(
        select(RiskScore)
        .where(RiskScore.customer_id == customer_id)
        .order_by(RiskScore.created_at.desc())
        .limit(25)
    )
    scores = scores_result.scalars().all()

    return [
        {
            "id": str(s.id),
            "customer_id": str(s.customer_id),
            "overall_score": float(s.overall_score),
            "risk_tier": s.risk_tier,
            "breakdown": _flatten_breakdown(s.breakdown),
            "created_at": s.created_at.isoformat(),
        }
        for s in scores
    ]
