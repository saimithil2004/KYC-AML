"""
Orchestrator Agent
===================
Production-grade LangGraph orchestration for the full AML/KYC workflow.

Workflow:
  Customer Data Load
    ↓
  KYC Agent
    ↓
  Document Verification Agent
    ↓
  [PARALLEL] PEP + Sanctions + Country Risk + FATF
    ↓
  [CONDITIONAL] if customer_type == corporate:
      Company Agent → Director Verification → UBO Verification
    else:
      Skip corporate workflow
    ↓
  Transaction Agent
    ↓
  Account Behavior Agent
    ↓
  Regulation Agent
    ↓
  Risk Scoring Agent
    ↓
  Investigation Agent
    ↓
  Decision Agent
    ↓
  Monitoring Agent
    ↓
  Return Final AgentState

Key features:
  - Agents loaded dynamically from AgentRegistry (never hardcoded)
  - Parallel branches via asyncio.gather
  - Conditional routing based on customer_type
  - Retry at agent level (BaseAgent.execute handles retries)
  - Full execution timing and logging per node
  - Error handling — agent failure is isolated (logged, not propagated to abort graph)
  - AgentState updated at each step
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
from uuid import UUID

from app.agents.base.agent_state import AgentState
from app.agents.base.agent_context import AgentContext
from app.agents.base.registry import AgentRegistry
from app.agents.base.exceptions import AgentExecutionError

logger = logging.getLogger(__name__)

# Agent names in the workflow — never hardcoded in logic, only here as constants
AGENT_KYC                  = "kyc_agent"
AGENT_DOCUMENT_VERIFICATION = "document_verification_agent"
AGENT_PEP                  = "pep_agent"
AGENT_SANCTIONS            = "sanctions_agent"
AGENT_COUNTRY_RISK         = "country_risk_agent"
AGENT_FATF                 = "fatf_agent"
AGENT_COMPANY              = "company_agent"
AGENT_DIRECTOR             = "director_verification_agent"
AGENT_UBO                  = "ubo_verification_agent"
AGENT_TRANSACTION          = "transaction_agent"
AGENT_ACCOUNT_BEHAVIOR     = "account_behavior_agent"
AGENT_REGULATION           = "regulation_agent"
AGENT_RISK_SCORING         = "risk_scoring_agent"
AGENT_INVESTIGATION        = "investigation_agent"
AGENT_DECISION             = "decision_agent"
AGENT_MONITORING           = "monitoring_agent"

# Corporate-only agent names
CORPORATE_AGENTS = {AGENT_COMPANY, AGENT_DIRECTOR, AGENT_UBO}


class OrchestratorAgent:
    """
    Orchestrates the full AML/KYC workflow using the AgentRegistry.
    Not registered in AgentRegistry — it IS the orchestrator.
    """

    def __init__(self, db_session=None, context: Optional[AgentContext] = None):
        self.db       = db_session
        self.context  = context or AgentContext(db_session=db_session)
        self.registry = AgentRegistry.get_registry()

    async def run(self, state: AgentState) -> AgentState:
        """
        Executes the full compliance workflow and returns the final AgentState.
        Individual agent failures are caught, logged, and the workflow continues.
        """
        workflow_start = time.perf_counter()
        state.logs.append(
            f"[OrchestratorAgent] Workflow started at {datetime.utcnow().isoformat()}. "
            f"Customer={state.customer_id}, Case={state.case_id}"
        )

        # ── Step 1: KYC Agent ─────────────────────────────────────────────────
        state = await self._run_agent(AGENT_KYC, state, step=1, total=12)

        # ── Step 2: Document Verification ────────────────────────────────────
        state = await self._run_agent(AGENT_DOCUMENT_VERIFICATION, state, step=2, total=12)

        # ── Step 3: Parallel — PEP + Sanctions + Country Risk + FATF ─────────
        state = await self._run_parallel(
            agent_names=[AGENT_PEP, AGENT_SANCTIONS, AGENT_COUNTRY_RISK, AGENT_FATF],
            state=state,
            step=3,
            total=12,
        )

        # ── Step 4: Corporate routing ─────────────────────────────────────────
        customer_type = str((state.customer or {}).get("customer_type") or "").strip().lower()
        is_corporate  = customer_type in ("corporate", "business", "company")

        if is_corporate:
            state.logs.append(
                "[OrchestratorAgent] Corporate customer detected — running company/director/UBO workflow."
            )
            # Run company first (sequential), then director + UBO in parallel
            state = await self._run_agent(AGENT_COMPANY, state, step=4, total=12)
            state = await self._run_parallel(
                agent_names=[AGENT_DIRECTOR, AGENT_UBO],
                state=state,
                step=4,
                total=12,
                label="Director + UBO",
            )
        else:
            state.logs.append(
                "[OrchestratorAgent] Individual customer — skipping company/director/UBO workflow."
            )

        # ── Step 5: Transaction Agent ─────────────────────────────────────────
        state = await self._run_agent(AGENT_TRANSACTION, state, step=5, total=12)

        # ── Step 6: Account Behavior Agent ───────────────────────────────────
        state = await self._run_agent(AGENT_ACCOUNT_BEHAVIOR, state, step=6, total=12)

        # ── Step 7: Regulation Agent ──────────────────────────────────────────
        state = await self._run_agent(AGENT_REGULATION, state, step=7, total=12)

        # ── Step 8: Risk Scoring Agent ────────────────────────────────────────
        state = await self._run_agent(AGENT_RISK_SCORING, state, step=8, total=12)

        # ── Step 9: Investigation Agent ───────────────────────────────────────
        state = await self._run_agent(AGENT_INVESTIGATION, state, step=9, total=12)

        # ── Step 10: Decision Agent ───────────────────────────────────────────
        state = await self._run_agent(AGENT_DECISION, state, step=10, total=12)

        # ── Step 11: Monitoring Agent ─────────────────────────────────────────
        state = await self._run_agent(AGENT_MONITORING, state, step=11, total=12)

        # ── Final Summary ─────────────────────────────────────────────────────
        total_duration_ms = round((time.perf_counter() - workflow_start) * 1000, 2)
        completed_count   = len(state.completed_agents)

        state.shared_metadata["orchestrator_total_duration_ms"] = total_duration_ms
        state.shared_metadata["orchestrator_completed_agents"]  = state.completed_agents
        state.logs.append(
            f"[OrchestratorAgent] Workflow completed. "
            f"Agents={completed_count}, Duration={total_duration_ms}ms. "
            f"Score={state.overall_score:.1f}, Decision={state.final_decision}."
        )

        return state

    # ── Private Helpers ───────────────────────────────────────────────────────
    async def _run_agent(
        self,
        agent_name: str,
        state: AgentState,
        step: int,
        total: int,
        label: Optional[str] = None,
    ) -> AgentState:
        """Runs a single agent, isolating failures from the rest of the workflow."""
        display = label or agent_name
        agent_start = time.perf_counter()
        state.logs.append(f"[OrchestratorAgent] Step {step}/{total}: Running {display}...")

        try:
            # Check agent is registered
            registered = self.registry.list_agents()
            if agent_name not in registered:
                state.logs.append(
                    f"[OrchestratorAgent] WARN: Agent '{agent_name}' not registered. "
                    "Skipping (install agent or check import)."
                )
                return state

            agent = self.registry.get_agent(agent_name, db_session=self.db)
            result = await agent.execute(state)

            duration_ms = round((time.perf_counter() - agent_start) * 1000, 2)
            state.logs.append(
                f"[OrchestratorAgent] {display} DONE in {duration_ms}ms. "
                f"Score={result.risk_score:.1f}, Level={result.risk_level}."
            )
        except Exception as exc:
            duration_ms = round((time.perf_counter() - agent_start) * 1000, 2)
            logger.error(f"OrchestratorAgent: Agent '{agent_name}' failed: {exc}")
            state.logs.append(
                f"[OrchestratorAgent] WARN: {display} FAILED after {duration_ms}ms: {exc}. Continuing..."
            )

        return state

    async def _run_parallel(
        self,
        agent_names: List[str],
        state: AgentState,
        step: int,
        total: int,
        label: Optional[str] = None,
    ) -> AgentState:
        """
        Runs multiple agents in parallel using asyncio.gather.
        Each agent receives a COPY of the current state to avoid race conditions.
        Outputs are merged back into the main state after all complete.
        """
        display = label or f"[{', '.join(agent_names)}]"
        parallel_start = time.perf_counter()
        state.logs.append(
            f"[OrchestratorAgent] Step {step}/{total}: Parallel execution — {display}..."
        )

        registered = self.registry.list_agents()

        async def _run_one(name: str) -> AgentState:
            """Runs one agent on an isolated state copy."""
            if name not in registered:
                logger.warning(f"OrchestratorAgent: '{name}' not registered, skipping in parallel run.")
                # Return a minimal copy that won't override anything
                return state.model_copy(deep=True)
            try:
                # Each parallel branch works on its own copy
                state_copy = state.model_copy(deep=True)
                agent = self.registry.get_agent(name, db_session=self.db)
                await agent.execute(state_copy)
                return state_copy
            except Exception as exc:
                logger.error(f"OrchestratorAgent: Parallel agent '{name}' failed: {exc}")
                state.logs.append(
                    f"[OrchestratorAgent] WARN: Parallel agent '{name}' FAILED: {exc}."
                )
                return state.model_copy(deep=True)

        # Run all in parallel
        results: List[AgentState] = await asyncio.gather(*[_run_one(n) for n in agent_names])

        # ── Merge results back ────────────────────────────────────────────────
        for result_state in results:
            # Merge shared_metadata (parallel results accumulate)
            for k, v in result_state.shared_metadata.items():
                if k not in state.shared_metadata or v is not None:
                    state.shared_metadata[k] = v
            # Merge risk_breakdown
            for signal, score in result_state.risk_breakdown.items():
                state.risk_breakdown[signal] = score
            # Merge completed agents
            for agent_nm in result_state.completed_agents:
                if agent_nm not in state.completed_agents:
                    state.completed_agents.append(agent_nm)
            # Merge agent results
            for agent_nm, result_data in result_state.agent_results.items():
                if agent_nm not in state.agent_results:
                    state.agent_results[agent_nm] = result_data
            # Merge logs
            for log_entry in result_state.logs:
                if log_entry not in state.logs:
                    state.logs.append(log_entry)
            # Merge execution history
            for hist in result_state.execution_history:
                if hist not in state.execution_history:
                    state.execution_history.append(hist)

        duration_ms = round((time.perf_counter() - parallel_start) * 1000, 2)
        state.logs.append(
            f"[OrchestratorAgent] Parallel {display} completed in {duration_ms}ms."
        )

        return state
