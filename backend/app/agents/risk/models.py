"""Risk Scoring Agent — Pydantic models."""
from datetime import datetime
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class ContributingFactor(BaseModel):
    """Represents a single signal's contribution to the overall risk score."""
    signal: str
    weight: float
    agent_score: float          # 0–100 from the individual agent
    contribution: float         # weight * (1 - agent_score / 100)
    explanation: str


class RiskScoringResult(BaseModel):
    """Final risk scoring output."""
    overall_score: float                        # 0–100
    risk_level: str                             # LOW | MEDIUM | HIGH
    contributing_factors: List[ContributingFactor] = Field(default_factory=list)
    explanation: str = ""
    weights_used: Dict[str, float] = Field(default_factory=dict)
    agent_scores_input: Dict[str, float] = Field(default_factory=dict)
    computed_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class RiskScoringAuditTrail(BaseModel):
    """Audit record for a risk scoring execution."""
    overall_score: float
    risk_level: str
    contributing_factors: List[Dict[str, Any]] = Field(default_factory=list)
    weights_used: Dict[str, float] = Field(default_factory=dict)
    agent_scores_input: Dict[str, float] = Field(default_factory=dict)
    execution_duration_ms: float = 0.0
    validation_timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
