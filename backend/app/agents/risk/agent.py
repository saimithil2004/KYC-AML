"""
Risk Scoring Agent
==================
Aggregates the outputs of all screening agents and calculates a single,
weighted overall risk score (0–100) with a corresponding risk level.

Signal mapping (configurable in app/agents/risk/config.py):
  pep         → state.shared_metadata["pep_score"]         (0–100, 100=clear)
  sanctions   → state.shared_metadata["sanctions_score"]   (0–100, 100=clear)
  country     → state.shared_metadata["country_score"]     (0–100, 100=clear)
  document    → state.shared_metadata["document_score"]    (0–100, 100=clear)
  transaction → state.shared_metadata["transaction_score"] (0–100, 100=clear)

Score formula
-------------
  contribution_i  = weight_i * (1 - agent_score_i / 100)
  overall_score   = sum(contribution_i)   [clamped 0–100]

The individual agent scores are inverted (high agent score = low risk contribution)
so that a score of 100 (all clear) contributes 0 to overall risk.

Risk levels (configurable):
  0–30  → LOW
  31–70 → MEDIUM
  71+   → HIGH
"""

import time
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from uuid import UUID

from app.agents.base.base_agent import BaseAgent
from app.agents.base.agent_state import AgentState
from app.agents.base.registry import AgentRegistry
from app.agents.base.exceptions import AgentValidationError, RiskCalculationError

from app.agents.risk.config import (
    RISK_WEIGHTS,
    DEFAULT_AGENT_SCORE,
    get_risk_level,
)
from app.agents.risk.models import (
    ContributingFactor,
    RiskScoringResult,
    RiskScoringAuditTrail,
)

logger = logging.getLogger(__name__)

# Map signal names → the shared_metadata key that holds the agent score
_SIGNAL_KEY_MAP: Dict[str, str] = {
    "pep": "pep_score",
    "sanctions": "sanctions_score",
    "country": "country_score",
    "document": "document_score",
    "transaction": "transaction_score",
}


