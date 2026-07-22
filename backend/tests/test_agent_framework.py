import pytest
import asyncio
from typing import Dict, Any, List

from app.agents.base.agent_state import AgentState
from app.agents.base.agent_result import AgentResult
from app.agents.base.base_agent import BaseAgent
from app.agents.base.registry import AgentRegistry
from app.agents.base.agent_context import AgentContext
from app.agents.base.metrics import AgentMetricsCollector
from app.agents.base.exceptions import (
    AgentExecutionError,
    AgentValidationError,
    DatabaseError,
    ConfigurationError,
    RiskCalculationError,
)


# Mock Subclass Agent
@AgentRegistry.register("mock_test_agent")
class MockTestAgent(BaseAgent):
    def get_name(self) -> str:
        return "mock_test_agent"

    def get_version(self) -> str:
        return "1.0.0"

    def get_description(self) -> str:
        return "Mock testing agent"

    def get_capabilities(self) -> List[str]:
        return ["mock_check"]

    async def process(self, state: AgentState) -> Dict[str, Any]:
        return {
            "score": 85.0,
            "findings": ["Everything is normal"],
            "risk_level": "low",
            "risk_score": 10.0,
            "_status": "success",
            "_reason": "Mock checks passed successfully.",
        }


@AgentRegistry.register("mock_failing_agent")
class MockFailingAgent(BaseAgent):
    def get_name(self) -> str:
        return "mock_failing_agent"

    def get_version(self) -> str:
        return "1.0.0"

    def get_description(self) -> str:
        return "Mock failing agent"

    def get_capabilities(self) -> List[str]:
        return ["failing_check"]

    async def process(self, state: AgentState) -> Dict[str, Any]:
        raise ValueError("Critical runtime validation error occurred.")


@pytest.mark.anyio
async def test_agent_registry():
    registry = AgentRegistry.get_registry()
    agent = registry.get_agent("mock_test_agent")
    assert agent.get_name() == "mock_test_agent"
    assert agent.get_version() == "1.0.0"
    assert agent.get_description() == "Mock testing agent"
    assert agent.get_capabilities() == ["mock_check"]
    assert isinstance(agent, BaseAgent)

    # Test unregister
    registry.unregister("mock_test_agent")
    with pytest.raises(Exception):
        registry.get_agent("mock_test_agent")

    # Re-register manually
    registry.register_agent_class("mock_test_agent", MockTestAgent)


@pytest.mark.anyio
async def test_agent_execution_success():
    state = AgentState(customer_id="cust-123", case_id="case-456")
    registry = AgentRegistry.get_registry()
    agent = registry.get_agent("mock_test_agent")

    res = await agent.execute(state)

    assert res.status == "success"
    assert res.success is True
    assert res.risk_level == "low"
    assert res.risk_score == 10.0
    assert res.findings == ["Everything is normal"]
    assert res.execution_time >= 0

    # Assert lifecycle hooks updated the state memory
    assert state.current_agent == "mock_test_agent"
    assert "mock_test_agent" in state.completed_agents
    assert len(state.execution_history) == 1
    assert state.execution_history[0]["agent"] == "mock_test_agent"
    assert state.execution_history[0]["reason"] == "Everything is normal"

    assert "mock_test_agent" in state.agent_results
    assert state.agent_results["mock_test_agent"]["status"] == "success"
    assert any("finished" in log for log in state.logs)


@pytest.mark.anyio
async def test_agent_execution_failure():
    state = AgentState(customer_id="cust-123", case_id="case-456")
    registry = AgentRegistry.get_registry()
    agent = registry.get_agent("mock_failing_agent")

    # Reset metrics collector counts
    AgentMetricsCollector.reset()

    with pytest.raises(AgentExecutionError) as exc_info:
        await agent.execute(state, retries=2)

    assert "validation error" in str(exc_info.value)
    assert any("failed" in log for log in state.logs)

    # Verify failure count is recorded
    metrics = AgentMetricsCollector.get_agent_metrics("mock_failing_agent")
    assert metrics["success_rate"] == 0.0
    assert metrics["failure_rate"] == 1.0


def test_exception_framework_fields():
    # Test structured metadata fields in custom exceptions
    exc = DatabaseError(
        message="Failed to connect to primary replica",
        details={"replica_id": 4, "timeout": True},
        severity="CRITICAL",
    )

    assert exc.error_code == "DATABASE_ERROR"
    assert exc.severity == "CRITICAL"
    assert exc.details["replica_id"] == 4
    assert exc.timestamp is not None
    assert "replica_id" in str(exc)


def test_agent_context_injection():
    dummy_db = "dummy_session"
    ctx = AgentContext(
        db_session=dummy_db, environment="staging", correlation_id="trace-999"
    )
    agent = MockTestAgent(context=ctx)

    assert agent.context.environment == "staging"
    assert agent.context.correlation_id == "trace-999"
    assert agent.db == "dummy_session"


def test_metrics_prometheus_exposition():
    AgentMetricsCollector.reset()
    AgentMetricsCollector.record_run("pep_agent", 45.2, True, retries=0)
    AgentMetricsCollector.record_run("pep_agent", 50.8, True, retries=1)

    metrics = AgentMetricsCollector.get_agent_metrics("pep_agent")
    assert metrics["usage_count"] == 2
    assert metrics["average_execution_time_ms"] == 48.0
    assert metrics["retry_count"] == 1
    assert metrics["success_rate"] == 1.0

    prom_str = AgentMetricsCollector.to_prometheus_format()
    assert "agent_usage_total" in prom_str
    assert 'agent_usage_total{agent="pep_agent"} 2' in prom_str
    assert "process_cpu_usage_ratio" in prom_str
    assert "process_memory_rss_bytes" in prom_str


def test_agent_logger():
    from app.agents.base.logger import AgentLogger

    payload = AgentLogger.log_execution(
        agent_name="kyc_agent",
        customer_id="cust-777",
        start_time="2026-07-12T10:00:00",
        end_time="2026-07-12T10:00:01",
        execution_time_ms=1050.2,
        correlation_id="corr-888",
        warnings=["Missing phone"],
        errors=[],
        risk_score=15.0,
        summary="Audit complete",
    )
    assert payload["agent_name"] == "kyc_agent"
    assert payload["customer_id"] == "cust-777"
    assert payload["risk_score"] == 15.0
    assert payload["warnings"] == ["Missing phone"]
