"""
Account Behavior Agent
========================
Detects suspicious account behavioral patterns:
  1. Dormant account (no activity for >180 days before a recent transaction)
  2. Reactivated account (dormant then sudden activity)
  3. Rapid transactions (>10 transactions in 24 hours)
  4. Mule account indicators (many small inbound, fewer large outbound)
  5. Linked account patterns (same receiver account number used multiple times)
"""

import time
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List
from collections import Counter

from app.agents.base.base_agent import BaseAgent
from app.agents.base.agent_state import AgentState
from app.agents.base.registry import AgentRegistry
from app.agents.base.exceptions import AgentValidationError

logger = logging.getLogger(__name__)

# Thresholds
DORMANCY_DAYS = 180
RAPID_TX_COUNT = 10  # Transactions within 24h
RAPID_TX_WINDOW_HOURS = 24
MULE_INBOUND_RATIO = 0.7  # >70% inbound small transactions
MULE_SMALL_AMOUNT = 1000.0  # £1,000 threshold for "small"
LINKED_ACCOUNT_MIN = 3  # Same receiver seen 3+ times


@AgentRegistry.register("account_behavior_agent")
class AccountBehaviorAgent(BaseAgent):
    """
    Account Behavior Agent.
    Identifies behavioral anomalies in account transaction history.
    """

    def get_name(self) -> str:
        return "account_behavior_agent"

    def get_version(self) -> str:
        return "1.0.0"

    def get_description(self) -> str:
        return (
            "Account behavior agent. Detects dormant accounts, reactivation patterns, "
            "rapid transaction velocity, mule account indicators, and linked account structures."
        )

    def get_capabilities(self) -> List[str]:
        return [
            "dormant_account_detection",
            "account_reactivation_detection",
            "rapid_transaction_velocity",
            "mule_account_indicators",
            "linked_account_detection",
        ]

    def validate_input(self, state: AgentState) -> bool:
        if not state.customer_id:
            raise AgentValidationError(
                message="customer_id missing in AgentState. Cannot run AccountBehaviorAgent.",
                details={"customer_id": None},
            )
        return True

    async def process(self, state: AgentState) -> Dict[str, Any]:
        start_time = time.perf_counter()
        state.logs.append(f"[{self.get_name()}] Starting account behavior analysis...")

        transactions: List[Dict[str, Any]] = state.transactions or []
        accounts: List[Dict[str, Any]] = state.accounts or []

        findings: List[str] = []
        warnings: List[str] = []
        errors: List[str] = []
        recommendations: List[str] = []

        flags: Dict[str, bool] = {
            "dormant_account": False,
            "account_reactivated": False,
            "rapid_transactions": False,
            "mule_indicators": False,
            "linked_accounts": False,
        }

        if not transactions:
            findings.append("No transaction history available for behavior analysis.")
            state.shared_metadata["account_behavior_score"] = 80.0
            state.risk_breakdown["account_behavior"] = 80.0
            execution_duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            state.logs.append(
                "AccountBehaviorAgent: No transactions — score=80 (neutral)."
            )
            return {
                "_status": "success",
                "_reason": "No transaction history. Neutral behavior score assigned.",
                "confidence": 0.8,
                "risk_score": 80.0,
                "risk_level": "low",
                "findings": findings,
                "warnings": warnings,
                "recommendations": recommendations,
                "errors": errors,
                "behavior_flags": flags,
                "account_behavior_score": 80.0,
                "execution_duration_ms": execution_duration_ms,
            }

        # ── Parse transactions ─────────────────────────────────────────────────
        parsed_txs = []
        now = datetime.utcnow()

        for tx in transactions:
            try:
                created_raw = tx.get("created_at")
                if isinstance(created_raw, str):
                    created_at = datetime.fromisoformat(
                        created_raw.replace("Z", "+00:00")
                    )
                    created_at = created_at.replace(tzinfo=None)
                elif isinstance(created_raw, datetime):
                    created_at = created_raw.replace(tzinfo=None)
                else:
                    created_at = now
                parsed_txs.append(
                    {
                        **tx,
                        "_created_at": created_at,
                        "_amount": float(tx.get("amount") or 0),
                        "_type": str(tx.get("transaction_type") or "").lower(),
                    }
                )
            except Exception:
                pass

        parsed_txs.sort(key=lambda t: t["_created_at"])

        # ── Check 1: Dormant account ──────────────────────────────────────────
        if len(parsed_txs) >= 2:
            first_tx = parsed_txs[0]["_created_at"]
            last_tx = parsed_txs[-1]["_created_at"]
            # Check for large gap in middle
            for i in range(1, len(parsed_txs)):
                gap = (
                    parsed_txs[i]["_created_at"] - parsed_txs[i - 1]["_created_at"]
                ).days
                if gap >= DORMANCY_DAYS:
                    flags["dormant_account"] = True
                    flags["account_reactivated"] = True
                    warnings.append(
                        f"Account dormancy detected: {gap}-day gap between transactions "
                        f"ending {parsed_txs[i]['_created_at'].date()}."
                    )
                    break

        # ── Check 2: Rapid transactions ───────────────────────────────────────
        window_end = now
        window_start = window_end - timedelta(hours=RAPID_TX_WINDOW_HOURS)
        recent_txs = [
            t for t in parsed_txs if window_start <= t["_created_at"] <= window_end
        ]
        if len(recent_txs) >= RAPID_TX_COUNT:
            flags["rapid_transactions"] = True
            warnings.append(
                f"Rapid transaction velocity detected: {len(recent_txs)} transactions in last "
                f"{RAPID_TX_WINDOW_HOURS} hours."
            )
            recommendations.append(
                "Investigate rapid transaction activity for potential layering."
            )

        # ── Check 3: Mule account indicators ─────────────────────────────────
        inbound_small = [
            t
            for t in parsed_txs
            if t["_type"] in ("credit", "receive", "transfer_in")
            and t["_amount"] <= MULE_SMALL_AMOUNT
        ]
        outbound_large = [
            t
            for t in parsed_txs
            if t["_type"] in ("debit", "send", "transfer_out")
            and t["_amount"] > MULE_SMALL_AMOUNT
        ]
        if len(parsed_txs) > 0:
            inbound_ratio = len(inbound_small) / len(parsed_txs)
            if inbound_ratio >= MULE_INBOUND_RATIO and len(outbound_large) > 0:
                flags["mule_indicators"] = True
                warnings.append(
                    f"Mule account pattern: {inbound_ratio:.0%} small inbound transactions "
                    f"with {len(outbound_large)} large outbound transfer(s)."
                )
                recommendations.append(
                    "Investigate account for potential money mule activity."
                )

        # ── Check 4: Linked accounts ──────────────────────────────────────────
        receiver_accounts = Counter(
            str(t.get("receiver_account_number") or "").strip()
            for t in parsed_txs
            if t.get("receiver_account_number")
        )
        frequent_receivers = {
            acc: cnt
            for acc, cnt in receiver_accounts.items()
            if cnt >= LINKED_ACCOUNT_MIN
        }
        if frequent_receivers:
            flags["linked_accounts"] = True
            for acc, cnt in list(frequent_receivers.items())[:3]:
                findings.append(
                    f"Frequent transfers to receiver account '{acc}': {cnt} transaction(s)."
                )
            recommendations.append(
                "Verify legitimacy of frequently used receiver accounts."
            )

        # ── Summary findings ──────────────────────────────────────────────────
        active_flags = [k for k, v in flags.items() if v]
        if not active_flags:
            findings.append("No suspicious account behavior patterns detected.")
        else:
            findings.append(f"Behavioral flags triggered: {', '.join(active_flags)}.")

        # ── Score ─────────────────────────────────────────────────────────────
        score = 100.0
        score -= flags["dormant_account"] * 15.0
        score -= flags["account_reactivated"] * 10.0
        score -= flags["rapid_transactions"] * 20.0
        score -= flags["mule_indicators"] * 30.0
        score -= flags["linked_accounts"] * 10.0
        score = round(max(0.0, min(100.0, score)), 2)
        risk_level = "high" if score < 40 else "medium" if score < 70 else "low"

        execution_duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        state.risk_breakdown["account_behavior"] = score
        state.shared_metadata["account_behavior_score"] = score
        state.shared_metadata["account_behavior_risk"] = risk_level
        state.shared_metadata["account_behavior_flags"] = flags

        state.logs.append(
            f"AccountBehaviorAgent: {len(parsed_txs)} tx(s) analysed. "
            f"Flags={active_flags}. Score={score}, Risk={risk_level}."
        )

        return {
            "_status": "success",
            "_reason": f"Account behavior analysis complete. Score={score}",
            "confidence": score / 100.0,
            "risk_score": score,
            "risk_level": risk_level,
            "findings": findings,
            "warnings": warnings,
            "recommendations": recommendations,
            "errors": errors,
            "account_behavior_score": score,
            "behavior_flags": flags,
            "transactions_analysed": len(parsed_txs),
            "execution_duration_ms": execution_duration_ms,
        }
