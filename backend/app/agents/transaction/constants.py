"""
Transaction Agent — Constants
==============================
Contains rule identifiers, risk levels, transaction statuses, and detection thresholds.
"""

# ─── Rule Identifiers ───────────────────────────────────────
RULE_STRUCTURING = "TX001"
RULE_VELOCITY = "TX002"
RULE_LARGE_VALUE = "TX003"
RULE_HIGH_RISK_COUNTRY = "TX004"
RULE_RAPID_IN_OUT = "TX005"
RULE_ROUND_AMOUNT = "TX006"
RULE_DORMANT_REACTIVATION = "TX007"
RULE_CASH_INTENSIVE = "TX008"
RULE_MULTIPLE_PATTERNS = "TX009"
RULE_TIME_ANOMALY = "TX010"

# ─── Risk Tiers ─────────────────────────────────────────────
RISK_LOW = "low"
RISK_MEDIUM = "medium"
RISK_HIGH = "high"
RISK_CRITICAL = "critical"

# ─── Transaction Statuses ───────────────────────────────────
TRANSACTION_STATUS_CLEAR = "CLEAR"
TRANSACTION_STATUS_WARNING = "WARNING"
TRANSACTION_STATUS_ALERT = "ALERT"
TRANSACTION_STATUS_CRITICAL = "CRITICAL"

# ─── Next Agent ─────────────────────────────────────────────
NEXT_AGENT = "account_agent"

# ─── Thresholds & Weights ───────────────────────────────────
# TX001: Structuring (Smurfing)
STRUCTURING_MIN_AMT = 8000.0
STRUCTURING_MAX_AMT = 9999.99
STRUCTURING_TIME_WINDOW_HOURS = 24

# TX002: Velocity
VELOCITY_COUNT_24H = 10
VELOCITY_COUNT_7D = 20

# TX003: Large Value
LARGE_VALUE_THRESHOLD = 50000.0

# TX005: Rapid In / Rapid Out
RAPID_IN_OUT_WINDOW_HOURS = 48
RAPID_IN_OUT_RATIO = 0.80

# TX006: Round Amounts
ROUND_AMOUNTS = {10000.0, 20000.0, 50000.0, 75000.0, 100000.0}
ROUND_AMOUNT_COUNT_THRESHOLD = 3

# TX007: Dormant Reactivation
DORMANT_DAYS_THRESHOLD = 90

# TX008: Cash Intensive
CASH_INTENSIVE_RATIO = 0.30
CASH_INTENSIVE_COUNT = 3

# TX009: Multiple Suspicious Patterns
MULTIPLE_PATTERNS_COUNT = 3

# TX010: Time Anomaly
ANOMALY_START_HOUR = 0  # Midnight
ANOMALY_END_HOUR = 5  # 5 AM
ANOMALY_COUNT_THRESHOLD = 3
