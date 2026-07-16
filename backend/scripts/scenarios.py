"""
AML Workflow — Shared Mock Scenarios
=====================================
Realistic mock customer datasets exercising every branch of the AML pipeline.

Scenarios
---------
1. INDIVIDUAL_CLEAN      — Standard individual, all clear
2. BUSINESS_CLEAN        — Standard business, all clear
3. PEP_MATCH             — Individual whose name matches PEP-UK-001
4. SANCTIONS_MATCH       — Individual matching SANC-IND-001 (terrorist financing)
5. HIGH_RISK_COUNTRY     — Individual with Russian nationality (HIGH risk jurisdiction)
6. BUSINESS_PEP_DIRECTOR — Business with a director who is a confirmed PEP
7. BUSINESS_SANCTIONED_UBO — Business whose UBO is a confirmed sanction match
"""

from typing import Dict, Any


# ─────────────────────────────────────────────────────────────────────────────
# Helper builders
# ─────────────────────────────────────────────────────────────────────────────

def _kyc_profile(
    occupation: str = "Software Engineer",
    source_of_funds: str = "Employment",
    source_of_wealth: str = "Savings",
    tax_residency: str = "United Kingdom",
) -> Dict[str, Any]:
    return {
        "occupation": occupation,
        "source_of_funds": source_of_funds,
        "source_of_wealth": source_of_wealth,
        "tax_residency": tax_residency,
    }


def _passport_doc(doc_number: str = "GB-123456789") -> Dict[str, Any]:
    return {"document_type": "passport", "document_number": doc_number}


def _base_individual(
    first_name: str,
    last_name: str,
    dob: str,
    nationality: str,
    country: str = "United Kingdom",
    passport_number: str = "GB-123456789",
) -> Dict[str, Any]:
    return {
        "customer_type": "individual",
        "first_name": first_name,
        "last_name": last_name,
        "dob": dob,
        "gender": "Male",
        "nationality": nationality,
        "street_address": "10 Downing Street",
        "city": "London",
        "postal_code": "SW1A 2AA",
        "country": country,
        "passport_number": passport_number,
    }


def _base_company(
    name: str,
    registration_number: str = "UK12345678",
    country: str = "United Kingdom",
) -> Dict[str, Any]:
    return {
        "customer_type": "business",
        "company_name": name,
        "registration_number": registration_number,
        "registered_country": country,
        "company_status": "active",
        "industry": "Financial Services",
        "registered_address": "1 Financial District, London, EC2V 8RF",
        "first_name": "Admin",
        "last_name": "Contact",
        "dob": "1985-01-01",
        "gender": "Female",
        "nationality": "United Kingdom",
        "street_address": "1 Financial District",
        "city": "London",
        "postal_code": "EC2V 8RF",
        "country": country,
    }


def _clean_director(first_name: str = "Alice", last_name: str = "Thompson") -> Dict[str, Any]:
    return {
        "first_name": first_name,
        "last_name": last_name,
        "dob": "1978-06-15",
        "nationality": "United Kingdom",
        "passport_number": "GB-DIRECTOR-001",
        "role": "director",
    }


def _clean_ubo(first_name: str = "Charles", last_name: str = "Bradford") -> Dict[str, Any]:
    return {
        "first_name": first_name,
        "last_name": last_name,
        "dob": "1970-03-22",
        "nationality": "United Kingdom",
        "passport_number": "GB-UBO-001",
        "ownership_percentage": 51.0,
        "role": "ubo",
    }


