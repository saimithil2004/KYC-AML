"""
Sanctions Business Rules Engine
================================

Evaluates all individual and company match results and applies rules SAN001–SAN010.
Aggregates them into overall status, risk level, findings, warnings, and recommendations.
"""

from typing import Dict, Any, List, Set

from app.agents.sanctions.models import SanctionMatchResult
from app.agents.screening.constants import (
    MATCH_CONFIRMED, MATCH_POSSIBLE, MATCH_NONE,
    RISK_LOW, RISK_MEDIUM, RISK_HIGH, RISK_CRITICAL
)
from app.agents.sanctions.constants import (
    RULE_NO_MATCH, RULE_POSSIBLE_MATCH, RULE_CONFIRMED_INDIVIDUAL,
    RULE_CONFIRMED_COMPANY, RULE_TERRORIST_FINANCING, RULE_ASSET_FREEZE,
    RULE_TRAVEL_BAN, RULE_MULTIPLE_MATCHES, RULE_PASSPORT_MATCH,
    RULE_REGISTRATION_MATCH,
    SANCTION_CATEGORY_TERRORIST, SANCTION_CATEGORY_ASSET_FREEZE,
    SANCTION_CATEGORY_TRAVEL_BAN,
    REC_CONTINUE, REC_MANUAL_REVIEW, REC_EDD, REC_ESCALATE, REC_SAR_REVIEW,
    SANCTIONS_STATUS_CLEAR, SANCTIONS_STATUS_POSSIBLE, SANCTIONS_STATUS_CONFIRMED,
    NEXT_AGENT
)


