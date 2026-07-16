"""
Shared Screening — Constants
==============================
Base constants shared across PEP Agent, Sanctions Agent, and Country Risk Agent.

PEP-specific constants (PEP categories, PEP statuses) remain in pep/constants.py.
Sanctions-specific constants remain in sanctions/constants.py.
Only the cross-cutting screening infrastructure lives here.
"""

# ─── Subject Roles ────────────────────────────────────────────────────────────
ROLE_CUSTOMER              = "CUSTOMER"
ROLE_DIRECTOR              = "DIRECTOR"
ROLE_UBO                   = "UBO"
ROLE_SHAREHOLDER           = "SHAREHOLDER"
ROLE_AUTHORISED_SIGNATORY  = "AUTHORISED_SIGNATORY"
ROLE_COMPANY               = "COMPANY"

ALL_INDIVIDUAL_ROLES = {
    ROLE_CUSTOMER,
    ROLE_DIRECTOR,
    ROLE_UBO,
    ROLE_SHAREHOLDER,
    ROLE_AUTHORISED_SIGNATORY,
}

# ─── Match Confidence Levels ──────────────────────────────────────────────────
MATCH_CONFIRMED   = "CONFIRMED_MATCH"
MATCH_POSSIBLE    = "POSSIBLE_MATCH"
MATCH_NONE        = "NO_MATCH"
MATCH_UNSCREENED  = "UNSCREENED"

# ─── Match Score Thresholds ───────────────────────────────────────────────────
THRESHOLD_CONFIRMED  = 95.0   # ≥ 95 → Confirmed
THRESHOLD_POSSIBLE   = 75.0   # ≥ 75 → Possible

# ─── Individual Matching Signal Weights (must sum to 1.0) ────────────────────
WEIGHT_NAME         = 0.50
WEIGHT_DOB          = 0.20
WEIGHT_NATIONALITY  = 0.15
WEIGHT_COUNTRY      = 0.10
WEIGHT_ROLE         = 0.05

# ─── Company Matching Signal Weights (must sum to 1.0) ───────────────────────
WEIGHT_COMPANY_NAME    = 0.55
WEIGHT_REG_NUMBER      = 0.30
WEIGHT_COMPANY_COUNTRY = 0.15

# ─── Risk Tiers ───────────────────────────────────────────────────────────────
RISK_LOW       = "low"
RISK_MEDIUM    = "medium"
RISK_HIGH      = "high"
RISK_CRITICAL  = "critical"

# ─── Entity Types ─────────────────────────────────────────────────────────────
ENTITY_INDIVIDUAL  = "INDIVIDUAL"
ENTITY_COMPANY     = "COMPANY"
