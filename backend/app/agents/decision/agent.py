"""
Decision Agent
===============
Makes the final compliance decision based on aggregated risk signals.

Decision values:
  APPROVE       — Score LOW (<= 30), no blocks, no PEP/sanctions confirmed
  MANUAL_REVIEW — Score MEDIUM (31–70), PEP possible, grey-list exposure
  EDD_REQUIRED  — Score MEDIUM/HIGH + EDD triggers
  REJECT        — Score HIGH (> 70), confirmed sanctions/blacklist/block triggers

Decision logic is deterministic and rule-based (no LLM). Writes to state.final_decision.
"""

import time
import logging
from datetime import datetime
from typing import Dict, Any, List

from app.agents.base.base_agent import BaseAgent
from app.agents.base.agent_state import AgentState
from app.agents.base.registry import AgentRegistry
from app.agents.base.exceptions import AgentValidationError

logger = logging.getLogger(__name__)

# Decision constants
DECISION_APPROVE       = "APPROVE"
DECISION_MANUAL_REVIEW = "MANUAL_REVIEW"
DECISION_EDD_REQUIRED  = "EDD_REQUIRED"
DECISION_REJECT        = "REJECT"

# Thresholds
APPROVE_MAX_SCORE  = 30.0
MEDIUM_MAX_SCORE   = 70.0


