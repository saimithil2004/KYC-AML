"""
Monitoring Agent
=================
Creates a monitoring schedule for the customer based on their risk tier.

Frequency rules:
  LOW    → Review every 60 months (5 years)
  MEDIUM → Review every 36 months (3 years)
  HIGH   → Review every 12 months (1 year)

Persists a MonitoringSchedule record to the database.
"""

import time
import logging
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional
from uuid import UUID

from app.agents.base.base_agent import BaseAgent
from app.agents.base.agent_state import AgentState
from app.agents.base.registry import AgentRegistry
from app.agents.base.exceptions import AgentValidationError

logger = logging.getLogger(__name__)

# Monitoring schedule rules (risk_tier → frequency in months)
MONITORING_FREQUENCY: Dict[str, int] = {
    "low": 60,  # 5 years
    "medium": 36,  # 3 years
    "high": 12,  # 1 year
    "critical": 6,  # 6 months (extra caution)
}


@AgentRegistry.register("monitoring_agent")
class MonitoringAgent(BaseAgent):
    """
    Monitoring Agent.
    Creates and persists a customer monitoring schedule based on risk tier.
    """

    def get_name(self) -> str:
        return "monitoring_agent"

    def get_version(self) -> str:
        return "1.0.0"

    def get_description(self) -> str:
        return (
            "Monitoring schedule agent. Creates a next-review schedule based on "
            "risk tier (LOW=5yr, MEDIUM=3yr, HIGH=1yr). Persists to the database."
        )

    def get_capabilities(self) -> List[str]:
        return [
            "monitoring_schedule_creation",
            "risk_tier_based_frequency",
            "next_review_date_calculation",
            "monitoring_schedule_persistence",
        ]

    def validate_input(self, state: AgentState) -> bool:
        if not state.customer_id:
            raise AgentValidationError(
                message="customer_id missing in AgentState. Cannot run MonitoringAgent.",
                details={"customer_id": None},
            )
        return True

    async def process(self, state: AgentState) -> Dict[str, Any]:
        start_time = time.perf_counter()
        state.logs.append(f"[{self.get_name()}] Creating monitoring schedule...")

        risk_tier = str(state.risk_tier or "low").lower()
        frequency = MONITORING_FREQUENCY.get(risk_tier, MONITORING_FREQUENCY["medium"])
        today = date.today()
        # Calculate next review date by adding months
        next_review_date = self._add_months(today, frequency)

        schedule = {
            "customer_id": state.customer_id,
            "risk_tier": risk_tier,
            "review_frequency_months": frequency,
            "last_review_date": today.isoformat(),
            "next_review_date": next_review_date.isoformat(),
            "status": "scheduled",
            "created_at": datetime.utcnow().isoformat(),
        }

        # ── Persist to DB ─────────────────────────────────────────────────────
        self._persist_schedule(state, frequency, today, next_review_date)

        # ── Update state ──────────────────────────────────────────────────────
        state.monitoring_schedule = schedule
        state.shared_metadata["monitoring_schedule"] = schedule
        state.shared_metadata["next_review_date"] = next_review_date.isoformat()
        state.shared_metadata["review_frequency_months"] = frequency

        execution_duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        state.logs.append(
            f"MonitoringAgent: Schedule created. Risk={risk_tier.upper()}, "
            f"Frequency={frequency}mo, Next review={next_review_date.isoformat()}."
        )

        return {
            "_status": "success",
            "_reason": f"Monitoring schedule created. Next review: {next_review_date.isoformat()}",
            "confidence": 1.0,
            "risk_score": 100.0,
            "risk_level": risk_tier,
            "findings": [
                f"Monitoring schedule established for {risk_tier.upper()} risk tier. "
                f"Next review: {next_review_date.isoformat()} ({frequency} months)."
            ],
            "warnings": [],
            "recommendations": [
                f"Schedule next compliance review for {next_review_date.isoformat()}."
            ],
            "errors": [],
            # Metadata
            "monitoring_schedule": schedule,
            "next_review_date": next_review_date.isoformat(),
            "review_frequency_months": frequency,
            "last_review_date": today.isoformat(),
            "execution_duration_ms": execution_duration_ms,
        }

    def _persist_schedule(
        self,
        state: AgentState,
        frequency: int,
        last_review: date,
        next_review: date,
    ) -> None:
        """Persists MonitoringSchedule to the database."""
        if not self.db:
            logger.warning(
                "MonitoringAgent: No DB session — skipping schedule persistence."
            )
            return
        try:
            from app.models.models import MonitoringSchedule

            cust_uuid = UUID(state.customer_id)

            # Check for existing schedule
            existing = (
                self.db.query(MonitoringSchedule)
                .filter(MonitoringSchedule.customer_id == cust_uuid)
                .first()
            )

            if existing:
                existing.review_frequency_months = frequency
                existing.next_review_date = next_review
                existing.last_review_date = last_review
                existing.status = "scheduled"
            else:
                record = MonitoringSchedule(
                    customer_id=cust_uuid,
                    next_review_date=next_review,
                    review_frequency_months=frequency,
                    last_review_date=last_review,
                    status="scheduled",
                )
                self.db.add(record)

            self.db.commit()
            logger.info(
                f"MonitoringAgent: Schedule persisted for customer {state.customer_id}."
            )
        except Exception as exc:
            logger.error(
                f"MonitoringAgent: Failed to persist monitoring schedule: {exc}"
            )
            try:
                self.db.rollback()
            except Exception:
                pass

    @staticmethod
    def _add_months(dt: date, months: int) -> date:
        """Adds months to a date, handling month boundary correctly."""
        import calendar

        month = dt.month - 1 + months
        year = dt.year + month // 12
        month = month % 12 + 1
        day = min(dt.day, calendar.monthrange(year, month)[1])
        return date(year, month, day)
