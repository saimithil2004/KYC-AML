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
            "reason": (
                ", ".join(result.findings) if result.findings else "Check completed."
            ),
            "execution_time_ms": result.execution_time,
            "timestamp": datetime.utcnow().isoformat(),
        }
        state.execution_history.append(history_item)
        state.logs.append(f"Post-execute hook finished for agent: {self.get_name()}")

    def cleanup(self, state: AgentState):
        """Cleanup hook run at the end of lifecycle, whether failed or successful."""
        pass

    async def execute(
        self, state: AgentState, retries: int = 3, backoff: float = 1.0
    ) -> AgentResult:
        """Executes the lifecycle: validate -> pre_execute -> process -> post_execute -> cleanup."""
        agent_name = self.get_name()
        logger.info(
            f"Agent '{agent_name}' execution started (Version: {self.get_version()})."
        )

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
                    metadata=filtered_data,
                )

                # AI Governance Interception Hook
                if self.db:
                    try:
                        from app.services.ai_governance_service import (
                            AIGovernanceService,
                        )
                        from app.services.explainability_service import (
                            ExplainabilityService,
                        )

                        prompt_content = (
                            data.get("prompt_content")
                            or f"Execute agent check for: {state.customer_id}"
                        )
                        response_content = data.get("response_content") or reason

                        input_tokens = int(
                            data.get("input_tokens") or len(prompt_content) // 4
                        )
                        output_tokens = int(
                            data.get("output_tokens") or len(response_content) // 4
                        )

                        model_name = data.get("model_name") or "gemini-2.0-flash"
                        template_name = (
                            data.get("prompt_template_name") or f"{agent_name}_prompt"
                        )

                        # Log execution in database
                        exec_log = await AIGovernanceService.log_execution(
                            db=self.db,
                            model_name=model_name,
                            template_name=template_name,
                            prompt_content=prompt_content,
                            response_content=response_content,
                            latency_ms=int(duration_ms),
                            input_tokens=input_tokens,
                            output_tokens=output_tokens,
                            customer_id=state.customer_id,
                            case_id=state.case_id,
                            investigation_id=state.investigation_id,
                            risk_score_id=getattr(state, "risk_score_id", None),
                        )

                        # Log explanation report
                        await ExplainabilityService.generate_explanation_report(
                            db=self.db,
                            execution_id=exec_log.id,
                            agent_name=agent_name,
                            overall_score=result.risk_score,
                            findings=result.findings,
                            rules_triggered=data.get("rules_triggered") or [],
                            matched_entities=data.get("matched_entities") or [],
                            missing_evidence=data.get("missing_evidence") or [],
                            alternative_outcomes=data.get("alternative_outcomes") or [],
                        )

                        # Attach governance metadata to agent result
                        result.metadata["ai_execution_id"] = str(exec_log.id)
                        result.metadata["model_version"] = self.get_version()
                        result.metadata["prompt_version"] = "1.0.0"
                        result.metadata["estimated_cost"] = exec_log.cost
                        result.metadata["tokens_used"] = exec_log.tokens_used
                    except Exception as ex:
                        logger.warning(
                            f"BaseAgent: AI Governance logging failed for '{agent_name}': {ex}"
                        )

                # Cache results and run post hooks
                state.agent_results[agent_name] = result.model_dump()
                self.post_execute(state, result)
                AgentMetricsCollector.record_run(
                    agent_name, result.execution_time, True, retries=attempt
                )

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
                    summary=(
                        ", ".join(result.findings)
                        if result.findings
                        else "Check completed successfully."
                    ),
                )
                return result

            except Exception as e:
                last_error = e
                wait_sec = backoff * (2**attempt)
                state.logs.append(
                    f"Agent '{agent_name}' attempt {attempt + 1} failed: {str(e)}"
                )

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
                    summary=f"Attempt {attempt + 1} failure: {str(e)}",
                )

                from app.agents.base.exceptions import (
                    AgentValidationError,
                    NonRetryableError,
                    ConfigurationError,
                )

                if isinstance(
                    e, (AgentValidationError, NonRetryableError, ConfigurationError)
                ):
                    logger.error(
                        f"Agent '{agent_name}' encountered non-retryable failure: {e}"
                    )
                    raise

                logger.warning(
                    f"Agent '{agent_name}' attempt {attempt + 1} failed: {e}. Retrying in {wait_sec}s..."
                )
                if attempt < retries - 1:
                    await asyncio.sleep(wait_sec)
            finally:
                self.cleanup(state)

        # Retries exhausted
        AgentMetricsCollector.record_run(agent_name, 0.0, False, retries=retries)
        raise AgentExecutionError(
            f"Agent {agent_name} retries exhausted. Error: {str(last_error)}"
        ) from last_error
