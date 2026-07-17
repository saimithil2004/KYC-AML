"""
AML Workflow Runner
====================
Temporary sequential orchestrator for the five completed AML agents.

    python backend/scripts/run_aml_workflow.py [scenario_name]

Available scenarios:
    individual_clean       — Normal individual, all clear
    business_clean         — Normal business, all clear
    pep_match              — PEP match on customer
    sanctions_match        — Sanctions match on customer
    high_risk_country      — High risk jurisdiction
    business_pep_director  — Business with PEP director
    business_sanctioned_ubo — Business with sanctioned UBO

If no argument is given the script defaults to `individual_clean`.

Architecture note
-----------------
This runner acts as a temporary stand-in for the LangGraph Orchestrator.
When LangGraph is implemented:
  - This sequential loop is replaced by a conditional graph.
  - Each node in the graph corresponds to one agent.
  - Transitions read `state.shared_metadata["next_agent"]` — which
    every agent already writes today — so zero agent changes are needed.
"""

import sys
import asyncio
import time
import logging
from pathlib import Path
from typing import Optional

# ── Ensure the backend package is importable when run from the repo root ──────
_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.agents.base.agent_state import AgentState
from app.agents.base.agent_result import AgentResult
from app.agents.base.exceptions import AgentValidationError, AgentExecutionError

from app.agents.kyc.agent import KycAgent
from app.agents.company.agent import CompanyAgent
from app.agents.pep.agent import PepAgent
from app.agents.sanctions.agent import SanctionsAgent
from app.agents.country.agent import CountryRiskAgent
from app.agents.transaction.agent import TransactionAgent

from scripts.scenarios import ALL_SCENARIOS

# ─────────────────────────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("aml.workflow_runner")


# ─────────────────────────────────────────────────────────────────────────────
# Terminal colour helpers (ANSI — gracefully degrade on Windows if needed)
# ─────────────────────────────────────────────────────────────────────────────
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

