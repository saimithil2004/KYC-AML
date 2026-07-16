import abc
import asyncio
import time
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from app.agents.base.agent_state import AgentState
from app.agents.base.agent_result import AgentResult
from app.agents.base.exceptions import AgentExecutionError
from app.agents.base.agent_context import AgentContext
from app.agents.base.metrics import AgentMetricsCollector

logger = logging.getLogger(__name__)

class BaseAgent(abc.ABC):
    """
    Abstract Base Class for all UK KYC/AML Agents.
    Supports timings, validations, lifecycle hooks, retries, and DI.
    """

    def __init__(self, context: Optional[AgentContext] = None):
        self.context = context or AgentContext()
        self.db = self.context.db_session


    @abc.abstractmethod
    def get_name(self) -> str:
        """Unique identifier name of the agent."""
        pass

    @abc.abstractmethod
    def get_version(self) -> str:
        """SemVer version string of the agent checks."""
        pass

    @abc.abstractmethod
    def get_description(self) -> str:
        """Text description of the agent checks."""
        pass

    @abc.abstractmethod
    def get_capabilities(self) -> List[str]:
        """List of validation checks this agent performs."""
        pass

    def validate_input(self, state: AgentState) -> bool:
        """Validates if the current state contains sufficient context for execution."""
        return True

    def pre_execute(self, state: AgentState):
        """Hook called immediately before process()."""
        state.current_agent = self.get_name()
        state.logs.append(f"Pre-execute hook started for agent: {self.get_name()}")

    @abc.abstractmethod
    async def process(self, state: AgentState) -> Dict[str, Any]:
        """Core check logic implemented by individual subclass agents."""
        pass

    def post_execute(self, state: AgentState, result: AgentResult):
        """Hook called immediately after successful execute()."""
        state.completed_agents.append(self.get_name())
        # Log metadata history
        history_item = {
            "agent": self.get_name(),
            "version": self.get_version(),
            "status": result.status,
            "reason": ", ".join(result.findings) if result.findings else "Check completed.",
            "execution_time_ms": result.execution_time,
            "timestamp": datetime.utcnow().isoformat()
        }
        state.execution_history.append(history_item)
        state.logs.append(f"Post-execute hook finished for agent: {self.get_name()}")

    def cleanup(self, state: AgentState):
        """Cleanup hook run at the end of lifecycle, whether failed or successful."""
        pass

    async def execute(self, state: AgentState, retries: int = 3, backoff: float = 1.0) -> AgentResult:
        """Executes the lifecycle: validate -> pre_execute -> process -> post_execute -> cleanup."""
        agent_name = self.get_name()
        logger.info(f"Agent '{agent_name}' execution started (Version: {self.get_version()}).")
        
        # 1. Validation check
        if not self.validate_input(state):
            state.logs.append(f"Agent '{agent_name}' validation failed.")
            raise AgentExecutionError(f"Agent {agent_name} input validation failed.")

        last_error = None
        start_time_iso = datetime.utcnow().isoformat()
        
        for attempt in range(retries):
            # Check for async cancellation
            try:
                await asyncio.sleep(0)  # Yield control to event loop
            except asyncio.CancelledError:
                logger.warning(f"Agent '{agent_name}' execution cancelled.")
                state.logs.append(f"Agent '{agent_name}' cancelled.")
                raise

            start_time = time.perf_counter()
            try:
                self.pre_execute(state)
                
                # Run core processing
                data = await self.process(state)
                
                duration_ms = (time.perf_counter() - start_time) * 1000
                status = data.get("_status", "success")
                reason = data.get("_reason", "Check completed successfully.")
                
                # Filter control values
                filtered_data = {k: v for k, v in data.items() if not k.startswith("_")}
                
                result = AgentResult(
                    status=status,
                    success=(status == "success"),
                    agent_name=agent_name,
                    execution_time=round(duration_ms, 2),
                    confidence=float(data.get("confidence") or 1.0),
                    risk_score=float(data.get("risk_score") or 0.0),
                    risk_level=str(data.get("risk_level") or "low"),
                    findings=data.get("findings") or [],
                    recommendations=data.get("recommendations") or [],
                    warnings=data.get("warnings") or [],
                    errors=data.get("errors") or [],
                    metadata=filtered_data
                )
                
                # Cache results and run post hooks
                state.agent_results[agent_name] = result.model_dump()
                self.post_execute(state, result)
                AgentMetricsCollector.record_run(agent_name, result.execution_time, True, retries=attempt)
                
                # Structured JSON logging
                from app.agents.base.logger import AgentLogger
                AgentLogger.log_execution(
                    agent_name=agent_name,
                    customer_id=state.customer_id,
                    start_time=start_time_iso,
                    end_time=datetime.utcnow().isoformat(),
                    execution_time_ms=result.execution_time,
                    correlation_id=self.context.correlation_id,
                    warnings=result.warnings,
                    errors=result.errors,
                    risk_score=result.risk_score,
                    summary=", ".join(result.findings) if result.findings else "Check completed successfully."
                )
                return result
                
            except Exception as e:
                last_error = e
                wait_sec = backoff * (2 ** attempt)
                state.logs.append(f"Agent '{agent_name}' attempt {attempt + 1} failed: {str(e)}")
                
                # Structured JSON logging of the failure attempt
                from app.agents.base.logger import AgentLogger
                AgentLogger.log_execution(
                    agent_name=agent_name,
                    customer_id=state.customer_id,
                    start_time=start_time_iso,
                    end_time=datetime.utcnow().isoformat(),
                    execution_time_ms=0.0,
                    correlation_id=self.context.correlation_id,
                    warnings=[],
                    errors=[str(e)],
                    risk_score=0.0,
                    summary=f"Attempt {attempt + 1} failure: {str(e)}"
                )
                
                from app.agents.base.exceptions import AgentValidationError, NonRetryableError, ConfigurationError
                if isinstance(e, (AgentValidationError, NonRetryableError, ConfigurationError)):
                    logger.error(f"Agent '{agent_name}' encountered non-retryable failure: {e}")
                    raise
                
                logger.warning(f"Agent '{agent_name}' attempt {attempt + 1} failed: {e}. Retrying in {wait_sec}s...")
                if attempt < retries - 1:
                    await asyncio.sleep(wait_sec)
            finally:
                self.cleanup(state)

        # Retries exhausted
        AgentMetricsCollector.record_run(agent_name, 0.0, False, retries=retries)
        raise AgentExecutionError(f"Agent {agent_name} retries exhausted. Error: {str(last_error)}") from last_error
