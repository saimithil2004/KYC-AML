"""
AI Rule Extraction Service — Phase 10
=====================================
Processes extracted regulation text using Gemini AI (if API key exists)
or a deterministic regex-based fallback parser.
Extracts threshold, block, EDD, and standard policy rules.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


class RuleExtractionService:
    """Service to convert plain text regulations into structured policy rules."""

    @staticmethod
    async def extract_rules(text: str) -> List[Dict[str, Any]]:
        """Extract rules using Gemini API, or fall back to deterministic parsing."""
        if not text or not text.strip():
            return []

        # 1. Try Gemini AI if API key is provided
        if settings.GEMINI_API_KEY and settings.GEMINI_API_KEY.strip():
            try:
                return await RuleExtractionService._extract_with_gemini(text)
            except Exception as exc:
                logger.error(f"Gemini rule extraction failed, falling back: {exc}")

        # 2. Fall back to deterministic keyword/regex parser
        return RuleExtractionService._extract_deterministically(text)

    @staticmethod
    async def _extract_with_gemini(text: str) -> List[Dict[str, Any]]:
        """Calls Gemini to parse regulations into structured JSON rules."""
        import google.generativeai as genai
        
        genai.configure(api_key=settings.GEMINI_API_KEY)
        
        prompt = f"""
        You are an expert compliance officer. Analyze the following AML/KYC regulation text and extract all policy rules.
        Format the output strictly as a JSON list of dictionaries. Do not include markdown code block styling or any other text.
        Each rule dictionary MUST contain these keys:
          - rule_name: Unique uppercase snake_case string (e.g. UK_LARGE_TRANSACTION_LIMIT)
          - rule_type: One of 'threshold', 'block', 'edd', 'aml', 'kyc', 'internal'
          - severity: One of 'critical', 'high', 'medium', 'low'
          - description: Clear text description of the rule
          - conditions: A JSON object outlining evaluation conditions (e.g. {{"max_transaction_amount": 10000}} or {{"sanctions_confirmed": true}} or {{"signal": "document", "score_threshold": 50}})
          - threshold: Numeric threshold value (float) or null
          - country: Specific ISO country or jurisdiction name (string) or null
          - expression: Mathematical or logical condition string (string) or null

        Regulation Text:
        {text}
        """
        
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = await model.generate_content_async(prompt)
        response_text = response.text.strip()
        
        # Clean response string of markdown tags
        if response_text.startswith("```"):
            # Remove leading ```json or ``` and trailing ```
            response_text = re.sub(r"^```(?:json)?\n", "", response_text)
            response_text = re.sub(r"\n```$", "", response_text)

        parsed = json.loads(response_text)
        if isinstance(parsed, list):
            return parsed
        raise ValueError("Gemini response is not a list of rules")

    @staticmethod
    def _extract_deterministically(text: str) -> List[Dict[str, Any]]:
        """Regex and keyword matching parser for local fallback runs."""
        rules = []
        
        # Look for keywords/paragraphs that represent rules
        sentences = re.split(r'(?:\n+|\. )', text)
        for idx, sentence in enumerate(sentences):
            sentence = sentence.strip()
            if not sentence or len(sentence) < 15:
                continue

            lowered = sentence.lower()
            
            # Pattern A: Transaction threshold rules
            # e.g., "transactions exceeding £10,000 must trigger EDD"
            # or "amounts over 5000"
            match_amount = re.search(r'(?:exceeding|over|greater than|above)\s*([£$€]?\s*\d{1,3}(?:,\d{3})*(?:\.\d{2})?)', lowered)
            if match_amount:
                amount_str = match_amount.group(1).replace("£", "").replace("$", "").replace("€", "").replace(",", "").strip()
                try:
                    amount = float(amount_str)
                    rule_type = "edd" if "edd" in lowered or "enhanced" in lowered else "threshold"
                    rules.append({
                        "rule_name": f"TX_LIMIT_THRESHOLD_{idx}",
                        "rule_type": rule_type,
                        "severity": "high" if rule_type == "edd" else "medium",
                        "description": sentence,
                        "conditions": {"max_transaction_amount": amount},
                        "threshold": amount,
                        "country": "United Kingdom" if "uk" in lowered or "united kingdom" in lowered else None,
                        "expression": f"transaction_amount > {amount}",
                    })
                    continue
                except ValueError:
                    pass

            # Pattern B: High risk countries block/warnings
            # e.g., "High Risk Countries (e.g. Russia, Iran) must be blocked"
            if "high risk country" in lowered or "jurisdiction" in lowered or "sanction" in lowered:
                rule_type = "block" if "block" in lowered or "prohibit" in lowered else "edd"
                rules.append({
                    "rule_name": f"COUNTRY_RISK_CHECK_{idx}",
                    "rule_type": rule_type,
                    "severity": "critical" if rule_type == "block" else "high",
                    "description": sentence,
                    "conditions": {"high_risk_country": True},
                    "threshold": None,
                    "country": None,
                    "expression": "country_risk == 'high'",
                })
                continue

            # Pattern C: Document completeness / KYC
            if "document" in lowered or "kyc" in lowered or "passport" in lowered or "identity" in lowered:
                rules.append({
                    "rule_name": f"DOCUMENT_VERIFICATION_RULE_{idx}",
                    "rule_type": "kyc",
                    "severity": "medium",
                    "description": sentence,
                    "conditions": {"signal": "document", "score_threshold": 60},
                    "threshold": 60.0,
                    "country": None,
                    "expression": "document_verification_score >= 60",
                })
                continue

        # If absolutely no rules were extracted, append default placeholder rules
        if not rules:
            rules.append({
                "rule_name": "DEFAULT_GENERIC_THRESHOLD",
                "rule_type": "threshold",
                "severity": "medium",
                "description": "Auto-generated generic transaction ceiling check.",
                "conditions": {"max_transaction_amount": 10000.0},
                "threshold": 10000.0,
                "country": None,
                "expression": "transaction_amount > 10000",
            })
            
        return rules
