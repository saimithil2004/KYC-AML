"""
Sanctions Validator — Subject Extraction & Normalisation
=========================================================

Extracts and normalises all individual and company screening subjects from AgentState.
Reuses the PEP Validator's subject extraction logic for individuals to prevent duplication,
and enriches the individuals with passport numbers. Also extracts company subjects.
"""

from typing import List, Dict, Any, Optional
import uuid

from app.agents.base.agent_state import AgentState
from app.agents.screening.models import ScreeningSubject, CompanyScreeningSubject
from app.agents.screening.constants import ROLE_CUSTOMER, ROLE_COMPANY
from app.agents.pep.validator import PepValidator


class SanctionsValidator:
    """
    Stateless validation and extraction helper for Sanctions Screening.
    """

    @staticmethod
    def build_individual_subjects(state: AgentState) -> List[ScreeningSubject]:
        """
        Extracts individual subjects using PepValidator.build_subjects(state)
        and enriches them with passport numbers from AgentState if available.
        """
        # Reuse PEP Agent subject extraction
        subjects = PepValidator.build_subjects(state)

        # Map to find and inject passport numbers
        for subj in subjects:
            passport = None
            if subj.role == ROLE_CUSTOMER:
                passport = (
                    state.customer.get("passport_number")
                    or state.customer_profile.get("passport_number")
                    or (
                        state.kyc_profile.get("passport_number")
                        if state.kyc_profile
                        else None
                    )
                )
            elif subj.role == "DIRECTOR":
                for d in state.directors or []:
                    if (
                        d.get("name") == subj.full_name
                        or f"{d.get('first_name', '')} {d.get('last_name', '')}".strip()
                        == subj.full_name
                    ):
                        passport = d.get("passport_number")
                        break
            elif subj.role == "UBO":
                for u in state.ubos or []:
                    if (
                        u.get("name") == subj.full_name
                        or f"{u.get('first_name', '')} {u.get('last_name', '')}".strip()
                        == subj.full_name
                    ):
                        passport = u.get("passport_number")
                        break
            elif subj.role == "SHAREHOLDER":
                shareholders = (
                    state.customer_profile.get("shareholders")
                    or (
                        state.companies[0].get("shareholders")
                        if state.companies
                        else None
                    )
                    or []
                )
                for s in shareholders:
                    if (
                        s.get("name") == subj.full_name
                        or f"{s.get('first_name', '')} {s.get('last_name', '')}".strip()
                        == subj.full_name
                    ):
                        passport = s.get("passport_number")
                        break
            elif subj.role == "AUTHORISED_SIGNATORY":
                signatories = state.customer_profile.get("authorised_signatories") or []
                for s in signatories:
                    if (
                        s.get("name") == subj.full_name
                        or f"{s.get('first_name', '')} {s.get('last_name', '')}".strip()
                        == subj.full_name
                    ):
                        passport = s.get("passport_number")
                        break

            if passport:
                subj.passport_number = str(passport).strip()

        return subjects

    @staticmethod
    def build_company_subjects(state: AgentState) -> List[CompanyScreeningSubject]:
        """
        Extracts all relevant company entities from AgentState for company sanctions screening.
        """
        companies: List[CompanyScreeningSubject] = []
        seen_keys = set()

        for idx, comp in enumerate(state.companies or []):
            name = comp.get("company_name") or comp.get("name")
            if not name:
                continue
            name_str = str(name).strip()
            reg_num = comp.get("registration_number") or comp.get("reg_number")
            reg_str = str(reg_num).strip() if reg_num else ""

            key = (name_str.lower(), reg_str.lower())
            if key not in seen_keys:
                seen_keys.add(key)
                companies.append(
                    CompanyScreeningSubject(
                        subject_id=f"subj-comp-{idx}-{uuid.uuid4().hex[:6]}",
                        role=ROLE_COMPANY,
                        company_name=name_str,
                        registration_number=reg_str or None,
                        country=comp.get("country")
                        or comp.get("registered_country")
                        or None,
                        business_address=(
                            comp.get("registered_address")
                            or comp.get("business_address")
                            or comp.get("address")
                            or None
                        ),
                    )
                )

        # Check if customer themselves is a business but not in state.companies list
        customer_type = str(state.customer.get("customer_type") or "").strip().lower()
        if customer_type == "business" and not state.companies:
            name = (
                state.customer.get("company_name")
                or state.customer.get("name")
                or f"{state.customer.get('first_name', '')} {state.customer.get('last_name', '')}".strip()
            )
            if name:
                name_str = str(name).strip()
                reg_num = state.customer.get(
                    "registration_number"
                ) or state.customer_profile.get("registration_number")
                reg_str = str(reg_num).strip() if reg_num else ""
                key = (name_str.lower(), reg_str.lower())
                if key not in seen_keys:
                    seen_keys.add(key)
                    companies.append(
                        CompanyScreeningSubject(
                            subject_id=f"subj-comp-cust-{uuid.uuid4().hex[:6]}",
                            role=ROLE_COMPANY,
                            company_name=name_str,
                            registration_number=reg_str or None,
                            country=state.customer.get("country")
                            or state.customer.get("registered_country")
                            or None,
                            business_address=state.customer.get("business_address")
                            or state.customer.get("address")
                            or None,
                        )
                    )

        return companies

    @staticmethod
    def validate_subjects(
        individuals: List[ScreeningSubject], companies: List[CompanyScreeningSubject]
    ) -> List[str]:
        """
        Returns a list of warnings about missing data on subjects or companies.
        """
        warnings = []
        for ind in individuals:
            if not ind.dob:
                warnings.append(
                    f"Individual '{ind.full_name}' is missing Date of Birth. Match accuracy reduced."
                )
            if not ind.passport_number:
                warnings.append(
                    f"Individual '{ind.full_name}' is missing Passport Number. Passport matching disabled."
                )

        for comp in companies:
            if not comp.registration_number:
                warnings.append(
                    f"Company '{comp.company_name}' is missing Registration Number. Company reg match disabled."
                )
            if not comp.country:
                warnings.append(
                    f"Company '{comp.company_name}' is missing Country. Country matching disabled."
                )

        return warnings
