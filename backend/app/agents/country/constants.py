# ============================================================
# Country Risk Agent — Constants
# ============================================================

# ─── Rule Identifiers ───────────────────────────────────────
RULE_LOW_RISK_COUNTRY          = "CR001"
RULE_MEDIUM_RISK_COUNTRY       = "CR002"
RULE_HIGH_RISK_COUNTRY         = "CR003"
RULE_PROHIBITED_COUNTRY        = "CR004"
RULE_MULTIPLE_HIGH_RISK        = "CR005"
RULE_HIGH_RISK_TX_DEST         = "CR006"
RULE_HIGH_RISK_CO_REG          = "CR007"
RULE_UNKNOWN_COUNTRY           = "CR008"

# ─── Risk Tiers ─────────────────────────────────────────────
RISK_LOW        = "low"
RISK_MEDIUM     = "medium"
RISK_HIGH       = "high"
RISK_PROHIBITED = "prohibited"
RISK_CRITICAL   = "critical"

# ─── Country Statuses ───────────────────────────────────────
COUNTRY_STATUS_CLEAR      = "CLEAR"
COUNTRY_STATUS_WARNING    = "WARNING"
COUNTRY_STATUS_SUSPENDED  = "SUSPENDED"

# ─── Deductions ─────────────────────────────────────────────
DEDUCTION_HIGH   = 30.0
DEDUCTION_MEDIUM = 10.0

# ─── Next Agent ─────────────────────────────────────────────
NEXT_AGENT = "transaction_agent"

# ─── Provider Names ─────────────────────────────────────────
PROVIDER_MOCK = "MockCountryRiskProvider"
