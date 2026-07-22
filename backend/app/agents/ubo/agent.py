"""
UBO Verification Agent
=======================
Verifies Ultimate Beneficial Owners (UBOs) for corporate customers.

Checks:
  1. Total ownership percentage (warn if < 75% disclosed)
  2. Individual UBO ownership threshold (flag if any UBO > 25% unverified)
  3. Missing or incomplete UBO records
  4. Circular ownership detection (UBO who is also a company)
  5. Unverified UBO status

Only runs for corporate (business) customers. Skips for individuals.
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

# ── Constants ─────────────────────────────────────────────────────────────────
UBO_DISCLOSURE_THRESHOLD = 75.0  # Minimum % of ownership that must be disclosed
UBO_SIGNIFICANT_STAKE = 25.0  # Significant ownership threshold
UBO_CIRCULAR_INDICATOR = "company"  # control_type value suggesting circular ownership


@AgentRegistry.register("ubo_verification_agent")
class UBOVerificationAgent(BaseAgent):
    """
    UBO Verification Agent.
    Validates Ultimate Beneficial Owners for corporate customers.
    """

    def get_name(self) -> str:
        return "ubo_verification_agent"

    def get_version(self) -> str:
        return "1.0.0"

    def get_description(self) -> str:
        return (
            "UBO verification agent. Validates ownership disclosure, significant stakes, "
            "missing owners, and circular ownership for corporate customers."
        )

    def get_capabilities(self) -> List[str]:
        return [
            "ubo_ownership_percentage_check",
            "missing_ubo_detection",
            "circular_ownership_detection",
            "ubo_verification_status_check",
            "significant_stake_check",
        ]

    def validate_input(self, state: AgentState) -> bool:
        if not state.customer_id:
            raise AgentValidationError(
                message="customer_id missing in AgentState. Cannot run UBOVerificationAgent.",
                details={"customer_id": None},
            )
        return True

    async def process(self, state: AgentState) -> Dict[str, Any]:
        start_time = time.perf_counter()
        state.logs.append(f"[{self.get_name()}] Starting UBO verification...")

        customer_type = (
            str((state.customer or {}).get("customer_type") or "").strip().lower()
        )

        # Skip for individual customers
        if customer_type not in ("corporate", "business", "company"):
            skip_msg = "UBO verification not applicable for individual customers."
            state.logs.append(f"UBOVerificationAgent: SKIPPED — {skip_msg}")
            state.shared_metadata["ubo_score"] = 100.0
            state.risk_breakdown["ubo"] = 100.0
            return {
                "_status": "success",
                "_reason": skip_msg,
                "confidence": 1.0,
                "risk_score": 100.0,
                "risk_level": "low",
                "findings": [skip_msg],
                "warnings": [],
                "recommendations": [],
                "errors": [],
                "ubo_score": 100.0,
                "skipped": True,
            }

        ubos: List[Dict[str, Any]] = state.ubos or []
        findings: List[str] = []
        warnings: List[str] = []
        errors: List[str] = []
        recommendations: List[str] = []

        # ── Check 1: UBO records present ──────────────────────────────────────
        if not ubos:
            errors.append("No UBO records found for corporate customer.")
            recommendations.append(
                "Collect and verify Ultimate Beneficial Owner information (>25% stake holders)."
            )
            state.shared_metadata["ubo_score"] = 0.0
            state.risk_breakdown["ubo"] = 0.0
            execution_duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            state.logs.append("UBOVerificationAgent: No UBO records — score=0.")
            return self._build_result(
                score=0.0,
                risk_level="high",
                findings=findings,
                warnings=warnings,
                errors=errors,
                recommendations=recommendations,
                ubos_checked=0,
                total_ownership=0.0,
                circular_count=0,
                unverified_count=0,
                execution_duration_ms=execution_duration_ms,
                state=state,
            )

        # ── Check 2: Total ownership disclosure ───────────────────────────────
        total_ownership = sum(float(u.get("ownership_percentage") or 0) for u in ubos)
        if total_ownership < UBO_DISCLOSURE_THRESHOLD:
            warnings.append(
                f"Incomplete UBO disclosure: only {total_ownership:.1f}% of ownership accounted for "
                f"(threshold: {UBO_DISCLOSURE_THRESHOLD}%)."
            )
            recommendations.append(
                "Request additional UBO disclosures to reach full ownership transparency."
            )
        else:
            findings.append(
                f"UBO ownership disclosure adequate: {total_ownership:.1f}% disclosed."
            )

        # ── Check 3: Significant stake holders ───────────────────────────────
        unverified_count = 0
        circular_count = 0

        for ubo in ubos:
            name = f"{ubo.get('first_name','')} {ubo.get('last_name','')}".strip()
            pct = float(ubo.get("ownership_percentage") or 0)
            status = str(ubo.get("verification_status") or "").lower()
            control_type = str(ubo.get("control_type") or "").lower()

            if pct >= UBO_SIGNIFICANT_STAKE and status not in ("verified", "approved"):
                unverified_count += 1
                errors.append(
                    f"UBO '{name}' holds {pct:.1f}% stake but verification status is '{status}'."
                )

            # ── Check 4: Circular ownership ───────────────────────────────────
            if UBO_CIRCULAR_INDICATOR in control_type:
                circular_count += 1
                warnings.append(
                    f"Possible circular ownership: UBO '{name}' has control_type '{control_type}', "
                    "suggesting corporate intermediary ownership."
                )

        if unverified_count > 0:
            recommendations.append(
                f"Verify {unverified_count} UBO(s) holding significant stakes."
            )
        if circular_count > 0:
            recommendations.append(
                "Investigate potential circular ownership structures and trace ultimate beneficial owners."
            )

        if unverified_count == 0 and circular_count == 0:
            findings.append(
                "All UBOs with significant stakes are verified. No circular ownership detected."
            )

        # ── Score calculation ─────────────────────────────────────────────────
        score = 100.0
        if total_ownership < UBO_DISCLOSURE_THRESHOLD:
            score -= 20.0
        score -= unverified_count * 15.0
        score -= circular_count * 10.0
        score = round(max(0.0, min(100.0, score)), 2)
        risk_level = "high" if score < 40 else "medium" if score < 70 else "low"

        execution_duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        state.logs.append(
            f"UBOVerificationAgent: {len(ubos)} UBO(s) checked, total ownership={total_ownership:.1f}%. "
            f"Score={score}, Risk={risk_level}."
        )

        return self._build_result(
            score=score,
            risk_level=risk_level,
            findings=findings,
            warnings=warnings,
            errors=errors,
            recommendations=recommendations,
            ubos_checked=len(ubos),
            total_ownership=total_ownership,
            circular_count=circular_count,
            unverified_count=unverified_count,
            execution_duration_ms=execution_duration_ms,
            state=state,
        )

    def _build_result(
        self,
        score: float,
        risk_level: str,
        findings: List[str],
        warnings: List[str],
        errors: List[str],
        recommendations: List[str],
        ubos_checked: int,
        total_ownership: float,
        circular_count: int,
        unverified_count: int,
        execution_duration_ms: float,
        state: AgentState,
    ) -> Dict[str, Any]:
        state.risk_breakdown["ubo"] = score
        state.shared_metadata["ubo_score"] = score
        state.shared_metadata["ubo_risk"] = risk_level
        state.shared_metadata["ubo_total_ownership"] = total_ownership
        state.shared_metadata["ubo_unverified"] = unverified_count
        state.shared_metadata["ubo_circular"] = circular_count

        return {
            "_status": "success",
            "_reason": f"UBO verification complete. Score={score}",
            "confidence": score / 100.0,
            "risk_score": score,
            "risk_level": risk_level,
            "findings": findings,
            "warnings": warnings,
            "recommendations": recommendations,
            "errors": errors,
            "ubo_score": score,
            "ubos_checked": ubos_checked,
            "total_ownership_pct": total_ownership,
            "unverified_significant_stakes": unverified_count,
            "circular_ownership_flags": circular_count,
            "execution_duration_ms": execution_duration_ms,
        }
