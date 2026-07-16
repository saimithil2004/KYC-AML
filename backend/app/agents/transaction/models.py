"""
Transaction Agent — Models
===========================
Defines the internal data structures and Pydantic models for the Transaction Agent.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class TransactionRecord(BaseModel):
    """
    Normalized representation of a single financial transaction.
    Validated and prepared by TransactionValidator.
    """
    transaction_id: str
    account_id: str
    amount: float
    currency: str
    direction: str                     # "INFLOW" or "OUTFLOW" (credit/debit)
    timestamp: datetime
    counterparty_name: Optional[str] = None
    counterparty_account: Optional[str] = None
    transaction_type: str              # "TRANSFER", "CASH_DEPOSIT", "CASH_WITHDRAWAL", "CARD", etc.
    originating_country: str = "United Kingdom"
    destination_country: str = "United Kingdom"
    status: str = "COMPLETED"


class PatternResult(BaseModel):
    """
    Holds the output of a single AML pattern detector execution.
    """
    pattern_id: str                    # e.g., "TX001"
    pattern_name: str                  # e.g., "Structuring (Smurfing)"
    triggered: bool
    confidence: float = 0.0            # 0.0 to 1.0
    severity: str = "low"              # "low", "medium", "high", "critical"
    finding: Optional[str] = None
    recommendation: Optional[str] = None
    triggered_transaction_ids: List[str] = Field(default_factory=list)
    execution_time_ms: float = 0.0


class TransactionAnalysis(BaseModel):
    """
    Aggregated outcome of the entire pattern detection and rules evaluation.
    """
    transaction_status: str            # CLEAR, WARNING, ALERT, CRITICAL
    transaction_score: float           # 0.0 to 100.0 (100 = safe, 0 = critical risk)
    risk_level: str                    # low, medium, high, critical
    triggered_patterns: List[PatternResult] = Field(default_factory=list)
    findings: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    rules_triggered: List[str] = Field(default_factory=list)


class TransactionAuditTrail(BaseModel):
    """
    Immutable audit trail object stored in shared_metadata and AgentResult.
    """
    validation_timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    execution_duration_ms: float = 0.0
    transactions_analysed: int = 0
    patterns_triggered: List[str] = Field(default_factory=list)
    rules_triggered: List[str] = Field(default_factory=list)
    risk_score: float = 0.0
    risk_level: str = "low"
    recommendations: List[str] = Field(default_factory=list)