class SanctionsRulesEngine:
    """
    Applies SAN001–SAN010 rules across all screened subjects (individuals and companies).
    """

    @staticmethod
    def evaluate(
        individual_results: List[SanctionMatchResult],
        company_results: List[SanctionMatchResult]
    ) -> Dict[str, Any]:
        """
        Aggregates results and triggers compliance rules.
        """
        findings: List[str] = []
        warnings: List[str] = []
        recommendations: List[str] = []
        all_rules: Set[str] = set()
        risk_influences: Set[str] = set()

        matched_subjects: List[Dict[str, Any]] = []
        matched_companies: List[Dict[str, Any]] = []

        total_matches = 0
        all_results = individual_results + company_results

        # ─── Individual / Company Rule Processing ────────────────────────────
        for result in all_results:
            is_company = result.entity_type == "COMPANY"
            subject_label = f"{result.subject_name} ({result.subject_role})"

            # SAN001: No Match
            if result.match_confidence == MATCH_NONE:
                all_rules.add(RULE_NO_MATCH)
                result.rules_triggered.append(RULE_NO_MATCH)
                continue

            # Found a match
            total_matches += 1
            if is_company:
                matched_companies.append(result.model_dump())
            else:
                matched_subjects.append(result.model_dump())

            # SAN002: Possible Match
            if result.match_confidence == MATCH_POSSIBLE:
                all_rules.add(RULE_POSSIBLE_MATCH)
                result.rules_triggered.append(RULE_POSSIBLE_MATCH)
                warnings.append(
                    f"[{RULE_POSSIBLE_MATCH}] {subject_label}: Possible sanctions match "
                    f"on list '{result.matched_list}' (score {result.match_score:.0f}%)."
                )
                recommendations.append(REC_MANUAL_REVIEW)
                risk_influences.add(RISK_MEDIUM)

            # SAN003 & SAN004: Confirmed Individual or Company Match
            elif result.match_confidence == MATCH_CONFIRMED:
                risk_influences.add(RISK_CRITICAL)

                if is_company:
                    all_rules.add(RULE_CONFIRMED_COMPANY)
                    result.rules_triggered.append(RULE_CONFIRMED_COMPANY)
                    findings.append(
                        f"[{RULE_CONFIRMED_COMPANY}] Confirmed Sanctioned Company match: "
                        f"'{result.subject_name}' found on list '{result.matched_list}'."
                    )
                    recommendations.append(REC_ESCALATE)
                    recommendations.append(REC_SAR_REVIEW)
                else:
                    all_rules.add(RULE_CONFIRMED_INDIVIDUAL)
                    result.rules_triggered.append(RULE_CONFIRMED_INDIVIDUAL)
                    findings.append(
                        f"[{RULE_CONFIRMED_INDIVIDUAL}] Confirmed Sanctioned Individual match: "
                        f"'{result.subject_name}' found on list '{result.matched_list}'."
                    )
                    recommendations.append(REC_ESCALATE)
                    recommendations.append(REC_SAR_REVIEW)

                # SAN009: Passport Match (Confirmed Match flag)
                if not is_company and "passport" in result.matched_fields:
                    all_rules.add(RULE_PASSPORT_MATCH)
                    result.rules_triggered.append(RULE_PASSPORT_MATCH)
                    findings.append(f"[{RULE_PASSPORT_MATCH}] Match confirmed via exact Passport Number.")

                # SAN010: Registration Number Match
                if is_company and "registration_number" in result.matched_fields:
                    all_rules.add(RULE_REGISTRATION_MATCH)
                    result.rules_triggered.append(RULE_REGISTRATION_MATCH)
                    findings.append(f"[{RULE_REGISTRATION_MATCH}] Company match confirmed via exact Registration Number.")

            # ─── Category-specific Rules ─────────────────────────────────────
            category = result.sanction_category
            
            # SAN005: Terrorist Financing Match -> Immediate Escalation
            if category == SANCTION_CATEGORY_TERRORIST and result.match_confidence == MATCH_CONFIRMED:
                all_rules.add(RULE_TERRORIST_FINANCING)
                result.rules_triggered.append(RULE_TERRORIST_FINANCING)
                result.requires_escalation = True
                findings.append(
                    f"[{RULE_TERRORIST_FINANCING}] CRITICAL: Subject '{result.subject_name}' matches "
                    f"terrorist financing sanction listing."
                )
                recommendations.append(REC_ESCALATE)
                recommendations.append(REC_SAR_REVIEW)
                risk_influences.add(RISK_CRITICAL)

            # SAN006: Asset Freeze
            if category == SANCTION_CATEGORY_ASSET_FREEZE:
                all_rules.add(RULE_ASSET_FREEZE)
                result.rules_triggered.append(RULE_ASSET_FREEZE)
                warnings.append(
                    f"[{RULE_ASSET_FREEZE}] Subject '{result.subject_name}' is subject to an Asset Freeze."
                )
                recommendations.append(REC_EDD)
                if result.match_confidence == MATCH_CONFIRMED:
                    risk_influences.add(RISK_CRITICAL)
                else:
                    risk_influences.add(RISK_HIGH)

            # SAN007: Travel Ban
            if category == SANCTION_CATEGORY_TRAVEL_BAN:
                all_rules.add(RULE_TRAVEL_BAN)
                result.rules_triggered.append(RULE_TRAVEL_BAN)
                warnings.append(
                    f"[{RULE_TRAVEL_BAN}] Subject '{result.subject_name}' is subject to a Travel Ban."
                )
                if result.match_confidence == MATCH_CONFIRMED:
                    risk_influences.add(RISK_CRITICAL)
                else:
                    risk_influences.add(RISK_MEDIUM)

        # SAN008: Multiple Matches
        if total_matches >= 2:
            all_rules.add(RULE_MULTIPLE_MATCHES)
            findings.append(
                f"[{RULE_MULTIPLE_MATCHES}] Multiple sanctions matches detected ({total_matches} subjects/companies)."
            )
            recommendations.append(REC_ESCALATE)
            risk_influences.add(RISK_CRITICAL)

        # ─── Aggregations ────────────────────────────────────────────────────
        all_confidences = {r.match_confidence for r in all_results}
        if MATCH_CONFIRMED in all_confidences:
            sanctions_status = SANCTIONS_STATUS_CONFIRMED
        elif MATCH_POSSIBLE in all_confidences:
            sanctions_status = SANCTIONS_STATUS_POSSIBLE
        else:
            sanctions_status = SANCTIONS_STATUS_CLEAR

        # Risk Tier
        if RISK_CRITICAL in risk_influences:
            risk_level = RISK_CRITICAL
        elif RISK_HIGH in risk_influences:
            risk_level = RISK_HIGH
        elif RISK_MEDIUM in risk_influences:
            risk_level = RISK_MEDIUM
        else:
            risk_level = RISK_LOW

        if sanctions_status == SANCTIONS_STATUS_CLEAR:
            findings.append(f"Sanctions screening complete. No active matches found for {len(all_results)} entities.")
            recommendations.append(REC_CONTINUE)

        # Remove duplicate recommendations while preserving order
        unique_recs = []
        for r in recommendations:
            if r not in unique_recs:
                unique_recs.append(r)

        return {
            "sanctions_status":       sanctions_status,
            "risk_level":             risk_level,
            "findings":               findings,
            "warnings":               warnings,
            "recommendations":        unique_recs,
            "all_rules_triggered":    sorted(all_rules),
            "matched_subjects":       matched_subjects,
            "matched_companies":      matched_companies,
            "next_agent":             NEXT_AGENT,
        }
