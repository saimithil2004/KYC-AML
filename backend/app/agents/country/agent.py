"""
Country Risk Agent
==================
Evaluates all countries associated with the case (addresses, nationalities, registration,
operating country, transaction origin/destination, bank country) to determine jurisdictional AML risk.

Execution flow
--------------
AgentState
  → CountryValidator.collect_countries() — extract and normalise all countries
  → CountryRulesEngine.evaluate()        — run rules CR001–CR008 against RiskMatrix
  → Calculate country risk score
  → Update AgentState                    — write results and routing info
  → Return AgentResult                   — strongly typed

Design constraints
------------------
• Deterministic — zero LLM calls
• No direct PostgreSQL queries or external API calls inside the agent class
• next_agent is always "transaction_agent" (never invoked directly)
"""

import time
from datetime import datetime
from typing import Dict, Any, List, Optional

from app.agents.base.base_agent import BaseAgent
from app.agents.base.agent_state import AgentState
from app.agents.base.registry import AgentRegistry
from app.agents.base.exceptions import AgentValidationError

from app.agents.country.constants import (
    RISK_LOW, RISK_MEDIUM, RISK_HIGH, RISK_PROHIBITED, RISK_CRITICAL,
    COUNTRY_STATUS_CLEAR, COUNTRY_STATUS_WARNING, COUNTRY_STATUS_SUSPENDED,
    DEDUCTION_HIGH, DEDUCTION_MEDIUM, NEXT_AGENT, PROVIDER_MOCK
)
from app.agents.country.models import CountryAuditTrail
from app.agents.country.provider import BaseCountryRiskProvider, MockCountryRiskProvider
from app.agents.country.risk_matrix import RiskMatrix
from app.agents.country.validator import CountryValidator
from app.agents.country.rules import CountryRulesEngine


@AgentRegistry.register("country_risk_agent")
class CountryRiskAgent(BaseAgent):
    """
    Country Risk Agent — Evaluates country associations to determine AML risk.
    The provider is injected at constructor time (defaults to MockCountryRiskProvider).
    """

    def __init__(self, provider: Optional[BaseCountryRiskProvider] = None, **kwargs):
        super().__init__(**kwargs)
        self._provider: BaseCountryRiskProvider = provider or MockCountryRiskProvider()
        self._risk_matrix = RiskMatrix(self._provider)

    # ── Agent Metadata ────────────────────────────────────────────────────────
    def get_name(self) -> str:
        return "country_risk_agent"

    def get_version(self) -> str:
        return "1.0.0"

    def get_description(self) -> str:
        return (
            "Deterministic country risk evaluation agent. Evaluates all countries "
            "associated with a case to determine AML jurisdictional risk."
        )

    def get_capabilities(self) -> List[str]:
        return [
            "country_collection",
            "country_normalization",
            "jurisdictional_risk_scoring",
            "fatf_list_check",
            "sanctioned_country_check",
            "rules_evaluation",
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
                message="Customer profile is missing in AgentState. Cannot run Country Risk Agent.",
                details={"customer": None}
            )
        return True

    # ── Core Processing ───────────────────────────────────────────────────────
    async def process(self, state: AgentState) -> Dict[str, Any]:
        start_time = time.perf_counter()

        # ── Step 1: Collect & Normalise Countries ─────────────────────────────
        collected = CountryValidator.collect_countries(state)

        # Ensure we have at least one country to evaluate (otherwise raise error)
        if not collected:
            raise AgentValidationError(
                message="No valid or invalid country details could be collected from AgentState.",
                details={"customer": state.customer}
            )

        # ── Step 2: Run Rules Engine ──────────────────────────────────────────
        eval_result = CountryRulesEngine.evaluate(collected, self._risk_matrix)

        country_status       = eval_result["country_status"]
        risk_level           = eval_result["risk_level"]
        evaluated_countries  = eval_result["evaluated_countries"]
        high_risk_countries  = eval_result["high_risk_countries"]
        prohibited_countries = eval_result["prohibited_countries"]
        unknown_countries    = eval_result["unknown_countries"]
        findings             = eval_result["findings"]
        warnings             = eval_result["warnings"]
        recommendations      = eval_result["recommendations"]
        rules_triggered      = eval_result["rules_triggered"]

        # ── Step 3: Calculate Country Risk Score ──────────────────────────────
        # 100 = low risk, decreases based on medium/high-risk countries.
        # Prohibited country makes score 0.
        country_score = self._calculate_country_score(
            evaluated_countries=evaluated_countries,
            high_risk_countries=high_risk_countries,
            prohibited_countries=prohibited_countries
        )

        execution_duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        # ── Step 4: Build Audit Trail ─────────────────────────────────────────
        audit = CountryAuditTrail(
            provider_used=self._provider.provider_name,
            countries_evaluated=evaluated_countries + unknown_countries,
            high_risk_countries=high_risk_countries,
            prohibited_countries=prohibited_countries,
            triggered_rules=rules_triggered,
            warnings=warnings,
            recommendations=recommendations,
            execution_duration_ms=execution_duration_ms,
            validation_timestamp=datetime.utcnow().isoformat()
        )

        # ── Step 5: Update AgentState ─────────────────────────────────────────
        state.risk_breakdown["country"] = country_score
        state.shared_metadata["country_status"]          = country_status
        state.shared_metadata["country_score"]           = country_score
        state.shared_metadata["country_risk"]            = risk_level
        state.shared_metadata["evaluated_countries"]     = evaluated_countries
        state.shared_metadata["high_risk_countries"]     = high_risk_countries
        state.shared_metadata["prohibited_countries"]    = prohibited_countries
        state.shared_metadata["country_findings"]        = findings
        state.shared_metadata["country_recommendations"] = recommendations
        state.shared_metadata["country_audit"]           = audit.model_dump()
        state.shared_metadata["next_agent"]              = NEXT_AGENT
        state.logs.append(
            f"CountryRiskAgent: {len(evaluated_countries)} country/countries evaluated via {self._provider.provider_name}. "
            f"Status={country_status}, Risk={risk_level}, Score={country_score}. "
            f"Routing to: {NEXT_AGENT}"
        )

        return {
            "_status": "success",
            "_reason": f"Country risk evaluation complete. Status: {country_status}",
            "confidence":        country_score,
            "risk_score":        country_score,
            "risk_level":        risk_level,
            "findings":          findings,
            "warnings":          warnings,
            "recommendations":   recommendations,
            "errors":            [],
            # Metadata fields
            "country_score":        country_score,
            "country_status":       country_status,
            "countries_evaluated":  evaluated_countries,
            "high_risk_countries":  high_risk_countries,
            "prohibited_countries": prohibited_countries,
            "rules_triggered":      rules_triggered,
            "next_agent":           NEXT_AGENT,
            "audit_trail":          audit.model_dump()
        }

    # ─── Private Helpers ──────────────────────────────────────────────────────
    def _calculate_country_score(
        self,
        evaluated_countries: List[str],
        high_risk_countries: List[str],
        prohibited_countries: List[str]
    ) -> float:
        """
        Calculates Country Risk Score (0-100).
        """
        if prohibited_countries:
            return 0.0

        score = 100.0
        medium_count = sum(1 for c in evaluated_countries if self._risk_matrix.is_medium(c))

        deductions = (len(high_risk_countries) * DEDUCTION_HIGH) + (medium_count * DEDUCTION_MEDIUM)
        score -= deductions

        # Floor score based on risk profiles
        if high_risk_countries:
            return max(10.0, score)
        if medium_count > 0:
            return max(50.0, score)
        return max(0.0, score)
