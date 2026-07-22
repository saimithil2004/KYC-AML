from typing import Dict, Any, List, Set, Tuple
from app.agents.kyc.constants import *
from app.agents.base.exceptions import AgentValidationError


class KycRulesEngine:
    """
    Evaluates rule criteria, adds structured warnings/recommendations,
    raises validation errors for critical issues, and routes to next agents.
    """

    @staticmethod
    def evaluate(
        customer: Dict[str, Any],
        kyc_profile: Dict[str, Any],
        documents: List[Dict[str, Any]],
        missing_fields: List[str],
    ) -> Dict[str, Any]:
        passed_rules: List[str] = []
        failed_rules: List[str] = []
        errors: List[str] = []
        warnings: List[str] = []
        recommendations: List[str] = []

        # Track risk impact
        risk_influences: Set[str] = set()

        # Rule 1: Missing Full Name -> Critical Validation Error
        if "first_name_or_last_name" in missing_fields:
            failed_rules.append(RULE_MISSING_NAME)
            errors.append(f"[{RULE_MISSING_NAME}] Full Name is missing.")
        else:
            passed_rules.append(RULE_MISSING_NAME)

        # Rule 2: Missing Date of Birth -> Critical Validation Error
        if "dob" in missing_fields:
            failed_rules.append(RULE_MISSING_DOB)
            errors.append(f"[{RULE_MISSING_DOB}] Date of Birth is missing.")
        else:
            passed_rules.append(RULE_MISSING_DOB)

        # Raise critical validation errors immediately as per existing exceptions model
        if errors:
            raise AgentValidationError(
                message="Critical KYC validation failure: mandatory fields missing.",
                details={"errors": errors},
            )

        # Rule 3: Missing Nationality -> Warning
        if "nationality" in missing_fields:
            failed_rules.append(RULE_MISSING_NATIONALITY)
            warnings.append(
                f"[{RULE_MISSING_NATIONALITY}] Nationality is missing from customer profile."
            )
        else:
            passed_rules.append(RULE_MISSING_NATIONALITY)

        # Rule 4: No Identity Document uploaded -> High Risk
        if "passport_or_national_id_or_driving_licence" in missing_fields:
            failed_rules.append(RULE_MISSING_DOCS)
            warnings.append(
                f"[{RULE_MISSING_DOCS}] No identity verification document (passport, national ID, driving licence) uploaded."
            )
            risk_influences.add(RISK_HIGH)
        else:
            passed_rules.append(RULE_MISSING_DOCS)

        # Rule 5: Source of Wealth missing -> Manual Review
        if "source_of_wealth" in missing_fields:
            failed_rules.append(RULE_MISSING_SOW)
            recommendations.append(
                f"[{RULE_MISSING_SOW}] Recommend Manual Review due to missing Source of Wealth declaration."
            )
        else:
            passed_rules.append(RULE_MISSING_SOW)

        # Rule 6: Source of Funds missing -> Medium Risk
        if "source_of_funds" in missing_fields:
            failed_rules.append(RULE_MISSING_SOF)
            warnings.append(
                f"[{RULE_MISSING_SOF}] Source of Funds is missing from declaration."
            )
            risk_influences.add(RISK_MEDIUM)
        else:
            passed_rules.append(RULE_MISSING_SOF)

        # Rule 7: Address incomplete -> Medium Risk
        address_parts = ["street_address", "city", "postal_code", "country"]
        is_address_incomplete = any(part in missing_fields for part in address_parts)
        if is_address_incomplete:
            failed_rules.append(RULE_MISSING_ADDRESS)
            warnings.append(
                f"[{RULE_MISSING_ADDRESS}] Residential address is incomplete."
            )
            risk_influences.add(RISK_MEDIUM)
        else:
            passed_rules.append(RULE_MISSING_ADDRESS)

        # Other optional fields
        if "occupation" in missing_fields:
            failed_rules.append(RULE_MISSING_OCCUPATION)
        else:
            passed_rules.append(RULE_MISSING_OCCUPATION)

        if "tax_residency" in missing_fields:
            failed_rules.append(RULE_MISSING_TAX_RESIDENCY)
        else:
            passed_rules.append(RULE_MISSING_TAX_RESIDENCY)

        if "gender" in missing_fields:
            failed_rules.append(RULE_MISSING_GENDER)
        else:
            passed_rules.append(RULE_MISSING_GENDER)

        # Evaluate risk level based on business rules
        if RISK_HIGH in risk_influences:
            risk_level = RISK_HIGH
        elif RISK_MEDIUM in risk_influences:
            risk_level = RISK_MEDIUM
        else:
            risk_level = RISK_LOW

        # Rule 8: Determine next workflow routing
        customer_type = str(customer.get("customer_type") or "").strip().lower()
        if customer_type == "business":
            next_agent = "company_agent"
            recommendations.append(
                "Business customer detected. Forwarding workflow to Company Agent."
            )
        else:
            next_agent = "pep_agent"

        return {
            "passed_rules": passed_rules,
            "failed_rules": failed_rules,
            "warnings": warnings,
            "recommendations": recommendations,
            "risk_level": risk_level,
            "next_agent": next_agent,
        }
