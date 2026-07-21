"""
Investigation Agent
====================
Generates an investigation summary, SAR explanation, and compliance narrative
for the case based on all agent results in AgentState.

AI Strategy:
  - Primary: Uses Google Gemini 2.0 Flash if GEMINI_API_KEY is configured
  - Fallback: Generates a deterministic, structured narrative from AgentState

This agent does NOT make final decisions — it generates human-readable summaries
to assist compliance officers in their review.
"""

import time
import logging
import os
from datetime import datetime
from typing import Dict, Any, List, Optional

from app.agents.base.base_agent import BaseAgent
from app.agents.base.agent_state import AgentState
from app.agents.base.registry import AgentRegistry
from app.agents.base.exceptions import AgentValidationError

logger = logging.getLogger(__name__)


@AgentRegistry.register("investigation_agent")
class InvestigationAgent(BaseAgent):
    """
    Investigation Agent.
    Produces investigation summaries, SAR explanations, and compliance narratives.
    Uses Gemini AI when available, falls back to deterministic template generation.
    """

    def get_name(self) -> str:
        return "investigation_agent"

    def get_version(self) -> str:
        return "1.0.0"

    def get_description(self) -> str:
        return (
            "Investigation summary agent. Generates structured investigation narratives, "
            "SAR explanations, and compliance reports from all screening results. "
            "Uses Gemini AI when API key is available."
        )

    def get_capabilities(self) -> List[str]:
        return [
            "investigation_summary",
            "sar_explanation",
            "compliance_narrative",
            "ai_summary_generation",
            "deterministic_fallback",
        ]

    def validate_input(self, state: AgentState) -> bool:
        if not state.customer_id:
            raise AgentValidationError(
                message="customer_id missing in AgentState. Cannot run InvestigationAgent.",
                details={"customer_id": None},
            )
        return True

    async def process(self, state: AgentState) -> Dict[str, Any]:
        start_time = time.perf_counter()
        state.logs.append(f"[{self.get_name()}] Generating AI-assisted investigation summary...")

        # ── Collect key facts ─────────────────────────────────────────────────
        sm = state.shared_metadata
        customer = state.customer or {}
        customer_name = (
            f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip()
            or customer.get("company_name", "Unknown Customer")
        )
        customer_type = str(customer.get("customer_type") or "individual").upper()

        overall_score  = state.overall_score
        risk_level     = sm.get("risk_level") or state.risk_tier.upper()
        pep_status     = sm.get("pep_status",      "UNKNOWN")
        sanctions_status = sm.get("sanctions_status", "UNKNOWN")
        country_status = sm.get("country_status",  "UNKNOWN")
        fatf_status    = sm.get("fatf_status",     "UNKNOWN")
        doc_score      = sm.get("document_score",  100)
        violations     = sm.get("regulation_violations", [])
        block_triggers = sm.get("regulation_block_triggers", [])
        edd_triggers   = sm.get("regulation_edd_triggers",   [])
        tx_status      = sm.get("transaction_status", "CLEAR")
        behavior_flags = sm.get("account_behavior_flags", {})

        gemini_key = (
            (self.context.config or {}).get("GEMINI_API_KEY")
            or os.environ.get("GEMINI_API_KEY")
            or ""
        )

        ai_used = False
        analysis_data = {}

        if gemini_key:
            try:
                analysis_data, ai_used = await self._generate_ai_summary_json(
                    gemini_key=gemini_key,
                    customer_name=customer_name,
                    customer_type=customer_type,
                    overall_score=overall_score,
                    risk_level=risk_level,
                    pep_status=pep_status,
                    sanctions_status=sanctions_status,
                    fatf_status=fatf_status,
                    violations=violations,
                    block_triggers=block_triggers,
                )
            except Exception as exc:
                logger.warning(f"InvestigationAgent: Gemini AI failed ({exc}). Using deterministic fallback.")

        if not ai_used:
            analysis_data = self._generate_deterministic_analysis(
                customer_name=customer_name,
                customer_type=customer_type,
                overall_score=overall_score,
                risk_level=risk_level,
                pep_status=pep_status,
                sanctions_status=sanctions_status,
                country_status=country_status,
                fatf_status=fatf_status,
                doc_score=doc_score,
                tx_status=tx_status,
                violations=violations,
                block_triggers=block_triggers,
                edd_triggers=edd_triggers,
                behavior_flags=behavior_flags,
            )

        execution_duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        # Store in shared metadata
        state.shared_metadata["investigation_summary"] = analysis_data.get("case_summary", "")
        state.shared_metadata["sar_explanation"] = f"AI Suspicious Behaviour Analysis: {analysis_data.get('suspicious_behaviour_analysis', '')}"
        state.shared_metadata["compliance_narrative"] = analysis_data.get("risk_explanation", "")
        state.shared_metadata["investigation_ai_used"] = ai_used
        state.shared_metadata["ai_analysis_workspace"] = analysis_data

        state.logs.append(
            f"InvestigationAgent: AI workspace assessment generated ({'AI' if ai_used else 'deterministic'}). "
            f"Duration={execution_duration_ms}ms."
        )

        return {
            "_status": "success",
            "_reason": "AI Investigation assistant results generated.",
            "confidence": 1.0,
            "risk_score": overall_score,
            "risk_level": risk_level.lower(),
            "findings": [analysis_data.get("case_summary", "")],
            "warnings": [],
            "recommendations": analysis_data.get("recommended_actions", []),
            "errors": [],
            # Detailed metadata payload for workspace
            "case_summary": analysis_data.get("case_summary"),
            "suspicious_behaviour_analysis": analysis_data.get("suspicious_behaviour_analysis"),
            "recommended_actions": analysis_data.get("recommended_actions"),
            "questions_for_investigator": analysis_data.get("questions_for_investigator"),
            "missing_evidence_suggestions": analysis_data.get("missing_evidence_suggestions"),
            "risk_explanation": analysis_data.get("risk_explanation"),
            "ai_used": ai_used,
            "execution_duration_ms": execution_duration_ms,
        }

    # ── AI Generation ─────────────────────────────────────────────────────────
    async def _generate_ai_summary_json(
        self,
        gemini_key: str,
        customer_name: str,
        customer_type: str,
        overall_score: float,
        risk_level: str,
        pep_status: str,
        sanctions_status: str,
        fatf_status: str,
        violations: List[Dict],
        block_triggers: List[str],
    ) -> tuple[dict, bool]:
        """Generates AI-powered workspace report using Google Gemini in JSON format."""
        import google.generativeai as genai
        import json

        genai.configure(api_key=gemini_key)
        model = genai.GenerativeModel("gemini-2.0-flash-exp")

        violation_text = "\n".join([
            f"  - {v['rule_name']}: {v['reason']}" for v in violations
        ]) or "  None"

        prompt = f"""You are an expert AML/KYC compliance AI agent. Generate an investigation workspace report.
        
Customer Name: {customer_name}
Customer Type: {customer_type}
Overall Risk Score: {overall_score:.1f}/100 ({risk_level})
PEP Status: {pep_status}
Sanctions Status: {sanctions_status}
FATF Status: {fatf_status}
Block Triggers: {', '.join(block_triggers) if block_triggers else 'None'}
Policy Violations:
{violation_text}

You MUST return a JSON object with the following keys. Do NOT wrap the JSON inside markdown tags like ```json or anything else. Just return raw JSON content:
{{
  "case_summary": "A detailed 2-3 sentence overview of this customer, their background risk, and why the case was flagged.",
  "suspicious_behaviour_analysis": "A detailed 2-3 sentence analysis of suspicious patterns, regulatory violations, list hits, or profile inconsistencies.",
  "recommended_actions": ["Action item 1", "Action item 2", "Action item 3"],
  "questions_for_investigator": ["Critical question 1 to ask the client/look up", "Critical question 2"],
  "missing_evidence_suggestions": ["Suggestion 1 (e.g. proof of address, source of wealth statement)", "Suggestion 2"],
  "risk_explanation": "A professional explanation of the computed risk score tier and compliance rating."
}}"""

        response = model.generate_content(prompt)
        text = response.text.strip()
        # Clean JSON markdown fences if any
        if text.startswith("```"):
            lines = text.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines[-1].startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()

        data = json.loads(text)
        return data, True

    # ── Deterministic Fallback ────────────────────────────────────────────────
    def _generate_deterministic_analysis(
        self,
        customer_name: str,
        customer_type: str,
        overall_score: float,
        risk_level: str,
        pep_status: str,
        sanctions_status: str,
        country_status: str,
        fatf_status: str,
        doc_score: float,
        tx_status: str,
        violations: List[Dict],
        block_triggers: List[str],
        edd_triggers: List[str],
        behavior_flags: Dict[str, bool],
    ) -> Dict[str, Any]:
        """Generates structured deterministic summaries when AI is unavailable."""
        now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        viol_count = len(violations)

        case_summary = (
            f"Automated compliance review of {customer_name} ({customer_type}) completed on {now_str}. "
            f"The customer has been assigned an overall risk score of {overall_score:.1f}/100, placing them in the {risk_level} risk category."
        )

        suspicious_behaviour = ""
        if block_triggers:
            suspicious_behaviour += f"Critical compliance block triggers met: {', '.join(block_triggers)}. "
        if sanctions_status == "CONFIRMED":
            suspicious_behaviour += "Active sanctions list confirmation. "
        if pep_status == "CONFIRMED_PEP":
            suspicious_behaviour += "Confirmed Politically Exposed Person (PEP) identification. "
        if fatf_status != "CLEAR" and fatf_status != "UNKNOWN":
            suspicious_behaviour += f"FATF high-risk jurisdiction flags detected ({fatf_status}). "
        if viol_count > 0:
            suspicious_behaviour += f"Violated {viol_count} active compliance policy rules. "

        if not suspicious_behaviour:
            suspicious_behaviour = f"No suspicious patterns identified. Risk score of {overall_score:.1f}/100 matches active standard compliance baseline."

        recommended_actions = []
        if block_triggers or sanctions_status == "CONFIRMED":
            recommended_actions = [
                "Freeze account immediately and restrict all debit/credit transactions.",
                "Generate draft Suspicious Activity Report (SAR) for compliance review.",
                "Escalate case to Senior Compliance Supervisor for immediate review."
            ]
        elif edd_triggers or overall_score >= 60.0:
            recommended_actions = [
                "Initiate Enhanced Due Diligence (EDD) procedures.",
                "Request validated source of wealth documentation and employment verification.",
                "Schedule review within 5 business days."
            ]
        else:
            recommended_actions = [
                "Proceed with standard KYC onboarding approval.",
                "Ensure routine daily transaction monitoring limits apply.",
                "Schedule next periodic review according to Low risk profile timelines."
            ]

        questions = [
            f"What is the client's verified line of business/employment context?",
            f"Can we verify the original beneficial ownership hierarchy?",
        ]
        if pep_status == "CONFIRMED_PEP":
            questions.append("Who is the political connection and source of funds for PEP exposure?")
        if tx_status == "SUSPICIOUS":
            questions.append("What is the source of funds and business justification for the large transactions?")

        missing_evidence = ["Official government-issued ID card or Passport photo page"]
        if overall_score >= 50.0:
            missing_evidence.extend([
                "Certified proof of residential/business address (recent utility bill/bank statement)",
                "Documented Source of Wealth statement with corresponding payslip/financial audits"
            ])
        else:
            missing_evidence.append("Proof of address document (utility bill < 3 months old)")

        risk_explanation = (
            f"Risk profile evaluation completed. The overall score of {overall_score:.1f}/100 is driven by "
            f"PEP status: {pep_status}, Sanctions check: {sanctions_status}, Document verification score: {doc_score}/100, "
            f"and high-risk jurisdiction association: {fatf_status}."
        )

        return {
            "case_summary": case_summary,
            "suspicious_behaviour_analysis": suspicious_behaviour.strip(),
            "recommended_actions": recommended_actions,
            "questions_for_investigator": questions,
            "missing_evidence_suggestions": missing_evidence,
            "risk_explanation": risk_explanation
        }
