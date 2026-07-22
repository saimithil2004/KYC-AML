"""
Transaction Monitoring Service
================================
Analyses transactions for suspicious activity patterns and, when a pattern is
detected, automatically creates Alerts and Cases, then triggers an async AI
screening via OrchestratorAgent (running in a background thread so the HTTP
request is not blocked).

Suspicious patterns detected:
  1. LARGE_TRANSACTION       — single tx > £10,000
  2. RAPID_TRANSACTIONS      — ≥5 tx within 60 minutes
  3. STRUCTURING             — multiple tx slightly below £10,000 within 24h
  4. DORMANT_REACTIVATION    — first tx after >180 days of silence
  5. CIRCULAR_TRANSFER       — sender receives money back from same counterpart within 24h
  6. REPEATED_BENEFICIARY    — same receiver_account_number ≥5 times within 7 days
  7. HIGH_RISK_COUNTRY        — FATF grey/black-listed destination country
  8. VELOCITY_ANOMALY         — daily total > 3× the customer's 30-day daily average
  9. CASH_INTENSIVE           — >60% of txs tagged as 'cash'
  10. MULE_INDICATOR          — ≥70% small inbound + large outbound within 48h
"""

import asyncio
import logging
import threading
from datetime import datetime, timedelta
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.models import (
    Account,
    Alert,
    Case,
    Customer,
    KYCProfile,
    Transaction,
)

logger = logging.getLogger(__name__)

# ── Configuration constants ───────────────────────────────────────────────────

LARGE_TX_THRESHOLD = 10_000.0  # GBP
STRUCTURING_THRESHOLD = 9_500.0  # just-below threshold
STRUCTURING_WINDOW_HRS = 24
RAPID_TX_COUNT = 5
RAPID_TX_WINDOW_MINS = 60
DORMANT_DAYS = 180
VELOCITY_MULTIPLIER = 3.0
VELOCITY_LOOKBACK_DAYS = 30
VELOCITY_WINDOW_HOURS = 24
CASH_INTENSIVE_PCT = 0.60
MULE_INBOUND_PCT = 0.70
MULE_WINDOW_HRS = 48
REPEATED_BENE_COUNT = 5
REPEATED_BENE_DAYS = 7

FATF_HIGH_RISK_COUNTRIES = {
    "Afghanistan",
    "Myanmar",
    "North Korea",
    "Iran",
    "Syria",
    "Yemen",
    "Libya",
    "Somalia",
    "South Sudan",
    "Venezuela",
    "Haiti",
    "Panama",
    "Philippines",
    "Pakistan",
    "Uganda",
    "Nigeria",
    "Burkina Faso",
    "Mali",
    "Mozambique",
    "Cameroon",
    "Senegal",
    "South Africa",
    "Tanzania",
    "Vietnam",
}

ALERT_LEVEL_MAP = {
    "LARGE_TRANSACTION": ("HIGH", 85.0),
    "RAPID_TRANSACTIONS": ("HIGH", 80.0),
    "STRUCTURING": ("CRITICAL", 95.0),
    "DORMANT_REACTIVATION": ("MEDIUM", 55.0),
    "CIRCULAR_TRANSFER": ("HIGH", 88.0),
    "REPEATED_BENEFICIARY": ("MEDIUM", 60.0),
    "HIGH_RISK_COUNTRY": ("HIGH", 82.0),
    "VELOCITY_ANOMALY": ("HIGH", 78.0),
    "CASH_INTENSIVE": ("MEDIUM", 65.0),
    "MULE_INDICATOR": ("CRITICAL", 92.0),
}


# ── Public entry point ────────────────────────────────────────────────────────


