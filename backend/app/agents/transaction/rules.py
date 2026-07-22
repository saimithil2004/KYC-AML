"""
Transaction Agent — Rules Engine
================================
Applies business rules TX001–TX008 to determine findings, alerts,
recommendations, and overall transaction status.
"""

from typing import List, Dict, Any, Set
from app.agents.transaction.models import PatternResult
from app.agents.transaction.constants import *


class TransactionRulesEngine:
    """
    Stateless business rules engine for transaction behavioral analysis.
    """

    @staticmethod
    def evaluate(pattern_results: List[PatternResult]) -> Dict[str, Any]:
        """
        Evaluates the triggered patterns and maps them to business outcomes.
        Returns:
            Dict containing transaction_status, findings, warnings, recommendations, rules_triggered
        """
        findings: List[str] = []
        warnings: List[str] = []
        recommendations: List[str] = []
        rules_triggered: List[str] = []

        # Find only triggered patterns
        triggered = [p for p in pattern_results if p.triggered]

        # ── Rule TX001: No Suspicious Activity ────────────────────────────────
        if not triggered:
            rules_triggered.append("TX001")
            findings.append(
                "No suspicious behavioral patterns detected in transaction history."
            )
            return {
                "transaction_status": TRANSACTION_STATUS_CLEAR,
                "findings": findings,
                "warnings": warnings,
                "recommendations": [
                    "Maintain standard transaction monitoring schedule."
                ],
                "rules_triggered": rules_triggered,
            }

        # ── Map specific pattern triggers to business rule triggers ───────────
        triggered_ids = {p.pattern_id for p in triggered}

        # Structuring
        if RULE_STRUCTURING in triggered_ids:
            rules_triggered.append("TX002")  # Business Rule TX002

        # Velocity / Large Value (both increase risk)
        if RULE_VELOCITY in triggered_ids or RULE_LARGE_VALUE in triggered_ids:
            rules_triggered.append("TX003")  # Business Rule TX003

        # High Risk Country Transfer
        if RULE_HIGH_RISK_COUNTRY in triggered_ids:
            rules_triggered.append("TX004")  # Business Rule TX004

        # Rapid In/Out
        if RULE_RAPID_IN_OUT in triggered_ids:
            rules_triggered.append("TX005")  # Business Rule TX005

        # Large Cash Deposit (Cash Intensive)
        if RULE_CASH_INTENSIVE in triggered_ids:
            rules_triggered.append("TX006")  # Business Rule TX006

        # Dormant Reactivation
        if RULE_DORMANT_REACTIVATION in triggered_ids:
            rules_triggered.append("TX007")  # Business Rule TX007

        # Multiple Alerts
        if RULE_MULTIPLE_PATTERNS in triggered_ids or len(triggered) >= 3:
            rules_triggered.append("TX008")  # Business Rule TX008

        # Consolidate findings, warnings, and recommendations from pattern results
        for pat in triggered:
            if pat.finding:
                findings.append(pat.finding)
            if pat.severity in (RISK_HIGH, RISK_CRITICAL):
                warnings.append(f"High risk indicator triggered: {pat.pattern_name}")
            if pat.recommendation:
                recommendations.append(pat.recommendation)

        # ── Determine overall status ──────────────────────────────────────────
        status = TRANSACTION_STATUS_WARNING

        # Check severities of triggered patterns
        severities = {p.severity.lower() for p in triggered}

        if (
            "TX008" in rules_triggered
            or "TX004" in rules_triggered
            or RISK_CRITICAL in severities
        ):
            status = TRANSACTION_STATUS_CRITICAL
        elif (
            "TX002" in rules_triggered
            or "TX005" in rules_triggered
            or RISK_HIGH in severities
        ):
            status = TRANSACTION_STATUS_ALERT
        elif len(triggered) >= 3:
            status = TRANSACTION_STATUS_CRITICAL

        # Dedup lists
        findings = list(dict.fromkeys(findings))
        warnings = list(dict.fromkeys(warnings))
        recommendations = list(dict.fromkeys(recommendations))
        rules_triggered = list(dict.fromkeys(rules_triggered))

        return {
            "transaction_status": status,
            "findings": findings,
            "warnings": warnings,
            "recommendations": recommendations,
            "rules_triggered": rules_triggered,
        }
