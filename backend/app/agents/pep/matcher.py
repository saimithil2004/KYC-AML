"""
PEP Matching Engine
====================

Multi-signal scoring that combines:
  • Full name similarity   — RapidFuzz token_sort_ratio   (weight 50 %)
  • Date of birth          — Exact match                  (weight 20 %)
  • Nationality            — Exact match                  (weight 15 %)
  • Country                — Exact match                  (weight 10 %)
  • Role keyword           — Keyword presence check       (weight  5 %)

A match is only classified as CONFIRMED when ALL of: name ≥ 90 + at least
one additional signal (DOB or nationality) match.  This prevents false
positives caused by common names.

Score thresholds (defined in constants.py):
  ≥ THRESHOLD_CONFIRMED (95) → CONFIRMED_MATCH
  ≥ THRESHOLD_POSSIBLE  (75) → POSSIBLE_MATCH
  < THRESHOLD_POSSIBLE       → NO_MATCH
"""

from typing import List, Optional, Tuple

from app.agents.pep.models import ScreeningSubject, PepRecord, PepMatchResult
from app.agents.pep.constants import (
    MATCH_CONFIRMED,
    MATCH_POSSIBLE,
    MATCH_NONE,
    THRESHOLD_CONFIRMED,
    THRESHOLD_POSSIBLE,
)
from app.agents.screening.matcher import BaseScreeningMatcher


class PepMatcher:
    """
    Stateless matching engine.

    ``score_subject()`` evaluates a single subject against a list of
    PEP records and returns the best PepMatchResult.
    """

    # ── Public API ────────────────────────────────────────────────────────────
    @staticmethod
    def score_subject(
        subject: ScreeningSubject,
        candidates: List[PepRecord],
    ) -> PepMatchResult:
        """
        Scores a subject against all candidate PEP records and returns
        the highest-scoring match result.

        If no candidate reaches THRESHOLD_POSSIBLE the result will have
        match_confidence=NO_MATCH and match_score < 75.
        """
        if not candidates:
            return PepMatcher._no_match_result(subject)

        best_score = 0.0
        best_record: Optional[PepRecord] = None
        best_reason = "No match found"

        for record in candidates:
            score, reason = PepMatcher._compute_score(subject, record)
            if score > best_score:
                best_score = score
                best_record = record
                best_reason = reason

        return PepMatcher._build_result(subject, best_record, best_score, best_reason)

    # ── Scoring Logic ─────────────────────────────────────────────────────────
    @staticmethod
    def _compute_score(
        subject: ScreeningSubject,
        record: PepRecord,
    ) -> Tuple[float, str]:
        """
        Computes the composite match score (0–100) for one subject/record pair
        by delegating to the shared BaseScreeningMatcher.
        Returns (score, human_readable_reason).
        """
        score, reasons, dob_match, nat_match, name_similarity = (
            BaseScreeningMatcher.compute_individual_score(
                subject_name=subject.full_name,
                record_name=record.full_name,
                subject_dob=subject.dob,
                record_dob=record.dob,
                subject_nationality=subject.nationality,
                record_nationality=record.nationality,
                subject_country=subject.country,
                record_country=record.country,
                subject_role=subject.role,
                record_position=record.position,
            )
        )
        score = BaseScreeningMatcher.apply_confirmed_guards(
            score=score,
            name_similarity=name_similarity,
            dob_match=dob_match,
            nat_match=nat_match,
            reasons=reasons,
        )
        return round(score, 2), "; ".join(reasons)

    # ── Result Builders ───────────────────────────────────────────────────────
    @staticmethod
    def _build_result(
        subject: ScreeningSubject,
        record: Optional[PepRecord],
        score: float,
        reason: str,
    ) -> PepMatchResult:
        if score >= THRESHOLD_CONFIRMED:
            confidence = MATCH_CONFIRMED
        elif score >= THRESHOLD_POSSIBLE:
            confidence = MATCH_POSSIBLE
        else:
            confidence = MATCH_NONE
            record = None  # Don't expose partial record for clear results

        return PepMatchResult(
            subject_id=subject.subject_id,
            subject_name=subject.full_name,
            subject_role=subject.role,
            match_confidence=confidence,
            match_score=score,
            matched_record=record,
            pep_category=record.category if record else None,
            reason=reason,
        )

    @staticmethod
    def _no_match_result(subject: ScreeningSubject) -> PepMatchResult:
        return PepMatchResult(
            subject_id=subject.subject_id,
            subject_name=subject.full_name,
            subject_role=subject.role,
            match_confidence=MATCH_NONE,
            match_score=0.0,
            matched_record=None,
            pep_category=None,
            reason="Provider returned no candidates",
        )