@AgentRegistry.register("decision_agent")
class DecisionAgent(BaseAgent):
    """
    Decision Agent.
    Makes the final compliance decision: APPROVE / MANUAL_REVIEW / EDD_REQUIRED / REJECT.
    """

    def get_name(self) -> str:
        return "decision_agent"

    def get_version(self) -> str:
        return "1.0.0"

    def get_description(self) -> str:
        return (
            "Final decision agent. Determines APPROVE / MANUAL_REVIEW / EDD_REQUIRED / REJECT "
            "based on risk score, policy violations, sanctions, PEP, and transaction behaviour."
        )

    def get_capabilities(self) -> List[str]:
        return [
            "final_decision_making",
            "risk_score_evaluation",
            "policy_violation_check",
            "sanctions_pep_check",
            "transaction_behavior_check",
            "decision_reason_generation",
        ]

    def validate_input(self, state: AgentState) -> bool:
        if not state.customer_id:
            raise AgentValidationError(
                message="customer_id missing in AgentState. Cannot run DecisionAgent.",
                details={"customer_id": None},
            )
        return True

    async def process(self, state: AgentState) -> Dict[str, Any]:
        start_time = time.perf_counter()
        state.logs.append(f"[{self.get_name()}] Making final compliance decision...")

        sm = state.shared_metadata

        # ── Collect decision signals ──────────────────────────────────────────
        overall_score      = state.overall_score
        risk_level         = sm.get("risk_level") or state.risk_tier.upper()
        sanctions_status   = sm.get("sanctions_status",  "CLEAR")
        pep_status         = sm.get("pep_status",        "CLEAR")
        fatf_black_listed  = sm.get("fatf_black_listed", [])
        block_triggers     = sm.get("regulation_block_triggers", [])
        edd_triggers       = sm.get("regulation_edd_triggers",   [])
        violations         = sm.get("regulation_violations",     [])
        tx_status          = sm.get("transaction_status",        "CLEAR")
        behavior_flags     = sm.get("account_behavior_flags",    {})

        is_confirmed_sanctions = str(sanctions_status).upper() == "CONFIRMED"
        is_confirmed_pep       = str(pep_status).upper() == "CONFIRMED_PEP"
        has_block_triggers     = len(block_triggers) > 0
        has_edd_triggers       = len(edd_triggers) > 0
        has_mule_indicators    = behavior_flags.get("mule_indicators", False)
        has_fatf_blacklist     = len(fatf_black_listed) > 0

        # ── Decision logic (priority order) ──────────────────────────────────
        decision = DECISION_APPROVE
        reasons: List[str] = []

        # 1. REJECT conditions (highest priority)
        if has_block_triggers or is_confirmed_sanctions or has_fatf_blacklist:
            decision = DECISION_REJECT
            if is_confirmed_sanctions:
                reasons.append("Confirmed sanctions match detected.")
            if has_block_triggers:
                reasons.append(f"Block policy triggers: {', '.join(block_triggers)}.")
            if has_fatf_blacklist:
                reasons.append(f"FATF black-listed jurisdiction: {', '.join(fatf_black_listed)}.")

        # 2. EDD REQUIRED
        elif has_edd_triggers or (overall_score > MEDIUM_MAX_SCORE):
            decision = DECISION_EDD_REQUIRED
            if overall_score > MEDIUM_MAX_SCORE:
                reasons.append(f"Overall risk score {overall_score:.1f}/100 exceeds HIGH threshold.")
            if has_edd_triggers:
                reasons.append(f"EDD triggers: {', '.join(edd_triggers)}.")
            if is_confirmed_pep:
                reasons.append("Confirmed PEP status requires Enhanced Due Diligence.")
            if has_mule_indicators:
                reasons.append("Mule account indicators detected in transaction behaviour.")

        # 3. MANUAL REVIEW
        elif (
            overall_score > APPROVE_MAX_SCORE
            or pep_status in ("CONFIRMED_PEP", "POSSIBLE_MATCH")
            or sanctions_status == "POSSIBLE_MATCH"
            or len(violations) > 0
        ):
            decision = DECISION_MANUAL_REVIEW
            if overall_score > APPROVE_MAX_SCORE:
                reasons.append(f"Risk score {overall_score:.1f}/100 in MEDIUM range — manual review required.")
            if pep_status not in ("CLEAR", "UNKNOWN"):
                reasons.append(f"PEP status: {pep_status} — requires human review.")
            if sanctions_status == "POSSIBLE_MATCH":
                reasons.append("Possible sanctions match — human review required.")
            if len(violations) > 0:
                reasons.append(f"{len(violations)} policy violation(s) require compliance officer review.")

        # 4. APPROVE
        else:
            decision = DECISION_APPROVE
            reasons.append(
                f"Risk score {overall_score:.1f}/100 within acceptable range. "
                "No blocks, sanctions, or PEP matches. All checks passed."
            )

        decision_reason = " | ".join(reasons)

        # ── Determine customer status ─────────────────────────────────────────
        customer_status_map = {
            DECISION_APPROVE:       "approved",
            DECISION_MANUAL_REVIEW: "referred",
            DECISION_EDD_REQUIRED:  "under_review",
            DECISION_REJECT:        "rejected",
        }
        new_customer_status = customer_status_map.get(decision, "referred")

        execution_duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        # ── Update AgentState ─────────────────────────────────────────────────
        state.final_decision  = decision
        state.decision_reason = decision_reason
        state.shared_metadata["final_decision"]     = decision
        state.shared_metadata["decision_reason"]    = decision_reason
        state.shared_metadata["customer_status"]    = new_customer_status

        # ── Persist to DB ─────────────────────────────────────────────────────
        self._persist_decision(state, decision, new_customer_status, decision_reason)

        state.logs.append(
            f"DecisionAgent: DECISION={decision}. Score={overall_score:.1f}. "
            f"Reason: {decision_reason[:100]}..."
        )

        return {
            "_status": "success",
            "_reason": f"Decision made: {decision}",
            "confidence": 1.0,
            "risk_score": overall_score,
            "risk_level": risk_level.lower(),
            "findings": [f"Final decision: {decision}. {decision_reason}"],
            "warnings": [],
            "recommendations": self._decision_recommendations(decision, edd_triggers, block_triggers),
            "errors": [],
            # Metadata
            "final_decision":      decision,
            "decision_reason":     decision_reason,
            "customer_status":     new_customer_status,
            "signals_evaluated": {
                "overall_score":     overall_score,
                "sanctions_status":  sanctions_status,
                "pep_status":        pep_status,
                "block_triggers":    block_triggers,
                "edd_triggers":      edd_triggers,
                "violations_count":  len(violations),
                "mule_indicators":   has_mule_indicators,
                "fatf_blacklisted":  has_fatf_blacklist,
            },
            "execution_duration_ms": execution_duration_ms,
        }

    def _persist_decision(
        self, state: AgentState, decision: str, status: str, reason: str
    ) -> None:
        """Updates customer and case status in the database."""
        if not self.db:
            return
        try:
            from uuid import UUID
            from app.models.models import Customer, Case, Alert
            cust_uuid = UUID(state.customer_id)

            # Update customer status
            customer = self.db.query(Customer).filter(Customer.id == cust_uuid).first()
            if customer:
                customer.status = status

            # Update case status and notes
            case_id_raw = state.shared_metadata.get("case_id") or state.case_id
            if case_id_raw:
                case = self.db.query(Case).filter(Case.id == UUID(str(case_id_raw))).first()
                if case:
                    case.status = "resolved_auto" if decision == DECISION_APPROVE else "open"
                    case.investigation_notes = (
                        (case.investigation_notes or "") +
                        f"\n[Decision Agent] {datetime.utcnow().isoformat()}: {decision} — {reason}"
                    )

            # Create alert for non-approve decisions
            if decision != DECISION_APPROVE:
                alert = Alert(
                    customer_id=cust_uuid,
                    alert_type=f"decision_{decision.lower()}",
                    risk_score=state.overall_score,
                    status="open",
                    alert_metadata={
                        "decision": decision,
                        "reason": reason,
                        "risk_level": state.risk_tier,
                    },
                )
                self.db.add(alert)

            self.db.commit()
        except Exception as exc:
            logger.error(f"DecisionAgent: DB persistence failed: {exc}")
            try:
                self.db.rollback()
            except Exception:
                pass

    @staticmethod
    def _decision_recommendations(
        decision: str, edd_triggers: List[str], block_triggers: List[str]
    ) -> List[str]:
        if decision == DECISION_REJECT:
            return [
                "Freeze account immediately.",
                "Escalate to senior compliance officer.",
                "File SAR if required by regulation.",
                f"Block triggers: {', '.join(block_triggers)}." if block_triggers else "",
            ]
        if decision == DECISION_EDD_REQUIRED:
            return [
                "Assign to compliance officer for Enhanced Due Diligence.",
                "Do not onboard until EDD is complete.",
                f"EDD triggers: {', '.join(edd_triggers)}." if edd_triggers else "",
            ]
        if decision == DECISION_MANUAL_REVIEW:
            return [
                "Assign case to compliance officer for manual review within 5 business days.",
                "Do not grant full access until review is complete.",
            ]
        return [
            "Proceed with standard onboarding.",
            "Apply monitoring schedule as per risk tier.",
        ]
