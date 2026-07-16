"""
Country Risk Agent — Business Rules Engine
===========================================

Evaluates rules CR001–CR008 on normalized country data against a RiskMatrix.
"""

from typing import Dict, Any, List, Set

from app.agents.country.risk_matrix import RiskMatrix
from app.agents.country.constants import (
    RULE_LOW_RISK_COUNTRY, RULE_MEDIUM_RISK_COUNTRY, RULE_HIGH_RISK_COUNTRY,
    RULE_PROHIBITED_COUNTRY, RULE_MULTIPLE_HIGH_RISK, RULE_HIGH_RISK_TX_DEST,
    RULE_HIGH_RISK_CO_REG, RULE_UNKNOWN_COUNTRY,
    RISK_LOW, RISK_MEDIUM, RISK_HIGH, RISK_PROHIBITED, RISK_CRITICAL,
    COUNTRY_STATUS_CLEAR, COUNTRY_STATUS_WARNING, COUNTRY_STATUS_SUSPENDED
)


class CountryRulesEngine:
    """
    Stateless evaluator for CR001–CR008 business rules.
    """

    @staticmethod
    def evaluate(
        collected_countries: Dict[str, Set[str]],
        risk_matrix: RiskMatrix
    ) -> Dict[str, Any]:
        """
        Runs the country risk rules engine.

        Parameters
        ----------
        collected_countries : Dict[str, Set[str]]
            Normalized (or UNKNOWN:) country strings mapped to the sources where they appeared.
        risk_matrix : RiskMatrix
            Matrix used to look up country classifications.

        Returns
        -------
        Dict with evaluation outcomes.
        """
        findings: List[str] = []
        warnings: List[str] = []
        recommendations: List[str] = []
        rules_triggered: Set[str] = set()

        evaluated_countries: Set[str] = set()
        high_risk_countries: Set[str] = set()
        prohibited_countries: Set[str] = set()
        unknown_countries: Set[str] = set()

        # ─── Evaluate each country ────────────────────────────────────────────
        for country, sources in collected_countries.items():
            # Handle Unknown Country Rule
            if country.startswith("UNKNOWN:"):
                raw_name = country.replace("UNKNOWN:", "")
                unknown_countries.add(raw_name)
                rules_triggered.add(RULE_UNKNOWN_COUNTRY)
                warnings.append(
                    f"[{RULE_UNKNOWN_COUNTRY}] Unknown country alias/code detected: '{raw_name}' "
                    f"under source(s) {sorted(list(sources))}."
                )
                recommendations.append(f"Correct country details for '{raw_name}' in the CRM.")
                continue

            # Standard standard country
            evaluated_countries.add(country)
            risk_level = risk_matrix.get_risk_level(country)

            # CR001: Low Risk Country
            if risk_level == RISK_LOW:
                rules_triggered.add(RULE_LOW_RISK_COUNTRY)
                findings.append(f"[{RULE_LOW_RISK_COUNTRY}] standard screening for '{country}' (Low Risk).")

            # CR002: Medium Risk Country
            elif risk_level == RISK_MEDIUM:
                rules_triggered.add(RULE_MEDIUM_RISK_COUNTRY)
                findings.append(f"[{RULE_MEDIUM_RISK_COUNTRY}] '{country}' is classified as Medium Risk.")
                recommendations.append(f"Apply standard ongoing monitoring for relationships with '{country}'.")

            # CR003: High Risk Country
            elif risk_level == RISK_HIGH:
                high_risk_countries.add(country)
                rules_triggered.add(RULE_HIGH_RISK_COUNTRY)
                warnings.append(f"[{RULE_HIGH_RISK_COUNTRY}] Association with High Risk country: '{country}'.")
                recommendations.append(f"Conduct Enhanced Due Diligence (EDD) due to High Risk country '{country}'.")

                # Contextual rules:
                # CR006: High-Risk Transaction Destination
                if "transaction_destination" in sources:
                    rules_triggered.add(RULE_HIGH_RISK_TX_DEST)
                    warnings.append(
                        f"[{RULE_HIGH_RISK_TX_DEST}] High Risk country '{country}' is a transaction destination."
                    )
                    recommendations.append(f"Escalate and review transactions routed to '{country}'.")

                # CR007: High-Risk Company Registration Country
                if "company_registration" in sources:
                    rules_triggered.add(RULE_HIGH_RISK_CO_REG)
                    warnings.append(
                        f"[{RULE_HIGH_RISK_CO_REG}] Business is incorporated in High Risk country '{country}'."
                    )

            # CR004: Prohibited Country
            elif risk_level == RISK_PROHIBITED:
                prohibited_countries.add(country)
                rules_triggered.add(RULE_PROHIBITED_COUNTRY)
                findings.append(f"[{RULE_PROHIBITED_COUNTRY}] CRITICAL: Association with PROHIBITED country '{country}'.")
                warnings.append(f"[{RULE_PROHIBITED_COUNTRY}] Prohibited jurisdiction: '{country}'.")
                recommendations.append(
                    f"Escalate to Compliance Officer immediately for relationship review regarding prohibited '{country}'."
                )

        # CR005: Multiple High-Risk Countries
        if len(high_risk_countries) >= 2:
            rules_triggered.add(RULE_MULTIPLE_HIGH_RISK)
            warnings.append(
                f"[{RULE_MULTIPLE_HIGH_RISK}] Multiple High Risk country associations: {sorted(list(high_risk_countries))}."
            )
            recommendations.append("Trigger Manual Compliance Review due to multiple high-risk jurisdictions.")

        # ─── Status Determination ─────────────────────────────────────────────
        if prohibited_countries:
            country_status = COUNTRY_STATUS_SUSPENDED
        elif high_risk_countries or unknown_countries:
            country_status = COUNTRY_STATUS_WARNING
        else:
            country_status = COUNTRY_STATUS_CLEAR

        # ─── Risk Level Aggregation ───────────────────────────────────────────
        if prohibited_countries:
            agg_risk_level = RISK_CRITICAL
        elif high_risk_countries:
            agg_risk_level = RISK_HIGH
        elif unknown_countries or collected_countries and any(
            risk_matrix.get_risk_level(c) == RISK_MEDIUM for c in evaluated_countries
        ):
            agg_risk_level = RISK_MEDIUM
        else:
            agg_risk_level = RISK_LOW

        return {
            "country_status":       country_status,
            "risk_level":           agg_risk_level,
            "evaluated_countries":  sorted(list(evaluated_countries)),
            "high_risk_countries":  sorted(list(high_risk_countries)),
            "prohibited_countries": sorted(list(prohibited_countries)),
            "unknown_countries":    sorted(list(unknown_countries)),
            "findings":             findings,
            "warnings":             warnings,
            "recommendations":      list(dict.fromkeys(recommendations)), # dedupe preserving order
            "rules_triggered":      sorted(list(rules_triggered)),
        }
