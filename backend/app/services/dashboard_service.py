"""
Dashboard Service — Phase 9
============================
Aggregates all compliance metrics for the dashboard API.
Uses optimised SQLAlchemy queries (no N+1).
All queries run async against PostgreSQL.
"""

import logging
from datetime import datetime, timedelta, date
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import func, case, and_, or_, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.models import (
    Account,
    AgentLog,
    Alert,
    AuditLog,
    Case,
    Customer,
    Document,
    KYCProfile,
    MonitoringSchedule,
    RiskScore,
    Transaction,
    User,
    Regulation,
    PolicyRule,
)

logger = logging.getLogger(__name__)


class DashboardService:
    """Aggregated dashboard statistics service."""

    # ─────────────────────────────────────────────────────────────────────────
    # Overview KPIs
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    async def get_overview(db: AsyncSession) -> Dict[str, Any]:
        """Return all top-level KPI cards in a single pass."""
        # Ensure schema first
        from app.core.schema_helpers import ensure_phase10_schema

        await ensure_phase10_schema(db)

        today_start = datetime.combine(date.today(), datetime.min.time())
        today_end = datetime.combine(date.today(), datetime.max.time())

        # ── Customer counts ──────────────────────────────────────────────────
        cust_total = (await db.execute(select(func.count(Customer.id)))).scalar_one()

        cust_by_status = (
            await db.execute(
                select(Customer.status, func.count(Customer.id)).group_by(
                    Customer.status
                )
            )
        ).all()
        status_map = {s: c for s, c in cust_by_status}

        # ── KYC pending: customers without a completed KYC ───────────────────
        kyc_done_ids = select(KYCProfile.customer_id)
        pending_kyc = (
            await db.execute(
                select(func.count(Customer.id)).where(Customer.id.not_in(kyc_done_ids))
            )
        ).scalar_one()

        # ── Risk scores ──────────────────────────────────────────────────────
        # Latest risk score per customer using a subquery
        latest_risk_subq = (
            select(
                RiskScore.customer_id, func.max(RiskScore.created_at).label("latest_at")
            )
            .group_by(RiskScore.customer_id)
            .subquery()
        )
        risk_rows = (
            await db.execute(
                select(RiskScore.risk_tier, func.count(RiskScore.id))
                .join(
                    latest_risk_subq,
                    and_(
                        RiskScore.customer_id == latest_risk_subq.c.customer_id,
                        RiskScore.created_at == latest_risk_subq.c.latest_at,
                    ),
                )
                .group_by(RiskScore.risk_tier)
            )
        ).all()
        risk_tier_map = {tier: cnt for tier, cnt in risk_rows}

        avg_risk_row = (
            await db.execute(
                select(func.avg(RiskScore.overall_score).label("avg_score")).join(
                    latest_risk_subq,
                    and_(
                        RiskScore.customer_id == latest_risk_subq.c.customer_id,
                        RiskScore.created_at == latest_risk_subq.c.latest_at,
                    ),
                )
            )
        ).scalar_one()

        # ── Alert counts ──────────────────────────────────────────────────────
        alert_total = (await db.execute(select(func.count(Alert.id)))).scalar_one()
        open_alerts = (
            await db.execute(select(func.count(Alert.id)).where(Alert.status == "open"))
        ).scalar_one()

        # ── Case counts ───────────────────────────────────────────────────────
        open_cases = (
            await db.execute(
                select(func.count(Case.id)).where(
                    Case.status.in_(["open", "investigating", "under_review"])
                )
            )
        ).scalar_one()

        # ── Transactions today ────────────────────────────────────────────────
        txns_today = (
            await db.execute(
                select(func.count(Transaction.id)).where(
                    Transaction.created_at.between(today_start, today_end)
                )
            )
        ).scalar_one()

        # ── AI Screenings today (audit log entries) ───────────────────────────
        screenings_today = (
            await db.execute(
                select(func.count(AuditLog.id)).where(
                    AuditLog.action.in_(
                        ["INITIATE_RESCREENING", "RESCREENING_COMPLETE"]
                    ),
                    AuditLog.created_at.between(today_start, today_end),
                )
            )
        ).scalar_one()

        # ── Phase 10 Regulations & Policy Rules Statistics ────────────────────
        reg_total = 0
        reg_active = 0
        reg_pending = 0
        reg_latest_upload = None
        reg_latest_rule_update = None

        try:
            reg_total = (
                await db.execute(select(func.count(Regulation.id)))
            ).scalar_one()
            reg_active = (
                await db.execute(
                    select(func.count(Regulation.id)).where(
                        Regulation.status == "active"
                    )
                )
            ).scalar_one()
            reg_pending = (
                await db.execute(
                    select(func.count(Regulation.id)).where(
                        Regulation.status.in_(["pending_review", "draft"])
                    )
                )
            ).scalar_one()

            latest_up_row = (
                await db.execute(
                    select(Regulation.created_at)
                    .order_by(Regulation.created_at.desc())
                    .limit(1)
                )
            ).first()
            if latest_up_row:
                reg_latest_upload = latest_up_row[0].isoformat()

            latest_rule_row = (
                await db.execute(
                    select(PolicyRule.created_at)
                    .order_by(PolicyRule.created_at.desc())
                    .limit(1)
                )
            ).first()
            if latest_rule_row:
                reg_latest_rule_update = latest_rule_row[0].isoformat()
        except Exception as e:
            logger.warning(f"Failed to fetch regulation counts: {e}")

        return {
            "customers": {
                "total": cust_total,
                "active": status_map.get("active", 0) + status_map.get("approved", 0),
                "pending_kyc": pending_kyc,
                "approved": status_map.get("approved", 0),
                "onboarding": status_map.get("onboarding", 0),
                "pending_verification": status_map.get("pending_verification", 0),
                "rejected": status_map.get("rejected", 0),
                "edd_required": status_map.get("edd_required", 0),
            },
            "risk": {
                "high": risk_tier_map.get("high", 0),
                "medium": risk_tier_map.get("medium", 0),
                "low": risk_tier_map.get("low", 0),
                "average_score": round(float(avg_risk_row or 0), 1),
            },
            "alerts": {
                "total": alert_total,
                "open": open_alerts,
            },
            "cases": {
                "open": open_cases,
            },
            "transactions": {
                "today": txns_today,
            },
            "ai": {
                "screenings_today": screenings_today,
            },
            "regulations": {
                "total": reg_total,
                "active": reg_active,
                "pending": reg_pending,
                "latest_upload": reg_latest_upload,
                "latest_rule_update": reg_latest_rule_update,
            },
        }

    # ─────────────────────────────────────────────────────────────────────────
    # Charts
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    async def get_charts(db: AsyncSession) -> Dict[str, Any]:
        """Return all chart datasets."""
        today = date.today()
        thirty_days_ago = today - timedelta(days=29)
        six_months_ago = today - timedelta(days=180)

        # 1. Customer Risk Distribution (pie)
        latest_risk_subq = (
            select(
                RiskScore.customer_id, func.max(RiskScore.created_at).label("latest_at")
            )
            .group_by(RiskScore.customer_id)
            .subquery()
        )
        risk_dist = (
            await db.execute(
                select(RiskScore.risk_tier, func.count(RiskScore.id))
                .join(
                    latest_risk_subq,
                    and_(
                        RiskScore.customer_id == latest_risk_subq.c.customer_id,
                        RiskScore.created_at == latest_risk_subq.c.latest_at,
                    ),
                )
                .group_by(RiskScore.risk_tier)
            )
        ).all()

        # 2. Alerts by type/severity (bar)
        alert_by_type = (
            await db.execute(
                select(Alert.alert_type, func.count(Alert.id))
                .group_by(Alert.alert_type)
                .order_by(func.count(Alert.id).desc())
                .limit(10)
            )
        ).all()

        # 3. Cases by status (doughnut)
        case_by_status = (
            await db.execute(
                select(Case.status, func.count(Case.id)).group_by(Case.status)
            )
        ).all()

        # 4. Transactions per day — last 30 days (line)
        txn_per_day = (
            await db.execute(
                select(
                    func.date(Transaction.created_at).label("day"),
                    func.count(Transaction.id).label("count"),
                    func.sum(Transaction.amount).label("volume"),
                )
                .where(
                    Transaction.created_at
                    >= datetime.combine(thirty_days_ago, datetime.min.time())
                )
                .group_by(func.date(Transaction.created_at))
                .order_by(func.date(Transaction.created_at))
            )
        ).all()

        # 5. Monthly screenings — last 6 months (area)
        screenings_monthly = (
            await db.execute(
                select(
                    func.date_trunc("month", AuditLog.created_at).label("month"),
                    func.count(AuditLog.id).label("count"),
                )
                .where(
                    AuditLog.action == "INITIATE_RESCREENING",
                    AuditLog.created_at
                    >= datetime.combine(six_months_ago, datetime.min.time()),
                )
                .group_by(func.date_trunc("month", AuditLog.created_at))
                .order_by(func.date_trunc("month", AuditLog.created_at))
            )
        ).all()

        # 6. Risk score trend — last 30 days (line)
        risk_trend = (
            await db.execute(
                select(
                    func.date(RiskScore.created_at).label("day"),
                    func.avg(RiskScore.overall_score).label("avg_score"),
                )
                .where(
                    RiskScore.created_at
                    >= datetime.combine(thirty_days_ago, datetime.min.time())
                )
                .group_by(func.date(RiskScore.created_at))
                .order_by(func.date(RiskScore.created_at))
            )
        ).all()

        # 7. Country risk distribution (table — top 15)
        country_dist = (
            await db.execute(
                select(
                    Transaction.receiver_country,
                    func.count(Transaction.id).label("count"),
                )
                .group_by(Transaction.receiver_country)
                .order_by(func.count(Transaction.id).desc())
                .limit(15)
            )
        ).all()

        return {
            "risk_distribution": [
                {"tier": tier, "count": count} for tier, count in risk_dist
            ],
            "alerts_by_type": [{"type": t, "count": c} for t, c in alert_by_type],
            "cases_by_status": [{"status": s, "count": c} for s, c in case_by_status],
            "transactions_per_day": [
                {
                    "day": str(row.day),
                    "count": row.count,
                    "volume": round(float(row.volume or 0), 2),
                }
                for row in txn_per_day
            ],
            "monthly_screenings": [
                {
                    "month": str(row.month)[:7],
                    "count": row.count,
                }
                for row in screenings_monthly
            ],
            "risk_score_trend": [
                {
                    "day": str(row.day),
                    "avg_score": round(float(row.avg_score or 0), 1),
                }
                for row in risk_trend
            ],
            "country_distribution": [
                {"country": country, "count": count} for country, count in country_dist
            ],
        }

    # ─────────────────────────────────────────────────────────────────────────
    # Activity Feed
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    async def get_activity(db: AsyncSession, limit: int = 30) -> List[Dict]:
        """Recent audit log activity for the live activity panel."""
        result = await db.execute(
            select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
        )
        logs = result.scalars().all()

        # Human-readable labels
        action_labels = {
            "CREATE_TRANSACTION": "Transaction recorded",
            "CSV_IMPORT_TRANSACTION": "Bulk transactions imported",
            "CREATE_ALERT": "Alert created",
            "UPDATE_ALERT": "Alert status updated",
            "CREATE_CASE": "Investigation case opened",
            "UPDATE_CASE": "Case updated",
            "CASE_DECISION": "Case decision recorded",
            "INITIATE_RESCREENING": "AML rescreening initiated",
            "RESCREENING_COMPLETE": "AML rescreening completed",
            "DELETE_TRANSACTION": "Transaction deleted",
            "DELETE_ALERT": "Alert deleted",
            "DELETE_CASE": "Case deleted",
            "UPDATE_TRANSACTION": "Transaction updated",
        }

        return [
            {
                "id": str(log.id),
                "action": log.action,
                "label": action_labels.get(
                    log.action, log.action.replace("_", " ").title()
                ),
                "entity_name": log.entity_name,
                "entity_id": str(log.entity_id),
                "user_id": str(log.user_id) if log.user_id else None,
                "ip_address": log.ip_address,
                "new_values": log.new_values,
                "created_at": log.created_at.isoformat(),
            }
            for log in logs
        ]

    # ─────────────────────────────────────────────────────────────────────────
    # High Risk Customers
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    async def get_high_risk(db: AsyncSession, limit: int = 10) -> List[Dict]:
        """Top high-risk customers with latest risk score and case info."""
        # Latest risk score subquery
        latest_risk_subq = (
            select(
                RiskScore.customer_id, func.max(RiskScore.created_at).label("latest_at")
            )
            .group_by(RiskScore.customer_id)
            .subquery()
        )

        risk_rows = (
            await db.execute(
                select(
                    Customer.id,
                    Customer.first_name,
                    Customer.last_name,
                    Customer.customer_type,
                    Customer.status,
                    RiskScore.overall_score,
                    RiskScore.risk_tier,
                    RiskScore.created_at.label("last_assessed"),
                )
                .join(RiskScore, RiskScore.customer_id == Customer.id)
                .join(
                    latest_risk_subq,
                    and_(
                        RiskScore.customer_id == latest_risk_subq.c.customer_id,
                        RiskScore.created_at == latest_risk_subq.c.latest_at,
                    ),
                )
                .where(RiskScore.risk_tier == "high")
                .order_by(RiskScore.overall_score.desc())
                .limit(limit)
            )
        ).all()

        results = []
        for row in risk_rows:
            # Get open case for this customer
            case_result = await db.execute(
                select(Case.id, Case.status, Case.priority)
                .where(
                    Case.customer_id == row.id,
                    Case.status.in_(["open", "investigating", "under_review"]),
                )
                .order_by(Case.created_at.desc())
                .limit(1)
            )
            open_case = case_result.first()

            results.append(
                {
                    "customer_id": str(row.id),
                    "name": f"{row.first_name or ''} {row.last_name or ''}".strip()
                    or "Unknown",
                    "customer_type": row.customer_type,
                    "status": row.status,
                    "risk_score": float(row.overall_score),
                    "risk_tier": row.risk_tier,
                    "last_assessed": (
                        row.last_assessed.isoformat() if row.last_assessed else None
                    ),
                    "open_case": (
                        {
                            "id": str(open_case.id),
                            "status": open_case.status,
                            "priority": open_case.priority,
                        }
                        if open_case
                        else None
                    ),
                }
            )

        return results

    # ─────────────────────────────────────────────────────────────────────────
    # Alert Dashboard
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    async def get_alerts_summary(db: AsyncSession) -> Dict[str, Any]:
        """Alert dashboard — counts by risk level and status."""
        today_start = datetime.combine(date.today(), datetime.min.time())
        week_start = datetime.combine(
            date.today() - timedelta(days=7), datetime.min.time()
        )
        month_start = datetime.combine(date.today().replace(day=1), datetime.min.time())

        # By risk score bucket
        risk_buckets = (
            await db.execute(
                select(
                    case(
                        (Alert.risk_score >= 90, "critical"),
                        (Alert.risk_score >= 75, "high"),
                        (Alert.risk_score >= 50, "medium"),
                        else_="low",
                    ).label("level"),
                    func.count(Alert.id).label("count"),
                ).group_by(text("level"))
            )
        ).all()

        # By status
        by_status = (
            await db.execute(
                select(Alert.status, func.count(Alert.id)).group_by(Alert.status)
            )
        ).all()

        # Time-based
        today_count = (
            await db.execute(
                select(func.count(Alert.id)).where(Alert.created_at >= today_start)
            )
        ).scalar_one()
        week_count = (
            await db.execute(
                select(func.count(Alert.id)).where(Alert.created_at >= week_start)
            )
        ).scalar_one()
        month_count = (
            await db.execute(
                select(func.count(Alert.id)).where(Alert.created_at >= month_start)
            )
        ).scalar_one()

        return {
            "by_risk_level": {b.level: b.count for b in risk_buckets},
            "by_status": {s: c for s, c in by_status},
            "time_periods": {
                "today": today_count,
                "this_week": week_count,
                "this_month": month_count,
            },
        }

    # ─────────────────────────────────────────────────────────────────────────
    # Case Dashboard
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    async def get_cases_summary(db: AsyncSession) -> Dict[str, Any]:
        """Case dashboard metrics."""
        # Counts by status
        by_status = (
            await db.execute(
                select(Case.status, func.count(Case.id)).group_by(Case.status)
            )
        ).all()
        status_map = {s: c for s, c in by_status}

        # Average resolution time (approved/rejected cases)
        avg_resolution = (
            await db.execute(
                select(
                    func.avg(
                        func.extract("epoch", Case.updated_at - Case.created_at) / 3600
                    ).label("avg_hours")
                ).where(Case.status.in_(["approved", "rejected"]))
            )
        ).scalar_one()

        # SAR filed count
        sar_filed = (
            await db.execute(select(func.count(Case.id)).where(Case.sar_filed == True))
        ).scalar_one()

        # Officer workload — cases per assigned officer (top 5)
        officer_workload = (
            await db.execute(
                select(Case.assigned_to, func.count(Case.id).label("count"))
                .where(
                    Case.assigned_to.isnot(None),
                    Case.status.in_(["open", "investigating", "under_review"]),
                )
                .group_by(Case.assigned_to)
                .order_by(func.count(Case.id).desc())
                .limit(5)
            )
        ).all()

        # Load officer emails
        officer_data = []
        for officer_id, count in officer_workload:
            user_result = await db.execute(
                select(User.email).where(User.id == officer_id)
            )
            email = user_result.scalar_one_or_none() or str(officer_id)[:8]
            officer_data.append({"officer": email, "cases": count})

        return {
            "by_status": status_map,
            "open": status_map.get("open", 0) + status_map.get("investigating", 0),
            "under_review": status_map.get("under_review", 0)
            + status_map.get("waiting_info", 0),
            "edd_required": status_map.get("edd_required", 0),
            "approved": status_map.get("approved", 0),
            "rejected": status_map.get("rejected", 0),
            "sar_filed": sar_filed,
            "avg_resolution_hours": round(float(avg_resolution or 0), 1),
            "officer_workload": officer_data,
        }

    # ─────────────────────────────────────────────────────────────────────────
    # Monitoring Dashboard
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    async def get_monitoring(db: AsyncSession) -> Dict[str, Any]:
        """Monitoring schedule metrics and upcoming reviews."""
        today = date.today()
        week_end = today + timedelta(days=7)
        month_end = today + timedelta(days=30)

        overdue = (
            await db.execute(
                select(func.count(MonitoringSchedule.id)).where(
                    MonitoringSchedule.next_review_date < today,
                    MonitoringSchedule.status == "scheduled",
                )
            )
        ).scalar_one()

        due_this_week = (
            await db.execute(
                select(func.count(MonitoringSchedule.id)).where(
                    MonitoringSchedule.next_review_date.between(today, week_end),
                    MonitoringSchedule.status == "scheduled",
                )
            )
        ).scalar_one()

        due_this_month = (
            await db.execute(
                select(func.count(MonitoringSchedule.id)).where(
                    MonitoringSchedule.next_review_date.between(today, month_end),
                    MonitoringSchedule.status == "scheduled",
                )
            )
        ).scalar_one()

        # Next 10 upcoming reviews
        upcoming = (
            await db.execute(
                select(MonitoringSchedule, Customer)
                .join(Customer, Customer.id == MonitoringSchedule.customer_id)
                .where(
                    MonitoringSchedule.next_review_date >= today,
                    MonitoringSchedule.status == "scheduled",
                )
                .order_by(MonitoringSchedule.next_review_date.asc())
                .limit(10)
            )
        ).all()

        upcoming_list = []
        for sched, cust in upcoming:
            upcoming_list.append(
                {
                    "schedule_id": str(sched.id),
                    "customer_id": str(cust.id),
                    "customer_name": f"{cust.first_name or ''} {cust.last_name or ''}".strip()
                    or "Unknown",
                    "next_review_date": str(sched.next_review_date),
                    "frequency_months": sched.review_frequency_months,
                    "last_review_date": (
                        str(sched.last_review_date) if sched.last_review_date else None
                    ),
                    "status": sched.status,
                }
            )

        return {
            "overdue": overdue,
            "due_this_week": due_this_week,
            "due_this_month": due_this_month,
            "total_scheduled": (
                await db.execute(
                    select(func.count(MonitoringSchedule.id)).where(
                        MonitoringSchedule.status == "scheduled"
                    )
                )
            ).scalar_one(),
            "upcoming": upcoming_list,
        }

    # ─────────────────────────────────────────────────────────────────────────
    # Global Search
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    async def search(db: AsyncSession, query: str, limit: int = 10) -> Dict[str, Any]:
        """Global search across customers, cases, alerts, transactions."""
        if not query or len(query.strip()) < 2:
            return {"customers": [], "cases": [], "alerts": [], "transactions": []}

        q = query.strip()

        # Customers — by name, ID prefix
        customers_result = await db.execute(
            select(Customer)
            .where(
                or_(
                    Customer.first_name.ilike(f"%{q}%"),
                    Customer.last_name.ilike(f"%{q}%"),
                    func.concat(Customer.first_name, " ", Customer.last_name).ilike(
                        f"%{q}%"
                    ),
                    Customer.id.cast(text("text")).ilike(f"{q}%"),
                    Customer.phone_number.ilike(f"%{q}%"),
                )
            )
            .limit(limit)
        )
        customers = customers_result.scalars().all()

        # Cases — by ID prefix
        cases_result = await db.execute(
            select(Case).where(Case.id.cast(text("text")).ilike(f"{q}%")).limit(limit)
        )
        cases = cases_result.scalars().all()

        # Alerts — by ID prefix or type
        alerts_result = await db.execute(
            select(Alert)
            .where(
                or_(
                    Alert.id.cast(text("text")).ilike(f"{q}%"),
                    Alert.alert_type.ilike(f"%{q}%"),
                )
            )
            .limit(limit)
        )
        alerts = alerts_result.scalars().all()

        # Transactions — by ID prefix or receiver name
        txns_result = await db.execute(
            select(Transaction)
            .where(
                or_(
                    Transaction.id.cast(text("text")).ilike(f"{q}%"),
                    Transaction.receiver_name.ilike(f"%{q}%"),
                    Transaction.receiver_account_number.ilike(f"%{q}%"),
                    Transaction.reference.ilike(f"%{q}%"),
                )
            )
            .limit(limit)
        )
        transactions = txns_result.scalars().all()

        return {
            "customers": [
                {
                    "id": str(c.id),
                    "name": f"{c.first_name or ''} {c.last_name or ''}".strip()
                    or "Unknown",
                    "type": c.customer_type,
                    "status": c.status,
                    "url": f"/admin/cases?customer_id={c.id}",
                }
                for c in customers
            ],
            "cases": [
                {
                    "id": str(c.id),
                    "status": c.status,
                    "priority": c.priority,
                    "customer_id": str(c.customer_id),
                    "url": f"/admin/cases/{c.id}",
                }
                for c in cases
            ],
            "alerts": [
                {
                    "id": str(a.id),
                    "type": a.alert_type,
                    "risk_score": float(a.risk_score),
                    "status": a.status,
                    "url": f"/admin/alerts",
                }
                for a in alerts
            ],
            "transactions": [
                {
                    "id": str(t.id),
                    "receiver": t.receiver_name,
                    "amount": float(t.amount),
                    "currency": t.currency,
                    "status": t.status,
                    "url": f"/admin/transactions/{t.id}",
                }
                for t in transactions
            ],
        }

    # ─────────────────────────────────────────────────────────────────────────
    # AI Dashboard
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    async def get_ai_summary(db: AsyncSession) -> Dict[str, Any]:
        """Latest AI agent execution results."""
        # Latest case with agent logs
        latest_case_result = await db.execute(
            select(Case).order_by(Case.created_at.desc()).limit(1)
        )
        latest_case = latest_case_result.scalars().first()

        agent_logs = []
        investigation_notes = None
        if latest_case:
            logs_result = await db.execute(
                select(AgentLog)
                .where(AgentLog.case_id == latest_case.id)
                .order_by(AgentLog.created_at.asc())
            )
            agent_logs = logs_result.scalars().all()
            investigation_notes = latest_case.investigation_notes

        # Recent risk scores (last 5)
        recent_scores = (
            (
                await db.execute(
                    select(RiskScore).order_by(RiskScore.created_at.desc()).limit(5)
                )
            )
            .scalars()
            .all()
        )

        # Agent execution stats from logs
        total_agents = len(agent_logs)
        completed = sum(1 for l in agent_logs if l.output_state is not None)
        failed = sum(1 for l in agent_logs if l.output_state is None)
        avg_exec_ms = (
            sum(l.execution_time_ms or 0 for l in agent_logs) / total_agents
            if total_agents
            else 0
        )

        return {
            "latest_case_id": str(latest_case.id) if latest_case else None,
            "investigation_summary": (
                (investigation_notes or "")[:500] if investigation_notes else None
            ),
            "agent_execution": {
                "total": total_agents,
                "completed": completed,
                "failed": failed,
                "avg_exec_ms": round(avg_exec_ms, 1),
            },
            "agent_logs": [
                {
                    "agent_name": l.agent_name,
                    "step_name": l.step_name,
                    "execution_time_ms": l.execution_time_ms,
                    "has_output": l.output_state is not None,
                    "created_at": l.created_at.isoformat(),
                }
                for l in agent_logs
            ],
            "recent_decisions": [
                {
                    "customer_id": str(r.customer_id),
                    "score": float(r.overall_score),
                    "tier": r.risk_tier,
                    "created_at": r.created_at.isoformat(),
                }
                for r in recent_scores
            ],
        }
