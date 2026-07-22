"""
Regulation Agent
=================
Reads active policy rules from the database and applies them against
the current AgentState to detect AML, KYC, EDD, and internal policy violations.

Policy Rule Types:
  - 'threshold'  : Score or value exceeds a numeric threshold
  - 'block'      : Absolute block condition (sanctions, PEP, blacklist)
  - 'edd'        : Enhanced Due Diligence trigger
  - 'aml'        : AML-specific rule
  - 'kyc'        : KYC completeness rule
  - 'internal'   : Internal bank policy rule

Rules are loaded from the `policy_rules` table (is_active=True).
"""

import time
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

from app.agents.base.base_agent import BaseAgent
from app.agents.base.agent_state import AgentState
from app.agents.base.registry import AgentRegistry
from app.agents.base.exceptions import AgentValidationError

logger = logging.getLogger(__name__)


@AgentRegistry.register("regulation_agent")
class RegulationAgent(BaseAgent):
    """
    Regulation Agent.
    Applies active policy rules to the AgentState and returns violations.
    """

    def get_name(self) -> str:
        return "regulation_agent"

    def get_version(self) -> str:
        return "1.0.0"

    def get_description(self) -> str:
        return (
            "Regulation compliance agent. Reads active policy rules from the database "
            "and applies AML/KYC/EDD/internal rules against the current case state. "
            "Returns all policy violations."
        )

    def get_capabilities(self) -> List[str]:
        return [
            "policy_rule_evaluation",
            "aml_policy_check",
            "kyc_policy_check",
            "edd_trigger_detection",
            "threshold_rule_check",
            "block_rule_check",
            "internal_rule_check",
        ]

    def validate_input(self, state: AgentState) -> bool:
        if not state.customer_id:
            raise AgentValidationError(
                message="customer_id missing in AgentState. Cannot run RegulationAgent.",
                details={"customer_id": None},
            )
        return True

    async def process(self, state: AgentState) -> Dict[str, Any]:
        start_time = time.perf_counter()
        state.logs.append(
            f"[{self.get_name()}] Starting regulation compliance check..."
        )

        # ── Load policy rules ─────────────────────────────────────────────────
        policy_rules = self._load_policy_rules(state)

        findings: List[str] = []
        warnings: List[str] = []
        violations: List[Dict[str, Any]] = []
        edd_triggers: List[str] = []
        block_triggers: List[str] = []
        recommendations: List[str] = []

        # ── Apply each active rule ────────────────────────────────────────────
        for rule in policy_rules:
            result = self._apply_rule(rule, state)
            if result["violated"]:
                violations.append(
                    {
                        "rule_name": rule.get("rule_name", "Unknown"),
                        "rule_type": rule.get("rule_type", ""),
                        "reason": result["reason"],
                        "severity": rule.get("severity")
                        or result.get("severity", "medium"),
                        "description": rule.get("description") or "",
                    }
                )
                rule_type = str(rule.get("rule_type") or "").lower()
                if rule_type == "block":
                    block_triggers.append(rule.get("rule_name", "Unknown"))
                    findings.append(
                        f"BLOCK RULE TRIGGERED: {rule.get('rule_name')} — {result['reason']}"
                    )
                elif rule_type == "edd":
                    edd_triggers.append(rule.get("rule_name", "Unknown"))
                    warnings.append(
                        f"EDD REQUIRED: {rule.get('rule_name')} — {result['reason']}"
                    )
                else:
                    warnings.append(
                        f"Policy violation ({rule_type.upper()}): {rule.get('rule_name')} — {result['reason']}"
                    )
            else:
                findings.append(f"Rule passed: {rule.get('rule_name', 'Unknown')}")

        if not violations:
            findings.append("All active policy rules passed. No violations detected.")
        else:
            recommendations.append(
                f"{len(violations)} policy violation(s) detected. Review and remediate before approval."
            )
        if edd_triggers:
            recommendations.append(
                f"Enhanced Due Diligence required due to: {', '.join(edd_triggers)}."
            )
        if block_triggers:
            recommendations.append(
                f"Block conditions triggered. Customer cannot be approved: {', '.join(block_triggers)}."
            )

        # ── Score ─────────────────────────────────────────────────────────────
        violation_count = len(violations)
        block_count = len(block_triggers)
        edd_count = len(edd_triggers)

        score = (
            100.0 - (block_count * 40.0) - (edd_count * 20.0) - (violation_count * 5.0)
        )
        score = round(max(0.0, min(100.0, score)), 2)
        risk_level = (
            "high"
            if block_count > 0 or score < 40
            else "medium" if score < 70 else "low"
        )

        execution_duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        # Update state
        state.shared_metadata["regulation_violations"] = violations
        state.shared_metadata["regulation_edd_triggers"] = edd_triggers
        state.shared_metadata["regulation_block_triggers"] = block_triggers
        state.shared_metadata["regulation_score"] = score

        state.logs.append(
            f"RegulationAgent: {len(policy_rules)} rules evaluated, {violation_count} violation(s). "
            f"Blocks={block_count}, EDD={edd_count}. Score={score}, Risk={risk_level}."
        )

        return {
            "_status": "success",
            "_reason": f"Regulation check complete. {violation_count} violation(s) found.",
            "confidence": score / 100.0,
            "risk_score": score,
            "risk_level": risk_level,
            "findings": findings,
            "warnings": warnings,
            "recommendations": recommendations,
            "errors": [],
            # Metadata
            "regulation_score": score,
            "violations": violations,
            "edd_triggers": edd_triggers,
            "block_triggers": block_triggers,
            "rules_evaluated": len(policy_rules),
            "execution_duration_ms": execution_duration_ms,
        }

    # ── Private Helpers ───────────────────────────────────────────────────────
    def _load_policy_rules(self, state: AgentState) -> List[Dict[str, Any]]:
        """Loads active policy rules from DB or falls back to defaults."""
        # Use pre-loaded policies from AgentState if available
        if state.policies:
            return state.policies

        # Attempt DB load if session available
        if self.db:
            try:
                from app.models.models import PolicyRule

                rules = (
                    self.db.query(PolicyRule).filter(PolicyRule.is_active == True).all()
                )
                return [
                    {
                        "rule_name": r.rule_name,
                        "rule_type": r.rule_type,
                        "conditions": r.conditions,
                        "severity": r.severity,
                        "description": r.description,
                        "expression": r.expression,
                        "threshold": float(r.threshold) if r.threshold else None,
                        "country": r.country,
                        "version": r.version,
                    }
                    for r in rules
                ]
            except Exception as exc:
                logger.warning(
                    f"RegulationAgent: Could not load policy rules from DB: {exc}"
                )

        # Built-in default rules (fallback)
        return self._default_rules()

    def _apply_rule(self, rule: Dict[str, Any], state: AgentState) -> Dict[str, Any]:
        """Applies a single policy rule against AgentState. Returns violated=True if breached."""
        rule_type = str(rule.get("rule_type") or "").lower()
        conditions = rule.get("conditions") or {}
        rule_name = rule.get("rule_name", "Unknown")

        try:
            if rule_type == "block":
                return self._apply_block_rule(rule_name, conditions, state)
            elif rule_type == "edd":
                return self._apply_edd_rule(rule_name, conditions, state)
            elif rule_type in ("threshold", "aml", "kyc", "internal"):
                return self._apply_threshold_rule(rule_name, conditions, state)
            else:
                return {"violated": False, "reason": "Unknown rule type — skipped."}
        except Exception as exc:
            logger.error(f"RegulationAgent: Error applying rule '{rule_name}': {exc}")
            return {"violated": False, "reason": f"Rule evaluation error: {exc}"}

    def _apply_block_rule(
        self, rule_name: str, conditions: Dict, state: AgentState
    ) -> Dict[str, Any]:
        """Evaluates BLOCK-type rules (absolute prohibition)."""
        sm = state.shared_metadata
        # Sanctions confirmed block
        if (
            conditions.get("sanctions_confirmed")
            and sm.get("sanctions_status") == "CONFIRMED"
        ):
            return {
                "violated": True,
                "reason": "Confirmed sanctions match — account must be blocked.",
                "severity": "critical",
            }
        # FATF black list
        if conditions.get("fatf_blacklist") and sm.get("fatf_black_listed"):
            return {
                "violated": True,
                "reason": f"Customer connected to FATF black-listed jurisdiction.",
                "severity": "critical",
            }
        return {"violated": False, "reason": "Block conditions not triggered."}

    def _apply_edd_rule(
        self, rule_name: str, conditions: Dict, state: AgentState
    ) -> Dict[str, Any]:
        """Evaluates EDD-type rules."""
        sm = state.shared_metadata
        # PEP confirmed EDD trigger
        if conditions.get("pep_confirmed") and sm.get("pep_status") == "CONFIRMED_PEP":
            return {
                "violated": True,
                "reason": "PEP status confirmed — Enhanced Due Diligence required.",
                "severity": "high",
            }
        # Risk score threshold
        threshold = conditions.get("overall_score_threshold")
        if threshold is not None and state.overall_score >= float(threshold):
            return {
                "violated": True,
                "reason": f"Overall risk score {state.overall_score:.1f} exceeds EDD threshold {threshold}.",
                "severity": "high",
            }
        # High-risk country
        if conditions.get("high_risk_country") and sm.get("high_risk_countries"):
            return {
                "violated": True,
                "reason": "High-risk jurisdiction connection triggers EDD.",
                "severity": "high",
            }
        return {"violated": False, "reason": "EDD conditions not triggered."}

    def _apply_threshold_rule(
        self, rule_name: str, conditions: Dict, state: AgentState
    ) -> Dict[str, Any]:
        """Evaluates threshold/AML/KYC/internal rules."""
        sm = state.shared_metadata
        threshold = conditions.get("score_threshold")
        signal = conditions.get("signal")
        if threshold is not None and signal:
            score = sm.get(f"{signal}_score") or state.risk_breakdown.get(signal, 100)
            if float(score) < float(threshold):
                return {
                    "violated": True,
                    "reason": f"{signal.upper()} score {score:.1f} is below minimum threshold {threshold}.",
                    "severity": "medium",
                }
        # Transaction amount
        max_tx = conditions.get("max_transaction_amount")
        if max_tx is not None:
            txs = state.transactions or []
            large = [t for t in txs if float(t.get("amount") or 0) > float(max_tx)]
            if large:
                return {
                    "violated": True,
                    "reason": f"{len(large)} transaction(s) exceed maximum allowed amount £{max_tx:,.0f}.",
                    "severity": "medium",
                }
        return {"violated": False, "reason": "Threshold conditions not triggered."}

    @staticmethod
    def _default_rules() -> List[Dict[str, Any]]:
        """Built-in fallback rules applied when no policy rules exist in DB."""
        return [
            {
                "rule_name": "SANCTIONS_BLOCK",
                "rule_type": "block",
                "conditions": {"sanctions_confirmed": True},
            },
            {
                "rule_name": "FATF_BLACKLIST_BLOCK",
                "rule_type": "block",
                "conditions": {"fatf_blacklist": True},
            },
            {
                "rule_name": "PEP_EDD",
                "rule_type": "edd",
                "conditions": {"pep_confirmed": True},
            },
            {
                "rule_name": "HIGH_RISK_SCORE_EDD",
                "rule_type": "edd",
                "conditions": {"overall_score_threshold": 70},
            },
            {
                "rule_name": "HIGH_RISK_COUNTRY_EDD",
                "rule_type": "edd",
                "conditions": {"high_risk_country": True},
            },
            {
                "rule_name": "DOCUMENT_COMPLETENESS",
                "rule_type": "kyc",
                "conditions": {"signal": "document", "score_threshold": 50},
            },
        ]
