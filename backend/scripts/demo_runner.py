"""
AML Demo Runner
================
Interactive terminal demo for client demonstrations.
Presents a Compliance Officer–grade report after executing the full AML pipeline.

Usage:
    python backend/scripts/demo_runner.py

The operator selects a scenario from the numbered menu,
then the full five-agent workflow executes and prints a detailed report.
"""

import sys
import asyncio
import time
import textwrap
from pathlib import Path
from typing import Optional

# ── Ensure the backend package is importable when run from the repo root ──────
_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from app.agents.base.agent_state import AgentState
from app.agents.base.agent_result import AgentResult
from app.agents.base.exceptions import AgentValidationError, AgentExecutionError

from app.agents.kyc.agent import KycAgent
from app.agents.company.agent import CompanyAgent
from app.agents.pep.agent import PepAgent
from app.agents.sanctions.agent import SanctionsAgent
from app.agents.country.agent import CountryRiskAgent

from scenarios import ALL_SCENARIOS


# ─────────────────────────────────────────────────────────────────────────────
# ANSI colours
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
    MAGENTA = "\033[95m"
    BLUE    = "\033[94m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    RESET   = "\033[0m"
except ImportError:
    GREEN = YELLOW = RED = CYAN = MAGENTA = BLUE = BOLD = DIM = RESET = ""


# ─────────────────────────────────────────────────────────────────────────────
# Scenario menu definition  (ordered for demo UX)
# ─────────────────────────────────────────────────────────────────────────────
MENU = [
    ("individual_clean",        "Normal Individual Customer"),
    ("business_clean",          "Business Customer (All Clear)"),
    ("pep_match",               "Individual — PEP Match"),
    ("sanctions_match",         "Individual — Sanctions Match (Terrorist Financing)"),
    ("high_risk_country",       "Individual — High Risk Country (Russia)"),
    ("business_pep_director",   "Business — Director is a PEP"),
    ("business_sanctioned_ubo", "Business — UBO is on Sanctions List"),
]


# ─────────────────────────────────────────────────────────────────────────────
# Report width constant
# ─────────────────────────────────────────────────────────────────────────────
W = 72


# ─────────────────────────────────────────────────────────────────────────────
# Formatters
# ─────────────────────────────────────────────────────────────────────────────
def _line(char: str = "-") -> None:
    print(char * W)


def _double(char: str = "=") -> None:
    print(char * W)


def _kv(key: str, value: str, colour: str = "", indent: int = 2) -> None:
    pad = " " * indent
    print(f"{pad}{DIM}{key:<30}{RESET}  {colour}{value}{RESET}")


def _status_colour(s: str) -> str:
    su = s.upper()
    if su in {"COMPLETE", "CLEAR", "SKIPPED", "PASS", "LOW"}:
        return GREEN
    if su in {"INCOMPLETE", "WARNING", "POSSIBLE_MATCH", "MEDIUM"}:
        return YELLOW
    return RED


def _risk_badge(risk: str) -> str:
    ru = risk.upper()
    colours = {
        "LOW": GREEN, "CLEAR": GREEN,
        "MEDIUM": YELLOW, "WARNING": YELLOW,
        "HIGH": RED, "CRITICAL": RED, "PROHIBITED": RED + BOLD,
        "CONFIRMED_PEP": RED, "CONFIRMED_SANCTION": RED,
        "SUSPENDED": RED,
    }
    c = colours.get(ru, RESET)
    return f"{c}[ {ru} ]{RESET}"


def _wrap(text: str, width: int = W - 6, indent: int = 4) -> str:
    return textwrap.fill(text, width=width, initial_indent=" " * indent,
                         subsequent_indent=" " * indent)


def _banner() -> None:
    _double()
    print(f"{BOLD}{CYAN}{'AML / KYC COMPLIANCE DEMONSTRATION PLATFORM':^{W}}{RESET}")
    print(f"{DIM}{'Enterprise UK AML + KYC Agentic AI Platform  |  Compliance Report':^{W}}{RESET}")
    _double()


def _section(title: str) -> None:
    print()
    print(f"  {BOLD}{CYAN}{title}{RESET}")
    _line()


def _agent_header(name: str, icon: str) -> None:
    print(f"\n  {BOLD}{icon}  {name}{RESET}")
    _line("·")


# ─────────────────────────────────────────────────────────────────────────────
# State builder
# ─────────────────────────────────────────────────────────────────────────────
def build_state(scenario: dict) -> AgentState:
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
# Pipeline runner with per-agent progress output
# ─────────────────────────────────────────────────────────────────────────────
async def _run_with_progress(scenario: dict):
    """Run the five-agent pipeline, printing live status per agent."""
    state   = build_state(scenario)
    timings = {}

    pipeline = [
        ("1/5", "🔍", "KYC Agent",          KycAgent()),
        ("2/5", "🏢", "Company Agent",      CompanyAgent()),
        ("3/5", "🏛️", "PEP Agent",          PepAgent()),
        ("4/5", "⛔", "Sanctions Agent",    SanctionsAgent()),
        ("5/5", "🌍", "Country Risk Agent", CountryRiskAgent()),
    ]

    print()
    print(f"  {DIM}Running AML Pipeline …{RESET}")
    _line()

    for step, icon, label, agent in pipeline:
        print(f"  {DIM}[{step}]{RESET}  {icon}  {label:<25}", end="", flush=True)
        t0 = time.perf_counter()
        try:
            result = await agent.execute(state)
            ms = (time.perf_counter() - t0) * 1000
            timings[agent.get_name()] = ms
            tick = f"{GREEN}✓{RESET}" if result.success else f"{RED}✗{RESET}"
            print(f"{tick}  {DIM}{ms:.0f}ms{RESET}")
        except (AgentValidationError, AgentExecutionError) as exc:
            ms = (time.perf_counter() - t0) * 1000
            timings[agent.get_name()] = ms
            print(f"{RED}✗  ERROR{RESET}")
            raise exc

    return state, timings


# ─────────────────────────────────────────────────────────────────────────────
# Full compliance report printer
# ─────────────────────────────────────────────────────────────────────────────
def _print_compliance_report(scenario: dict, state: AgentState, timings: dict) -> None:
    meta     = state.shared_metadata
    customer = state.customer
    ctype    = str(customer.get("customer_type", "unknown")).upper()

    name_parts = []
    if customer.get("company_name"):
        name_parts = [customer["company_name"]]
    else:
        if customer.get("first_name"): name_parts.append(customer["first_name"])
        if customer.get("last_name"):  name_parts.append(customer["last_name"])
    full_name = " ".join(name_parts) or "N/A"

    total_ms = sum(timings.values())

    # ── Header ────────────────────────────────────────────────────────────────
    print()
    _double()
    print(f"{BOLD}{CYAN}  AML COMPLIANCE OFFICER REPORT{RESET}")
    print(f"  {DIM}Scenario: {scenario.get('label', 'N/A')}{RESET}")
    _double()

    # ── Case ──────────────────────────────────────────────────────────────────
    _section("CASE INFORMATION")
    _kv("Customer ID",      state.customer_id)
    _kv("Case ID",          state.case_id)
    _kv("Customer Name",    full_name)
    _kv("Customer Type",    ctype)
    _kv("Nationality",      customer.get("nationality", "N/A"))
    _kv("Country",          customer.get("country", customer.get("registered_country", "N/A")))
    desc = scenario.get("description", "")
    if desc:
        print()
        print(_wrap(f"ℹ  {desc}"))

    # ── KYC Agent ─────────────────────────────────────────────────────────────
    _agent_header("KYC AGENT — Know Your Customer", "🔍")
    kyc_status = meta.get("kyc_status", "N/A")
    kyc_score  = meta.get("kyc_score", 0.0)
    _kv("Status",         kyc_status,            _status_colour(kyc_status))
    _kv("Completeness Score", f"{kyc_score:.1f} / 100.0")
    _kv("Execution Time", f"{timings.get('kyc_agent', 0):.1f} ms")
    missing = meta.get("missing_fields", [])
    if missing:
        _kv("Missing Fields", ", ".join(missing), YELLOW)
    else:
        _kv("Missing Fields", "None", GREEN)
    _kv("Overall Risk Tier", state.risk_tier.upper(), _status_colour(state.risk_tier))

    # ── Company Agent ─────────────────────────────────────────────────────────
    _agent_header("COMPANY AGENT — Corporate Verification", "🏢")
    comp_result   = state.agent_results.get("company_agent", {})
    comp_meta     = comp_result.get("metadata", {})
    routing       = comp_meta.get("routing", {})
    comp_status   = routing.get("company_agent_status") or "N/A"
    comp_executed = routing.get("company_agent_executed", False)
    comp_next     = routing.get("next_agent", meta.get("next_agent", "N/A"))
    _kv("Status",         str(comp_status),      _status_colour(str(comp_status)))
    _kv("Verification Run", "YES" if comp_executed else "NO (Individual customer)")
    if comp_executed:
        _kv("Company Score",  f"{comp_result.get('risk_score', 0.0):.1f} / 100.0")
    _kv("Routing To",     comp_next)
    _kv("Execution Time", f"{timings.get('company_agent', 0):.1f} ms")

    # ── PEP Agent ─────────────────────────────────────────────────────────────
    _agent_header("PEP AGENT — Politically Exposed Persons", "🏛️")
    pep_status = meta.get("pep_status", "N/A")
    pep_score  = meta.get("pep_score", 0.0)
    pep_risk   = meta.get("pep_risk", "N/A")
    edd        = meta.get("edd_required", False)
    _kv("Status",         pep_status,            _status_colour(pep_status))
    _kv("PEP Score",      f"{pep_score:.1f} / 100.0")
    _kv("Risk Level",     str(pep_risk).upper(), _status_colour(str(pep_risk)))
    _kv("EDD Required",   "YES" if edd else "NO", RED if edd else GREEN)
    _kv("Manual Review",  "YES" if meta.get("manual_review_required") else "NO")
    _kv("Execution Time", f"{timings.get('pep_agent', 0):.1f} ms")

    matched_pep = meta.get("matched_subjects", [])
    if matched_pep and pep_status != "CLEAR":
        print(f"\n    {BOLD}PEP Match Details:{RESET}")
        for m in matched_pep[:3]:
            print(f"      {RED}• {m.get('full_name', '?')}"
                  f"  [{m.get('match_confidence', '?')}]{RESET}")
            if m.get("pep_category"):
                print(f"        Category: {m['pep_category']}")
            if m.get("position"):
                print(f"        Position: {m['position']}")

    pep_recs = meta.get("pep_recommendations", [])
    if pep_recs:
        print(f"\n    {BOLD}Recommendations:{RESET}")
        for r in pep_recs[:4]:
            print(f"      {YELLOW}→ {r}{RESET}")

    # ── Sanctions Agent ───────────────────────────────────────────────────────
    _agent_header("SANCTIONS AGENT — Watchlist Screening", "⛔")
    san_status = meta.get("sanctions_status", "N/A")
    san_score  = meta.get("sanctions_score", 0.0)
    san_risk   = meta.get("sanctions_risk", "N/A")
    _kv("Status",         san_status,             _status_colour(san_status))
    _kv("Sanctions Score",f"{san_score:.1f} / 100.0")
    _kv("Risk Level",     str(san_risk).upper(),  _status_colour(str(san_risk)))
    _kv("Execution Time", f"{timings.get('sanctions_agent', 0):.1f} ms")

    san_audit = meta.get("sanctions_audit", {})
    lists_checked = san_audit.get("sanctions_lists_checked", [])
    if lists_checked:
        _kv("Lists Checked", ", ".join(lists_checked[:4]))

    matched_san = meta.get("matched_subjects", [])
    if matched_san and san_status != "CLEAR":
        print(f"\n    {BOLD}Sanctions Match Details:{RESET}")
        for m in matched_san[:3]:
            print(f"      {RED}• {m.get('full_name', '?')}"
                  f"  [{m.get('sanction_category', '?')}]"
                  f"  List: {m.get('sanction_list', '?')}{RESET}")

    san_recs = meta.get("sanctions_recommendations", [])
    if san_recs:
        print(f"\n    {BOLD}Recommendations:{RESET}")
        for r in san_recs[:4]:
            print(f"      {RED}→ {r}{RESET}")

    # ── Country Risk Agent ────────────────────────────────────────────────────
    _agent_header("COUNTRY RISK AGENT — Jurisdictional Assessment", "🌍")
    cty_status   = meta.get("country_status", "N/A")
    cty_score    = meta.get("country_score", 0.0)
    cty_risk     = meta.get("country_risk", "N/A")
    high_risk    = meta.get("high_risk_countries", [])
    prohibited   = meta.get("prohibited_countries", [])
    evaluated    = meta.get("evaluated_countries", [])
    _kv("Status",         cty_status,             _status_colour(cty_status))
    _kv("Country Score",  f"{cty_score:.1f} / 100.0")
    _kv("Risk Level",     str(cty_risk).upper(),  _status_colour(str(cty_risk)))
    _kv("Countries Evaluated", str(len(evaluated)))
    _kv("Execution Time", f"{timings.get('country_risk_agent', 0):.1f} ms")

    if high_risk:
        _kv("High Risk Countries", ", ".join(high_risk), YELLOW)
    if prohibited:
        _kv("Prohibited Countries", ", ".join(prohibited), RED)

    cty_recs = meta.get("country_recommendations", [])
    if cty_recs:
        print(f"\n    {BOLD}Recommendations:{RESET}")
        for r in cty_recs[:3]:
            print(f"      {YELLOW}→ {r}{RESET}")

    # ── Overall Assessment ────────────────────────────────────────────────────
    _section("OVERALL COMPLIANCE ASSESSMENT")

    overall_score = state.overall_score
    risk_tier     = state.risk_tier.upper()

    print(f"  {BOLD}Risk Score:    {_risk_badge(risk_tier)}  {overall_score:.1f} / 100.0{RESET}")
    print()

    breakdown = state.risk_breakdown
    for agent_key, score in breakdown.items():
        bar_len = int(score / 5)
        bar_filled = "█" * bar_len
        bar_empty  = "░" * (20 - bar_len)
        colour = GREEN if score >= 70 else (YELLOW if score >= 40 else RED)
        print(f"  {DIM}{agent_key:<12}{RESET}  {colour}{bar_filled}{bar_empty}{RESET}  {colour}{score:.0f}{RESET}")

    # ── Pipeline Metrics ──────────────────────────────────────────────────────
    _section("PIPELINE METRICS")
    _kv("Total Agents Run",   str(len(timings)))
    _kv("Total Execution",    f"{total_ms:.1f} ms")
    _kv("Agents Completed",   str(len(state.completed_agents)))
    _kv("Next Agent",         str(meta.get("next_agent", "none")))
    _kv("Audit Entries",      str(len(state.execution_history)))

    # ── Final Verdict ─────────────────────────────────────────────────────────
    print()
    _double()
    # Determine summary verdict
    is_sanctioned  = meta.get("sanctions_status", "") == "CONFIRMED_SANCTION"
    is_prohibited  = meta.get("country_status", "") == "SUSPENDED"
    is_pep         = meta.get("pep_status", "") == "CONFIRMED_PEP"
    kyc_failed     = meta.get("kyc_status", "") == "FAILED"

    if is_sanctioned or is_prohibited:
        verdict = f"{RED}{BOLD}⛔ REJECTED — IMMEDIATE ESCALATION REQUIRED{RESET}"
    elif is_pep or kyc_failed:
        verdict = f"{YELLOW}{BOLD}⚠  ENHANCED DUE DILIGENCE REQUIRED — MANUAL REVIEW{RESET}"
    elif risk_tier in {"HIGH", "CRITICAL"}:
        verdict = f"{YELLOW}{BOLD}⚠  HIGH RISK — COMPLIANCE OFFICER REVIEW REQUIRED{RESET}"
    else:
        verdict = f"{GREEN}{BOLD}✓  APPROVED — STANDARD MONITORING{RESET}"

    print(f"\n  {verdict}")
    print()
    _double()
    print()


# ─────────────────────────────────────────────────────────────────────────────
# Interactive menu
# ─────────────────────────────────────────────────────────────────────────────
def _show_menu() -> None:
    print()
    _double()
    print(f"{BOLD}{CYAN}  SELECT AML DEMO SCENARIO{RESET}")
    _line()
    for i, (_, label) in enumerate(MENU, start=1):
        print(f"  {BOLD}{CYAN}{i}.{RESET}  {label}")
    _line()
    print(f"  {DIM}Enter a number (1–{len(MENU)}) or 'q' to quit{RESET}")
    print()


def _get_choice() -> Optional[int]:
    while True:
        raw = input(f"  {BOLD}Your choice: {RESET}").strip().lower()
        if raw in ("q", "quit", "exit"):
            return None
        if raw.isdigit():
            choice = int(raw)
            if 1 <= choice <= len(MENU):
                return choice
        print(f"  {YELLOW}Please enter a number between 1 and {len(MENU)}.{RESET}")


# ─────────────────────────────────────────────────────────────────────────────
# Main loop
# ─────────────────────────────────────────────────────────────────────────────
async def _demo_loop() -> None:
    _banner()
    print(f"\n  {DIM}This demo executes the complete AML pipeline across five agents{RESET}")
    print(f"  {DIM}and generates a Compliance Officer–grade report.{RESET}")

    while True:
        _show_menu()
        choice = _get_choice()
        if choice is None:
            print(f"\n  {CYAN}Exiting demo. Goodbye.{RESET}\n")
            break

        scenario_key, label = MENU[choice - 1]
        scenario = ALL_SCENARIOS[scenario_key]

        print(f"\n  {GREEN}→ Loading: {BOLD}{label}{RESET}")

        try:
            state, timings = await _run_with_progress(scenario)
            _print_compliance_report(scenario, state, timings)
        except (AgentValidationError, AgentExecutionError) as exc:
            print(f"\n  {RED}{BOLD}PIPELINE ERROR{RESET}")
            print(f"  {RED}{exc}{RESET}\n")

        # Pause before showing menu again
        input(f"  {DIM}Press ENTER to return to the menu …{RESET}")


def main() -> None:
    try:
        asyncio.run(_demo_loop())
    except KeyboardInterrupt:
        print(f"\n\n  {CYAN}Demo interrupted. Goodbye.{RESET}\n")


if __name__ == "__main__":
    main()
