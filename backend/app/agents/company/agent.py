"""
Company Agent
=============
Performs deterministic, rule-based company verification for BUSINESS customers
as part of the UK AML + KYC workflow.

Routing behaviour
-----------------
* INDIVIDUAL customer  →  skip all verification, set next_agent = "pep_agent"
* BUSINESS   customer  →  run full verification,  set next_agent = "pep_agent"

The agent NEVER invokes the next agent directly.  It only writes a
LangGraph-compatible AgentRoutingInfo object into AgentState.shared_metadata
so that the Orchestrator can determine the next graph node.
"""

import time
from datetime import datetime
from typing import Dict, Any, List

from app.agents.base.base_agent import BaseAgent
from app.agents.base.agent_state import AgentState
from app.agents.base.registry import AgentRegistry
from app.agents.base.exceptions import AgentValidationError

from app.agents.company.constants import (
    CUSTOMER_TYPE_INDIVIDUAL,
    CUSTOMER_TYPE_BUSINESS,
    STATUS_COMPLETE,
    STATUS_INCOMPLETE,
    STATUS_FAILED,
    STATUS_SKIPPED,
    SCORE_COMPLETE_THRESHOLD,
    SCORE_INCOMPLETE_THRESHOLD,
    RISK_LOW,
)
from app.agents.company.models import CompanyAuditTrail, AgentRoutingInfo
from app.agents.company.validator import CompanyValidator
from app.agents.company.rules import CompanyRulesEngine