try:
    import colorama
    colorama.init(autoreset=True)
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    RED     = "\033[91m"
    CYAN    = "\033[96m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    RESET   = "\033[0m"
except ImportError:
    GREEN = YELLOW = RED = CYAN = BOLD = DIM = RESET = ""


# ─────────────────────────────────────────────────────────────────────────────
# Print helpers
# ─────────────────────────────────────────────────────────────────────────────
W = 60   # report width

def _divider(char: str = "-") -> None:
    print(char * W)

def _header(title: str) -> None:
    print()
    print("=" * W)
    print(f"{BOLD}{CYAN}  {title}{RESET}")
    print("=" * W)

def _section(title: str) -> None:
    print(f"\n{BOLD}  {title}{RESET}")
    _divider()

def _kv(key: str, value: str, colour: str = "") -> None:
    print(f"  {DIM}{key:<22}{RESET}  {colour}{value}{RESET}")

def _status_colour(status: str) -> str:
    status_upper = status.upper()
    if status_upper in {"COMPLETE", "CLEAR", "PASS", "SKIPPED"}:
        return GREEN
    if status_upper in {"INCOMPLETE", "WARNING", "POSSIBLE_MATCH"}:
        return YELLOW
    if status_upper in {"FAILED", "CONFIRMED_SANCTION", "CONFIRMED_PEP",
                        "SUSPENDED", "HIGH", "CRITICAL"}:
        return RED
    return RESET


# ─────────────────────────────────────────────────────────────────────────────
# State builder
# ─────────────────────────────────────────────────────────────────────────────
def build_state(scenario: dict) -> AgentState:
    """Construct an AgentState from a scenario dict."""
    return AgentState(
        customer_id=scenario["customer_id"],
        case_id=scenario["case_id"],
        customer=scenario.get("customer", {}),
        kyc_profile=scenario.get("kyc_profile"),
        uploaded_documents=scenario.get("uploaded_documents", []),
        directors=scenario.get("directors", []),
        ubos=scenario.get("ubos", []),
        companies=scenario.get("companies", []),
        transactions=scenario.get("transactions", []),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Workflow Metrics
# ─────────────────────────────────────────────────────────────────────────────
class WorkflowMetrics:
    def __init__(self) -> None:
        self.start_ms: float = time.perf_counter() * 1000
        self.agent_times: dict[str, float] = {}
        self.agents_executed: int = 0
        self.agents_skipped: int = 0
        self.workflow_success: bool = False
        self.error: Optional[str] = None

    @property
    def total_ms(self) -> float:
        return (time.perf_counter() * 1000) - self.start_ms

    def record_agent(self, name: str, duration_ms: float, skipped: bool = False) -> None:
        self.agent_times[name] = duration_ms
        if skipped:
            self.agents_skipped += 1
        else:
            self.agents_executed += 1


# ─────────────────────────────────────────────────────────────────────────────
# Core workflow execution
# ─────────────────────────────────────────────────────────────────────────────
async def run_workflow(scenario: dict) -> tuple[AgentState, WorkflowMetrics]:
    """
    Execute the complete AML pipeline for the given scenario.

    Returns (final_state, metrics) on success.
    Raises on unrecoverable agent failure (after logging).
    """
    metrics = WorkflowMetrics()
    state   = build_state(scenario)

    logger.info("Workflow START  — customer_id=%s  case_id=%s",
                state.customer_id, state.case_id)

    # ── Agent pipeline definition ─────────────────────────────────────────────
    # CompanyAgent is listed here but conditionally skipped based on customer type.
    pipeline = [
        ("KYC Agent",          KycAgent()),
        ("Company Agent",      CompanyAgent()),
        ("PEP Agent",          PepAgent()),
        ("Sanctions Agent",    SanctionsAgent()),
        ("Country Risk Agent", CountryRiskAgent()),
        ("Transaction Agent",  TransactionAgent()),
    ]

    for display_name, agent in pipeline:
        agent_name = agent.get_name()

        # ── Conditional skip: Company Agent for individual customers ──────────
        if agent_name == "company_agent":
            customer_type = str(state.customer.get("customer_type", "")).strip().lower()
            if customer_type == "individual":
                logger.info("Agent SKIP  — %s  (Individual customer)", agent_name)
                metrics.record_agent(agent_name, 0.0, skipped=True)
                # Write skip status so assertions can read it
                state.shared_metadata["company_agent_status"] = "SKIPPED"
                state.shared_metadata["company_skip_reason"]  = "Individual Customer"
                continue   # Company Agent still runs (it self-skips), but we record metrics here

        logger.info("Agent START — %s", agent_name)
        t0 = time.perf_counter()

        result: AgentResult = await agent.execute(state)

        duration_ms = (time.perf_counter() - t0) * 1000
        metrics.record_agent(agent_name, duration_ms)
        logger.info("Agent FINISH — %s  status=%s  score=%.1f  time=%.1fms",
                    agent_name, result.status, result.risk_score, duration_ms)

        if not result.success:
            metrics.error = f"{display_name} returned failure status."
            metrics.workflow_success = False
            logger.error("Workflow ABORT — %s failed.", agent_name)
            raise AgentExecutionError(metrics.error)

    metrics.workflow_success = True
    logger.info("Workflow FINISH — total=%.1fms  executed=%d  skipped=%d",
                metrics.total_ms, metrics.agents_executed, metrics.agents_skipped)
    return state, metrics


# ─────────────────────────────────────────────────────────────────────────────
# Report printer
# ─────────────────────────────────────────────────────────────────────────────
def print_report(scenario: dict, state: AgentState, metrics: WorkflowMetrics) -> None:
    meta = state.shared_metadata
    customer = state.customer
    customer_type = str(customer.get("customer_type", "unknown")).upper()

    name_parts = []
    if customer.get("first_name"):
        name_parts.append(customer["first_name"])
    if customer.get("last_name"):
        name_parts.append(customer["last_name"])
    if customer.get("company_name"):
        name_parts = [customer["company_name"]]
    full_name = " ".join(name_parts) or "Unknown"

    _header("AML COMPLIANCE WORKFLOW REPORT")

    # ── Case info ─────────────────────────────────────────────────────────────
    _section("CASE INFORMATION")
    _kv("Customer ID",     state.customer_id)
    _kv("Case ID",         state.case_id)
    _kv("Customer Name",   full_name)
    _kv("Customer Type",   customer_type)
    _kv("Scenario",        scenario.get("label", "N/A"))

    # ── KYC Agent ─────────────────────────────────────────────────────────────
    _section("KYC AGENT")
    kyc_status = meta.get("kyc_status", "N/A")
    kyc_score  = meta.get("kyc_score", 0.0)
    _kv("Status",  kyc_status,         _status_colour(kyc_status))
    _kv("Score",   f"{kyc_score:.1f}",  "")
    _kv("Time",    f"{metrics.agent_times.get('kyc_agent', 0):.1f} ms")
    missing = meta.get("missing_fields", [])
    if missing:
        _kv("Missing Fields", ", ".join(missing), YELLOW)

    # ── Company Agent ─────────────────────────────────────────────────────────
    _section("COMPANY AGENT")
    company_result = state.agent_results.get("company_agent", {})
    company_meta   = company_result.get("metadata", {})
    routing        = company_meta.get("routing", {})
    comp_status    = routing.get("company_agent_status") or meta.get("company_agent_status", "N/A")
    comp_score     = company_result.get("risk_score", 0.0)
    comp_time      = metrics.agent_times.get("company_agent", 0)
    _kv("Status",  str(comp_status),   _status_colour(str(comp_status)))
    if comp_status not in ("SKIPPED", "N/A"):
        _kv("Score", f"{comp_score:.1f}")
    _kv("Time",    f"{comp_time:.1f} ms")

    # ── PEP Agent ─────────────────────────────────────────────────────────────
    _section("PEP AGENT")
    pep_status = meta.get("pep_status", "N/A")
    pep_score  = meta.get("pep_score", 0.0)
    pep_risk   = meta.get("pep_risk", "N/A")
    _kv("Status",     pep_status,           _status_colour(pep_status))
    _kv("Score",      f"{pep_score:.1f}")
    _kv("Risk Level", str(pep_risk).upper())
    _kv("EDD Required", str(meta.get("edd_required", False)))
    _kv("Time",       f"{metrics.agent_times.get('pep_agent', 0):.1f} ms")
    matched = meta.get("matched_subjects", [])
    if matched:
        for m in matched:
            print(f"    {RED}⚠ Match: {m.get('full_name', '?')} — {m.get('match_confidence', '?')}{RESET}")

    # ── Sanctions Agent ───────────────────────────────────────────────────────
    _section("SANCTIONS AGENT")
    san_status = meta.get("sanctions_status", "N/A")
    san_score  = meta.get("sanctions_score", 0.0)
    san_risk   = meta.get("sanctions_risk", "N/A")
    _kv("Status",     san_status,          _status_colour(san_status))
    _kv("Score",      f"{san_score:.1f}")
    _kv("Risk Level", str(san_risk).upper())
    _kv("Time",       f"{metrics.agent_times.get('sanctions_agent', 0):.1f} ms")
    san_matches = meta.get("matched_subjects", [])
    for m in san_matches:
        print(f"    {RED}⚠ Sanctioned: {m.get('full_name', '?')} — {m.get('sanction_list', '?')}{RESET}")

    # ── Country Risk Agent ────────────────────────────────────────────────────
    _section("COUNTRY RISK AGENT")
    cty_status = meta.get("country_status", "N/A")
    cty_score  = meta.get("country_score", 0.0)
    cty_risk   = meta.get("country_risk", "N/A")
    _kv("Status",     cty_status,          _status_colour(cty_status))
    _kv("Score",      f"{cty_score:.1f}")
    _kv("Risk Level", str(cty_risk).upper())
    _kv("Time",       f"{metrics.agent_times.get('country_risk_agent', 0):.1f} ms")
    high_risk = meta.get("high_risk_countries", [])
    prohibited = meta.get("prohibited_countries", [])
    if high_risk:
        _kv("High Risk Countries", ", ".join(high_risk), YELLOW)
    if prohibited:
        _kv("Prohibited Countries", ", ".join(prohibited), RED)

    # ── Transaction Agent ─────────────────────────────────────────────────────
    _section("TRANSACTION AGENT")
    tx_status = meta.get("transaction_status", "N/A")
    tx_score  = meta.get("transaction_score", 0.0)
    tx_risk   = meta.get("transaction_risk", "N/A")
    _kv("Status",     tx_status,           _status_colour(tx_status))
    _kv("Score",      f"{tx_score:.1f}")
    _kv("Risk Level", str(tx_risk).upper())
    _kv("Time",       f"{metrics.agent_times.get('transaction_agent', 0):.1f} ms")
    tx_alerts = meta.get("transaction_alerts", [])
    if tx_alerts:
        _kv("Triggered Alerts", ", ".join(tx_alerts), YELLOW)

    # ── Summary ───────────────────────────────────────────────────────────────
    _section("WORKFLOW SUMMARY")
    _kv("Agents Executed",  str(metrics.agents_executed))
    _kv("Agents Skipped",   str(metrics.agents_skipped))
    overall_score = min(state.risk_breakdown.values()) if state.risk_breakdown else state.overall_score
    
    max_severity_val = 1
    for val in state.risk_breakdown.values():
        if val < 25:
            tier_val = 4      # CRITICAL
        elif val < 50:
            tier_val = 3      # HIGH
        elif val < 80:
            tier_val = 2      # MEDIUM
        else:
            tier_val = 1      # LOW
        max_severity_val = max(max_severity_val, tier_val)
        
    reverse_map = {1: "low", 2: "medium", 3: "high", 4: "critical"}
    risk_tier = reverse_map[max_severity_val].upper()

    _kv("Overall Score",    f"{overall_score:.1f}")
    _kv("Risk Tier",        risk_tier)
    _kv("Total Time",       f"{metrics.total_ms:.1f} ms")

    workflow_colour = GREEN if metrics.workflow_success else RED
    workflow_label  = "✓ WORKFLOW COMPLETE" if metrics.workflow_success else "✗ WORKFLOW FAILED"
    print()
    print(f"  {workflow_colour}{BOLD}{workflow_label}{RESET}")

    # ── Routing ───────────────────────────────────────────────────────────────
    next_agent = meta.get("next_agent", "none")
    print(f"  {DIM}Next agent (LangGraph): {next_agent}{RESET}")
    print()
    print("═" * W)
    print()


# ─────────────────────────────────────────────────────────────────────────────
# Entrypoint
# ─────────────────────────────────────────────────────────────────────────────
async def main() -> None:
    scenario_name = (sys.argv[1] if len(sys.argv) > 1 else "individual_clean").strip().lower()

    if scenario_name not in ALL_SCENARIOS:
        print(f"\n{RED}Unknown scenario: '{scenario_name}'{RESET}")
        print(f"Available: {', '.join(ALL_SCENARIOS)}\n")
        sys.exit(1)

    scenario = ALL_SCENARIOS[scenario_name]
    print(f"\n{CYAN}Loading scenario: {BOLD}{scenario['label']}{RESET}")

    try:
        state, metrics = await run_workflow(scenario)
        print_report(scenario, state, metrics)
    except (AgentValidationError, AgentExecutionError) as exc:
        print(f"\n{RED}{BOLD}WORKFLOW FAILED{RESET}")
        print(f"  {RED}Error: {exc}{RESET}\n")
        sys.exit(2)


if __name__ == "__main__":
    asyncio.run(main())
