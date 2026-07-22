"""
Transaction Agent
==================
Evaluates behavioral transaction risk using deterministic checks.
Identifies structuring, velocity anomalies, large values, high-risk countries,
pass-through transfers, cash intensity, and reactivation.
Processes all available transactions and updates AgentState.
"""

import time
from datetime import datetime
from typing import Dict, Any, List, Optional

from app.agents.base.base_agent import BaseAgent
from app.agents.base.agent_state import AgentState
from app.agents.base.registry import AgentRegistry
from app.agents.base.exceptions import AgentValidationError

from app.agents.transaction.constants import (
    RISK_LOW,
    NEXT_AGENT,
    TRANSACTION_STATUS_CLEAR,
)
from app.agents.transaction.models import TransactionAuditTrail
from app.agents.transaction.validator import TransactionValidator
from app.agents.transaction.analyzer import TransactionAnalyzer
from app.agents.transaction.rules import TransactionRulesEngine
from app.agents.transaction.risk_calculator import TransactionRiskCalculator


@AgentRegistry.register("transaction_agent")
class TransactionAgent(BaseAgent):
    """
    Transaction Agent — Performs behavioral risk analysis on customer transactions.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    # ── Agent Metadata ────────────────────────────────────────────────────────
    def get_name(self) -> str:
        return "transaction_agent"

    def get_version(self) -> str:
        return "1.0.0"

    def get_description(self) -> str:
        return (
            "Deterministic behavioral AML analysis agent. Evaluates transactions for structuring, "
            "velocity, large transfers, cash behavior, and jurisdictional exposure."
        )

    def get_capabilities(self) -> List[str]:
        return [
            "transaction_validation",
            "pattern_analysis",
            "structuring_detection",
            "velocity_scoring",
            "large_value_check",
            "rapid_in_out_check",
            "dormant_reactivation_check",
            "cash_intensive_check",
            "rules_evaluation",
            "langgraph_routing_output",
        ]

    # ── Input Validation ──────────────────────────────────────────────────────
    def validate_input(self, state: AgentState) -> bool:
        """
        Requires customer profile. Lack of transactions is handled as a warning, not failure.
        """
        if not state.customer:
            raise AgentValidationError(
                message="Customer profile is missing in AgentState. Cannot run Transaction Agent.",
                details={"customer": None},
            )
        return True

    # ── Core Processing ───────────────────────────────────────────────────────
    async def process(self, state: AgentState) -> Dict[str, Any]:
        start_time = time.perf_counter()
        state.logs.append(f"[{self.get_name()}] Starting transaction analysis...")

        # ── Step 1: Validate and Normalize Transactions ───────────────────────
        raw_txs = state.transactions or []
        valid_records, val_warnings, val_errors = (
            TransactionValidator.validate_and_normalize(raw_txs)
        )

        # ── Step 2: Extract country risk contexts from Country Risk Agent ─────
        high_risk_countries = state.shared_metadata.get("high_risk_countries") or []
        prohibited_countries = state.shared_metadata.get("prohibited_countries") or []

        # ── Step 3: Run Pattern Analyzer ──────────────────────────────────────
        pattern_results = TransactionAnalyzer.analyze(
            transactions=valid_records,
            high_risk_countries=high_risk_countries,
            prohibited_countries=prohibited_countries,
        )

        triggered_patterns = [p for p in pattern_results if p.triggered]

        # ── Step 4: Run Business Rules ────────────────────────────────────────
        eval_result = TransactionRulesEngine.evaluate(pattern_results)

        tx_status = eval_result["transaction_status"]
        findings = eval_result["findings"]
        warnings = eval_result["warnings"] + val_warnings
        errors = val_errors
        recommendations = eval_result["recommendations"]
        rules_triggered = eval_result["rules_triggered"]

        # ── Step 5: Calculate Risk Score ──────────────────────────────────────
        tx_score, risk_level = TransactionRiskCalculator.calculate(triggered_patterns)

        execution_duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        # ── Step 6: Create Audit Trail ────────────────────────────────────────
        triggered_pattern_ids = [p.pattern_id for p in triggered_patterns]
        audit = TransactionAuditTrail(
            validation_timestamp=datetime.utcnow().isoformat(),
            execution_duration_ms=execution_duration_ms,
            transactions_analysed=len(valid_records),
            patterns_triggered=triggered_pattern_ids,
            rules_triggered=rules_triggered,
            risk_score=tx_score,
            risk_level=risk_level,
            recommendations=recommendations,
        )

        # Calculate metrics for metadata
        amounts = [r.amount for r in valid_records]
        avg_val = round(sum(amounts) / len(amounts), 2) if amounts else 0.0
        max_val = max(amounts) if amounts else 0.0
        min_val = min(amounts) if amounts else 0.0
        speed = (
            round(len(valid_records) / (execution_duration_ms / 1000.0), 2)
            if execution_duration_ms > 0
            else 0.0
        )
        success_rate = round(len(valid_records) / len(raw_txs), 2) if raw_txs else 1.0

        metrics = {
            "transactions_analysed": len(valid_records),
            "patterns_triggered": len(triggered_patterns),
            "average_transaction_value": avg_val,
            "highest_transaction": max_val,
            "lowest_transaction": min_val,
            "execution_time_ms": execution_duration_ms,
            "processing_speed_tx_per_sec": speed,
            "success_rate": success_rate,
            "failure_rate": round(1.0 - success_rate, 2),
        }

        # ── Step 7: Update AgentState ─────────────────────────────────────────
        state.risk_breakdown["transaction"] = tx_score
        state.shared_metadata["transaction_status"] = tx_status
        state.shared_metadata["transaction_score"] = tx_score
        state.shared_metadata["transaction_risk"] = risk_level
        state.shared_metadata["transaction_findings"] = findings
        state.shared_metadata["transaction_alerts"] = [
            p.pattern_name for p in triggered_patterns
        ]
        state.shared_metadata["transaction_patterns"] = [
            p.model_dump() for p in pattern_results
        ]
        state.shared_metadata["transaction_recommendations"] = recommendations
        state.shared_metadata["transaction_audit"] = audit.model_dump()
        state.shared_metadata["next_agent"] = NEXT_AGENT

        # Update overall case risk tier if transaction risk is critical
        if risk_level == "critical":
            state.risk_tier = "critical"

        state.logs.append(
            f"TransactionAgent finished. Analysed: {len(valid_records)}, Score: {tx_score}, "
            f"Risk: {risk_level}, Status: {tx_status}. Routing to: {NEXT_AGENT}"
        )

        # ── Step 8: Return AgentResult compatible dict ────────────────────────
        return {
            "_status": "success",
            "_reason": f"Transaction behavioral analysis complete. Status: {tx_status}",
            "confidence": 1.0,
            "risk_score": tx_score,
            "risk_level": risk_level,
            "findings": findings,
            "warnings": warnings,
            "recommendations": recommendations,
            "errors": errors,
            # Metadata
            "transaction_status": tx_status,
            "transaction_score": tx_score,
            "rules_triggered": rules_triggered,
            "next_agent": NEXT_AGENT,
            "metrics": metrics,
            "audit_trail": audit.model_dump(),
        }
