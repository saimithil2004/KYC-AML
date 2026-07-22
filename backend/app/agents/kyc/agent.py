import time
from datetime import datetime
from typing import Dict, Any, List, Optional
from app.agents.base.base_agent import BaseAgent
from app.agents.base.agent_state import AgentState
from app.agents.base.registry import AgentRegistry
from app.agents.base.exceptions import AgentValidationError, AgentExecutionError

from app.agents.kyc.constants import *
from app.agents.kyc.models import KycAuditTrail
from app.agents.kyc.validator import KycValidator
from app.agents.kyc.rules import KycRulesEngine


@AgentRegistry.register("kyc_agent")
class KycAgent(BaseAgent):
    """
    KYC Agent: Performs deterministic, rule-based validations on customer profiles
    to check completeness, calculate scores, and route the workflow accordingly.
    """

    def get_name(self) -> str:
        return "kyc_agent"

    def get_version(self) -> str:
        return "1.0.0"

    def get_description(self) -> str:
        return "Deterministic validation agent auditing individual & corporate customer KYC compliance."

    def get_capabilities(self) -> List[str]:
        return [
            "personal_info_verification",
            "address_completeness_check",
            "identity_document_presence_check",
            "occupation_declaration_check",
            "source_of_funds_check",
            "source_of_wealth_check",
            "tax_residency_check",
        ]

    def validate_input(self, state: AgentState) -> bool:
        """Validates that customer state exists in shared memory."""
        if not state.customer:
            raise AgentValidationError(
                message="Mandatory customer profile object is missing in AgentState.",
                details={"customer": None},
            )
        return True

    async def process(self, state: AgentState) -> Dict[str, Any]:
        start_time = time.perf_counter()

        customer = state.customer
        # Safely default KYC profile to an empty dict if missing or None
        kyc_profile = state.kyc_profile or {}
        docs = state.uploaded_documents or []

        # ─── 1. FIELD VALIDATION & SCORING ──────────────────────────────────────
        score_personal, missing_personal, passed_personal = (
            KycValidator.validate_personal_info(customer)
        )
        score_address, missing_address, passed_address = KycValidator.validate_address(
            customer
        )
        score_docs, missing_docs, passed_docs = (
            KycValidator.validate_identity_documents(docs)
        )
        score_occupation, missing_occupation, passed_occupation = (
            KycValidator.validate_occupation(kyc_profile)
        )
        score_sof, missing_sof, passed_sof = KycValidator.validate_source_of_funds(
            kyc_profile
        )
        score_sow, missing_sow, passed_sow = KycValidator.validate_source_of_wealth(
            kyc_profile
        )
        score_tax, missing_tax, passed_tax = KycValidator.validate_tax_residency(
            kyc_profile
        )

        # Calculate final completeness score (0-100)
        kyc_score = (
            score_personal
            + score_address
            + score_docs
            + score_occupation
            + score_sof
            + score_sow
            + score_tax
        )

        # Gather all missing fields
        missing_fields = (
            missing_personal
            + missing_address
            + missing_docs
            + missing_occupation
            + missing_sof
            + missing_sow
            + missing_tax
        )

        # Gather all passed check summaries
        findings = (
            passed_personal
            + passed_address
            + passed_docs
            + passed_occupation
            + passed_sof
            + passed_sow
            + passed_tax
        )

        # ─── 2. BUSINESS RULES ENGINE ───────────────────────────────────────────
        eval_result = KycRulesEngine.evaluate(
            customer, kyc_profile, docs, missing_fields
        )

        passed_rules = eval_result["passed_rules"]
        failed_rules = eval_result["failed_rules"]
        warnings = eval_result["warnings"]
        recommendations = eval_result["recommendations"]
        risk_level = eval_result["risk_level"]
        next_agent = eval_result["next_agent"]

        # ─── 3. DETERMINING STATUS ──────────────────────────────────────────────
        if kyc_score >= 100.0 and len(warnings) == 0:
            kyc_status = STATUS_COMPLETE
        elif kyc_score >= 60.0:
            kyc_status = STATUS_INCOMPLETE
        else:
            kyc_status = STATUS_FAILED

        execution_duration = (time.perf_counter() - start_time) * 1000

        # ─── 4. AUDIT TRAIL OBJECT ──────────────────────────────────────────────
        audit_trail = KycAuditTrail(
            passed_rules=passed_rules,
            failed_rules=failed_rules,
            validation_timestamp=datetime.utcnow().isoformat(),
            execution_duration=round(execution_duration, 2),
            kyc_score=kyc_score,
            kyc_status=kyc_status,
        )

        # ─── 5. UPDATE AGENT STATE ──────────────────────────────────────────────
        # Map overall score/tier
        state.overall_score = kyc_score
        state.risk_tier = risk_level
        state.risk_breakdown["kyc"] = kyc_score

        # Ephemeral routing and variables
        state.shared_metadata["kyc_status"] = kyc_status
        state.shared_metadata["kyc_score"] = kyc_score
        state.shared_metadata["missing_fields"] = missing_fields
        state.shared_metadata["kyc_audit_trail"] = audit_trail.model_dump()
        state.shared_metadata["next_agent"] = next_agent

        state.logs.append(
            f"KycAgent screening finished. Score: {kyc_score}, Status: {kyc_status}, Routing to: {next_agent}"
        )

        # Return dict mapped to Pydantic AgentResult inside BaseAgent execute
        return {
            "_status": "success",
            "_reason": f"KYC Audit execution complete. Status: {kyc_status}",
            "confidence": kyc_score,  # Renamed completeness/validation score representation
            "risk_score": kyc_score,  # Validation Score
            "risk_level": risk_level,
            "findings": findings,
            "missing_fields": missing_fields,
            "warnings": warnings,
            "recommendations": recommendations,
            "kyc_status": kyc_status,
            "next_agent": next_agent,
            "audit_trail": audit_trail.model_dump(),
        }
