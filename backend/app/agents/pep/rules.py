"""
PEP Business Rules Engine
==========================

Evaluates all PepMatchResults and applies business rules PEP001–PEP007.

Rules are applied at the SUBJECT level (one result per subject) and then
aggregated to produce:
  • Overall pep_status  (CLEAR / POSSIBLE_MATCH / CONFIRMED_PEP)
  • Overall risk_level  (low / medium / high / critical)
  • Findings list
  • Warnings list
  • Recommendations list
  • All triggered rule IDs

This class is stateless and contains zero I/O.
"""

from typing import Dict, Any, List, Set

from app.agents.pep.models import PepMatchResult
from app.agents.pep.constants import (
    # Rule IDs
    RULE_NO_MATCH,
    RULE_POSSIBLE_MATCH,
    RULE_CONFIRMED_PEP,
    RULE_FOREIGN_PEP,
    RULE_FAMILY_MEMBER,
    RULE_CURRENT_OFFICE,
    RULE_FORMER_PEP,
    # Match levels
    MATCH_CONFIRMED,
    MATCH_POSSIBLE,
    MATCH_NONE,
    # PEP categories
    PEP_CATEGORY_FOREIGN,
    PEP_CATEGORY_FAMILY_MEMBER,
    PEP_CATEGORY_CLOSE_ASSOCIATE,
    PEP_CATEGORY_FORMER_PEP,
    PEP_CATEGORY_CURRENT_PEP,
    PEP_CATEGORY_DOMESTIC,
    PEP_CATEGORY_INTERNATIONAL_ORG,
    # Statuses & risk
    PEP_STATUS_CLEAR,
    PEP_STATUS_POSSIBLE,
    PEP_STATUS_CONFIRMED,
    RISK_LOW,
    RISK_MEDIUM,
    RISK_HIGH,
    RISK_CRITICAL,
    # Next agent
    NEXT_AGENT,
)


