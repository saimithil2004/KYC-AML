"""
PEP Agent
==========
Screens all persons associated with a customer against Politically Exposed
Person (PEP) datasets to determine whether Enhanced Due Diligence is required.

Execution flow
--------------
AgentState
  → PepValidator.build_subjects()    — extract + deduplicate subjects
  → PepValidator.validate_subjects() — warn on incomplete subject data
  → BasePepProvider.search()         — fetch PEP candidates per subject
  → PepMatcher.score_subject()       — multi-signal scoring per subject
  → PepRulesEngine.evaluate()        — apply PEP001–PEP007 across all results
  → Update AgentState                — write all outputs + routing
  → Return AgentResult               — strongly-typed, never a raw dict

Design constraints
------------------
• Deterministic — zero LLM calls
• No direct PostgreSQL queries
• No external API calls from within the agent class
• All inputs from AgentState; all outputs to AgentState
• Provider is injected via constructor (default: MockPepProvider)
• next_agent is always "sanctions_agent" — never invoked directly
"""

import time
from datetime import datetime
from typing import Dict, Any, List, Optional, Type

from app.agents.base.base_agent import BaseAgent
from app.agents.base.agent_state import AgentState
from app.agents.base.registry import AgentRegistry
from app.agents.base.exceptions import AgentValidationError, ExternalAPIError

from app.agents.pep.constants import (
    PEP_STATUS_CLEAR,
    PEP_STATUS_POSSIBLE,
    PEP_STATUS_CONFIRMED,
    RISK_LOW,
    RISK_MEDIUM,
    RISK_HIGH,
    RISK_CRITICAL,
    NEXT_AGENT,
    PROVIDER_MOCK,
)
from app.agents.pep.models import (
    ScreeningSubject,
    PepMatchResult,
    PepAuditTrail,
)
from app.agents.pep.provider import BasePepProvider, MockPepProvider
from app.agents.pep.validator import PepValidator
from app.agents.pep.matcher import PepMatcher
from app.agents.pep.rules import PepRulesEngine


