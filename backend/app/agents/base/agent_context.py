import logging
from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field, ConfigDict

class AgentContext(BaseModel):
    """
    Context container holding shared infrastructure clients and trace details.
    Supplies Database, Redis, configuration, and audit logs/IDs to running agents.
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)

    db_session: Optional[Any] = None
    redis_client: Optional[Any] = None
    llm_client: Optional[Any] = None
    config: Dict[str, Any] = Field(default_factory=dict)
    logger: Any = Field(default_factory=lambda: logging.getLogger("app.agents"))
    
    current_user: Optional[Dict[str, Any]] = None
    correlation_id: Optional[str] = None
    request_id: Optional[str] = None
    current_time: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    environment: str = "development"
