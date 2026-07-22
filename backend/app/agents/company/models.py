from datetime import datetime
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field


class CompanyAuditTrail(BaseModel):
    """
    Immutable audit record produced after each Company Agent execution.
    Stored inside AgentResult.metadata and AgentState.shared_metadata.
    """

    passed_rules: List[str] = Field(default_factory=list)
    failed_rules: List[str] = Field(default_factory=list)
    validation_timestamp: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat()
    )
    execution_duration_ms: float = 0.0
    company_score: float = 0.0
    company_status: str = "FAILED"
    customer_type: str = "unknown"
    skipped: bool = False
    skip_reason: Optional[str] = None


class AgentRoutingInfo(BaseModel):
    """
    LangGraph-compatible routing descriptor produced by every agent.

    The orchestrator consumes this object to determine which node
    runs next. Agents NEVER invoke each other directly — they only
    populate this routing object and update AgentState.
    """

    customer_type: str
    current_agent: str
    next_agent: str
    company_agent_executed: bool = False
    skip_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()
