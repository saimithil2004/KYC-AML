from typing import Dict, Any, List, Tuple
from app.agents.kyc.constants import *

class KycValidator:
    """
    Validates individual fields and calculates individual validation score components.
    Does not run business decisions or rule evaluations.
    """

    @staticmethod
    def validate_personal_info(customer: Dict[str, Any]) -> Tuple[float, List[str], List[str]]:
        """Validates Name, DOB, Gender, Nationality. Max 20 points."""
        score = 0.0
        missing = []
        passed = []

        if customer.get("first_name") and customer.get("last_name"):
            score += 5.0
            passed.append("Name")
        else:
            missing.append("first_name_or_last_name")

        if customer.get("dob"):
            score += 5.0
            passed.append("Date of Birth")
        else:
            missing.append("dob")

        if customer.get("gender"):
            score += 5.0
            passed.append("Gender")
        else:
            missing.append("gender")

        if customer.get("nationality"):
            score += 5.0
            passed.append("Nationality")
        else:
            missing.append("nationality")

        return score, missing, passed

    @staticmethod
    def validate_address(customer: Dict[str, Any]) -> Tuple[float, List[str], List[str]]:
        """Validates Street, City, Postal Code, Country. Max 20 points."""
        score = 0.0
        missing = []
        passed = []

        if customer.get("street_address"):
            score += 5.0
            passed.append("Street Address")
        else:
            missing.append("street_address")

        if customer.get("city"):
            score += 5.0
            passed.append("City")
        else:
            missing.append("city")

        if customer.get("postal_code"):
            score += 5.0
            passed.append("Postal Code")
        else:
            missing.append("postal_code")

        if customer.get("country"):
            score += 5.0
            passed.append("Country")
        else:
            missing.append("country")

        return score, missing, passed

    @staticmethod
    def validate_identity_documents(documents: List[Dict[str, Any]]) -> Tuple[float, List[str], List[str]]:
        """Validates presence of passport, national_id, or driving_licence. Max 20 points."""
        passed_docs = []
        for doc in documents:
            doc_type = str(doc.get("document_type") or "").strip().lower()
            if doc_type in ["passport", "national_id", "driving_licence"]:
                passed_docs.append(doc_type)

        if len(passed_docs) > 0:
            return 20.0, [], [f"Identity Document ({', '.join(passed_docs)})"]
        return 0.0, ["passport_or_national_id_or_driving_licence"], []

    @staticmethod
    def validate_occupation(kyc_profile: Dict[str, Any]) -> Tuple[float, List[str], List[str]]:
        """Validates Occupation. Max 10 points."""
        if kyc_profile.get("occupation"):
            return 10.0, [], ["Occupation"]
        return 0.0, ["occupation"], []

    @staticmethod
    def validate_source_of_funds(kyc_profile: Dict[str, Any]) -> Tuple[float, List[str], List[str]]:
        """Validates Source of Funds. Max 15 points."""
        if kyc_profile.get("source_of_funds"):
            return 15.0, [], ["Source of Funds"]
        return 0.0, ["source_of_funds"], []

    @staticmethod
    def validate_source_of_wealth(kyc_profile: Dict[str, Any]) -> Tuple[float, List[str], List[str]]:
        """Validates Source of Wealth. Max 10 points."""
        if kyc_profile.get("source_of_wealth"):
            return 10.0, [], ["Source of Wealth"]
        return 0.0, ["source_of_wealth"], []

    @staticmethod
    def validate_tax_residency(kyc_profile: Dict[str, Any]) -> Tuple[float, List[str], List[str]]:
        """Validates Tax Residency. Max 5 points."""
        if kyc_profile.get("tax_residency"):
            return 5.0, [], ["Tax Residency"]
        return 0.0, ["tax_residency"], []
