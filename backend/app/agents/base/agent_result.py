from datetime import datetime
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

class AgentResult(BaseModel):
    """Normalized response payload returned by all UK AML + KYC compliance agents."""
    status: str  # "success" or "failed"
    success: bool
    agent_name: str
    execution_time: float  # In milliseconds
    confidence: float = 1.0  # 0.0 to 1.0
    risk_score: float = 0.0  # 0.0 to 100.0
    risk_level: str = "low"  # "low", "medium", "high"
    findings: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
