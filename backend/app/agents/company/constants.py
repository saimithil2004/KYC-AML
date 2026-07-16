# ============================================================
# Company Agent — Validation Constants
# ============================================================

# ─── Customer Type Tokens ───────────────────────────────────
CUSTOMER_TYPE_INDIVIDUAL = "individual"
CUSTOMER_TYPE_BUSINESS   = "business"

# ─── Score Weights (must sum to 100) ────────────────────────
WEIGHT_REGISTRATION    = 20.0   # Company registration number + incorporation date
WEIGHT_STATUS          = 15.0   # Company status (active, dissolved, etc.)
WEIGHT_ADDRESS         = 15.0   # Registered address
WEIGHT_INDUSTRY        = 10.0   # SIC/industry code
WEIGHT_DIRECTORS       = 15.0   # At least one verified director present
WEIGHT_SHAREHOLDERS    = 10.0   # At least one shareholder present
WEIGHT_UBOS            = 10.0   # At least one UBO (>25% ownership) declared
WEIGHT_DOCUMENTS       = 5.0    # Company incorporation documents uploaded

# ─── Rule Identifiers ───────────────────────────────────────
RULE_MISSING_REG_NUMBER   = "CO001"
RULE_MISSING_STATUS       = "CO002"
RULE_INVALID_STATUS       = "CO003"
RULE_MISSING_ADDRESS      = "CO004"
RULE_MISSING_INDUSTRY     = "CO005"
RULE_NO_DIRECTORS         = "CO006"
RULE_NO_SHAREHOLDERS      = "CO007"
RULE_NO_UBOS              = "CO008"
RULE_NO_COMPANY_DOCS      = "CO009"
RULE_DISSOLVED_COMPANY    = "CO010"

# ─── Company Statuses ───────────────────────────────────────
STATUS_COMPLETE   = "COMPLETE"
STATUS_INCOMPLETE = "INCOMPLETE"
STATUS_FAILED     = "FAILED"
STATUS_SKIPPED    = "SKIPPED"

# ─── Accepted Active Company Statuses ───────────────────────
ACTIVE_COMPANY_STATUSES = {"active", "registered", "trading"}

# ─── Risk Tiers ─────────────────────────────────────────────
RISK_LOW    = "low"
RISK_MEDIUM = "medium"
RISK_HIGH   = "high"

# ─── Score Thresholds ───────────────────────────────────────
SCORE_COMPLETE_THRESHOLD   = 100.0
SCORE_INCOMPLETE_THRESHOLD = 60.0
