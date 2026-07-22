"""
Sanctions Matching Engine
==========================

Performs multi-signal matching for individuals and companies:
  • Individuals: Name (50%), DOB (20%), Nationality (15%), Country (10%), Role (5%)
                 Passport Number Match (Boosts to CONFIRMED / 100%)
  • Companies: Company Name (55%), Reg Number (30%), Country (15%)
               Reg Number Match (Boosts to CONFIRMED / 100%)

Reuses BaseScreeningMatcher to prevent code duplication.
"""

from typing import List, Optional, Tuple, Union
from rapidfuzz import fuzz

from app.agents.screening.models import ScreeningSubject, CompanyScreeningSubject
from app.agents.screening.constants import (
    MATCH_CONFIRMED,
    MATCH_POSSIBLE,
    MATCH_NONE,
    THRESHOLD_CONFIRMED,
    THRESHOLD_POSSIBLE,
    ENTITY_INDIVIDUAL,
    ENTITY_COMPANY,
)
from app.agents.screening.matcher import BaseScreeningMatcher
from app.agents.sanctions.models import SanctionRecord, SanctionMatchResult
from app.agents.sanctions.constants import (
    WEIGHT_COMPANY_NAME,
    WEIGHT_REG_NUMBER,
    WEIGHT_COMPANY_COUNTRY,
)