@AgentRegistry.register("company_agent")
class CompanyAgent(BaseAgent):
    """
    Company Agent:
    - Skips silently for INDIVIDUAL customers (not an error).
    - Runs full company verification for BUSINESS customers.
    - Populates AgentState with an AgentRoutingInfo object for the Orchestrator.
    """

    # ── Agent Metadata ────────────────────────────────────────
    def get_name(self) -> str:
        return "company_agent"

    def get_version(self) -> str:
        return "1.0.0"

    def get_description(self) -> str:
        return (
            "Deterministic company verification agent. Validates registration, "
            "status, address, directors, shareholders, UBOs, and documents for "
            "BUSINESS customers. Silently skips INDIVIDUAL customers."
        )

    def get_capabilities(self) -> List[str]:
        return [
            "customer_type_routing",
            "company_registration_check",
            "company_status_check",
            "registered_address_check",
            "industry_classification_check",
            "directors_verification",
            "shareholders_verification",
            "ubo_disclosure_check",
            "company_documents_check",
            "langgraph_routing_output",
        ]

    # ── Input Validation ──────────────────────────────────────
    def validate_input(self, state: AgentState) -> bool:
        """
        Requires that `customer` dict is present and contains a customer_type.
        Company-specific fields (companies, directors, etc.) are validated
        inside process() because they are only mandatory for BUSINESS customers.
        """
        if not state.customer:
            raise AgentValidationError(
                message="Customer profile is missing in AgentState. Cannot run Company Agent.",
                details={"customer": None},
            )
        customer_type = str(state.customer.get("customer_type") or "").strip().lower()
        if not customer_type:
            raise AgentValidationError(
                message="customer_type is missing from the customer profile.",
                details={"customer_type": None},
            )
        return True

    # ── Core Processing ───────────────────────────────────────
    async def process(self, state: AgentState) -> Dict[str, Any]:
        start_time = time.perf_counter()
        customer_type = str(state.customer.get("customer_type") or "").strip().lower()

        # ═══════════════════════════════════════════════════════
        # PATH A — INDIVIDUAL CUSTOMER → SKIP
        # ═══════════════════════════════════════════════════════
        if customer_type == CUSTOMER_TYPE_INDIVIDUAL:
            return self._build_skip_result(state, customer_type, start_time)

        # ═══════════════════════════════════════════════════════
        # PATH B — BUSINESS CUSTOMER → FULL VERIFICATION
        # ═══════════════════════════════════════════════════════
        return await self._run_business_verification(state, customer_type, start_time)

    # ── Skip Path (Individual) ────────────────────────────────
    def _build_skip_result(
        self,
        state: AgentState,
        customer_type: str,
        start_time: float,
    ) -> Dict[str, Any]:
        """
        Returns a success result signalling intentional skip.
        Updates AgentState with routing info immediately.
        This is NOT an error condition.
        """
        skip_reason = "Individual Customer — company verification not applicable."
        execution_duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        # Build LangGraph-compatible routing object
        routing = AgentRoutingInfo(
            customer_type=customer_type.upper(),
            current_agent="company_agent",
            next_agent="pep_agent",
            company_agent_executed=False,
            skip_reason=skip_reason,
        )

        # Audit trail
        audit = CompanyAuditTrail(
            passed_rules=[],
            failed_rules=[],
            validation_timestamp=datetime.utcnow().isoformat(),
            execution_duration_ms=execution_duration_ms,
            company_score=0.0,
            company_status=STATUS_SKIPPED,
            customer_type=customer_type.upper(),
            skipped=True,
            skip_reason=skip_reason,
        )

        # Write routing into shared state
        state.shared_metadata["company_agent_status"] = STATUS_SKIPPED
        state.shared_metadata["company_agent_routing"] = routing.to_dict()
        state.shared_metadata["company_audit_trail"] = audit.model_dump()
        state.shared_metadata["next_agent"] = "pep_agent"
        state.logs.append(
            f"CompanyAgent: SKIPPED — {skip_reason} Routing to: pep_agent"
        )

        return {
            "_status": "success",
            "_reason": f"Company Agent skipped: {skip_reason}",
            "confidence": 100.0,
            "risk_score": 0.0,
            "risk_level": RISK_LOW,
            "findings": [f"Company Agent intentionally skipped. {skip_reason}"],
            "warnings": [],
            "recommendations": [],
            "errors": [],
            "company_status": STATUS_SKIPPED,
            "company_score": 0.0,
            "next_agent": "pep_agent",
            "routing": routing.to_dict(),
            "audit_trail": audit.model_dump(),
        }

    # ── Business Verification Path ────────────────────────────
    async def _run_business_verification(
        self,
        state: AgentState,
        customer_type: str,
        start_time: float,
    ) -> Dict[str, Any]:
        """
        Executes the full 8-dimension company verification workflow
        sourcing all data exclusively from AgentState (no DB calls).
        """

        # Pull company data from AgentState
        companies = state.companies or []
        directors = state.directors or []
        ubos = state.ubos or []
        docs = state.uploaded_documents or []

        # Use first company entry as the primary record for flat-field checks.
        # AgentState.companies is a list; take index 0 if present.
        company = companies[0] if companies else {}

        # Extract shareholders from the company dict or a dedicated list
        # (some schemas store them nested; support both conventions).
        shareholders = (
            state.customer_profile.get("shareholders")
            or company.get("shareholders")
            or []
        )

        # ── Field-level scoring ──────────────────────────────
        score_reg, missing_reg, passed_reg = CompanyValidator.validate_registration(
            company
        )
        score_stat, missing_stat, passed_stat = CompanyValidator.validate_status(
            company
        )
        score_addr, missing_addr, passed_addr = CompanyValidator.validate_address(
            company
        )
        score_ind, missing_ind, passed_ind = CompanyValidator.validate_industry(company)
        score_dir, missing_dir, passed_dir = CompanyValidator.validate_directors(
            directors
        )
        score_shr, missing_shr, passed_shr = CompanyValidator.validate_shareholders(
            shareholders
        )
        score_ubo, missing_ubo, passed_ubo = CompanyValidator.validate_ubos(ubos)
        score_docs, missing_docs, passed_docs = (
            CompanyValidator.validate_company_documents(docs)
        )

        company_score = (
            score_reg
            + score_stat
            + score_addr
            + score_ind
            + score_dir
            + score_shr
            + score_ubo
            + score_docs
        )

        missing_fields = (
            missing_reg
            + missing_stat
            + missing_addr
            + missing_ind
            + missing_dir
            + missing_shr
            + missing_ubo
            + missing_docs
        )

        findings = (
            passed_reg
            + passed_stat
            + passed_addr
            + passed_ind
            + passed_dir
            + passed_shr
            + passed_ubo
            + passed_docs
        )

        # ── Business rules engine ────────────────────────────
        eval_result = CompanyRulesEngine.evaluate(
            company=company,
            missing_fields=missing_fields,
            directors=directors,
            shareholders=shareholders,
            ubos=ubos,
        )

        passed_rules = eval_result["passed_rules"]
        failed_rules = eval_result["failed_rules"]
        warnings = eval_result["warnings"]
        recommendations = eval_result["recommendations"]
        risk_level = eval_result["risk_level"]
        next_agent = eval_result["next_agent"]  # always "pep_agent"

        # ── Status determination ─────────────────────────────
        if company_score >= SCORE_COMPLETE_THRESHOLD and not warnings:
            company_status = STATUS_COMPLETE
        elif company_score >= SCORE_INCOMPLETE_THRESHOLD:
            company_status = STATUS_INCOMPLETE
        else:
            company_status = STATUS_FAILED

        execution_duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        # ── Audit trail ──────────────────────────────────────
        audit = CompanyAuditTrail(
            passed_rules=passed_rules,
            failed_rules=failed_rules,
            validation_timestamp=datetime.utcnow().isoformat(),
            execution_duration_ms=execution_duration_ms,
            company_score=company_score,
            company_status=company_status,
            customer_type=customer_type.upper(),
            skipped=False,
            skip_reason=None,
        )

        # ── LangGraph-compatible routing object ──────────────
        routing = AgentRoutingInfo(
            customer_type=customer_type.upper(),
            current_agent="company_agent",
            next_agent=next_agent,
            company_agent_executed=True,
            skip_reason=None,
        )

        # ── Update AgentState ────────────────────────────────
        state.risk_breakdown["company"] = company_score
        state.shared_metadata["company_status"] = company_status
        state.shared_metadata["company_score"] = company_score
        state.shared_metadata["company_missing_fields"] = missing_fields
        state.shared_metadata["company_audit_trail"] = audit.model_dump()
        state.shared_metadata["company_agent_routing"] = routing.to_dict()
        state.shared_metadata["next_agent"] = next_agent
        state.logs.append(
            f"CompanyAgent: Score={company_score}, Status={company_status}, "
            f"Risk={risk_level}, Routing to: {next_agent}"
        )

        return {
            "_status": "success",
            "_reason": f"Company verification complete. Status: {company_status}",
            "confidence": company_score,
            "risk_score": company_score,
            "risk_level": risk_level,
            "findings": findings,
            "warnings": warnings,
            "recommendations": recommendations,
            "errors": [],
            "missing_fields": missing_fields,
            "company_status": company_status,
            "company_score": company_score,
            "next_agent": next_agent,
            "routing": routing.to_dict(),
            "audit_trail": audit.model_dump(),
        }
