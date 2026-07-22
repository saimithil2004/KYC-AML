"""
Risk Scoring Configuration
===========================
Centralised, configurable weights and thresholds for the RiskScoringAgent.
All values can be overridden via environment variables or a config file without
touching agent logic, satisfying the SOLID Open/Closed principle.

Weight semantics
----------------
Each weight represents the maximum risk contribution of that signal when
it is at its worst (score 0 from the individual agent).
The final overall_score is in the range 0–100.

  overall_score = sum(weight_i * (1 - agent_score_i / 100))  for each signal

Thresholds
----------
  LOW    : 0  – 30
  MEDIUM : 31 – 70
  HIGH   : 71 – 100
"""

from typing import Dict

# ── Risk Signal Weights ───────────────────────────────────────────────────────
# Must sum to 100 for a normalised score.
RISK_WEIGHTS: Dict[str, float] = {
    "pep": 30.0,  # PEP screening signal
    "sanctions": 40.0,  # Sanctions screening signal (highest weight)
    "country": 10.0,  # Country / jurisdiction risk
    "document": 10.0,  # Document verification signal
    "transaction": 10.0,  # Transaction behaviour signal
}

# ── Risk Level Thresholds ─────────────────────────────────────────────────────
RISK_THRESHOLDS: Dict[str, float] = {
    "LOW": 30.0,  # overall_score <= 30 → LOW
    "MEDIUM": 70.0,  # 31 <= overall_score <= 70 → MEDIUM
    "HIGH": 100.0,  # overall_score > 70 → HIGH
}

# ── Individual Agent Default Scores ──────────────────────────────────────────
# Used when an agent did not run or returned no result.
# 50.0 = neutral / unknown — does not inflate nor deflate risk.
DEFAULT_AGENT_SCORE: float = 50.0

# ── Score Interpretation Labels ───────────────────────────────────────────────
RISK_LEVEL_LOW = "LOW"
RISK_LEVEL_MEDIUM = "MEDIUM"
RISK_LEVEL_HIGH = "HIGH"


def get_risk_level(score: float) -> str:
    """Returns the risk level string for a given overall score (0–100)."""
    if score <= RISK_THRESHOLDS["LOW"]:
        return RISK_LEVEL_LOW
    if score <= RISK_THRESHOLDS["MEDIUM"]:
        return RISK_LEVEL_MEDIUM
    return RISK_LEVEL_HIGH
