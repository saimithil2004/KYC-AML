"""
Continuous Monitoring & Automated Re-Screening Service — Phase 11
===================================================================
Orchestrates re-screening triggers, Celery scheduler tasks tracking,
change detection, risk delta computations, and monitoring history database logs.
"""

import logging
import time
from uuid import UUID, uuid4
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import select, update, func, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.schema_helpers import ensure_phase11_schema
from app.models.models import (
    Customer, KYCProfile, Document, Case, Alert, RiskScore,
    MonitoringSchedule, MonitoringJob, MonitoringHistory, PolicyRule,
    Transaction, Company, Director, UBO
)
from app.services.screening_service import ScreeningService
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)


class MonitoringService:
    """Core compliance monitoring service."""

    @staticmethod
    async def get_statistics(db: AsyncSession) -> Dict[str, Any]:
        """Fetch continuous monitoring aggregate metrics for dashboard integration."""
        await ensure_phase11_schema(db)

        today_start = datetime.combine(date.today(), datetime.min.time())

        # 1. Customers Under Monitoring (Customers with a MonitoringSchedule active)
        cust_monitoring = (await db.execute(
            select(func.count(func.distinct(MonitoringSchedule.customer_id)))
            .where(MonitoringSchedule.status == "scheduled")
        )).scalar_one() or 0

        # 2. Today's Screenings (MonitoringHistory created today)
        today_screenings = (await db.execute(
            select(func.count(MonitoringHistory.id))
            .where(MonitoringHistory.screening_date >= today_start)
        )).scalar_one() or 0

        # 3. Queued Jobs
        queued = (await db.execute(
            select(func.count(MonitoringJob.id))
            .where(MonitoringJob.status == "queued")
        )).scalar_one() or 0

        # 4. Running Jobs
        running = (await db.execute(
            select(func.count(MonitoringJob.id))
            .where(MonitoringJob.status == "running")
        )).scalar_one() or 0

        # 5. Failed Jobs
        failed = (await db.execute(
            select(func.count(MonitoringJob.id))
            .where(MonitoringJob.status == "failed")
        )).scalar_one() or 0

        # 6. Upcoming Reviews (MonitoringSchedule due in next 30 days)
        thirty_days_later = date.today() + timedelta(days=30)
        upcoming = (await db.execute(
            select(func.count(MonitoringSchedule.id))
            .where(and_(
                MonitoringSchedule.next_review_date <= thirty_days_later,
                MonitoringSchedule.status == "scheduled"
            ))
        )).scalar_one() or 0

        # 7. Risk Changes Today (RiskScore changes tracked in history today)
        risk_changes = (await db.execute(
            select(func.count(MonitoringHistory.id))
            .where(and_(
                MonitoringHistory.screening_date >= today_start,
                MonitoringHistory.risk_delta != 0
            ))
        )).scalar_one() or 0

        # 8. Completed Reviews (Successful runs in history)
        completed_reviews = (await db.execute(
            select(func.count(MonitoringHistory.id))
        )).scalar_one() or 0

        return {
            "customers_under_monitoring": cust_monitoring,
            "todays_screenings": today_screenings,
            "queued_jobs": queued,
            "running_jobs": running,
            "failed_jobs": failed,
            "upcoming_reviews": upcoming,
            "risk_changes_today": risk_changes,
            "completed_reviews": completed_reviews
        }

    @staticmethod
    async def create_monitoring_job(
        db: AsyncSession,
        customer_id: UUID,
        trigger_reason: str
    ) -> MonitoringJob:
        """Create and queue a monitoring job."""
        await ensure_phase11_schema(db)

        job = MonitoringJob(
            id=uuid4(),
            customer_id=customer_id,
            status="queued",
            trigger_reason=trigger_reason,
            retry_count=0
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)
        return job

    @staticmethod
    async def run_rescreening(
        db: AsyncSession,
        customer_id: UUID,
        trigger_reason: str,
        job_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """
        Runs automated re-screening for a customer.
        Reuses existing ScreeningService.
        """
        await ensure_phase11_schema(db)
        start_time = time.time()

        # Update or create monitoring job status to running
        job = None
        if job_id:
            res = await db.execute(select(MonitoringJob).where(MonitoringJob.id == job_id))
            job = res.scalars().first()

        if not job:
            job = MonitoringJob(
                id=uuid4(),
                customer_id=customer_id,
                status="running",
                trigger_reason=trigger_reason,
                retry_count=0,
                worker_name="celery-worker"
            )
            db.add(job)
        else:
            job.status = "running"
            job.worker_name = "celery-worker"
            job.updated_at = datetime.utcnow()

        await db.commit()
        await db.refresh(job)

        # 1. Fetch previous screening data (old risk score and decision)
        score_res = await db.execute(
            select(RiskScore)
            .where(RiskScore.customer_id == customer_id)
            .order_by(desc(RiskScore.created_at))
            .limit(1)
        )
        old_risk = score_res.scalars().first()
        old_score = float(old_risk.overall_score) if old_risk else 0.0

        # Try to infer previous decision from latest case decision
        case_res = await db.execute(
            select(Case)
            .where(Case.customer_id == customer_id)
            .order_by(desc(Case.created_at))
            .limit(1)
        )
        old_case = case_res.scalars().first()
        old_decision = old_case.status if old_case else "UNKNOWN"

        try:
            # 2. Invoke the main Orchestrator via existing ScreeningService
            # We call the async runner as we are inside an AsyncSession context
            result = await ScreeningService.run_screening_async(str(customer_id))

            # Fetch updated RiskScore
            new_score_res = await db.execute(
                select(RiskScore)
                .where(RiskScore.customer_id == customer_id)
                .order_by(desc(RiskScore.created_at))
                .limit(1)
            )
            new_risk = new_score_res.scalars().first()
            new_score = float(new_risk.overall_score) if new_risk else float(result.get("score", 0.0))

            new_decision = result.get("decision", "MANUAL_REVIEW")
            case_uuid = UUID(result["case_id"]) if result.get("case_id") else None

            # Calculate Deltas
            risk_delta = new_score - old_score
            if risk_delta > 5.0:
                risk_trend = "deteriorating"
            elif risk_delta < -5.0:
                risk_trend = "improving"
            else:
                risk_trend = "stable"

            # Query active alerts for this customer
            alert_count = 0
            alerts_res = await db.execute(
                select(func.count(Alert.id))
                .where(and_(Alert.customer_id == customer_id, Alert.status == "open"))
            )
            alert_count = alerts_res.scalar_one() or 0

            # Store screening in monitoring history
            history = MonitoringHistory(
                id=uuid4(),
                customer_id=customer_id,
                trigger_reason=trigger_reason,
                old_score=old_score,
                new_score=new_score,
                old_decision=old_decision,
                new_decision=new_decision,
                risk_delta=risk_delta,
                new_alerts_count=alert_count,
                resolved_alerts_count=0,  # default
                risk_trend=risk_trend,
                agents_executed=result.get("agents_completed", []),
                execution_time_ms=int((time.time() - start_time) * 1000),
                case_id=case_uuid,
                risk_score_id=new_risk.id if new_risk else None
            )
            db.add(history)

            # Update Job as completed
            job.status = "completed"
            job.case_id = case_uuid
            job.execution_time_ms = history.execution_time_ms
            job.error_message = None

            # Update MonitoringSchedule review date
            sched_res = await db.execute(
                select(MonitoringSchedule)
                .where(MonitoringSchedule.customer_id == customer_id)
            )
            sched = sched_res.scalars().first()
            if sched:
                sched.last_review_date = date.today()
                sched.next_review_date = date.today() + timedelta(days=sched.review_frequency_months * 30)
                sched.status = "scheduled"

            # Part 8: Alert Automation
            # Automatically generate Alert entities based on risk thresholds or monitoring anomalies
            await MonitoringService._generate_automated_alerts(
                db=db,
                customer_id=customer_id,
                case_id=case_uuid,
                risk_delta=risk_delta,
                new_score=new_score,
                new_decision=new_decision,
                trigger_reason=trigger_reason,
                result=result
            )

            await db.commit()
            return result

        except Exception as exc:
            logger.error(f"MonitoringService: Automated re-screening failed for customer {customer_id}: {exc}")
            job.status = "failed"
            job.error_message = str(exc)
            job.retry_count += 1
            await db.commit()
            raise exc

    @staticmethod
    async def _generate_automated_alerts(
        db: AsyncSession,
        customer_id: UUID,
        case_id: Optional[UUID],
        risk_delta: float,
        new_score: float,
        new_decision: str,
        trigger_reason: str,
        result: Dict[str, Any]
    ):
        """Part 8 - Automatically generate alerts for compliance operations."""
        alert_triggers = []

        # 1. Risk increase
        if risk_delta >= 10.0:
            alert_triggers.append({
                "type": "risk_increase",
                "desc": f"Risk score increased by {risk_delta:.1f} points (new score: {new_score:.1f})."
            })

        # 2. High-risk customer
        if new_score >= 70.0:
            alert_triggers.append({
                "type": "high_risk_tier",
                "desc": f"Customer risk level evaluated in High tier (score: {new_score:.1f})."
            })

        # 3. Policy violation
        if new_decision in ("REJECT", "EDD_REQUIRED"):
            alert_triggers.append({
                "type": "policy_violation",
                "desc": f"Automatic screening result flag: {new_decision}."
            })

        # 4. Large transactions / Anomalies
        if trigger_reason == "new_transaction":
            alert_triggers.append({
                "type": "transaction_anomaly",
                "desc": "Re-screen triggered due to high value or anomaly transaction."
            })

        # 5. Sanctions or PEP hit detection
        if "sanctions_agent" in result.get("agents_completed", []):
            alert_triggers.append({
                "type": "sanctions_hit",
                "desc": "Periodic scan included sanctions screening verify loop."
            })

        # Insert alerts into the database
        for trigger in alert_triggers:
            alert_id = uuid4()
            db.add(Alert(
                id=alert_id,
                customer_id=customer_id,
                transaction_id=None,
                alert_type=trigger["type"],
                risk_score=new_score,
                status="open",
                alert_metadata={
                    "severity": "high" if new_score >= 70.0 else "medium",
                    "description": trigger["desc"],
                    "case_id": str(case_id) if case_id else None,
                    "notes": f"Auto-generated alert via Phase 11 Continuous Monitoring Engine ({trigger_reason})."
                }
            ))

    @staticmethod
    async def cancel_job(db: AsyncSession, job_id: UUID) -> bool:
        """Cancel a queued or running job."""
        await ensure_phase11_schema(db)
        res = await db.execute(select(MonitoringJob).where(MonitoringJob.id == job_id))
        job = res.scalars().first()
        if job and job.status in ("queued", "running"):
            job.status = "failed"
            job.error_message = "Job cancelled by compliance officer."
            await db.commit()
            return True
        return False

    @staticmethod
    async def retry_job(db: AsyncSession, job_id: UUID) -> bool:
        """Retry a failed job by resetting status to queued."""
        await ensure_phase11_schema(db)
        res = await db.execute(select(MonitoringJob).where(MonitoringJob.id == job_id))
        job = res.scalars().first()
        if job and job.status == "failed":
            job.status = "queued"
            job.retry_count += 1
            job.error_message = None
            await db.commit()
            return True
        return False

    @staticmethod
    async def detect_and_trigger_rescreen(
        db: AsyncSession,
        customer_id: UUID,
        trigger_reason: str
    ) -> Optional[MonitoringJob]:
        """
        Part 5 - Change Detection.
        Queues and immediately schedules/triggers a rescreening run.
        """
        await ensure_phase11_schema(db)

        # Check if there is already a running/queued job to avoid duplicate screenings
        exist_res = await db.execute(
            select(MonitoringJob)
            .where(and_(
                MonitoringJob.customer_id == customer_id,
                MonitoringJob.status.in_(["queued", "running"])
            ))
        )
        existing = exist_res.scalars().first()
        if existing:
            logger.info(f"Screening already pending/running for customer {customer_id}. Skipping duplicate trigger.")
            return existing

        job = await MonitoringService.create_monitoring_job(db, customer_id, trigger_reason)
        return job
