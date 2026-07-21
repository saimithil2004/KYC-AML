"""
Director Verification Agent
============================
Validates directors associated with corporate customers.

Checks:
  1. Director completeness (required fields)
  2. Inactive directors (is_active = False)
  3. Unverified directors
  4. Nationality mismatch vs company incorporation country
  5. Minimum director count

Only applies to corporate/business customers.
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

REQUIRED_DIRECTOR_FIELDS = ["first_name", "last_name"]
MINIMUM_DIRECTORS         = 1


@AgentRegistry.register("director_verification_agent")
class DirectorVerificationAgent(BaseAgent):
    """
    Director Verification Agent.
    Validates corporate director records for completeness, activity, and nationality.
    """

    def get_name(self) -> str:
        return "director_verification_agent"

    def get_version(self) -> str:
        return "1.0.0"

    def get_description(self) -> str:
        return (
            "Director verification agent. Validates director completeness, "
            "activity status, verification status, and nationality against "
            "company incorporation country."
        )

    def get_capabilities(self) -> List[str]:
        return [
            "director_completeness_check",
            "inactive_director_detection",
            "director_verification_status_check",
            "nationality_mismatch_check",
            "minimum_director_count_check",
        ]

    def validate_input(self, state: AgentState) -> bool:
        if not state.customer_id:
            raise AgentValidationError(
                message="customer_id missing in AgentState. Cannot run DirectorVerificationAgent.",
                details={"customer_id": None},
            )
        return True

    async def process(self, state: AgentState) -> Dict[str, Any]:
        start_time = time.perf_counter()
        state.logs.append(f"[{self.get_name()}] Starting director verification...")

        customer_type = str((state.customer or {}).get("customer_type") or "").strip().lower()

        # Skip for individual customers
        if customer_type not in ("corporate", "business", "company"):
            skip_msg = "Director verification not applicable for individual customers."
            state.logs.append(f"DirectorVerificationAgent: SKIPPED — {skip_msg}")
            state.shared_metadata["director_score"] = 100.0
            state.risk_breakdown["director"] = 100.0
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
                "director_score": 100.0,
                "skipped": True,
            }

        directors: List[Dict[str, Any]] = state.directors or []
        companies:  List[Dict[str, Any]] = state.companies  or []
        company_country = str((companies[0] if companies else {}).get("country_of_incorporation") or "").strip().lower()

        findings:        List[str] = []
        warnings:        List[str] = []
        errors:          List[str] = []
        recommendations: List[str] = []

        # ── Check: Minimum director count ─────────────────────────────────────
        if len(directors) < MINIMUM_DIRECTORS:
            errors.append(
                f"Insufficient directors: {len(directors)} found, minimum is {MINIMUM_DIRECTORS}."
            )
            recommendations.append("Add at least one active director to the corporate record.")

        inactive_count   = 0
        unverified_count = 0
        incomplete_count = 0
        nationality_mismatch_count = 0

        for director in directors:
            first  = str(director.get("first_name") or "").strip()
            last   = str(director.get("last_name")  or "").strip()
            name   = f"{first} {last}".strip() or "Unknown"
            is_active  = director.get("is_active", True)
            status     = str(director.get("verification_status") or "").lower()
            nationality = str(director.get("nationality") or "").strip().lower()

            # ── Completeness check ────────────────────────────────────────────
            missing = [f for f in REQUIRED_DIRECTOR_FIELDS if not director.get(f)]
            if missing:
                incomplete_count += 1
                warnings.append(
                    f"Director record missing fields {missing}: '{name}'."
                )

            # ── Activity check ────────────────────────────────────────────────
            if not is_active:
                inactive_count += 1
                warnings.append(
                    f"Inactive director found: '{name}'. "
                    "Verify whether this director should be removed from the corporate record."
                )

            # ── Verification status check ─────────────────────────────────────
            if status not in ("verified", "approved"):
                unverified_count += 1
                warnings.append(
                    f"Director '{name}' has unverified status: '{status}'."
                )

            # ── Nationality mismatch check ────────────────────────────────────
            if nationality and company_country and nationality != company_country:
                nationality_mismatch_count += 1
                # Not an error — cross-border directors are common, but worth noting
                findings.append(
                    f"Director '{name}' nationality ({nationality}) differs from "
                    f"company incorporation country ({company_country})."
                )

        if inactive_count == 0 and unverified_count == 0 and incomplete_count == 0:
            findings.append("All directors are active, verified, and have complete records.")

        if unverified_count > 0:
            recommendations.append(f"Verify {unverified_count} director(s) to complete KYC.")
        if inactive_count > 0:
            recommendations.append(
                f"Review {inactive_count} inactive director(s) and update corporate records."
            )

        # ── Score calculation ─────────────────────────────────────────────────
        score = 100.0
        total = max(len(directors), 1)
        score -= (inactive_count   / total) * 20.0
        score -= (unverified_count / total) * 20.0
        score -= (incomplete_count / total) * 15.0
        if len(directors) < MINIMUM_DIRECTORS:
            score -= 25.0
        score = round(max(0.0, min(100.0, score)), 2)
        risk_level = "high" if score < 40 else "medium" if score < 70 else "low"

        execution_duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        # Update state
        state.risk_breakdown["director"] = score
        state.shared_metadata["director_score"]        = score
        state.shared_metadata["director_risk"]         = risk_level
        state.shared_metadata["director_inactive"]     = inactive_count
        state.shared_metadata["director_unverified"]   = unverified_count
        state.shared_metadata["director_incomplete"]   = incomplete_count
        state.shared_metadata["director_nat_mismatch"] = nationality_mismatch_count

        state.logs.append(
            f"DirectorVerificationAgent: {len(directors)} director(s). "
            f"Inactive={inactive_count}, Unverified={unverified_count}. "
            f"Score={score}, Risk={risk_level}."
        )

        return {
            "_status": "success",
            "_reason": f"Director verification complete. Score={score}",
            "confidence": score / 100.0,
            "risk_score": score,
            "risk_level": risk_level,
            "findings":   findings,
            "warnings":   warnings,
            "recommendations": recommendations,
            "errors":     errors,
            "director_score":          score,
            "directors_checked":       len(directors),
            "inactive_directors":      inactive_count,
            "unverified_directors":    unverified_count,
            "incomplete_directors":    incomplete_count,
            "nationality_mismatches":  nationality_mismatch_count,
            "execution_duration_ms":   execution_duration_ms,
        }