def _clean_company_entity(
    company_name: str = "Alpha Holdings Ltd",
    registration_number: str = "UK-HOLD-001",
    country: str = "United Kingdom",
) -> Dict[str, Any]:
    return {
        "company_name": company_name,
        "registration_number": registration_number,
        "country": country,
        "company_status": "active",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Scenario 1 — Normal Individual Customer (All Clear)
# ─────────────────────────────────────────────────────────────────────────────
SCENARIO_INDIVIDUAL_CLEAN: Dict[str, Any] = {
    "label": "Normal Individual Customer",
    "description": "Standard UK individual with fully complete KYC profile. No PEP, sanction, or country-risk flags expected.",
    "customer_id": "CUST-001",
    "case_id": "CASE-001",
    "customer": _base_individual(
        first_name="John",
        last_name="Smith",
        dob="1985-04-20",
        nationality="United Kingdom",
        passport_number="GB-001-CLEAN",
    ),
    "kyc_profile": _kyc_profile(),
    "uploaded_documents": [_passport_doc("GB-001-CLEAN")],
    "directors": [],
    "ubos": [],
    "companies": [],
    "transactions": [],
}

# ─────────────────────────────────────────────────────────────────────────────
# Scenario 2 — Business Customer (All Clear)
# ─────────────────────────────────────────────────────────────────────────────
SCENARIO_BUSINESS_CLEAN: Dict[str, Any] = {
    "label": "Business Customer (All Clear)",
    "description": "Fully verified UK business with clean directors, UBOs, and company documents.",
    "customer_id": "CUST-002",
    "case_id": "CASE-002",
    "customer": _base_company(
        name="Meridian Capital Ltd",
        registration_number="UK-MER-001",
    ),
    "kyc_profile": _kyc_profile(occupation="Financial Director"),
    "uploaded_documents": [
        _passport_doc("GB-002-CLEAN"),
        {"document_type": "company_registration", "document_number": "UK-MER-001"},
    ],
    "directors": [_clean_director()],
    "ubos": [_clean_ubo()],
    "companies": [_clean_company_entity()],
    "transactions": [],
}

# ─────────────────────────────────────────────────────────────────────────────
# Scenario 3 — PEP Match (Individual)
# ─────────────────────────────────────────────────────────────────────────────
# The MockPepProvider returns all PEP records.
# The name "James Alexander Wilson" matches PEP-UK-001 (Domestic PEP, current MP).
SCENARIO_PEP_MATCH: Dict[str, Any] = {
    "label": "PEP Match — Individual",
    "description": "Customer name matches a confirmed current domestic PEP (UK MP, Treasury Committee).",
    "customer_id": "CUST-003",
    "case_id": "CASE-003",
    "customer": _base_individual(
        first_name="James",
        last_name="Wilson",
        dob="1965-03-22",
        nationality="United Kingdom",
        passport_number="GB-003-PEP",
    ),
    "kyc_profile": _kyc_profile(occupation="Politician", source_of_wealth="Public Service"),
    "uploaded_documents": [_passport_doc("GB-003-PEP")],
    "directors": [],
    "ubos": [],
    "companies": [],
    "transactions": [],
}

# ─────────────────────────────────────────────────────────────────────────────
# Scenario 4 — Sanctions Match (Individual)
# ─────────────────────────────────────────────────────────────────────────────
# "Ahmed Al-Masri" matches SANC-IND-001 (UN sanctions, TERRORIST_FINANCING).
# Exact passport match SYR-987654-A bypasses score threshold → CONFIRMED_SANCTION.
SCENARIO_SANCTIONS_MATCH: Dict[str, Any] = {
    "label": "Sanctions Match — Individual",
    "description": "Customer passport and name match an active UN terrorist financing sanction entry.",
    "customer_id": "CUST-004",
    "case_id": "CASE-004",
    "customer": _base_individual(
        first_name="Ahmed",
        last_name="Al-Masri",
        dob="1978-11-12",
        nationality="Syria",
        country="Syria",
        passport_number="SYR-987654-A",
    ),
    "kyc_profile": _kyc_profile(
        occupation="Trader",
        source_of_funds="Unknown",
        source_of_wealth="Unknown",
        tax_residency="Syria",
    ),
    "uploaded_documents": [_passport_doc("SYR-987654-A")],
    "directors": [],
    "ubos": [],
    "companies": [],
    "transactions": [],
}

# ─────────────────────────────────────────────────────────────────────────────
# Scenario 5 — High Risk Country (Individual)
# ─────────────────────────────────────────────────────────────────────────────
# Russia is rated HIGH in MockCountryRiskProvider. Score deduction = 30 pts.
SCENARIO_HIGH_RISK_COUNTRY: Dict[str, Any] = {
    "label": "High Risk Country — Russia",
    "description": "Customer is a Russian national residing in Russia. Country risk is HIGH per FATF/UK watchlist.",
    "customer_id": "CUST-005",
    "case_id": "CASE-005",
    "customer": _base_individual(
        first_name="Alexei",
        last_name="Volkov",
        dob="1980-06-15",
        nationality="Russia",
        country="Russia",
        passport_number="RUS-VOL-001",
    ),
    "kyc_profile": _kyc_profile(
        occupation="Business Owner",
        source_of_funds="Business Income",
        source_of_wealth="Business",
        tax_residency="Russia",
    ),
    "uploaded_documents": [_passport_doc("RUS-VOL-001")],
    "directors": [],
    "ubos": [],
    "companies": [],
    "transactions": [],
}

# ─────────────────────────────────────────────────────────────────────────────
# Scenario 6 — Business with PEP Director
# ─────────────────────────────────────────────────────────────────────────────
SCENARIO_BUSINESS_PEP_DIRECTOR: Dict[str, Any] = {
    "label": "Business Customer — PEP Director",
    "description": "Business customer where one director is a confirmed domestic PEP. EDD required.",
    "customer_id": "CUST-006",
    "case_id": "CASE-006",
    "customer": _base_company(
        name="Wilson Capital Partners Ltd",
        registration_number="UK-WCP-001",
    ),
    "kyc_profile": _kyc_profile(occupation="Investment Management"),
    "uploaded_documents": [
        _passport_doc("GB-006-CLEAN"),
        {"document_type": "company_registration", "document_number": "UK-WCP-001"},
    ],
    "directors": [
        # PEP director — full name matches PEP-UK-001 (James Alexander Wilson, MP)
        # Using full name to score above the 75-point POSSIBLE_MATCH threshold
        {
            "first_name": "James Alexander",
            "last_name": "Wilson",
            "dob": "1965-03-22",
            "nationality": "United Kingdom",
            "passport_number": "GB-006-PEP",
            "role": "director",
        },
        # Clean co-director
        _clean_director(first_name="Helen", last_name="Barnes"),
    ],
    "ubos": [_clean_ubo()],
    "companies": [_clean_company_entity()],
    "transactions": [],
}

# ─────────────────────────────────────────────────────────────────────────────
# Scenario 7 — Business with Sanctioned UBO
# ─────────────────────────────────────────────────────────────────────────────
SCENARIO_BUSINESS_SANCTIONED_UBO: Dict[str, Any] = {
    "label": "Business Customer — Sanctioned UBO",
    "description": "Business customer where the beneficial owner matches an active sanctions entry.",
    "customer_id": "CUST-007",
    "case_id": "CASE-007",
    "customer": _base_company(
        name="Global Reach Trading Ltd",
        registration_number="UK-GRT-001",
    ),
    "kyc_profile": _kyc_profile(occupation="International Trade"),
    "uploaded_documents": [
        _passport_doc("GB-007-CLEAN"),
        {"document_type": "company_registration", "document_number": "UK-GRT-001"},
    ],
    "directors": [_clean_director()],
    "ubos": [
        # Sanctioned UBO — matches SANC-IND-001 (terrorist financing)
        {
            "first_name": "Ahmed",
            "last_name": "Al-Masri",
            "dob": "1978-11-12",
            "nationality": "Syria",
            "passport_number": "SYR-987654-A",
            "ownership_percentage": 75.0,
            "role": "ubo",
        }
    ],
    "companies": [_clean_company_entity()],
    "transactions": [],
}

# ─────────────────────────────────────────────────────────────────────────────
# Scenario 8 — Empty Customer (Validation Error Expected)
# ─────────────────────────────────────────────────────────────────────────────
SCENARIO_EMPTY_CUSTOMER: Dict[str, Any] = {
    "label": "Empty Customer (Validation Error)",
    "description": "Empty customer dict — KycAgent must raise AgentValidationError.",
    "customer_id": "CUST-008",
    "case_id": "CASE-008",
    "customer": {},
    "kyc_profile": {},
    "uploaded_documents": [],
    "directors": [],
    "ubos": [],
    "companies": [],
    "transactions": [],
}

# ─────────────────────────────────────────────────────────────────────────────
# Registry
# ─────────────────────────────────────────────────────────────────────────────
ALL_SCENARIOS: Dict[str, Dict[str, Any]] = {
    "individual_clean": SCENARIO_INDIVIDUAL_CLEAN,
    "business_clean": SCENARIO_BUSINESS_CLEAN,
    "pep_match": SCENARIO_PEP_MATCH,
    "sanctions_match": SCENARIO_SANCTIONS_MATCH,
    "high_risk_country": SCENARIO_HIGH_RISK_COUNTRY,
    "business_pep_director": SCENARIO_BUSINESS_PEP_DIRECTOR,
    "business_sanctioned_ubo": SCENARIO_BUSINESS_SANCTIONED_UBO,
    "empty_customer": SCENARIO_EMPTY_CUSTOMER,
}