class PepRulesEngine:
    """
    Applies PEP001–PEP007 across all match results and returns a
    fully aggregated evaluation dict.
    """

    @staticmethod
    def evaluate(match_results: List[PepMatchResult]) -> Dict[str, Any]:
        """
        Parameters
        ----------
        match_results : List[PepMatchResult]
            One result per screened subject.

        Returns
        -------
        Dict containing:
            pep_status, risk_level, findings, warnings, recommendations,
            all_rules_triggered, edd_required, manual_review_required,
            matched_subjects, next_agent
        """
        findings: List[str] = []
        warnings: List[str] = []
        recommendations: List[str] = []
        all_rules: Set[str] = set()
        risk_influences: Set[str] = set()
        matched_subjects: List[Dict[str, Any]] = []

        edd_required = False
        manual_review_required = False

        # ── Per-subject rule evaluation ───────────────────────────────────────
        for result in match_results:
            subject_label = f"{result.subject_name} ({result.subject_role})"

            # ── PEP001: No Match ─────────────────────────────────────────────
            if result.match_confidence == MATCH_NONE:
                all_rules.add(RULE_NO_MATCH)
                findings.append(
                    f"[{RULE_NO_MATCH}] {subject_label}: No PEP match found. Clear to proceed."
                )
                result.rules_triggered.append(RULE_NO_MATCH)
                continue  # No further rules for this subject

            # Subject has a match — add to matched list
            matched_subjects.append(result.model_dump())

            # ── PEP002: Possible Match → Manual Review ────────────────────────
            if result.match_confidence == MATCH_POSSIBLE:
                all_rules.add(RULE_POSSIBLE_MATCH)
                result.rules_triggered.append(RULE_POSSIBLE_MATCH)
                result.requires_manual_review = True
                manual_review_required = True
                warnings.append(
                    f"[{RULE_POSSIBLE_MATCH}] {subject_label}: Possible PEP match "
                    f"(score {result.match_score:.0f}%). Manual Review required."
                )
                recommendations.append(
                    f"Initiate Manual Review for '{result.subject_name}' — "
                    f"possible PEP match against '{result.matched_record.full_name if result.matched_record else 'unknown'}' "
                    f"({result.match_score:.0f}% confidence)."
                )
                risk_influences.add(RISK_MEDIUM)

            # ── PEP003: Confirmed PEP → EDD ───────────────────────────────────
            if result.match_confidence == MATCH_CONFIRMED:
                all_rules.add(RULE_CONFIRMED_PEP)
                result.rules_triggered.append(RULE_CONFIRMED_PEP)
                result.requires_edd = True
                edd_required = True
                findings.append(
                    f"[{RULE_CONFIRMED_PEP}] {subject_label}: Confirmed PEP match — "
                    f"Enhanced Due Diligence (EDD) required."
                )
                recommendations.append(
                    f"[EDD REQUIRED] '{result.subject_name}' confirmed as PEP — "
                    f"'{result.matched_record.full_name if result.matched_record else ''}' "
                    f"({result.pep_category}). Conduct Enhanced Due Diligence immediately."
                )
                risk_influences.add(RISK_HIGH)

            # ── Category-specific rules (applied after match level rules) ─────
            category = result.pep_category or ""
            record = result.matched_record

            # ── PEP004: Foreign PEP ───────────────────────────────────────────
            if category == PEP_CATEGORY_FOREIGN:
                all_rules.add(RULE_FOREIGN_PEP)
                result.rules_triggered.append(RULE_FOREIGN_PEP)
                warnings.append(
                    f"[{RULE_FOREIGN_PEP}] {subject_label}: Foreign PEP detected. "
                    "Risk level increased."
                )
                risk_influences.add(RISK_HIGH)

            # ── PEP005: Family Member ─────────────────────────────────────────
            if category == PEP_CATEGORY_FAMILY_MEMBER:
                all_rules.add(RULE_FAMILY_MEMBER)
                result.rules_triggered.append(RULE_FAMILY_MEMBER)
                warnings.append(
                    f"[{RULE_FAMILY_MEMBER}] {subject_label}: Family member of PEP detected. "
                    "Risk level increased."
                )
                risk_influences.add(RISK_HIGH)

            # ── PEP005: Close Associate (same rule bucket as family) ──────────
            if category == PEP_CATEGORY_CLOSE_ASSOCIATE:
                all_rules.add(RULE_FAMILY_MEMBER)
                result.rules_triggered.append(RULE_FAMILY_MEMBER)
                warnings.append(
                    f"[{RULE_FAMILY_MEMBER}] {subject_label}: Close Associate of PEP detected."
                )
                risk_influences.add(RISK_MEDIUM)

            # ── PEP006: Current Office Holder ─────────────────────────────────
            if (
                record
                and record.is_current
                and category
                in (
                    PEP_CATEGORY_DOMESTIC,
                    PEP_CATEGORY_FOREIGN,
                    PEP_CATEGORY_INTERNATIONAL_ORG,
                )
            ):
                all_rules.add(RULE_CURRENT_OFFICE)
                result.rules_triggered.append(RULE_CURRENT_OFFICE)
                warnings.append(
                    f"[{RULE_CURRENT_OFFICE}] {subject_label}: Current office holder — "
                    "High Risk classification applied."
                )
                risk_influences.add(RISK_CRITICAL)

            # ── PEP007: Former PEP ────────────────────────────────────────────
            if category == PEP_CATEGORY_FORMER_PEP or (
                record and not record.is_current
            ):
                all_rules.add(RULE_FORMER_PEP)
                result.rules_triggered.append(RULE_FORMER_PEP)
                warnings.append(
                    f"[{RULE_FORMER_PEP}] {subject_label}: Former PEP — Medium Risk applied. "
                    "Enhanced monitoring recommended."
                )
                recommendations.append(
                    f"Apply enhanced ongoing monitoring for former PEP '{result.subject_name}'."
                )
                risk_influences.add(RISK_MEDIUM)

        # ── Aggregate PEP Status ──────────────────────────────────────────────
        all_confidences = {r.match_confidence for r in match_results}
        if MATCH_CONFIRMED in all_confidences:
            pep_status = PEP_STATUS_CONFIRMED
        elif MATCH_POSSIBLE in all_confidences:
            pep_status = PEP_STATUS_POSSIBLE
        else:
            pep_status = PEP_STATUS_CLEAR

        # ── Aggregate Risk Level ──────────────────────────────────────────────
        if RISK_CRITICAL in risk_influences:
            risk_level = RISK_CRITICAL
        elif RISK_HIGH in risk_influences:
            risk_level = RISK_HIGH
        elif RISK_MEDIUM in risk_influences:
            risk_level = RISK_MEDIUM
        else:
            risk_level = RISK_LOW

        # ── Summary finding for clear results ─────────────────────────────────
        if pep_status == PEP_STATUS_CLEAR:
            findings.append(
                f"All {len(match_results)} subject(s) screened — no PEP matches found."
            )

        return {
            "pep_status": pep_status,
            "risk_level": risk_level,
            "findings": findings,
            "warnings": warnings,
            "recommendations": recommendations,
            "all_rules_triggered": sorted(all_rules),
            "edd_required": edd_required,
            "manual_review_required": manual_review_required,
            "matched_subjects": matched_subjects,
            "next_agent": NEXT_AGENT,
        }
