import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

class AgentLogger:
    """
    Structured JSON logger for compliance agent executions.
    Ensures logs are formatted as single-line JSON items for ingestion.
    """
    @staticmethod
    def log_execution(
        agent_name: str,
        customer_id: str,
        start_time: str,
        end_time: str,
        execution_time_ms: float,
        correlation_id: Optional[str] = None,
        warnings: List[str] = None,
        errors: List[str] = None,
        risk_score: float = 0.0,
        summary: str = ""
    ) -> Dict[str, Any]:
        log_payload = {
            "timestamp": datetime.utcnow().isoformat(),
            "event": "agent_execution",
            "agent_name": agent_name,
            "customer_id": customer_id,
            "start_time": start_time,
            "end_time": end_time,
            "execution_time_ms": execution_time_ms,
            "correlation_id": correlation_id or "N/A",
            "risk_score": risk_score,
            "warnings": warnings or [],
            "errors": errors or [],
            "summary": summary
        }
        logger = logging.getLogger(f"app.agents.{agent_name}")
        logger.info(json.dumps(log_payload))
        return log_payload
