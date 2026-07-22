from typing import Dict, Any, List, Set
from app.agents.company.constants import *


class CompanyRulesEngine:
    """
    Deterministic, LLM-free business rules engine for company verification.

    Evaluates the aggregated missing-field list produced by CompanyValidator,
    assigns risk tiers, generates structured warnings / recommendations,
    and returns the LangGraph-compatible routing destination (next_agent).

    The engine NEVER writes to AgentState or calls external services.
    """

    @staticmethod
    def evaluate(
        company: Dict[str, Any],
        missing_fields: List[str],
        directors: List[Dict[str, Any]],
        shareholders: List[Dict[str, Any]],
        ubos: List[Dict[str, Any]],
    ) -> Dict[str, Any]:

        passed_rules: List[str] = []
        failed_rules: List[str] = []
        warnings:     List[str] = []
        recommendations: List[str] = []
        risk_influences: Set[str] = set()

        # ── CO001 · Company Registration Number ─────────────────────────────
        if "company_registration_number" in missing_fields:
            failed_rules.append(RULE_MISSING_REG_NUMBER)
            warnings.append(
                f"[{RULE_MISSING_REG_NUMBER}] Company registration number is missing. "
                "This is a mandatory field for UK company verification."
            )
            risk_influences.add(RISK_HIGH)
        else:
            passed_rules.append(RULE_MISSING_REG_NUMBER)

        # ── CO002 · Company Status Presence ─────────────────────────────────
        status_missing = any(f == "company_status" or f.startswith("company_status") for f in missing_fields)
        if status_missing:
            failed_rules.append(RULE_MISSING_STATUS)
            warnings.append(
                f"[{RULE_MISSING_STATUS}] Company status field is missing or not declared."
            )
            risk_influences.add(RISK_MEDIUM)
        else:
            passed_rules.append(RULE_MISSING_STATUS)

        # ── CO003 · Dissolved / Inactive Company ────────────────────────────
        inactive_status = any(f.startswith("company_status_inactive:") for f in missing_fields)
        if inactive_status:
            raw_status = next(
                (f.split(":", 1)[1] for f in missing_fields if f.startswith("company_status_inactive:")),
                "unknown"
            )
            failed_rules.append(RULE_DISSOLVED_COMPANY)
            warnings.append(
                f"[{RULE_DISSOLVED_COMPANY}] Company status is '{raw_status}'. "
                "Only Active/Registered/Trading companies pass verification."
            )
            risk_influences.add(RISK_HIGH)
        else:
            passed_rules.append(RULE_DISSOLVED_COMPANY)

        # ── CO004 · Registered Address ──────────────────────────────────────
        address_tags = {
            "registered_street", "registered_city",
            "registered_postcode", "registered_country",
        }
        if address_tags & set(missing_fields):
            failed_rules.append(RULE_MISSING_ADDRESS)
            warnings.append(
                f"[{RULE_MISSING_ADDRESS}] Registered company address is incomplete. "
                "All four address fields (street, city, postcode, country) are required."
            )
            risk_influences.add(RISK_MEDIUM)
        else:
            passed_rules.append(RULE_MISSING_ADDRESS)

        # ── CO005 · Industry Classification ─────────────────────────────────
        if "industry_code_or_business_type" in missing_fields:
            failed_rules.append(RULE_MISSING_INDUSTRY)
            warnings.append(
                f"[{RULE_MISSING_INDUSTRY}] Industry code or business type is missing."
            )
        else:
            passed_rules.append(RULE_MISSING_INDUSTRY)

        # ── CO006 · Directors ────────────────────────────────────────────────
        if "no_verified_directors" in missing_fields:
            failed_rules.append(RULE_NO_DIRECTORS)
            warnings.append(
                f"[{RULE_NO_DIRECTORS}] No verified directors found. "
                "UK AML regulations require at least one declared director."
            )
            risk_influences.add(RISK_HIGH)
        else:
            passed_rules.append(RULE_NO_DIRECTORS)

        # ── CO007 · Shareholders ─────────────────────────────────────────────
        if "no_shareholders" in missing_fields:
            failed_rules.append(RULE_NO_SHAREHOLDERS)
            warnings.append(
                f"[{RULE_NO_SHAREHOLDERS}] No shareholders declared."
            )
            risk_influences.add(RISK_MEDIUM)
        else:
            passed_rules.append(RULE_NO_SHAREHOLDERS)

        # ── CO008 · UBO Disclosure ───────────────────────────────────────────
        if "no_qualifying_ubos" in missing_fields:
            failed_rules.append(RULE_NO_UBOS)
            recommendations.append(
                f"[{RULE_NO_UBOS}] No UBO with ≥25% ownership declared. "
                "MLR 2017 (as amended through 2024/2026) and ECCTA 2023 require disclosure of all beneficial owners above 25%. "
                "Recommend Enhanced Due Diligence (EDD)."
            )
            risk_influences.add(RISK_HIGH)
        else:
            passed_rules.append(RULE_NO_UBOS)

        # ── CO009 · Company Documents ────────────────────────────────────────
        if "no_company_incorporation_documents" in missing_fields:
            failed_rules.append(RULE_NO_COMPANY_DOCS)
            recommendations.append(
                f"[{RULE_NO_COMPANY_DOCS}] No company incorporation documents uploaded. "
                "Request Certificate of Incorporation or equivalent."
            )
        else:
            passed_rules.append(RULE_NO_COMPANY_DOCS)

        # ── Risk Tier Resolution ─────────────────────────────────────────────
        if RISK_HIGH in risk_influences:
            risk_level = RISK_HIGH
        elif RISK_MEDIUM in risk_influences:
            risk_level = RISK_MEDIUM
        else:
            risk_level = RISK_LOW

        # ── Next Agent Routing ────────────────────────────────────────────────
        # After full company verification the workflow always continues
        # to PEP screening for directors / shareholders / UBOs.
        next_agent = "pep_agent"

        return {
            "passed_rules":   passed_rules,
            "failed_rules":   failed_rules,
            "warnings":       warnings,
            "recommendations": recommendations,
            "risk_level":     risk_level,
            "next_agent":     next_agent,
        }
