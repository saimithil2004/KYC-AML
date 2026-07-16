from typing import Dict, Any, List, Tuple
from app.agents.company.constants import *


class CompanyValidator:
    """
    Stateless, deterministic field-level validator for company data.

    All methods accept raw dicts sourced from AgentState and return a
    (score, missing_tags, passed_summary_strings) triple following the
    exact same contract as KycValidator to keep the codebase uniform.
    """

    # ─────────────────────────────────────────────────────────
    # 1. Company Registration
    # ─────────────────────────────────────────────────────────
    @staticmethod
    def validate_registration(company: Dict[str, Any]) -> Tuple[float, List[str], List[str]]:
        """
        Checks: company_registration_number, incorporation_date.
        Max score: WEIGHT_REGISTRATION (20 pts — 10 per field).
        """
        score = 0.0
        missing: List[str] = []
        passed: List[str] = []

        reg_number = str(company.get("company_registration_number") or "").strip()
        if reg_number:
            score += 10.0
            passed.append(f"Company registration number present: {reg_number}")
        else:
            missing.append("company_registration_number")

        inc_date = str(company.get("incorporation_date") or "").strip()
        if inc_date:
            score += 10.0
            passed.append(f"Incorporation date present: {inc_date}")
        else:
            missing.append("incorporation_date")

        return score, missing, passed

    # ─────────────────────────────────────────────────────────
    # 2. Company Status
    # ─────────────────────────────────────────────────────────
    @staticmethod
    def validate_status(company: Dict[str, Any]) -> Tuple[float, List[str], List[str]]:
        """
        Checks: company_status field presence (15 pts).
        Active/Registered/Trading statuses earn full marks.
        Dissolved/Struck-off companies flag zero and mark high-risk.
        """
        score = 0.0
        missing: List[str] = []
        passed: List[str] = []

        status = str(company.get("company_status") or "").strip().lower()
        if not status:
            missing.append("company_status")
        elif status in ACTIVE_COMPANY_STATUSES:
            score += WEIGHT_STATUS
            passed.append(f"Company status is active: '{status}'")
        else:
            # Status present but not an active state — partial flag
            missing.append(f"company_status_inactive:{status}")

        return score, missing, passed

    # ─────────────────────────────────────────────────────────
    # 3. Registered Address
    # ─────────────────────────────────────────────────────────
    @staticmethod
    def validate_address(company: Dict[str, Any]) -> Tuple[float, List[str], List[str]]:
        """
        Checks four address sub-fields (15 pts — 3.75 each).
        """
        score = 0.0
        missing: List[str] = []
        passed: List[str] = []

        address_fields = {
            "registered_street":   "registered_street",
            "registered_city":     "registered_city",
            "registered_postcode": "registered_postcode",
            "registered_country":  "registered_country",
        }
        per_field = WEIGHT_ADDRESS / len(address_fields)

        for field_key, tag in address_fields.items():
            value = str(company.get(field_key) or "").strip()
            if value:
                score += per_field
                passed.append(f"Address field '{field_key}' is present")
            else:
                missing.append(tag)

        return score, missing, passed

    # ─────────────────────────────────────────────────────────
    # 4. Business / Industry Classification
    # ─────────────────────────────────────────────────────────
    @staticmethod
    def validate_industry(company: Dict[str, Any]) -> Tuple[float, List[str], List[str]]:
        """Checks: industry_code or business_type (10 pts)."""
        score = 0.0
        missing: List[str] = []
        passed: List[str] = []

        industry = (
            str(company.get("industry_code") or "").strip() or
            str(company.get("business_type") or "").strip()
        )
        if industry:
            score += WEIGHT_INDUSTRY
            passed.append(f"Industry classification present: '{industry}'")
        else:
            missing.append("industry_code_or_business_type")

        return score, missing, passed

    # ─────────────────────────────────────────────────────────
    # 5. Directors
    # ─────────────────────────────────────────────────────────
    @staticmethod
    def validate_directors(directors: List[Dict[str, Any]]) -> Tuple[float, List[str], List[str]]:
        """
        Checks: at least one director entry in state.directors (15 pts).
        Each director entry must have a name field to count.
        """
        score = 0.0
        missing: List[str] = []
        passed: List[str] = []

        valid_directors = [
            d for d in directors
            if str(d.get("name") or d.get("first_name") or "").strip()
        ]

        if valid_directors:
            score += WEIGHT_DIRECTORS
            passed.append(f"{len(valid_directors)} director(s) declared")
        else:
            missing.append("no_verified_directors")

        return score, missing, passed

    # ─────────────────────────────────────────────────────────
    # 6. Shareholders
    # ─────────────────────────────────────────────────────────
    @staticmethod
    def validate_shareholders(shareholders: List[Dict[str, Any]]) -> Tuple[float, List[str], List[str]]:
        """Checks: at least one shareholder entry (10 pts)."""
        score = 0.0
        missing: List[str] = []
        passed: List[str] = []

        valid_shareholders = [
            s for s in shareholders
            if str(s.get("name") or s.get("shareholder_name") or "").strip()
        ]

        if valid_shareholders:
            score += WEIGHT_SHAREHOLDERS
            passed.append(f"{len(valid_shareholders)} shareholder(s) declared")
        else:
            missing.append("no_shareholders")

        return score, missing, passed

    # ─────────────────────────────────────────────────────────
    # 7. Ultimate Beneficial Owners (UBOs)
    # ─────────────────────────────────────────────────────────
    @staticmethod
    def validate_ubos(ubos: List[Dict[str, Any]]) -> Tuple[float, List[str], List[str]]:
        """
        Checks: at least one UBO with ≥ 25% ownership declared (10 pts).
        UK POCA/MLR 2017 requires disclosure of all beneficial owners above 25%.
        """
        score = 0.0
        missing: List[str] = []
        passed: List[str] = []

        qualifying_ubos = [
            u for u in ubos
            if str(u.get("name") or "").strip()
            and float(u.get("ownership_percentage") or 0.0) >= 25.0
        ]

        if qualifying_ubos:
            score += WEIGHT_UBOS
            passed.append(f"{len(qualifying_ubos)} UBO(s) with ≥25% ownership declared")
        else:
            missing.append("no_qualifying_ubos")

        return score, missing, passed

    # ─────────────────────────────────────────────────────────
    # 8. Company Documents
    # ─────────────────────────────────────────────────────────
    @staticmethod
    def validate_company_documents(documents: List[Dict[str, Any]]) -> Tuple[float, List[str], List[str]]:
        """
        Checks: at least one company incorporation document uploaded (5 pts).
        Recognised types: certificate_of_incorporation, memorandum_of_association,
        articles_of_association, company_registration_certificate.
        """
        score = 0.0
        missing: List[str] = []
        passed: List[str] = []

        COMPANY_DOC_TYPES = {
            "certificate_of_incorporation",
            "memorandum_of_association",
            "articles_of_association",
            "company_registration_certificate",
            "company_document",
        }

        found = [
            d for d in documents
            if str(d.get("document_type") or "").strip().lower() in COMPANY_DOC_TYPES
        ]

        if found:
            score += WEIGHT_DOCUMENTS
            passed.append(f"{len(found)} company document(s) uploaded")
        else:
            missing.append("no_company_incorporation_documents")

        return score, missing, passed
