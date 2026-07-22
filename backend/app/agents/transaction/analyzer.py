"""
Transaction Agent — Analyzer
============================
Orchestrates the running of all 10 transaction pattern detectors
and returns a combined list of PatternResult objects.
"""

import time
from typing import List
from app.agents.transaction.models import TransactionRecord, PatternResult
from app.agents.transaction.patterns import TransactionPatternDetectors
from app.agents.transaction.constants import (
    RULE_MULTIPLE_PATTERNS,
    RISK_CRITICAL,
    MULTIPLE_PATTERNS_COUNT,
)


class TransactionAnalyzer:
    """
    Combines the executions of all 10 pattern detectors.
    """

    @staticmethod
    def analyze(
        transactions: List[TransactionRecord],
        high_risk_countries: List[str],
        prohibited_countries: List[str],
    ) -> List[PatternResult]:
        """
        Executes all 10 patterns against the list of transactions.
        """
        results: List[PatternResult] = []

        if not transactions:
            return results

        # ── 1. Structuring (TX001) ───────────────────────────────────────────
        results.append(TransactionPatternDetectors.detect_structuring(transactions))

        # ── 2. Velocity (TX002) ──────────────────────────────────────────────
        results.append(TransactionPatternDetectors.detect_velocity(transactions))

        # ── 3. Large Value (TX003) ───────────────────────────────────────────
        results.append(TransactionPatternDetectors.detect_large_value(transactions))

        # ── 4. High Risk Country (TX004) ─────────────────────────────────────
        results.append(
            TransactionPatternDetectors.detect_high_risk_country_transfers(
                transactions, high_risk_countries, prohibited_countries
            )
        )

        # ── 5. Rapid In / Rapid Out (TX005) ──────────────────────────────────
        results.append(TransactionPatternDetectors.detect_rapid_in_out(transactions))

        # ── 6. Round Amounts (TX006) ─────────────────────────────────────────
        results.append(TransactionPatternDetectors.detect_round_amounts(transactions))

        # ── 7. Dormant Reactivation (TX007) ──────────────────────────────────
        results.append(
            TransactionPatternDetectors.detect_dormant_reactivation(transactions)
        )

        # ── 8. Cash Intensive (TX008) ────────────────────────────────────────
        results.append(TransactionPatternDetectors.detect_cash_intensive(transactions))

        # ── 10. Time Anomaly (TX010) ─────────────────────────────────────────
        results.append(TransactionPatternDetectors.detect_time_anomaly(transactions))

        # ── 9. Multiple Suspicious Patterns (TX009) ──────────────────────────
        # Evaluated after the others have run. Triggers if count of other triggered patterns >= threshold.
        t0 = time.perf_counter()
        triggered_others = [r for r in results if r.triggered]
        triggered_tx_ids = []
        for r in triggered_others:
            for tx_id in r.triggered_transaction_ids:
                if tx_id not in triggered_tx_ids:
                    triggered_tx_ids.append(tx_id)

        triggered_tx009 = len(triggered_others) >= MULTIPLE_PATTERNS_COUNT

        finding = None
        recomm = None
        if triggered_tx009:
            finding = f"[{RULE_MULTIPLE_PATTERNS}] Multiple Suspicious Patterns: Triggered {len(triggered_others)} separate transaction risk indicators simultaneously."
            recomm = "Initiate immediate high-priority audit. Combine KYC, company, and jurisdictional profiles to assess full customer exposure."

        tx009_result = PatternResult(
            pattern_id=RULE_MULTIPLE_PATTERNS,
            pattern_name="Multiple Suspicious Patterns",
            triggered=triggered_tx009,
            confidence=0.95 if triggered_tx009 else 0.0,
            severity=RISK_CRITICAL,
            finding=finding,
            recommendation=recomm,
            triggered_transaction_ids=triggered_tx_ids if triggered_tx009 else [],
            execution_time_ms=round((time.perf_counter() - t0) * 1000, 2),
        )

        results.append(tx009_result)

        return results
