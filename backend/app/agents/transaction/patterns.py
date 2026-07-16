"""
Transaction Agent — Patterns
=============================
Stateless detector functions for each of the 10 AML transaction patterns:
  - TX001: Structuring (Smurfing)
  - TX002: Velocity
  - TX003: Large Value
  - TX004: High Risk Country
  - TX005: Rapid In / Rapid Out
  - TX006: Round Amounts
  - TX007: Dormant Account Reactivation
  - TX008: Cash Intensive Behavior
  - TX009: Multiple Suspicious Patterns (evaluated across results)
  - TX010: Time Anomaly
"""

import time
import math
from datetime import datetime, timedelta
from typing import List, Set, Dict, Any
from app.agents.transaction.models import TransactionRecord, PatternResult
from app.agents.transaction.constants import *


class TransactionPatternDetectors:
    """
    Isolated detection logic for each transaction pattern.
    """

    # ─────────────────────────────────────────────────────────────────────────
    # TX001: Structuring (Smurfing)
    # ─────────────────────────────────────────────────────────────────────────
    @staticmethod
    def detect_structuring(transactions: List[TransactionRecord]) -> PatternResult:
        t0 = time.perf_counter()
        triggered_ids = []
        
        # Sort by timestamp
        sorted_txs = sorted(transactions, key=lambda x: x.timestamp)
        
        # Find all transactions just below reporting threshold
        candidate_txs = [
            tx for tx in sorted_txs
            if STRUCTURING_MIN_AMT <= tx.amount <= STRUCTURING_MAX_AMT
        ]

        # For each candidate, find if there are others in a 24h window
        for i, tx1 in enumerate(candidate_txs):
            window_txs = [tx1.transaction_id]
            for tx2 in candidate_txs[i+1:]:
                if (tx2.timestamp - tx1.timestamp) <= timedelta(hours=STRUCTURING_TIME_WINDOW_HOURS):
                    window_txs.append(tx2.transaction_id)
            if len(window_txs) >= 2:
                for tx_id in window_txs:
                    if tx_id not in triggered_ids:
                        triggered_ids.append(tx_id)

        triggered = len(triggered_ids) >= 2
        confidence = 0.85 if triggered else 0.0
        
        finding = None
        recomm = None
        if triggered:
            finding = f"[{RULE_STRUCTURING}] Potential structuring detected: {len(triggered_ids)} transactions found between {STRUCTURING_MIN_AMT} and {STRUCTURING_MAX_AMT} within {STRUCTURING_TIME_WINDOW_HOURS} hours."
            recomm = "Verify source of wealth and check for linked accounts or structured deposit behaviour."

        return PatternResult(
            pattern_id=RULE_STRUCTURING,
            pattern_name="Structuring (Smurfing)",
            triggered=triggered,
            confidence=confidence,
            severity=RISK_HIGH,
            finding=finding,
            recommendation=recomm,
            triggered_transaction_ids=triggered_ids,
            execution_time_ms=round((time.perf_counter() - t0) * 1000, 2)
        )

    # ─────────────────────────────────────────────────────────────────────────
    # TX002: Velocity
    # ─────────────────────────────────────────────────────────────────────────
    @staticmethod
    def detect_velocity(transactions: List[TransactionRecord]) -> PatternResult:
        t0 = time.perf_counter()
        triggered_ids = []
        sorted_txs = sorted(transactions, key=lambda x: x.timestamp)

        # Check 24-hour moving window
        for i, tx1 in enumerate(sorted_txs):
            window = [tx1]
            for tx2 in sorted_txs[i+1:]:
                if (tx2.timestamp - tx1.timestamp) <= timedelta(hours=24):
                    window.append(tx2)
            if len(window) >= VELOCITY_COUNT_24H:
                for tx in window:
                    if tx.transaction_id not in triggered_ids:
                        triggered_ids.append(tx.transaction_id)

        # Check 7-day moving window if not already flagged in 24h
        if not triggered_ids:
            for i, tx1 in enumerate(sorted_txs):
                window = [tx1]
                for tx2 in sorted_txs[i+1:]:
                    if (tx2.timestamp - tx1.timestamp) <= timedelta(days=7):
                        window.append(tx2)
                if len(window) >= VELOCITY_COUNT_7D:
                    for tx in window:
                        if tx.transaction_id not in triggered_ids:
                            triggered_ids.append(tx.transaction_id)

        triggered = len(triggered_ids) > 0
        confidence = 0.80 if triggered else 0.0
        
        finding = None
        recomm = None
        if triggered:
            finding = f"[{RULE_VELOCITY}] High transaction velocity detected: {len(triggered_ids)} transactions clustered in short windows."
            recomm = "Review transaction frequency patterns and check for automated or bot-like payment execution."

        return PatternResult(
            pattern_id=RULE_VELOCITY,
            pattern_name="Velocity Detection",
            triggered=triggered,
            confidence=confidence,
            severity=RISK_MEDIUM,
            finding=finding,
            recommendation=recomm,
            triggered_transaction_ids=triggered_ids,
            execution_time_ms=round((time.perf_counter() - t0) * 1000, 2)
        )

    # ─────────────────────────────────────────────────────────────────────────
    # TX003: Large Value Transactions
    # ─────────────────────────────────────────────────────────────────────────
    @staticmethod
    def detect_large_value(transactions: List[TransactionRecord]) -> PatternResult:
        t0 = time.perf_counter()
        triggered_ids = [
            tx.transaction_id for tx in transactions
            if tx.amount >= LARGE_VALUE_THRESHOLD
        ]
        
        triggered = len(triggered_ids) > 0
        confidence = 0.95 if triggered else 0.0
        
        finding = None
        recomm = None
        if triggered:
            finding = f"[{RULE_LARGE_VALUE}] Large value transfer detected: {len(triggered_ids)} transaction(s) exceeding threshold of {LARGE_VALUE_THRESHOLD} GBP."
            recomm = "Perform source of funds verification for this transaction and obtain copy of invoice/agreement."

        return PatternResult(
            pattern_id=RULE_LARGE_VALUE,
            pattern_name="Large Value Transactions",
            triggered=triggered,
            confidence=confidence,
            severity=RISK_HIGH,
            finding=finding,
            recommendation=recomm,
            triggered_transaction_ids=triggered_ids,
            execution_time_ms=round((time.perf_counter() - t0) * 1000, 2)
        )

    # ─────────────────────────────────────────────────────────────────────────
    # TX004: High-Risk Country Transfers
    # ─────────────────────────────────────────────────────────────────────────
    @staticmethod
    def detect_high_risk_country_transfers(
        transactions: List[TransactionRecord],
        high_risk_countries: List[str],
        prohibited_countries: List[str]
    ) -> PatternResult:
        t0 = time.perf_counter()
        triggered_ids = []
        severity = RISK_HIGH
        
        hr_set = {c.lower() for c in high_risk_countries}
        pr_set = {c.lower() for c in prohibited_countries}

        is_prohibited = False
        for tx in transactions:
            countries = {tx.originating_country.lower(), tx.destination_country.lower()}
            if countries & pr_set:
                triggered_ids.append(tx.transaction_id)
                is_prohibited = True
            elif countries & hr_set:
                triggered_ids.append(tx.transaction_id)

        triggered = len(triggered_ids) > 0
        confidence = 0.95 if triggered else 0.0
        
        if is_prohibited:
            severity = RISK_CRITICAL
            finding = f"[{RULE_HIGH_RISK_COUNTRY}] Critical Alert: Transfer involving PROHIBITED jurisdictional exposure ({len(triggered_ids)} transaction(s))."
            recomm = "Immediately freeze transaction/account and escalate to Money Laundering Reporting Officer (MLRO)."
        elif triggered:
            finding = f"[{RULE_HIGH_RISK_COUNTRY}] High Risk Country Transfer: Jurisdictional exposure detected to HIGH-risk countries ({len(triggered_ids)} transaction(s))."
            recomm = "Conduct Enhanced Due Diligence (EDD) on the counterparty and verify local connection/justification."
        else:
            finding = None
            recomm = None

        return PatternResult(
            pattern_id=RULE_HIGH_RISK_COUNTRY,
            pattern_name="High-Risk Country Transfers",
            triggered=triggered,
            confidence=confidence,
            severity=severity,
            finding=finding,
            recommendation=recomm,
            triggered_transaction_ids=triggered_ids,
            execution_time_ms=round((time.perf_counter() - t0) * 1000, 2)
        )

    # ─────────────────────────────────────────────────────────────────────────
    # TX005: Rapid In / Rapid Out
    # ─────────────────────────────────────────────────────────────────────────
    @staticmethod
    def detect_rapid_in_out(transactions: List[TransactionRecord]) -> PatternResult:
        t0 = time.perf_counter()
        triggered_ids = []
        
        # Sort by timestamp
        sorted_txs = sorted(transactions, key=lambda x: x.timestamp)
        
        # Separate inflows and outflows
        inflows = [tx for tx in sorted_txs if tx.direction == "INFLOW"]
        outflows = [tx for tx in sorted_txs if tx.direction == "OUTFLOW"]

        for inf in inflows:
            # Find all outflows on the same account within 48h after this inflow
            matching_outflows = [
                outf for outf in outflows
                if outf.account_id == inf.account_id
                and inf.timestamp <= outf.timestamp <= (inf.timestamp + timedelta(hours=RAPID_IN_OUT_WINDOW_HOURS))
            ]
            
            if not matching_outflows:
                continue
                
            total_outflow = sum(o.amount for o in matching_outflows)
            if total_outflow >= inf.amount * RAPID_IN_OUT_RATIO:
                # Flag the inflow and all participating outflows
                if inf.transaction_id not in triggered_ids:
                    triggered_ids.append(inf.transaction_id)
                for o in matching_outflows:
                    if o.transaction_id not in triggered_ids:
                        triggered_ids.append(o.transaction_id)

        triggered = len(triggered_ids) >= 2
        confidence = 0.90 if triggered else 0.0
        
        finding = None
        recomm = None
        if triggered:
            finding = f"[{RULE_RAPID_IN_OUT}] Rapid In/Out (Pass-through/Layering) detected: funds are entering and exiting the account immediately."
            recomm = "Analyze transactional economic purpose and check if the account is acting as a money mule or pass-through agent."

        return PatternResult(
            pattern_id=RULE_RAPID_IN_OUT,
            pattern_name="Rapid In / Rapid Out",
            triggered=triggered,
            confidence=confidence,
            severity=RISK_HIGH,
            finding=finding,
            recommendation=recomm,
            triggered_transaction_ids=triggered_ids,
            execution_time_ms=round((time.perf_counter() - t0) * 1000, 2)
        )

    # ─────────────────────────────────────────────────────────────────────────
    # TX006: Round Amount Detection
    # ─────────────────────────────────────────────────────────────────────────
    @staticmethod
    def detect_round_amounts(transactions: List[TransactionRecord]) -> PatternResult:
        t0 = time.perf_counter()
        triggered_ids = []
        
        for tx in transactions:
            # Check if amount matches the list of round values or is a clean multiple
            if tx.amount in ROUND_AMOUNTS:
                triggered_ids.append(tx.transaction_id)
            elif tx.amount > 0 and tx.amount % 1000.0 == 0.0:
                triggered_ids.append(tx.transaction_id)

        triggered = len(triggered_ids) >= ROUND_AMOUNT_COUNT_THRESHOLD
        confidence = 0.75 if triggered else 0.0
        
        finding = None
        recomm = None
        if triggered:
            finding = f"[{RULE_ROUND_AMOUNT}] Round amount anomalies: found {len(triggered_ids)} transaction(s) at exact round sums."
            recomm = "Verify underlying business activities; round amount payments often lack normal business invoice details."

        return PatternResult(
            pattern_id=RULE_ROUND_AMOUNT,
            pattern_name="Round Amount Detection",
            triggered=triggered,
            confidence=confidence,
            severity=RISK_MEDIUM,
            finding=finding,
            recommendation=recomm,
            triggered_transaction_ids=triggered_ids if triggered else [],
            execution_time_ms=round((time.perf_counter() - t0) * 1000, 2)
        )

    # ─────────────────────────────────────────────────────────────────────────
    # TX007: Dormant Account Reactivation
    # ─────────────────────────────────────────────────────────────────────────
    @staticmethod
    def detect_dormant_reactivation(transactions: List[TransactionRecord]) -> PatternResult:
        t0 = time.perf_counter()
        triggered_ids = []
        
        sorted_txs = sorted(transactions, key=lambda x: x.timestamp)
        
        # Check gaps between consecutive transactions
        for i in range(1, len(sorted_txs)):
            gap = sorted_txs[i].timestamp - sorted_txs[i-1].timestamp
            if gap >= timedelta(days=DORMANT_DAYS_THRESHOLD):
                # Reactivation transaction triggers the alert
                triggered_ids.append(sorted_txs[i].transaction_id)

        triggered = len(triggered_ids) > 0
        confidence = 0.85 if triggered else 0.0
        
        finding = None
        recomm = None
        if triggered:
            finding = f"[{RULE_DORMANT_REACTIVATION}] Dormant account reactivation: sudden transaction activity after at least {DORMANT_DAYS_THRESHOLD} days of dormancy."
            recomm = "Confirm account holder identity and verify if there is a change in account control or takeover."

        return PatternResult(
            pattern_id=RULE_DORMANT_REACTIVATION,
            pattern_name="Dormant Account Reactivation",
            triggered=triggered,
            confidence=confidence,
            severity=RISK_HIGH,
            finding=finding,
            recommendation=recomm,
            triggered_transaction_ids=triggered_ids,
            execution_time_ms=round((time.perf_counter() - t0) * 1000, 2)
        )

    # ─────────────────────────────────────────────────────────────────────────
    # TX008: Cash Intensive Behaviour
    # ─────────────────────────────────────────────────────────────────────────
    @staticmethod
    def detect_cash_intensive(transactions: List[TransactionRecord]) -> PatternResult:
        t0 = time.perf_counter()
        triggered_ids = []

        cash_txs = [tx for tx in transactions if "CASH" in tx.transaction_type.upper()]
        
        # Trigger if count of cash transactions >= threshold
        if len(cash_txs) >= CASH_INTENSIVE_COUNT:
            triggered_ids = [tx.transaction_id for tx in cash_txs]
        else:
            # Or if total cash amount represents >= 30% of total volume
            total_amt = sum(tx.amount for tx in transactions)
            cash_amt = sum(tx.amount for tx in cash_txs)
            if total_amt > 0 and (cash_amt / total_amt) >= CASH_INTENSIVE_RATIO:
                triggered_ids = [tx.transaction_id for tx in cash_txs]

        triggered = len(triggered_ids) > 0
        confidence = 0.80 if triggered else 0.0
        
        finding = None
        recomm = None
        if triggered:
            finding = f"[{RULE_CASH_INTENSIVE}] Cash intensive behaviour: multiple cash deposits/withdrawals or cash representing over {CASH_INTENSIVE_RATIO*100:.0f}% of total volume."
            recomm = "Obtain physical proof of cash origins and verify business model cash necessity."

        return PatternResult(
            pattern_id=RULE_CASH_INTENSIVE,
            pattern_name="Cash Intensive Behaviour",
            triggered=triggered,
            confidence=confidence,
            severity=RISK_MEDIUM,
            finding=finding,
            recommendation=recomm,
            triggered_transaction_ids=triggered_ids,
            execution_time_ms=round((time.perf_counter() - t0) * 1000, 2)
        )

    # ─────────────────────────────────────────────────────────────────────────
    # TX010: Transaction Time Anomaly
    # ─────────────────────────────────────────────────────────────────────────
    @staticmethod
    def detect_time_anomaly(transactions: List[TransactionRecord]) -> PatternResult:
        t0 = time.perf_counter()
        triggered_ids = []

        for tx in transactions:
            hour = tx.timestamp.hour
            if ANOMALY_START_HOUR <= hour < ANOMALY_END_HOUR:
                triggered_ids.append(tx.transaction_id)

        triggered = len(triggered_ids) >= ANOMALY_COUNT_THRESHOLD
        confidence = 0.70 if triggered else 0.0
        
        finding = None
        recomm = None
        if triggered:
            finding = f"[{RULE_TIME_ANOMALY}] Time anomaly: {len(triggered_ids)} transaction(s) executed during abnormal hours ({ANOMALY_START_HOUR:02d}:00–{ANOMALY_END_HOUR:02d}:00)."
            recomm = "Cross-reference IP address logs or execution origin of abnormal-hour transactions."

        return PatternResult(
            pattern_id=RULE_TIME_ANOMALY,
            pattern_name="Transaction Time Anomaly",
            triggered=triggered,
            confidence=confidence,
            severity=RISK_LOW,
            finding=finding,
            recommendation=recomm,
            triggered_transaction_ids=triggered_ids if triggered else [],
            execution_time_ms=round((time.perf_counter() - t0) * 1000, 2)
        )
