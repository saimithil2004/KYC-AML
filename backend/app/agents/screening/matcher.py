"""
Shared Screening — Matching Engine Base
========================================

Provides the core matching logic reused across all screening agents:
  • BaseScreeningMatcher: Compute individual composite scores
"""

from typing import List, Optional, Tuple
from rapidfuzz import fuzz

from app.agents.screening.constants import (
    WEIGHT_NAME,
    WEIGHT_DOB,
    WEIGHT_NATIONALITY,
    WEIGHT_COUNTRY,
    WEIGHT_ROLE,
    THRESHOLD_CONFIRMED,
    THRESHOLD_POSSIBLE,
)


class BaseScreeningMatcher:
    """
    Stateless base matching engine.
    Encapsulates core scoring equations and overrides so PEP and Sanctions matchers
    remain DRY and reuse the exact same formulas.
    """

    @staticmethod
    def compute_individual_score(
        subject_name: str,
        record_name: str,
        subject_dob: Optional[str],
        record_dob: Optional[str],
        subject_nationality: Optional[str],
        record_nationality: Optional[str],
        subject_country: Optional[str],
        record_country: Optional[str],
        subject_role: Optional[str],
        record_position: Optional[str],
    ) -> Tuple[float, List[str], bool, bool, float]:
        """
        Computes the standard composite score (0-100) based on weighted signals.

        Returns
        -------
        Tuple[float, List[str], bool, bool, float]
            - Composite score (0-100) before CONFIRMED/POSSIBLE threshold checks
            - List of reason strings
            - dob_match (bool)
            - nat_match (bool)
            - name_similarity score (0-100)
        """
        reasons: List[str] = []
        score = 0.0

        # ── Signal 1: Name (50 %) ────────────────────────────────────────────
        name_similarity = fuzz.token_sort_ratio(
            subject_name.lower().strip(),
            record_name.lower().strip(),
        )
        score += name_similarity * WEIGHT_NAME
        reasons.append(f"Name similarity {name_similarity:.0f}%")

        # ── Signal 2: DOB (20 %) ─────────────────────────────────────────────
        dob_match = False
        if subject_dob and record_dob:
            if subject_dob.strip() == record_dob.strip():
                score += 100 * WEIGHT_DOB
                dob_match = True
                reasons.append("DOB exact match")

        # ── Signal 3: Nationality (15 %) ─────────────────────────────────────
        nat_match = False
        if subject_nationality and record_nationality:
            if (
                subject_nationality.strip().lower()
                == record_nationality.strip().lower()
            ):
                score += 100 * WEIGHT_NATIONALITY
                nat_match = True
                reasons.append("Nationality match")

        # ── Signal 4: Country (10 %) ──────────────────────────────────────────
        if subject_country and record_country:
            if subject_country.strip().lower() == record_country.strip().lower():
                score += 100 * WEIGHT_COUNTRY
                reasons.append("Country match")

        # ── Signal 5: Role keyword (5 %) ──────────────────────────────────────
        if record_position and subject_role:
            role_lower = subject_role.lower()
            pos_lower = record_position.lower()
            if any(
                kw in pos_lower
                for kw in [
                    role_lower,
                    "director",
                    "minister",
                    "governor",
                    "official",
                    "senator",
                ]
            ):
                score += 100 * WEIGHT_ROLE
                reasons.append("Role keyword match")

        return score, reasons, dob_match, nat_match, name_similarity

    @staticmethod
    def apply_confirmed_guards(
        score: float,
        name_similarity: float,
        dob_match: bool,
        nat_match: bool,
        reasons: List[str],
    ) -> float:
        """
        Applies standard anti-false-positive and confirmed overrides/guards.
        Reused by PEP and Sanctions individual screeners.
        """
        # Exact name + secondary signal -> confirmed override
        if name_similarity == 100 and (dob_match or nat_match):
            score = max(score, THRESHOLD_CONFIRMED)
            reasons.append("(exact name + secondary signal → CONFIRMED override)")
        # Low name similarity cap
        elif score >= THRESHOLD_CONFIRMED and name_similarity < 85:
            score = min(score, THRESHOLD_POSSIBLE - 1)
            reasons.append("(name similarity too low for CONFIRMED)")
        # No secondary signals cap
        elif score >= THRESHOLD_CONFIRMED and not (dob_match or nat_match):
            score = min(score, THRESHOLD_POSSIBLE - 1)
            reasons.append("(no secondary signal — capped at POSSIBLE)")

        return score
