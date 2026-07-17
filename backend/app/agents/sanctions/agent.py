"""
Sanctions Agent
===============
Screens all relevant individuals and companies associated with the customer against
international sanctions watchlists.

Execution flow
--------------
AgentState
  → SanctionsValidator.build_individual_subjects()  — load & enrich individual subjects
  → SanctionsValidator.build_company_subjects()     — load company subjects
  → BaseSanctionsProvider.search_individuals/companies() — query watchlists
  → SanctionsMatcher.score_individual/company()     — multi-signal matching
  → SanctionsRulesEngine.evaluate()                 — run rules SAN001–SAN010
  → Compute sanctions score (0-100) and risk level
  → Update AgentState                               — write results and routing info
  → Return AgentResult                              — strongly typed

Design constraints
------------------
• Deterministic — zero LLM calls
• No PostgreSQL database queries or external API calls inside the agent class
• next_agent is always "country_risk_agent" (never invoked directly)
"""

import time
from datetime import datetime
from typing import Dict, Any, List, Optional

from app.agents.base.base_agent import BaseAgent
from app.agents.base.agent_state import AgentState
from app.agents.base.registry import AgentRegistry
from app.agents.base.exceptions import AgentValidationError

from app.agents.screening.models import ScreeningSubject, CompanyScreeningSubject
from app.agents.screening.constants import (
    MATCH_CONFIRMED, MATCH_POSSIBLE, RISK_LOW, RISK_MEDIUM, RISK_HIGH, RISK_CRITICAL
)
from app.agents.sanctions.constants import (
    SANCTIONS_STATUS_CLEAR, SANCTIONS_STATUS_POSSIBLE, SANCTIONS_STATUS_CONFIRMED,
    NEXT_AGENT, PROVIDER_MOCK, ALL_SANCTIONS_LISTS
)
from app.agents.sanctions.models import (
    SanctionMatchResult, SanctionsAuditTrail
)
from app.agents.sanctions.provider import BaseSanctionsProvider, MockSanctionsProvider
from app.agents.sanctions.validator import SanctionsValidator
from app.agents.sanctions.matcher import SanctionsMatcher
from app.agents.sanctions.rules import SanctionsRulesEngine


