"""
Country Risk Agent — Models
============================

CountryRiskProfile
    A model representing the risk parameters of a single country.

CountryRiskAssessment
    A model summarizing the risk assessment details of a list of evaluated countries.

CountryAuditTrail
    The immutable per-run audit record produced by the Country Risk Agent.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ─────────────────────────────────────────────────────────────────────────────
# CountryRiskProfile — risk properties for a country
# ─────────────────────────────────────────────────────────────────────────────
class CountryRiskProfile(BaseModel):
    """
    Holds the risk classification and details for a country.
    """

    country_name: str
    iso_alpha2: str
    iso_alpha3: str
    risk_level: str  # RISK_LOW, RISK_MEDIUM, RISK_HIGH, RISK_PROHIBITED
    is_fatf_listed: bool = False
    is_sanctioned: bool = False
    source: str = "unknown"
    last_updated: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# CountryRiskAssessment — assessment outcome
# ─────────────────────────────────────────────────────────────────────────────
class CountryRiskAssessment(BaseModel):
    """
    Aggregated details of a country risk screening execution.
    """

    country_status: str
    country_score: float
    risk_level: str
    evaluated_countries: List[str] = Field(default_factory=list)
    high_risk_countries: List[str] = Field(default_factory=list)
    prohibited_countries: List[str] = Field(default_factory=list)
    findings: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    rules_triggered: List[str] = Field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# CountryAuditTrail — audit trail
# ─────────────────────────────────────────────────────────────────────────────
class CountryAuditTrail(BaseModel):
    """Immutable per-run audit record produced by the Country Risk Agent."""

    provider_used: str
    countries_evaluated: List[str] = Field(default_factory=list)
    risk_matrix_version: str = "1.0.0"
    high_risk_countries: List[str] = Field(default_factory=list)
    prohibited_countries: List[str] = Field(default_factory=list)
    triggered_rules: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    execution_duration_ms: float = 0.0
    validation_timestamp: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat()
    )