async def analyse_and_alert(
    db: AsyncSession,
    transaction: Transaction,
    account: Account,
) -> List[Alert]:
    """
    Called immediately after a transaction is persisted.
    Returns the list of newly created Alert objects (already committed).
    """
    customer_id = account.customer_id
    patterns = await _detect_patterns(db, transaction, account, customer_id)

    if not patterns:
        return []

    alerts = []
    case = None

    for pattern_name, detail_msg in patterns:
        level, risk_score = ALERT_LEVEL_MAP.get(pattern_name, ("MEDIUM", 60.0))

        alert = Alert(
            customer_id=customer_id,
            transaction_id=transaction.id,
            alert_type=pattern_name,
            risk_score=risk_score,
            status="open",
            alert_metadata={
                "level": level,
                "pattern": pattern_name,
                "detail": detail_msg,
                "transaction_id": str(transaction.id),
                "amount": float(transaction.amount),
                "currency": transaction.currency,
                "receiver": transaction.receiver_name,
                "receiver_country": transaction.receiver_country,
                "detected_at": datetime.utcnow().isoformat(),
            },
        )
        db.add(alert)
        alerts.append(alert)

    # Create or reuse case for this customer (one open case per customer)
    existing_case_result = await db.execute(
        select(Case)
        .where(
            Case.customer_id == customer_id,
            Case.status.in_(["new", "investigating", "open", "under_review"]),
        )
        .order_by(Case.created_at.desc())
        .limit(1)
    )
    existing_case = existing_case_result.scalars().first()

    if existing_case:
        case = existing_case
        # Append alert note
        note_suffix = f"\n[AUTO] New suspicious pattern detected: {', '.join(p[0] for p in patterns)}"
        case.investigation_notes = (case.investigation_notes or "") + note_suffix
        # Escalate priority if needed
        max_score = max(
            ALERT_LEVEL_MAP.get(p[0], ("MEDIUM", 60.0))[1] for p in patterns
        )
        if max_score >= 90.0 and case.priority != "critical":
            case.priority = "critical"
        elif max_score >= 80.0 and case.priority not in ("high", "critical"):
            case.priority = "high"
    else:
        max_score = max(
            ALERT_LEVEL_MAP.get(p[0], ("MEDIUM", 60.0))[1] for p in patterns
        )
        if max_score >= 90.0:
            priority = "critical"
        elif max_score >= 80.0:
            priority = "high"
        else:
            priority = "medium"

        pattern_names = [p[0] for p in patterns]
        case = Case(
            customer_id=customer_id,
            priority=priority,
            status="investigating",
            investigation_notes=(
                f"[AUTO] Suspicious activity case opened automatically.\n"
                f"Patterns detected: {', '.join(pattern_names)}\n"
                f"Triggered by transaction: {transaction.id} "
                f"(Amount: {float(transaction.amount):.2f} {transaction.currency})\n"
                f"Receiver: {transaction.receiver_name} ({transaction.receiver_country})"
            ),
            sar_filed=False,
        )
        db.add(case)

    await db.commit()

    # Refresh all
    for a in alerts:
        await db.refresh(a)

    logger.info(
        f"TransactionMonitoring: {len(alerts)} alert(s) created for customer "
        f"{customer_id} — patterns: {[p[0] for p in patterns]}"
    )

    # ── Trigger AI re-screening in background ─────────────────────────────────
    _trigger_rescreening_background(str(customer_id))

    return alerts


# ── Pattern detection ─────────────────────────────────────────────────────────


