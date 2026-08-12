from datetime import datetime
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class AgentState(BaseModel):
    """
    Shared memory context representing the full state of a case.
    Every agent reads from and updates this same state context.
    """

    customer_id: str
    case_id: str
    investigation_id: Optional[str] = None
    risk_score_id: Optional[str] = None

    # Core Domain Context Models (Inputs/References)
    customer: Dict[str, Any] = Field(default_factory=dict)
    customer_profile: Dict[str, Any] = Field(default_factory=dict)
    kyc_profile: Optional[Dict[str, Any]] = None
    uploaded_documents: List[Dict[str, Any]] = Field(default_factory=list)
    accounts: List[Dict[str, Any]] = Field(default_factory=list)
    transactions: List[Dict[str, Any]] = Field(default_factory=list)
    companies: List[Dict[str, Any]] = Field(default_factory=list)
    directors: List[Dict[str, Any]] = Field(default_factory=list)
    ubos: List[Dict[str, Any]] = Field(default_factory=list)
    alerts: List[Dict[str, Any]] = Field(default_factory=list)
    risk_scores: List[Dict[str, Any]] = Field(default_factory=list)
    policies: List[Dict[str, Any]] = Field(default_factory=list)
    monitoring_schedule: Optional[Dict[str, Any]] = None

    # Execution Tracking
    current_agent: Optional[str] = None
    completed_agents: List[str] = Field(default_factory=list)
    execution_history: List[Dict[str, Any]] = Field(default_factory=list)

    # Shared Metadata
    shared_metadata: Dict[str, Any] = Field(default_factory=dict)

    # Outputs aggregated from individual agent executions
    agent_results: Dict[str, Any] = Field(default_factory=dict)

    # Central risk engine metrics
    overall_score: float = 0.0
    risk_tier: str = "low"
    risk_breakdown: Dict[str, float] = Field(default_factory=dict)

    # Decision output
    final_decision: Optional[str] = None  # "approve", "reject", "edd", "manual_review"
    decision_reason: Optional[str] = None

    # Execution logs
    logs: List[str] = Field(default_factory=list)

    def serialize(self) -> str:
        """Serializes current state into a JSON string."""
        return self.model_dump_json()

    @classmethod
    def deserialize(cls, json_str: str) -> "AgentState":
        """Deserializes JSON string into an AgentState instance."""
        return cls.model_validate_json(json_str)

    def update_metadata(self, key: str, value: Any) -> "AgentState":
        """Returns a copy of the state with the updated metadata key (Immutable-friendly)."""
        copied = self.model_copy(deep=True)
        copied.shared_metadata[key] = value
        return copied