@AgentRegistry.register("risk_scoring_agent")
class RiskScoringAgent(BaseAgent):
    """
    Central Risk Scoring Agent.
    Aggregates outputs from all screening agents and produces a final
    weighted risk score (0–100) with risk level and contributing factors.
    Persists the result to the risk_scores table.
    """

    # ── Agent Metadata ────────────────────────────────────────────────────────
    def get_name(self) -> str:
        return "risk_scoring_agent"

    def get_version(self) -> str:
        return "1.0.0"

    def get_description(self) -> str:
        return (
            "Central risk scoring agent. Aggregates PEP, sanctions, country, "
            "document, and transaction signals using configurable weights to "
            "produce an overall risk score (0–100) and risk level (LOW/MEDIUM/HIGH)."
        )

    def get_capabilities(self) -> List[str]:
        return [
            "weighted_risk_aggregation",
            "configurable_weights",
            "contributing_factor_breakdown",
            "risk_level_classification",
            "audit_trail_generation",
            "risk_score_persistence",
        ]

    # ── Input Validation ──────────────────────────────────────────────────────
    def validate_input(self, state: AgentState) -> bool:
        if not state.customer_id:
            raise AgentValidationError(
                message="customer_id is missing in AgentState. Cannot run RiskScoringAgent.",
                details={"customer_id": None},
            )
        return True

    # ── Core Processing ───────────────────────────────────────────────────────
    async def process(self, state: AgentState) -> Dict[str, Any]:
        start_time = time.perf_counter()
        state.logs.append(f"[{self.get_name()}] Starting risk aggregation...")

        # ── Step 1: Collect individual agent scores ───────────────────────────
        agent_scores: Dict[str, float] = {}
        for signal, meta_key in _SIGNAL_KEY_MAP.items():
            raw = state.shared_metadata.get(meta_key)
            if raw is None:
                # Fall back to risk_breakdown which agents also write to
                raw = state.risk_breakdown.get(signal)
            if raw is None:
                logger.warning(
                    f"RiskScoringAgent: No score for signal '{signal}' — using default {DEFAULT_AGENT_SCORE}"
                )
                raw = DEFAULT_AGENT_SCORE
            agent_scores[signal] = float(raw)

        # ── Step 2: Compute weighted contributions ────────────────────────────
        contributing_factors: List[ContributingFactor] = []
        overall_score: float = 0.0

        for signal, weight in RISK_WEIGHTS.items():
            agent_score = agent_scores.get(signal, DEFAULT_AGENT_SCORE)
            # Invert: agent_score 100 = all clear → 0 contribution
            contribution = weight * (1.0 - (agent_score / 100.0))
            overall_score += contribution

            factor = ContributingFactor(
                signal=signal,
                weight=weight,
                agent_score=agent_score,
                contribution=round(contribution, 2),
                explanation=self._explain_factor(signal, agent_score, contribution),
            )
            contributing_factors.append(factor)

        # Clamp to 0–100
        overall_score = round(min(max(overall_score, 0.0), 100.0), 2)

        # ── Step 3: Determine risk level ──────────────────────────────────────
        risk_level = get_risk_level(overall_score)

        # ── Step 4: Build explanation ─────────────────────────────────────────
        top_factors = sorted(
            contributing_factors, key=lambda f: f.contribution, reverse=True
        )
        top_signal_names = [
            f.signal.upper() for f in top_factors[:3] if f.contribution > 0
        ]
        explanation = self._build_explanation(
            overall_score, risk_level, top_signal_names
        )

        # ── Step 5: Build result & audit trail ───────────────────────────────
        execution_duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        result = RiskScoringResult(
            overall_score=overall_score,
            risk_level=risk_level,
            contributing_factors=contributing_factors,
            explanation=explanation,
            weights_used=dict(RISK_WEIGHTS),
            agent_scores_input=agent_scores,
        )

        audit = RiskScoringAuditTrail(
            overall_score=overall_score,
            risk_level=risk_level,
            contributing_factors=[f.model_dump() for f in contributing_factors],
            weights_used=dict(RISK_WEIGHTS),
            agent_scores_input=agent_scores,
            execution_duration_ms=execution_duration_ms,
        )

        # ── Step 6: Persist to DB ─────────────────────────────────────────────
        await self._persist_risk_score(
            state, overall_score, risk_level, contributing_factors, agent_scores
        )

        # ── Step 7: Update AgentState ─────────────────────────────────────────
        state.overall_score = overall_score
        state.risk_tier = risk_level.lower()
        state.shared_metadata["risk_scoring_result"] = result.model_dump()
        state.shared_metadata["risk_scoring_audit"] = audit.model_dump()
        state.shared_metadata["overall_score"] = overall_score
        state.shared_metadata["risk_level"] = risk_level
        state.shared_metadata["contributing_factors"] = [
            f.model_dump() for f in contributing_factors
        ]
        state.shared_metadata["risk_explanation"] = explanation

        state.logs.append(
            f"RiskScoringAgent: overall_score={overall_score}, risk_level={risk_level}. "
            f"Top factors: {top_signal_names}"
        )

        return {
            "_status": "success",
            "_reason": f"Risk scoring complete. Score={overall_score}, Level={risk_level}",
            "confidence": 1.0,
            "risk_score": overall_score,
            "risk_level": risk_level.lower(),
            "findings": [explanation],
            "warnings": [],
            "recommendations": self._build_recommendations(risk_level),
            "errors": [],
            # Metadata
            "overall_score": overall_score,
            "risk_level": risk_level,
            "contributing_factors": [f.model_dump() for f in contributing_factors],
            "explanation": explanation,
            "weights_used": dict(RISK_WEIGHTS),
            "audit_trail": audit.model_dump(),
        }

    # ── Private Helpers ───────────────────────────────────────────────────────
    def _explain_factor(
        self, signal: str, agent_score: float, contribution: float
    ) -> str:
        """Generates a human-readable explanation for a single contributing factor."""
        if contribution <= 0:
            return f"{signal.upper()} check: All clear (score {agent_score:.0f}/100). No risk contribution."
        pct = round((contribution / RISK_WEIGHTS.get(signal, 1)) * 100)
        return (
            f"{signal.upper()} check: Agent score {agent_score:.0f}/100 "
            f"→ {pct}% of maximum weight triggered ({contribution:.1f} risk points)."
        )

    def _build_explanation(
        self, score: float, level: str, top_signals: List[str]
    ) -> str:
        """Constructs a concise overall narrative for the risk score."""
        if not top_signals:
            return (
                f"Overall risk score: {score:.1f}/100 ({level}). "
                "All screening signals returned clear results."
            )
        signals_str = ", ".join(top_signals)
        return (
            f"Overall risk score: {score:.1f}/100 ({level}). "
            f"Primary risk contributors: {signals_str}. "
            f"{'Immediate review required.' if level == 'HIGH' else 'Standard monitoring applies.' if level == 'MEDIUM' else 'No elevated concerns identified.'}"
        )

    def _build_recommendations(self, risk_level: str) -> List[str]:
        if risk_level == "HIGH":
            return [
                "Escalate to senior compliance officer immediately.",
                "Conduct Enhanced Due Diligence (EDD).",
                "Consider SAR filing if evidence of money laundering exists.",
            ]
        if risk_level == "MEDIUM":
            return [
                "Schedule standard Enhanced Due Diligence review.",
                "Increase transaction monitoring frequency.",
            ]
        return [
            "Continue standard monitoring. Schedule next review per monitoring schedule."
        ]

    async def _persist_risk_score(
        self,
        state: AgentState,
        overall_score: float,
        risk_level: str,
        contributing_factors: List[ContributingFactor],
        agent_scores: Dict[str, float],
    ) -> None:
        """Persists RiskScore record to the database if a DB session is available (supports Async and Sync)."""
        if not self.db:
            logger.warning(
                "RiskScoringAgent: No DB session — skipping risk_score persistence."
            )
            return
        try:
            from uuid import UUID
            from sqlalchemy.ext.asyncio import AsyncSession
            from sqlalchemy import select
            from app.models.models import RiskScore, KYCProfile

            cust_uuid = UUID(state.customer_id)
            breakdown = {
                f.signal: {
                    "weight": f.weight,
                    "agent_score": f.agent_score,
                    "contribution": f.contribution,
                }
                for f in contributing_factors
            }
            record = RiskScore(
                customer_id=cust_uuid,
                overall_score=overall_score,
                risk_tier=risk_level.lower(),
                breakdown=breakdown,
            )
            self.db.add(record)

            if isinstance(self.db, AsyncSession):
                res = await self.db.execute(select(KYCProfile).where(KYCProfile.customer_id == cust_uuid))
                kyc = res.scalars().first()
                if kyc:
                    kyc.risk_category = risk_level.lower()
                    kyc.screening_completed_at = datetime.utcnow()
                await self.db.commit()
            else:
                kyc = (
                    self.db.query(KYCProfile)
                    .filter(KYCProfile.customer_id == cust_uuid)
                    .first()
                )
                if kyc:
                    kyc.risk_category = risk_level.lower()
                    kyc.screening_completed_at = datetime.utcnow()
                self.db.commit()

            logger.info(
                f"RiskScoringAgent: Risk score persisted for customer {state.customer_id}."
            )
        except Exception as exc:
            logger.error(f"RiskScoringAgent: Failed to persist risk score: {exc}")
            try:
                if isinstance(self.db, AsyncSession):
                    await self.db.rollback()
                else:
                    self.db.rollback()
            except Exception:
                pass