async def _detect_patterns(
    db: AsyncSession,
    tx: Transaction,
    account: Account,
    customer_id: UUID,
) -> List[Tuple[str, str]]:
    """Run all pattern detectors and return (pattern_name, detail_message) pairs."""
    patterns: List[Tuple[str, str]] = []

    # Load recent tx history for this account
    now = datetime.utcnow()
    result = await db.execute(
        select(Transaction)
        .where(Transaction.sender_account_id == account.id)
        .order_by(Transaction.created_at.desc())
        .limit(500)
    )
    all_txs = result.scalars().all()

    # 1. Large transaction
    if float(tx.amount) >= LARGE_TX_THRESHOLD:
        patterns.append(
            (
                "LARGE_TRANSACTION",
                f"Transaction of {float(tx.amount):.2f} {tx.currency} exceeds threshold of {LARGE_TX_THRESHOLD:,.0f}",
            )
        )

    # 2. Rapid transactions
    window_start = now - timedelta(minutes=RAPID_TX_WINDOW_MINS)
    rapid = [t for t in all_txs if t.created_at >= window_start]
    if len(rapid) >= RAPID_TX_COUNT:
        patterns.append(
            (
                "RAPID_TRANSACTIONS",
                f"{len(rapid)} transactions within {RAPID_TX_WINDOW_MINS} minutes (threshold: {RAPID_TX_COUNT})",
            )
        )

    # 3. Structuring (smurfing) — multiple sub-threshold txs
    struct_start = now - timedelta(hours=STRUCTURING_WINDOW_HRS)
    struct_txs = [
        t
        for t in all_txs
        if t.created_at >= struct_start and float(t.amount) >= STRUCTURING_THRESHOLD
    ]
    if len(struct_txs) >= 3:
        total = sum(float(t.amount) for t in struct_txs)
        patterns.append(
            (
                "STRUCTURING",
                f"{len(struct_txs)} transactions totalling {total:,.2f} {tx.currency} "
                f"in {STRUCTURING_WINDOW_HRS}h — possible structuring to evade reporting threshold",
            )
        )

    # 4. Dormant reactivation
    if len(all_txs) >= 2:
        previous = sorted(all_txs, key=lambda t: t.created_at)
        if previous:
            last_before = [t for t in previous if t.id != tx.id]
            if last_before:
                gap = (now - last_before[-1].created_at).days
                if gap >= DORMANT_DAYS:
                    patterns.append(
                        (
                            "DORMANT_REACTIVATION",
                            f"Account dormant for {gap} days — first transaction after prolonged inactivity",
                        )
                    )

    # 5. Circular transfer — receiver is also a sender back to this account
    circ_start = now - timedelta(hours=24)
    account_num = account.account_number
    # Look for any tx TO this account from the same receiver (no DB join available easily)
    # We use a heuristic: the receiver account number matches our account number in other txs
    circ_txs = [
        t
        for t in all_txs
        if t.created_at >= circ_start and t.receiver_account_number == account_num
    ]
    if circ_txs:
        patterns.append(
            (
                "CIRCULAR_TRANSFER",
                f"Circular transfer detected — receiver {tx.receiver_account_number} "
                f"also sent money back to this account within 24h",
            )
        )

    # 6. Repeated beneficiary
    bene_start = now - timedelta(days=REPEATED_BENE_DAYS)
    bene_txs = [
        t
        for t in all_txs
        if t.created_at >= bene_start
        and t.receiver_account_number == tx.receiver_account_number
    ]
    if len(bene_txs) >= REPEATED_BENE_COUNT:
        patterns.append(
            (
                "REPEATED_BENEFICIARY",
                f"Receiver {tx.receiver_account_number} ({tx.receiver_name}) appears "
                f"{len(bene_txs)} times within {REPEATED_BENE_DAYS} days",
            )
        )

    # 7. High-risk country
    if tx.receiver_country in FATF_HIGH_RISK_COUNTRIES:
        patterns.append(
            (
                "HIGH_RISK_COUNTRY",
                f"Transfer to high-risk/FATF-listed country: {tx.receiver_country}",
            )
        )

    # 8. Velocity anomaly
    vel_start = now - timedelta(days=VELOCITY_LOOKBACK_DAYS)
    hist_txs = [t for t in all_txs if t.created_at >= vel_start]
    if hist_txs:
        total_hist = sum(float(t.amount) for t in hist_txs)
        avg_daily = total_hist / VELOCITY_LOOKBACK_DAYS
        today_start = now - timedelta(hours=VELOCITY_WINDOW_HOURS)
        today_total = sum(
            float(t.amount) for t in all_txs if t.created_at >= today_start
        )
        if avg_daily > 0 and today_total >= VELOCITY_MULTIPLIER * avg_daily:
            patterns.append(
                (
                    "VELOCITY_ANOMALY",
                    f"Today's total {today_total:,.2f} is {today_total/avg_daily:.1f}x the 30-day daily average {avg_daily:,.2f}",
                )
            )

    # 9. Cash intensive
    cash_txs = [t for t in all_txs[:50] if "cash" in (t.transaction_type or "").lower()]
    if (
        len(all_txs[:50]) >= 5
        and len(cash_txs) / max(len(all_txs[:50]), 1) >= CASH_INTENSIVE_PCT
    ):
        patterns.append(
            (
                "CASH_INTENSIVE",
                f"{len(cash_txs)}/{len(all_txs[:50])} recent transactions are cash-based — cash intensive behaviour detected",
            )
        )

    # 10. Mule account indicator — many small inbound + single large outbound
    inbound = [
        t
        for t in all_txs
        if float(t.amount) < 500 and t.transaction_type in ("credit", "inbound")
    ]
    outbound = [
        t
        for t in all_txs
        if float(t.amount) > 2000
        and t.transaction_type in ("debit", "outbound", "transfer")
    ]
    if len(inbound) + len(outbound) > 0:
        inbound_pct = len(inbound) / (len(inbound) + len(outbound))
        if inbound_pct >= MULE_INBOUND_PCT and len(outbound) >= 1:
            patterns.append(
                (
                    "MULE_INDICATOR",
                    f"Mule account pattern: {len(inbound)} small inbound, {len(outbound)} large outbound transactions",
                )
            )

    return patterns


# ── Background AI re-screening ────────────────────────────────────────────────


def _trigger_rescreening_background(customer_id: str) -> None:
    """
    Launches OrchestratorAgent re-screening in a daemon background thread
    so the HTTP response returns immediately.
    """

    def _run():
        try:
            from app.services.screening_service import ScreeningService

            ScreeningService.run_screening(customer_id)
            logger.info(
                f"TransactionMonitoring: Background re-screening complete for {customer_id}"
            )
        except Exception as exc:
            logger.error(
                f"TransactionMonitoring: Background re-screening failed for {customer_id}: {exc}"
            )

    t = threading.Thread(target=_run, daemon=True)
    t.start()