class SanctionsMatcher:
    """
    Screener and matcher for sanctions records.
    """

    @staticmethod
    def score_individual(
        subject: ScreeningSubject, candidates: List[SanctionRecord]
    ) -> SanctionMatchResult:
        """
        Scores an individual subject against all candidate individual sanctions records.
        """
        if not candidates:
            return SanctionsMatcher._no_match_result(subject, ENTITY_INDIVIDUAL)

        best_score = 0.0
        best_record: Optional[SanctionRecord] = None
        best_reason = "No match found"
        best_matched_fields: List[str] = []

        for record in candidates:
            score, reason, matched_fields = SanctionsMatcher._compute_individual_score(
                subject, record
            )
            if score > best_score:
                best_score = score
                best_record = record
                best_reason = reason
                best_matched_fields = matched_fields

        return SanctionsMatcher._build_result(
            subject_id=subject.subject_id,
            subject_name=subject.full_name,
            subject_role=subject.role,
            entity_type=ENTITY_INDIVIDUAL,
            score=best_score,
            record=best_record,
            reason=best_reason,
            matched_fields=best_matched_fields,
        )

    @staticmethod
    def score_company(
        subject: CompanyScreeningSubject, candidates: List[SanctionRecord]
    ) -> SanctionMatchResult:
        """
        Scores a company subject against all candidate company sanctions records.
        """
        if not candidates:
            return SanctionsMatcher._no_match_result(subject, ENTITY_COMPANY)

        best_score = 0.0
        best_record: Optional[SanctionRecord] = None
        best_reason = "No match found"
        best_matched_fields: List[str] = []

        for record in candidates:
            score, reason, matched_fields = SanctionsMatcher._compute_company_score(
                subject, record
            )
            if score > best_score:
                best_score = score
                best_record = record
                best_reason = reason
                best_matched_fields = matched_fields

        return SanctionsMatcher._build_result(
            subject_id=subject.subject_id,
            subject_name=subject.company_name,
            subject_role=subject.role,
            entity_type=ENTITY_COMPANY,
            score=best_score,
            record=best_record,
            reason=best_reason,
            matched_fields=best_matched_fields,
        )

    # ─── Individual Matching Logic ───────────────────────────────────────────
    @staticmethod
    def _compute_individual_score(
        subject: ScreeningSubject, record: SanctionRecord
    ) -> Tuple[float, str, List[str]]:
        """
        Computes composite individual match score, reusing BaseScreeningMatcher.
        Includes Passport Number matching override.
        """
        score, reasons, dob_match, nat_match, name_sim = (
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
                record_position=None,  # No role matching in sanctions
            )
        )

        matched_fields = ["name"]
        if dob_match:
            matched_fields.append("dob")
        if nat_match:
            matched_fields.append("nationality")
        if (
            subject.country
            and record.country
            and subject.country.strip().lower() == record.country.strip().lower()
        ):
            matched_fields.append("country")

        # Passport Number check (direct override)
        passport_matched = False
        if subject.passport_number and record.passport_number:
            subj_pp = subject.passport_number.strip().replace(" ", "").lower()
            rec_pp = record.passport_number.strip().replace(" ", "").lower()
            if subj_pp == rec_pp:
                passport_matched = True
                matched_fields.append("passport")

        # Apply confirmed guards or passport match boost
        if passport_matched:
            # Passport matches exactly -> if name similarity is reasonably high (>= 70%), it is CONFIRMED
            if name_sim >= 70:
                score = 100.0
                reasons.append(
                    "Passport number exact match (Name similarity >= 70% -> CONFIRMED)"
                )
            else:
                # Name is too different, cap at POSSIBLE_MATCH to prevent identity theft false positives
                score = min(score, THRESHOLD_POSSIBLE)
                reasons.append(
                    "Passport number exact match but Name similarity too low (< 70% -> Capped)"
                )
        else:
            score = BaseScreeningMatcher.apply_confirmed_guards(
                score=score,
                name_similarity=name_sim,
                dob_match=dob_match,
                nat_match=nat_match,
                reasons=reasons,
            )

        # Sanctions override: If name similarity is high (>= 80%), ensure it is at least a POSSIBLE_MATCH
        if name_sim >= 80.0:
            score = max(score, THRESHOLD_POSSIBLE)
            reasons.append(
                f"(high name similarity {name_sim:.0f}% → POSSIBLE_MATCH override)"
            )

        return round(score, 2), "; ".join(reasons), matched_fields

    # ─── Company Matching Logic ──────────────────────────────────────────────
    @staticmethod
    def _compute_company_score(
        subject: CompanyScreeningSubject, record: SanctionRecord
    ) -> Tuple[float, str, List[str]]:
        """
        Computes composite company match score.
        Includes Registration Number match override.
        """
        reasons: List[str] = []
        matched_fields: List[str] = []
        score = 0.0

        # Company Name (55%)
        name_sim = fuzz.token_sort_ratio(
            subject.company_name.lower().strip(),
            record.full_name.lower().strip(),  # Record stores company name under full_name
        )
        score += name_sim * WEIGHT_COMPANY_NAME
        reasons.append(f"Company name similarity {name_sim:.0f}%")
        matched_fields.append("company_name")

        # Reg Number (30%)
        reg_matched = False
        if subject.registration_number and record.registration_number:
            subj_reg = subject.registration_number.strip().replace(" ", "").lower()
            rec_reg = record.registration_number.strip().replace(" ", "").lower()
            if subj_reg == rec_reg:
                reg_matched = True
                score += 100 * WEIGHT_REG_NUMBER
                reasons.append("Company registration number match")
                matched_fields.append("registration_number")

        # Country (15%)
        country_matched = False
        if subject.country and record.country:
            if subject.country.strip().lower() == record.country.strip().lower():
                country_matched = True
                score += 100 * WEIGHT_COMPANY_COUNTRY
                reasons.append("Company country match")
                matched_fields.append("country")

        # Overrides & Guards
        if reg_matched:
            # Registration number matches exactly -> if company name similarity is reasonably high (>= 70%) -> CONFIRMED
            if name_sim >= 70:
                score = 100.0
                reasons.append(
                    "Exact Registration Number Match (Name similarity >= 70% -> CONFIRMED)"
                )
            else:
                score = min(score, THRESHOLD_POSSIBLE)
                reasons.append(
                    "Registration Number Match but Company Name similarity too low (< 70% -> Capped)"
                )
        else:
            # Exact name + country match -> CONFIRMED override
            if name_sim == 100.0 and country_matched:
                score = max(score, THRESHOLD_CONFIRMED)
                reasons.append(
                    "(exact company name + country match → CONFIRMED override)"
                )
            # High company name similarity -> at least POSSIBLE
            elif name_sim >= 80.0:
                score = max(score, THRESHOLD_POSSIBLE)
                reasons.append(
                    f"(high company name similarity {name_sim:.0f}% → POSSIBLE_MATCH override)"
                )
            else:
                # Guard name match only
                if score >= THRESHOLD_CONFIRMED and name_sim < 85:
                    score = min(score, THRESHOLD_POSSIBLE - 1)
                    reasons.append("(Company name similarity too low for CONFIRMED)")
                elif score >= THRESHOLD_CONFIRMED and not country_matched:
                    score = min(score, THRESHOLD_POSSIBLE - 1)
                    reasons.append("(No country signal - capped at POSSIBLE)")

        return round(score, 2), "; ".join(reasons), matched_fields

    # ─── Helper Builders ─────────────────────────────────────────────────────
    @staticmethod
    def _build_result(
        subject_id: str,
        subject_name: str,
        subject_role: str,
        entity_type: str,
        score: float,
        record: Optional[SanctionRecord],
        reason: str,
        matched_fields: List[str],
    ) -> SanctionMatchResult:
        if score >= THRESHOLD_CONFIRMED:
            confidence = MATCH_CONFIRMED
        elif score >= THRESHOLD_POSSIBLE:
            confidence = MATCH_POSSIBLE
        else:
            confidence = MATCH_NONE
            record = None

        return SanctionMatchResult(
            subject_id=subject_id,
            subject_name=subject_name,
            subject_role=subject_role,
            entity_type=entity_type,
            match_confidence=confidence,
            match_score=score,
            matched_record=record,
            sanction_category=record.sanction_category if record else None,
            matched_list=record.sanction_list if record else None,
            matched_fields=matched_fields,
            reason=reason,
        )

    @staticmethod
    def _no_match_result(
        subject: Union[ScreeningSubject, CompanyScreeningSubject], entity_type: str
    ) -> SanctionMatchResult:
        name = (
            subject.full_name
            if isinstance(subject, ScreeningSubject)
            else subject.company_name
        )
        return SanctionMatchResult(
            subject_id=subject.subject_id,
            subject_name=name,
            subject_role=subject.role,
            entity_type=entity_type,
            match_confidence=MATCH_NONE,
            match_score=0.0,
            matched_record=None,
            matched_fields=[],
            reason="No sanctions candidates found",
        )
