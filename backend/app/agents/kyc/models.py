from datetime import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class KycAuditTrail(BaseModel):
    """Audit object representing the validation trail of a KYC screening run."""

    passed_rules: List[str] = Field(default_factory=list)
    failed_rules: List[str] = Field(default_factory=list)
    validation_timestamp: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat()
    )
    execution_duration: float = 0.0
    kyc_score: float = 0.0
    kyc_status: str = "PENDING"
