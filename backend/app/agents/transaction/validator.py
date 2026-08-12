"""
Transaction Agent — Validator
==============================
Validates and normalizes raw transaction dictionaries from AgentState.
Ensures schema adherence, checks currency formats, currency types,
positive transaction amounts, and reports warnings and errors.
Continues processing other transactions if one is corrupt.
"""

import logging
from datetime import datetime
from typing import List, Dict, Any, Tuple
from app.agents.base.exceptions import AgentValidationError
from app.agents.transaction.models import TransactionRecord

logger = logging.getLogger(__name__)


class TransactionValidator:
    """
    Stateless validator/normalizer for transactions.
    """

    @staticmethod
    def validate_and_normalize(
        raw_transactions: List[Dict[str, Any]],
    ) -> Tuple[List[TransactionRecord], List[str], List[str]]:
        """
        Parses and validates a list of raw transaction dicts.
        Returns:
            (valid_records, warnings, errors)
        """
        valid_records: List[TransactionRecord] = []
        warnings: List[str] = []
        errors: List[str] = []

        if not raw_transactions:
            warnings.append("No transaction history found for the customer.")
            return valid_records, warnings, errors

        for idx, tx in enumerate(raw_transactions):
            tx_id = tx.get("transaction_id", f"TX-MOCK-INDEX-{idx}")
            try:
                # ── Check essential presence ──────────────────────────────────
                required_fields = [
                    "amount",
                    "direction",
                    "timestamp",
                    "transaction_type",
                ]
                missing = [f for f in required_fields if f not in tx]
                if missing:
                    err_msg = f"Transaction {tx_id} is missing required fields: {', '.join(missing)}"
                    errors.append(err_msg)
                    logger.warning(err_msg)
                    continue

                # ── Validate amount (must be positive) ────────────────────────
                raw_amount = tx.get("amount")
                try:
                    amount = float(raw_amount)
                    if amount < 0:
                        raise ValueError("Amount cannot be negative.")
                except (ValueError, TypeError) as e:
                    err_msg = f"Transaction {tx_id} has invalid amount '{raw_amount}': {str(e)}"
                    errors.append(err_msg)
                    logger.warning(err_msg)
                    continue

                # ── Validate currency ─────────────────────────────────────────
                currency = str(tx.get("currency") or "").strip().upper()
                if not currency or len(currency) != 3 or not currency.isalpha():
                    err_msg = f"Transaction {tx_id} has invalid ISO currency code '{currency}'"
                    errors.append(err_msg)
                    logger.warning(err_msg)
                    continue

                # ── Validate direction ────────────────────────────────────────
                direction = str(tx.get("direction") or "").strip().upper()
                if direction not in ("INFLOW", "OUTFLOW", "CREDIT", "DEBIT"):
                    err_msg = f"Transaction {tx_id} has invalid direction '{direction}' (must be INFLOW or OUTFLOW)"
                    errors.append(err_msg)
                    logger.warning(err_msg)
                    continue

                # Map CREDIT/DEBIT to normalized INFLOW/OUTFLOW
                if direction in ("CREDIT", "INFLOW"):
                    norm_direction = "INFLOW"
                else:
                    norm_direction = "OUTFLOW"

                # ── Validate timestamp ────────────────────────────────────────
                raw_time = tx.get("timestamp")
                timestamp = None
                if isinstance(raw_time, datetime):
                    timestamp = raw_time
                elif isinstance(raw_time, str):
                    try:
                        timestamp = datetime.fromisoformat(raw_time.replace("Z", "+00:00"))
                    except Exception:
                        for fmt in (
                            "%Y-%m-%dT%H:%M:%S.%f",
                            "%Y-%m-%dT%H:%M:%S",
                            "%Y-%m-%d %H:%M:%S",
                            "%Y-%m-%d",
                        ):
                            try:
                                timestamp = datetime.strptime(raw_time, fmt)
                                break
                            except ValueError:
                                continue

                if not timestamp:
                    # Fallback to datetime.utcnow() but issue a warning
                    timestamp = datetime.utcnow()
                    warnings.append(
                        f"Transaction {tx_id} timestamp '{raw_time}' could not be parsed. Fallback to current time."
                    )

                # ── Validate Countries ────────────────────────────────────────
                orig_country = str(
                    tx.get("originating_country") or "United Kingdom"
                ).strip()
                dest_country = str(
                    tx.get("destination_country") or "United Kingdom"
                ).strip()

                if not orig_country or len(orig_country) < 2:
                    warnings.append(
                        f"Transaction {tx_id} originating country is invalid or empty."
                    )
                if not dest_country or len(dest_country) < 2:
                    warnings.append(
                        f"Transaction {tx_id} destination country is invalid or empty."
                    )

                # ── Build record ──────────────────────────────────────────────
                record = TransactionRecord(
                    transaction_id=str(tx_id),
                    account_id=str(tx.get("account_id") or "default_account"),
                    amount=amount,
                    currency=currency,
                    direction=norm_direction,
                    timestamp=timestamp,
                    counterparty_name=tx.get("counterparty_name"),
                    counterparty_account=tx.get("counterparty_account"),
                    transaction_type=str(tx.get("transaction_type")),
                    originating_country=orig_country,
                    destination_country=dest_country,
                    status=str(tx.get("status") or "COMPLETED").upper(),
                )
                valid_records.append(record)

            except Exception as e:
                err_msg = f"Unexpected error parsing transaction {tx_id}: {str(e)}"
                errors.append(err_msg)
                logger.error(err_msg, exc_info=True)

        return valid_records, warnings, errors
