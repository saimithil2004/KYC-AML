"""
PEP Validator — Subject Extraction
====================================

Builds the unified list of ScreeningSubjects from AgentState.

This module is intentionally the SINGLE place in the codebase that
knows how to extract person records from AgentState.  Future agents
that need to screen individuals (Sanctions Agent, Country Risk Agent)
import and reuse this function directly:

    from app.agents.pep.validator import PepValidator
    subjects = PepValidator.build_subjects(state)

No agent-specific logic lives here — just normalisation and deduplication.
"""

import uuid
from typing import Any, Dict, List

from app.agents.base.agent_state import AgentState
# ScreeningSubject and ROLE_* constants come from the shared screening package
from app.agents.screening.models import ScreeningSubject
from app.agents.screening.constants import (
    ROLE_CUSTOMER, ROLE_DIRECTOR, ROLE_UBO,
    ROLE_SHAREHOLDER, ROLE_AUTHORISED_SIGNATORY,
)


class PepValidator:
    """
    Stateless subject extractor + deduplication utility.

    All methods are static to preserve the same design convention used
    by KycValidator and CompanyValidator.
    """

    @staticmethod
    def build_subjects(state: AgentState) -> List[ScreeningSubject]:
        """
        Produces a deduplicated, normalised list of ScreeningSubjects
        from every relevant data source inside AgentState.

        Sources processed (in priority order):
          1. Customer record          → ROLE_CUSTOMER
          2. Directors list           → ROLE_DIRECTOR
          3. UBOs list                → ROLE_UBO
          4. Shareholders             → ROLE_SHAREHOLDER
          5. Authorised signatories   → ROLE_AUTHORISED_SIGNATORY

        Deduplication is performed by (full_name, dob) tuple so that the
        same real person appearing in multiple roles is only screened once.
        """
        subjects: List[ScreeningSubject] = []
        seen_keys: set = set()

        # ── 1. Customer ───────────────────────────────────────────────────────
        customer_subject = PepValidator._extract_customer(state.customer)
        if customer_subject:
            key = (customer_subject.full_name.lower(), customer_subject.dob or "")
            if key not in seen_keys:
                seen_keys.add(key)
                subjects.append(customer_subject)

        # ── 2. Directors ──────────────────────────────────────────────────────
        for idx, director in enumerate(state.directors or []):
            subject = PepValidator._extract_person(
                person=director,
                role=ROLE_DIRECTOR,
                idx=idx,
                company_name=PepValidator._get_company_name(state),
            )
            if subject:
                key = (subject.full_name.lower(), subject.dob or "")
                if key not in seen_keys:
                    seen_keys.add(key)
                    subjects.append(subject)

        # ── 3. UBOs ───────────────────────────────────────────────────────────
        for idx, ubo in enumerate(state.ubos or []):
            subject = PepValidator._extract_person(
                person=ubo,
                role=ROLE_UBO,
                idx=idx,
                company_name=PepValidator._get_company_name(state),
            )
            if subject:
                key = (subject.full_name.lower(), subject.dob or "")
                if key not in seen_keys:
                    seen_keys.add(key)
                    subjects.append(subject)

        # ── 4. Shareholders ───────────────────────────────────────────────────
        shareholders = (
            state.customer_profile.get("shareholders") or
            (state.companies[0].get("shareholders") if state.companies else None) or
            []
        )
        for idx, sh in enumerate(shareholders):
            subject = PepValidator._extract_person(
                person=sh,
                role=ROLE_SHAREHOLDER,
                idx=idx,
                company_name=PepValidator._get_company_name(state),
            )
            if subject:
                key = (subject.full_name.lower(), subject.dob or "")
                if key not in seen_keys:
                    seen_keys.add(key)
                    subjects.append(subject)

        # ── 5. Authorised Signatories ─────────────────────────────────────────
        signatories = state.customer_profile.get("authorised_signatories") or []
        for idx, sig in enumerate(signatories):
            subject = PepValidator._extract_person(
                person=sig,
                role=ROLE_AUTHORISED_SIGNATORY,
                idx=idx,
                company_name=PepValidator._get_company_name(state),
            )
            if subject:
                key = (subject.full_name.lower(), subject.dob or "")
                if key not in seen_keys:
                    seen_keys.add(key)
                    subjects.append(subject)

        return subjects

    # ── Private helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _extract_customer(customer: Dict[str, Any]) -> ScreeningSubject | None:
        """Extracts the primary customer as a ScreeningSubject."""
        if not customer:
            return None

        first = str(customer.get("first_name") or "").strip()
        last  = str(customer.get("last_name")  or "").strip()
        full_name = f"{first} {last}".strip()

        if not full_name:
            return None

        return ScreeningSubject(
            subject_id=f"subj-cust-{uuid.uuid4().hex[:8]}",
            role=ROLE_CUSTOMER,
            full_name=full_name,
            dob=str(customer.get("dob") or "").strip() or None,
            nationality=str(customer.get("nationality") or "").strip() or None,
            country=str(customer.get("country") or
                        customer.get("registered_country") or "").strip() or None,
            company_name=None,
        )

    @staticmethod
    def _extract_person(
        person: Dict[str, Any],
        role: str,
        idx: int,
        company_name: str | None = None,
    ) -> ScreeningSubject | None:
        """
        Normalises a raw person dict (director / UBO / shareholder / signatory)
        into a ScreeningSubject.  Supports multiple name field conventions.
        """
        # Support both "name" and "first_name"/"last_name" conventions
        if person.get("name"):
            full_name = str(person["name"]).strip()
        else:
            first = str(person.get("first_name") or "").strip()
            last  = str(person.get("last_name")  or "").strip()
            full_name = f"{first} {last}".strip()

        if not full_name:
            return None

        return ScreeningSubject(
            subject_id=f"subj-{role.lower()}-{idx}-{uuid.uuid4().hex[:6]}",
            role=role,
            full_name=full_name,
            dob=str(person.get("dob") or "").strip() or None,
            nationality=str(person.get("nationality") or "").strip() or None,
            country=str(person.get("country") or "").strip() or None,
            company_name=company_name,
        )

    @staticmethod
    def _get_company_name(state: AgentState) -> str | None:
        """Extracts a company name from state for association with non-customer subjects."""
        if state.companies:
            company = state.companies[0]
            return (
                str(company.get("company_name") or "").strip() or
                str(company.get("name") or "").strip() or
                None
            )
        if state.customer_profile.get("company_name"):
            return str(state.customer_profile["company_name"]).strip()
        return None

    @staticmethod
    def validate_subjects(subjects: List[ScreeningSubject]) -> List[str]:
        """
        Returns a list of validation warning strings for the subject list.
        Empty list means all subjects are valid.
        """
        warnings: List[str] = []
        if not subjects:
            warnings.append("No screening subjects could be extracted from AgentState.")
            return warnings

        for s in subjects:
            if not s.dob:
                warnings.append(
                    f"Subject '{s.full_name}' ({s.role}) is missing Date of Birth — "
                    "match accuracy is reduced."
                )
            if not s.nationality:
                warnings.append(
                    f"Subject '{s.full_name}' ({s.role}) is missing Nationality — "
                    "match accuracy is reduced."
                )
        return warnings
