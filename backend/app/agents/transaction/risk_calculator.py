"""
Transaction Agent — Risk Calculator
===================================
Calculates the transaction risk score (0-100) and maps it to a risk level
(LOW, MEDIUM, HIGH, CRITICAL) based on the triggered patterns.
"""

from typing import List, Tuple
from app.agents.transaction.models import PatternResult
from app.agents.transaction.constants import (
    RISK_LOW,
    RISK_MEDIUM,
    RISK_HIGH,
    RISK_CRITICAL,
)


class TransactionRiskCalculator:
    """
    Combines the severities of triggered patterns to produce a composite score.
    """

    @staticmethod
    def calculate(triggered_patterns: List[PatternResult]) -> Tuple[float, str]:
        """
        Calculates the risk score from triggered patterns.
        Score decreases from 100.0 (safe) down to 0.0 (maximum risk).

        Returns:
            (risk_score, risk_level)
        """
        if not triggered_patterns:
            return 100.0, RISK_LOW

        score = 100.0

        # Count triggers by severity
        critical_count = 0
        high_count = 0
        medium_count = 0
        low_count = 0

        for pat in triggered_patterns:
            sev = pat.severity.lower()
            if sev == RISK_CRITICAL:
                critical_count += 1
            elif sev == RISK_HIGH:
                high_count += 1
            elif sev == RISK_MEDIUM:
                medium_count += 1
            else:
                low_count += 1

        # Deductions
        # CRITICAL patterns: -40 each (max -80)
        score -= min(80.0, critical_count * 40.0)

        # HIGH patterns: -25 each (max -50)
        score -= min(50.0, high_count * 25.0)

        # MEDIUM patterns: -15 each (max -30)
        score -= min(30.0, medium_count * 15.0)

        # LOW patterns: -5 each
        score -= low_count * 5.0

        # Additional penalty if multiple patterns are triggered
        total_triggered_patterns = len(triggered_patterns)
        if total_triggered_patterns >= 3:
            score -= 15.0

        # Clamp between 0.0 and 100.0
        score = max(0.0, min(100.0, score))

        # Map to risk level
        if score >= 80.0:
            level = RISK_LOW
        elif score >= 50.0:
            level = RISK_MEDIUM
        elif score >= 25.0:
            level = RISK_HIGH
        else:
            level = RISK_CRITICAL

        # Override level if high/critical patterns triggered
        if critical_count > 0:
            level = RISK_CRITICAL
        elif high_count > 0:
            if level in (RISK_LOW, RISK_MEDIUM):
                level = RISK_HIGH

        return round(score, 2), level
