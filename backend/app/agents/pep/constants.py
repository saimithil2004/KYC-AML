# ============================================================
# PEP Agent — Constants
# ============================================================
#
# Cross-cutting constants (roles, match levels, thresholds, weights, risks)
# are imported from the shared screening package and re-exported here so
# all existing PEP imports continue to work without modification.
#
from app.agents.screening.constants import (
    ROLE_CUSTOMER,
    ROLE_DIRECTOR,
    ROLE_UBO,
    ROLE_SHAREHOLDER,
    ROLE_AUTHORISED_SIGNATORY,
    ROLE_COMPANY,
    MATCH_CONFIRMED,
    MATCH_POSSIBLE,
    MATCH_NONE,
    MATCH_UNSCREENED,
    THRESHOLD_CONFIRMED,
    THRESHOLD_POSSIBLE,
    WEIGHT_NAME,
    WEIGHT_DOB,
    WEIGHT_NATIONALITY,
    WEIGHT_COUNTRY,
    WEIGHT_ROLE,
    RISK_LOW,
    RISK_MEDIUM,
    RISK_HIGH,
    RISK_CRITICAL,
)  # noqa: F401

# ─── Rule Identifiers ───────────────────────────────────────
RULE_NO_MATCH = "PEP001"
RULE_POSSIBLE_MATCH = "PEP002"
RULE_CONFIRMED_PEP = "PEP003"
RULE_FOREIGN_PEP = "PEP004"
RULE_FAMILY_MEMBER = "PEP005"
RULE_CURRENT_OFFICE = "PEP006"
RULE_FORMER_PEP = "PEP007"

# ─── PEP Categories ─────────────────────────────────────────
PEP_CATEGORY_DOMESTIC = "DOMESTIC_PEP"
PEP_CATEGORY_FOREIGN = "FOREIGN_PEP"
PEP_CATEGORY_INTERNATIONAL_ORG = "INTERNATIONAL_ORG_PEP"
PEP_CATEGORY_FAMILY_MEMBER = "FAMILY_MEMBER"
PEP_CATEGORY_CLOSE_ASSOCIATE = "CLOSE_ASSOCIATE"
PEP_CATEGORY_FORMER_PEP = "FORMER_PEP"
PEP_CATEGORY_CURRENT_PEP = "CURRENT_PEP"

ALL_PEP_CATEGORIES = {
    PEP_CATEGORY_DOMESTIC,
    PEP_CATEGORY_FOREIGN,
    PEP_CATEGORY_INTERNATIONAL_ORG,
    PEP_CATEGORY_FAMILY_MEMBER,
    PEP_CATEGORY_CLOSE_ASSOCIATE,
    PEP_CATEGORY_FORMER_PEP,
    PEP_CATEGORY_CURRENT_PEP,
}

# ─── PEP Statuses ───────────────────────────────────────────
PEP_STATUS_CLEAR = "CLEAR"
PEP_STATUS_POSSIBLE = "POSSIBLE_MATCH"
PEP_STATUS_CONFIRMED = "CONFIRMED_PEP"

# ─── Next Agent ─────────────────────────────────────────────
NEXT_AGENT = "sanctions_agent"

# ─── Provider Names ─────────────────────────────────────────
PROVIDER_MOCK = "MockPepProvider"
PROVIDER_OPEN_SANCTIONS = "OpenSanctionsProvider"
PROVIDER_WORLD_CHECK = "WorldCheckProvider"
PROVIDER_DOW_JONES = "DowJonesProvider"
