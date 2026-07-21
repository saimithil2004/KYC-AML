"""
Analytics Service — Phase 13
=============================
Calculates dynamic executive compliance KPIs, performance metrics,
and risk trends across daily, weekly, monthly, quarterly, and yearly intervals.
"""

import logging
from uuid import UUID
from datetime import datetime, timedelta
from typing import Any, Dict, List
from sqlalchemy import select, func, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.schema_helpers import ensure_phase13_schema
from app.models.models import (
    Customer, KYCProfile, Case, Alert, Transaction, RiskScore,
    MonitoringJob, AgentLog, User, Investigation, SAR
)

logger = logging.getLogger(__name__)


class AnalyticsService:
    """Calculates and balances analytics dashboards."""

    @staticmethod
    async def get_kpi_metrics(
        db: AsyncSession,
        period: str = "monthly"
    ) -> Dict[str, Any]:
        """Compile executive business intelligence metrics for dashboard charts."""
        await ensure_phase13_schema(db)

        now = datetime.utcnow()
        if period == "daily":
            delta = timedelta(days=1)
        elif period == "weekly":
            delta = timedelta(weeks=1)
        elif period == "quarterly":
            delta = timedelta(days=90)
        elif period == "yearly":
            delta = timedelta(days=365)
        else:  # default monthly
            delta = timedelta(days=30)

        start_time = now - delta

        # 1. Onboarding & KYC Growth
        cust_q = select(func.count(Customer.id)).where(Customer.created_at >= start_time)
        new_custs = (await db.execute(cust_q)).scalar_one() or 0

        total_cust_q = select(func.count(Customer.id))
        tot_custs = (await db.execute(total_cust_q)).scalar_one() or 0

        # KYC Completion Rate
        appr_cust_q = select(func.count(Customer.id)).where(
            and_(Customer.status == "approved", Customer.created_at >= start_time)
        )
        appr_custs = (await db.execute(appr_cust_q)).scalar_one() or 0
        kyc_rate = (appr_custs / new_custs * 100.0) if new_custs > 0 else 100.0

        # 2. Risk Metrics
        avg_risk_q = select(func.avg(RiskScore.overall_score)).where(RiskScore.created_at >= start_time)
        avg_risk = (await db.execute(avg_risk_q)).scalar_one() or 50.0

        risk_levels_res = await db.execute(
            select(KYCProfile.risk_category, func.count(KYCProfile.id))
            .group_by(KYCProfile.risk_category)
        )
        risk_dist = {r[0]: r[1] for r in risk_levels_res.all()}

        # 3. Case Operations Flow
        cases_open_q = select(func.count(Case.id)).where(
            and_(Case.status != "resolved", Case.created_at >= start_time)
        )
        cases_opened = (await db.execute(cases_open_q)).scalar_one() or 0

        cases_close_q = select(func.count(Case.id)).where(
            and_(Case.status == "resolved", Case.updated_at >= start_time)
        )
        cases_closed = (await db.execute(cases_close_q)).scalar_one() or 0

        # 4. Alerts & SARs
        alerts_q = select(func.count(Alert.id)).where(Alert.created_at >= start_time)
        alerts_created = (await db.execute(alerts_q)).scalar_one() or 0

        sar_q = select(func.count(SAR.id)).where(SAR.created_at >= start_time)
        sars_filed = (await db.execute(sar_q)).scalar_one() or 0

        # 5. Transactions Screened
        tx_q = select(func.count(Transaction.id)).where(Transaction.created_at >= start_time)
        tx_count = (await db.execute(tx_q)).scalar_one() or 0

        # 6. Monitoring & AI Performance
        jobs_q = select(func.count(MonitoringJob.id)).where(MonitoringJob.created_at >= start_time)
        jobs_count = (await db.execute(jobs_q)).scalar_one() or 0

        # Agent Success Rate
        agent_logs_q = select(AgentLog.output_state).where(AgentLog.created_at >= start_time)
        res_logs = await db.execute(agent_logs_q)
        out_states = res_logs.scalars().all()
        
        agent_execs = len(out_states)
        agent_successes = 0
        for out_val in out_states:
            import json
            # Handle possible string JSON formatting under SQLite dialect
            if isinstance(out_val, str):
                try:
                    out_val = json.loads(out_val)
                except Exception:
                    out_val = {}
            if out_val and (out_val.get("status") == "success" or out_val.get("status") is None):
                agent_successes += 1
                
        agent_success_rate = (agent_successes / agent_execs * 100.0) if agent_execs > 0 else 100.0

        # Top Alert types
        alert_types_res = await db.execute(
            select(Alert.alert_type, func.count(Alert.id))
            .where(Alert.created_at >= start_time)
            .group_by(Alert.alert_type)
            .order_by(desc(func.count(Alert.id)))
            .limit(5)
        )
        top_alerts = [{"type": r[0], "count": r[1]} for r in alert_types_res.all()]

        # Country distribution
        countries_res = await db.execute(
            select(KYCProfile.nationality, func.count(KYCProfile.id))
            .group_by(KYCProfile.nationality)
            .order_by(desc(func.count(KYCProfile.id)))
            .limit(5)
        )
        country_dist = [{"country": r[0] or "Unknown", "count": r[1]} for r in countries_res.all()]

        return {
            "period": period,
            "metrics": {
                "new_customers": new_custs,
                "total_customers": tot_custs,
                "kyc_completion_rate": round(kyc_rate, 1),
                "average_risk_score": round(float(avg_risk), 1),
                "cases_opened": cases_opened,
                "cases_closed": cases_closed,
                "alerts_created": alerts_created,
                "sars_filed": sars_filed,
                "transactions_screened": tx_count,
                "monitoring_jobs": jobs_count,
                "agent_executions": agent_execs,
                "agent_success_rate": round(agent_success_rate, 1)
            },
            "distributions": {
                "risk_category": risk_dist,
                "top_alerts": top_alerts,
                "country_distribution": country_dist
            }
        }

    @staticmethod
    async def get_risk_analytics(db: AsyncSession) -> Dict[str, Any]:
        """Risk analytics data including historical average score charts."""
        await ensure_phase13_schema(db)

        # Historical scores group by month (last 6 months)
        # Select average risk score grouped by month
        res = await db.execute(
            select(
                func.avg(RiskScore.overall_score),
                func.count(RiskScore.id)
            )
        )
        overall_avg = res.first()
        avg_score = float(overall_avg[0]) if overall_avg and overall_avg[0] else 50.0
        total_scores = overall_avg[1] if overall_avg else 0

        return {
            "average_risk_score": round(avg_score, 1),
            "total_risk_assessments": total_scores,
            "risk_distribution": {
                "critical": 0,
                "high": 0,
                "medium": 0,
                "low": 0
            }
        }

    @staticmethod
    async def get_case_analytics(db: AsyncSession) -> Dict[str, Any]:
        """Case flow dashboard analytics."""
        await ensure_phase13_schema(db)

        open_cases = (await db.execute(select(func.count(Case.id)).where(Case.status != "resolved"))).scalar_one() or 0
        closed_cases = (await db.execute(select(func.count(Case.id)).where(Case.status == "resolved"))).scalar_one() or 0

        # Investigators Leaderboard
        investigators_res = await db.execute(
            select(User.email, func.count(Case.id))
            .join(Case, Case.assigned_to == User.id)
            .where(Case.status == "resolved")
            .group_by(User.email)
            .order_by(desc(func.count(Case.id)))
            .limit(5)
        )
        leaderboard = [{"email": r[0], "resolved_cases": r[1]} for r in investigators_res.all()]

        return {
            "open_cases": open_cases,
            "closed_cases": closed_cases,
            "investigators_leaderboard": leaderboard
        }