@AgentRegistry.register("sanctions_agent")
class SanctionsAgent(BaseAgent):
    """
    Sanctions Agent — Screens all individuals and companies for watchlists exposure.
    The provider is injected at constructor time (defaults to MockSanctionsProvider).
    """

    def __init__(self, provider: Optional[BaseSanctionsProvider] = None, **kwargs):
        super().__init__(**kwargs)
        self._provider: BaseSanctionsProvider = provider or MockSanctionsProvider()

    # ── Agent Metadata ────────────────────────────────────────────────────────
    def get_name(self) -> str:
        return "sanctions_agent"

    def get_version(self) -> str:
        return "1.0.0"

    def get_description(self) -> str:
        return (
            "Deterministic sanctions screening agent. Screens all associated "
            "individuals and companies against international sanctions lists (OFAC, "
            "UK, UN, EU, OpenSanctions, etc.)."
        )

    def get_capabilities(self) -> List[str]:
        return [
            "sanctions_screening",
            "individual_sanctions_check",
            "company_sanctions_check",
            "passport_number_matching",
            "company_registration_matching",
            "multi_signal_scoring",
            "manual_review_escalation",
            "langgraph_routing_output",
            "provider_agnostic_architecture"
        ]

    # ── Input Validation ──────────────────────────────────────────────────────
    def validate_input(self, state: AgentState) -> bool:
        """
        Requires customer profile to be present.
        """
        if not state.customer:
            raise AgentValidationError(
                message="Customer profile is missing in AgentState. Cannot run Sanctions Agent.",
                details={"customer": None}
            )
        return True

    # ── Core Processing ───────────────────────────────────────────────────────
    async def process(self, state: AgentState) -> Dict[str, Any]:
        start_time = time.perf_counter()

        # ── Step 1: Build + validate screening subjects ───────────────────────
        individuals = SanctionsValidator.build_individual_subjects(state)
        companies = SanctionsValidator.build_company_subjects(state)
        validation_warnings = SanctionsValidator.validate_subjects(individuals, companies)

        if not individuals and not companies:
            raise AgentValidationError(
                message="No valid individual or company screening subjects could be extracted.",
                details={"customer": state.customer}
            )

        # ── Step 2: Screen individuals & companies ────────────────────────────
        match_results: List[SanctionMatchResult] = []
        provider_errors: List[str] = []

        # Individual screening
        for subject in individuals:
            try:
                candidates = await self._provider.search_individuals(subject)
                result = SanctionsMatcher.score_individual(subject, candidates)
                match_results.append(result)
            except Exception as exc:
                provider_errors.append(f"Provider failure for individual '{subject.full_name}': {exc}")
                match_results.append(SanctionMatchResult(
                    subject_id=subject.subject_id,
                    subject_name=subject.full_name,
                    subject_role=subject.role,
                    entity_type="INDIVIDUAL",
                    match_confidence="UNSCREENED",
                    match_score=0.0,
                    reason=f"Provider error: {exc}"
                ))

        # Company screening
        for subject in companies:
            try:
                candidates = await self._provider.search_companies(subject)
                result = SanctionsMatcher.score_company(subject, candidates)
                match_results.append(result)
            except Exception as exc:
                provider_errors.append(f"Provider failure for company '{subject.company_name}': {exc}")
                match_results.append(SanctionMatchResult(
                    subject_id=subject.subject_id,
                    subject_name=subject.company_name,
                    subject_role=subject.role,
                    entity_type="COMPANY",
                    match_confidence="UNSCREENED",
                    match_score=0.0,
                    reason=f"Provider error: {exc}"
                ))

        # ── Step 3: Evaluate Business Rules ──────────────────────────────────
        individual_matches = [r for r in match_results if r.entity_type == "INDIVIDUAL"]
        company_matches = [r for r in match_results if r.entity_type == "COMPANY"]

        eval_result = SanctionsRulesEngine.evaluate(
            individual_results=individual_matches,
            company_results=company_matches
        )

        sanctions_status   = eval_result["sanctions_status"]
        risk_level         = eval_result["risk_level"]
        findings           = eval_result["findings"]
        warnings           = eval_result["warnings"] + validation_warnings + provider_errors
        recommendations    = eval_result["recommendations"]
        all_rules          = eval_result["all_rules_triggered"]
        matched_subjects   = eval_result["matched_subjects"]
        matched_companies  = eval_result["matched_companies"]
        next_agent         = eval_result["next_agent"]

        # ── Step 4: Compute Sanctions Score ───────────────────────────────────
        # 100 = Clear
        # 60 = Possible Match (Manual Review)
        # 10 = Confirmed High Risk Match
        # 0 = Confirmed Critical Risk Match (e.g. Terrorist financing, active freeze)
        sanctions_score = SanctionsAgent._compute_sanctions_score(sanctions_status, risk_level)

        execution_duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        # ── Step 5: Build Audit Trail ─────────────────────────────────────────
        matched_lists = list({r.matched_list for r in match_results if r.matched_list})
        audit = SanctionsAuditTrail(
            provider_used=self._provider.provider_name,
            sanctions_lists_checked=ALL_SANCTIONS_LISTS,
            subjects_screened=len(individuals),
            companies_screened=len(companies),
            matches_found=len(matched_subjects) + len(matched_companies),
            matched_lists=matched_lists,
            rules_triggered=all_rules,
            warnings=warnings,
            recommendations=recommendations,
            execution_duration_ms=execution_duration_ms,
            validation_timestamp=datetime.utcnow().isoformat()
        )

        # ── Step 6: Update AgentState ─────────────────────────────────────────
        state.risk_breakdown["sanctions"] = sanctions_score
        state.shared_metadata["sanctions_status"]          = sanctions_status
        state.shared_metadata["sanctions_score"]           = sanctions_score
        state.shared_metadata["sanctions_risk"]            = risk_level
        state.shared_metadata["matched_subjects"]          = matched_subjects
        state.shared_metadata["sanctions_matched_subjects"] = matched_subjects
        state.shared_metadata["matched_companies"]         = matched_companies
        state.shared_metadata["sanctions_findings"]        = findings
        state.shared_metadata["sanctions_recommendations"] = recommendations
        state.shared_metadata["sanctions_audit"]           = audit.model_dump()
        state.shared_metadata["next_agent"]                = next_agent
        state.logs.append(
            f"SanctionsAgent: {len(individuals)} individual(s), {len(companies)} company/companies "
            f"screened via {self._provider.provider_name}. Status={sanctions_status}, Risk={risk_level}. "
            f"Routing to: {next_agent}"
        )

        return {
            "_status": "success",
            "_reason": f"Sanctions screening complete. Status: {sanctions_status}",
            "confidence":        sanctions_score,
            "risk_score":        sanctions_score,
            "risk_level":        risk_level,
            "findings":          findings,
            "warnings":          warnings,
            "recommendations":   recommendations,
            "errors":            provider_errors,
            # Metadata fields
            "sanctions_score":   sanctions_score,
            "sanctions_status":  sanctions_status,
            "matched_subjects":  matched_subjects,
            "matched_companies": matched_companies,
            "rules_triggered":   all_rules,
            "next_agent":        next_agent,
            "audit_trail":       audit.model_dump()
        }

    @staticmethod
    def _compute_sanctions_score(status: str, risk: str) -> float:
        """
        Computes numeric sanctions score.
        """
        if status == SANCTIONS_STATUS_CLEAR:
            return 100.0
        if status == SANCTIONS_STATUS_POSSIBLE:
            return 60.0
        # CONFIRMED
        if risk == RISK_CRITICAL:
            return 0.0
        return 10.0