@AgentRegistry.register("pep_agent")
class PepAgent(BaseAgent):
    """
    PEP Agent — screens all associated persons for PEP exposure.

    The provider is injected at construction time, defaulting to
    ``MockPepProvider`` for development and testing.  In production,
    pass an OpenSanctionsProvider or WorldCheckProvider instance.
    """

    def __init__(self, provider: Optional[BasePepProvider] = None, **kwargs):
        super().__init__(**kwargs)
        self._provider: BasePepProvider = provider or MockPepProvider()

    # ── Agent Metadata ────────────────────────────────────────────────────────
    def get_name(self) -> str:
        return "pep_agent"

    def get_version(self) -> str:
        return "1.0.0"

    def get_description(self) -> str:
        return (
            "Deterministic PEP screening agent. Screens all associated persons "
            "(customer, directors, UBOs, shareholders, signatories) against PEP "
            "datasets. Applies PEP001–PEP007 rules and determines EDD requirement."
        )

    def get_capabilities(self) -> List[str]:
        return [
            "pep_screening",
            "multi_subject_extraction",
            "subject_deduplication",
            "fuzzy_name_matching",
            "multi_signal_scoring",
            "edd_determination",
            "manual_review_flagging",
            "langgraph_routing_output",
            "provider_agnostic_architecture",
        ]

    # ── Input Validation ──────────────────────────────────────────────────────
    def validate_input(self, state: AgentState) -> bool:
        """
        Requires a non-empty customer dict with at minimum a name field.
        Subject extraction is handled inside process(); we only gate on the
        customer being present so the agent knows who the screening is for.
        """
        if not state.customer:
            raise AgentValidationError(
                message="Customer profile is missing in AgentState. Cannot run PEP Agent.",
                details={"customer": None},
            )
        customer = state.customer
        has_name = (
            str(customer.get("first_name") or "").strip()
            or str(customer.get("name") or "").strip()
        )
        if not has_name:
            raise AgentValidationError(
                message="Customer name is missing. Cannot build screening subjects.",
                details={"customer": customer},
            )
        return True

    # ── Core Processing ───────────────────────────────────────────────────────
    async def process(self, state: AgentState) -> Dict[str, Any]:
        start_time = time.perf_counter()

        # ── Step 1: Build + validate screening subjects ───────────────────────
        subjects: List[ScreeningSubject] = PepValidator.build_subjects(state)
        subject_warnings = PepValidator.validate_subjects(subjects)

        if not subjects:
            raise AgentValidationError(
                message="No valid screening subjects could be extracted from AgentState.",
                details={"customer": state.customer},
            )

        # ── Step 2: Screen each subject via provider + matcher ────────────────
        match_results: List[PepMatchResult] = []
        provider_errors: List[str] = []

        for subject in subjects:
            try:
                candidates = await self._provider.search(subject)
                result = PepMatcher.score_subject(subject, candidates)
                match_results.append(result)
            except Exception as exc:
                # Provider failure is non-fatal: mark subject as unscreened
                # and continue.  Unscreened subjects are flagged in warnings.
                provider_errors.append(
                    f"Provider failure for subject '{subject.full_name}': {exc}"
                )
                match_results.append(
                    PepMatchResult(
                        subject_id=subject.subject_id,
                        subject_name=subject.full_name,
                        subject_role=subject.role,
                        match_confidence="UNSCREENED",
                        match_score=0.0,
                        reason=f"Provider error: {exc}",
                    )
                )

        # ── Step 3: Apply business rules ──────────────────────────────────────
        eval_result = PepRulesEngine.evaluate(match_results)

        pep_status = eval_result["pep_status"]
        risk_level = eval_result["risk_level"]
        findings = eval_result["findings"]
        warnings = eval_result["warnings"] + subject_warnings + provider_errors
        recommendations = eval_result["recommendations"]
        all_rules = eval_result["all_rules_triggered"]
        edd_required = eval_result["edd_required"]
        manual_review = eval_result["manual_review_required"]
        matched_subjects = eval_result["matched_subjects"]
        next_agent = eval_result["next_agent"]  # always "sanctions_agent"

        # ── Step 4: Compute PEP score (100 = clear, decreases per match) ──────
        # PEP score represents screening completeness / confidence in clearance.
        # 100 = all clear, 0 = confirmed PEP with current office.
        pep_score = PepAgent._compute_pep_score(pep_status, risk_level)

        execution_duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        # ── Step 5: Build audit trail ─────────────────────────────────────────
        confirmed_count = sum(
            1 for r in match_results if r.match_confidence == "CONFIRMED_MATCH"
        )
        possible_count = sum(
            1 for r in match_results if r.match_confidence == "POSSIBLE_MATCH"
        )
        audit = PepAuditTrail(
            provider_used=self._provider.provider_name,
            subjects_screened=len(subjects),
            matches_found=len(matched_subjects),
            confirmed_peps=confirmed_count,
            possible_matches=possible_count,
            rules_triggered=all_rules,
            warnings=warnings,
            recommendations=recommendations,
            execution_duration_ms=execution_duration_ms,
            validation_timestamp=datetime.utcnow().isoformat(),
        )

        # ── Step 6: Update AgentState ─────────────────────────────────────────
        state.risk_breakdown["pep"] = pep_score
        state.shared_metadata["pep_status"] = pep_status
        state.shared_metadata["pep_score"] = pep_score
        state.shared_metadata["pep_risk"] = risk_level
        state.shared_metadata["screened_subjects"] = [s.model_dump() for s in subjects]
        state.shared_metadata["matched_subjects"] = matched_subjects
        state.shared_metadata["pep_matched_subjects"] = matched_subjects
        state.shared_metadata["pep_findings"] = findings
        state.shared_metadata["pep_recommendations"] = recommendations
        state.shared_metadata["pep_audit_trail"] = audit.model_dump()
        state.shared_metadata["next_agent"] = next_agent
        state.shared_metadata["edd_required"] = edd_required
        state.shared_metadata["manual_review_required"] = manual_review
        state.logs.append(
            f"PepAgent: {len(subjects)} subject(s) screened via {self._provider.provider_name}. "
            f"Status={pep_status}, Risk={risk_level}, EDD={edd_required}. "
            f"Routing to: {next_agent}"
        )

        return {
            "_status": "success",
            "_reason": f"PEP screening complete. Status: {pep_status}",
            "confidence": pep_score,
            "risk_score": pep_score,
            "risk_level": risk_level,
            "findings": findings,
            "warnings": warnings,
            "recommendations": recommendations,
            "errors": provider_errors,
            # Metadata fields (accessible via result.metadata)
            "pep_status": pep_status,
            "pep_score": pep_score,
            "screened_subjects": [s.model_dump() for s in subjects],
            "matched_subjects": matched_subjects,
            "edd_required": edd_required,
            "manual_review_required": manual_review,
            "rules_triggered": all_rules,
            "next_agent": next_agent,
            "audit_trail": audit.model_dump(),
        }

    # ── Private helpers ───────────────────────────────────────────────────────
    @staticmethod
    def _compute_pep_score(pep_status: str, risk_level: str) -> float:
        """
        Converts PEP status + risk level to a 0–100 numeric score.

        100 = all clear (no matches)
         60 = possible match (manual review)
         20 = confirmed PEP / medium risk
          0 = confirmed PEP / critical risk (current office holder)
        """
        if pep_status == PEP_STATUS_CLEAR:
            return 100.0
        if pep_status == PEP_STATUS_POSSIBLE:
            return 60.0
        # CONFIRMED_PEP
        if risk_level == RISK_CRITICAL:
            return 0.0
        if risk_level == RISK_HIGH:
            return 10.0
        return 20.0
