"""
FATF Agent — Grey List & Black List Country Checks.
Checks if any countries associated with the customer appear on the
FATF Grey List (Increased Monitoring) or Black List (High-Risk Jurisdictions).
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

# ── FATF Lists (as of 2024 — update via configuration as lists change) ────────
# Source: https://www.fatf-gafi.org/en/topics/high-risk-and-other-monitored-jurisdictions.html

FATF_BLACK_LIST: set = {
    # High-Risk Jurisdictions subject to a Call for Action (Black List)
    "democratic people's republic of korea",
    "north korea",
    "dprk",
    "iran",
    "myanmar",
    "burma",
}

FATF_GREY_LIST: set = {
    # Jurisdictions under Increased Monitoring (Grey List)
    "bulgaria",
    "burkina faso",
    "cameroon",
    "croatia",
    "democratic republic of the congo",
    "haiti",
    "kenya",
    "mali",
    "monaco",
    "mozambique",
    "namibia",
    "nigeria",
    "philippines",
    "senegal",
    "south africa",
    "south sudan",
    "syria",
    "tanzania",
    "venezuela",
    "vietnam",
    "yemen",
    # Added periodically — maintain this list
    "algeria",
    "angola",
    "ivory coast",
    "liberia",
    "somalia",
    "sudan",
}


@AgentRegistry.register("fatf_agent")
class FATFAgent(BaseAgent):
    """
    FATF Agent.
    Checks countries associated with the customer against FATF Grey and Black lists.
    """

    def get_name(self) -> str:
        return "fatf_agent"

    def get_version(self) -> str:
        return "1.0.0"

    def get_description(self) -> str:
        return (
            "FATF jurisdiction screening agent. Checks customer-associated countries "
            "against FATF High-Risk (Black List) and Increased Monitoring (Grey List) jurisdictions."
        )

    def get_capabilities(self) -> List[str]:
        return [
            "fatf_black_list_check",
            "fatf_grey_list_check",
            "multi_country_evaluation",
            "jurisdiction_risk_classification",
        ]

    def validate_input(self, state: AgentState) -> bool:
        if not state.customer_id:
            raise AgentValidationError(
                message="customer_id missing in AgentState. Cannot run FATFAgent.",
                details={"customer_id": None},
            )
        return True

    async def process(self, state: AgentState) -> Dict[str, Any]:
        start_time = time.perf_counter()
        state.logs.append(f"[{self.get_name()}] Starting FATF jurisdiction check...")

        # Collect all countries from state
        countries: List[str] = self._collect_countries(state)

        findings: List[str] = []
        warnings: List[str] = []
        recommendations: List[str] = []

        black_listed: List[str] = []
        grey_listed: List[str] = []

        for country in countries:
            country_lower = country.strip().lower()
            if country_lower in FATF_BLACK_LIST:
                black_listed.append(country)
                findings.append(
                    f"FATF BLACK LIST: '{country}' is a High-Risk Jurisdiction subject to a Call for Action."
                )
            elif country_lower in FATF_GREY_LIST:
                grey_listed.append(country)
                warnings.append(
                    f"FATF GREY LIST: '{country}' is under Increased Monitoring."
                )

        # ── Determine status and score ────────────────────────────────────────
        if black_listed:
            fatf_status = "BLACK_LISTED"
            fatf_score = 0.0
            risk_level = "critical"
            recommendations.append(
                "REJECT or SUSPEND — customer has connection to FATF black-listed jurisdiction."
            )
            recommendations.append(
                "File Suspicious Activity Report (SAR) as required by regulation."
            )
        elif grey_listed:
            fatf_status = "GREY_LISTED"
            fatf_score = max(30.0, 100.0 - len(grey_listed) * 20.0)
            risk_level = "high"
            recommendations.append(
                "Apply Enhanced Due Diligence (EDD) for FATF grey-list exposure."
            )
            recommendations.append("Increase transaction monitoring frequency.")
        else:
            fatf_status = "CLEAR"
            fatf_score = 100.0
            risk_level = "low"
            findings.append("No FATF grey-list or black-list jurisdictions identified.")

        execution_duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        # Update AgentState
        state.risk_breakdown["fatf"] = fatf_score
        state.shared_metadata["fatf_status"] = fatf_status
        state.shared_metadata["fatf_score"] = fatf_score
        state.shared_metadata["fatf_black_listed"] = black_listed
        state.shared_metadata["fatf_grey_listed"] = grey_listed
        state.shared_metadata["fatf_countries_checked"] = countries

        state.logs.append(
            f"FATFAgent: {len(countries)} countries checked. Status={fatf_status}, Score={fatf_score}. "
            f"Black: {black_listed}, Grey: {grey_listed}."
        )

        return {
            "_status": "success",
            "_reason": f"FATF check complete. Status: {fatf_status}",
            "confidence": fatf_score / 100.0,
            "risk_score": fatf_score,
            "risk_level": risk_level,
            "findings": findings,
            "warnings": warnings,
            "recommendations": recommendations,
            "errors": [],
            # Metadata
            "fatf_status": fatf_status,
            "fatf_score": fatf_score,
            "black_listed": black_listed,
            "grey_listed": grey_listed,
            "countries_checked": countries,
            "execution_duration_ms": execution_duration_ms,
        }

    @staticmethod
    def _collect_countries(state: AgentState) -> List[str]:
        """Collects all unique countries from AgentState."""
        countries: set = set()

        # From customer profile
        customer = state.customer or {}
        for field in ("country", "nationality"):
            val = customer.get(field)
            if val and isinstance(val, str):
                countries.add(val.strip())

        # From KYC profile
        kyc = state.kyc_profile or {}
        for field in ("nationality", "tax_residency"):
            val = kyc.get(field)
            if val and isinstance(val, str):
                countries.add(val.strip())

        # From country risk agent (already evaluated)
        evaluated = state.shared_metadata.get("evaluated_countries") or []
        for c in evaluated:
            if c and isinstance(c, str):
                countries.add(c.strip())

        # From companies
        for company in state.companies or []:
            val = company.get("country_of_incorporation")
            if val and isinstance(val, str):
                countries.add(val.strip())

        return [c for c in countries if c]
