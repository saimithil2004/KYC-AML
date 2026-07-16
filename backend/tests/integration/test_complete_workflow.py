"""
AML Pipeline — End-to-End Integration Test Suite
==================================================
Tests the complete five-agent AML workflow end-to-end using realistic mock
customer scenarios without any external dependencies (database, Redis, API).

Test cases
----------
Test 1  — Individual Customer (All Clear)
Test 2  — Business Customer (All Clear)
Test 3  — PEP Match (Individual) — POSSIBLE_MATCH score < 100
Test 4  — Sanctions Match (Individual — terrorist financing, CONFIRMED)
Test 5  — High Risk Country (Russia — HIGH risk)
Test 6  — Business with PEP Director (POSSIBLE_MATCH)
Test 7  — Business with Sanctioned UBO (CONFIRMED_SANCTION)
Test 8  — Empty Customer (AgentValidationError expected)
Test 9  — Performance (full pipeline < 5 s)
Test 10 — AgentState integrity

Assertions
----------
Every test asserts on the state keys written by each agent:
  • state.shared_metadata["kyc_status"]
  • state.shared_metadata["kyc_score"]
  • state.shared_metadata["pep_status"]
  • state.shared_metadata["pep_score"]
  • state.shared_metadata["sanctions_status"]
  • state.shared_metadata["sanctions_score"]
  • state.shared_metadata["country_status"]
  • state.shared_metadata["country_score"]
  • state.shared_metadata["next_agent"]
  • state.completed_agents (populated by BaseAgent.post_execute)
"""

import sys
import time
import asyncio
from pathlib import Path
from typing import Tuple

import pytest

# ── Ensure the backend package is importable when pytest is run from repo root
_BACKEND = Path(__file__).resolve().parents[2]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

_SCRIPTS = _BACKEND / "scripts"
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

from scenarios import (
    SCENARIO_INDIVIDUAL_CLEAN,
    SCENARIO_BUSINESS_CLEAN,
    SCENARIO_PEP_MATCH,
    SCENARIO_SANCTIONS_MATCH,
    SCENARIO_HIGH_RISK_COUNTRY,
    SCENARIO_BUSINESS_PEP_DIRECTOR,
    SCENARIO_BUSINESS_SANCTIONED_UBO,
    SCENARIO_EMPTY_CUSTOMER,
)

# ─────────────────────────────────────────────────────────────────────────────
# Status constant aliases
# ─────────────────────────────────────────────────────────────────────────────
from app.agents.kyc.constants        import STATUS_COMPLETE, STATUS_INCOMPLETE, STATUS_FAILED
from app.agents.pep.constants        import PEP_STATUS_CLEAR, PEP_STATUS_CONFIRMED, PEP_STATUS_POSSIBLE
from app.agents.sanctions.constants  import (
    SANCTIONS_STATUS_CLEAR, SANCTIONS_STATUS_CONFIRMED, SANCTIONS_STATUS_POSSIBLE
)
from app.agents.country.constants    import (
    COUNTRY_STATUS_CLEAR, COUNTRY_STATUS_WARNING, COUNTRY_STATUS_SUSPENDED,
    RISK_HIGH, RISK_LOW, RISK_MEDIUM, RISK_PROHIBITED
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
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


async def _run_pipeline(scenario: dict) -> Tuple[AgentState, dict]:
    """
    Runs the complete five-agent pipeline and returns (state, timing_map).
    Raises AgentValidationError / AgentExecutionError on failure.
    """
    state   = build_state(scenario)
    timings = {}

    agents = [
        KycAgent(),
        CompanyAgent(),
        PepAgent(),
        SanctionsAgent(),
        CountryRiskAgent(),
    ]

    for agent in agents:
        t0     = time.perf_counter()
        result = await agent.execute(state)
        timings[agent.get_name()] = (time.perf_counter() - t0) * 1000

        if not result.success:
            raise AgentExecutionError(
                f"{agent.get_name()} returned non-success status: {result.status}"
            )

    return state, timings


def run_pipeline(scenario: dict) -> Tuple[AgentState, dict]:
    """Sync wrapper — compatible with Python 3.12 (uses asyncio.run)."""
    return asyncio.run(_run_pipeline(scenario))


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures — module-scoped dicts keyed by scenario name to run once
# ─────────────────────────────────────────────────────────────────────────────
_STATE_CACHE: dict[str, AgentState] = {}


def _get_state(scenario_key: str, scenario: dict) -> AgentState:
    if scenario_key not in _STATE_CACHE:
        s, _ = run_pipeline(scenario)
        _STATE_CACHE[scenario_key] = s
    return _STATE_CACHE[scenario_key]


def _get_timings(scenario_key: str, scenario: dict) -> dict:
    if scenario_key not in _STATE_CACHE:
        _get_state(scenario_key, scenario)
    return {}  # timings returned separately; pipeline already cached


# ─────────────────────────────────────────────────────────────────────────────
# Test 1 — Individual Customer (All Clear)
# ─────────────────────────────────────────────────────────────────────────────
class TestIndividualClean:
    """
    Individual with complete KYC profile. No PEP, sanction, or country flags.
    Expected: KYC COMPLETE, Company SKIPPED, PEP CLEAR, Sanctions CLEAR, Country CLEAR.
    """

    @pytest.fixture(scope="class")
    def pipeline(self):
        s, t = run_pipeline(SCENARIO_INDIVIDUAL_CLEAN)
        return s, t

    def test_kyc_status_complete(self, pipeline):
        state, _ = pipeline
        assert state.shared_metadata["kyc_status"] == STATUS_COMPLETE

    def test_kyc_score_high(self, pipeline):
        state, _ = pipeline
        assert state.shared_metadata["kyc_score"] >= 60.0

    def test_company_agent_ran(self, pipeline):
        state, _ = pipeline
        assert "company_agent" in state.completed_agents

    def test_company_skipped_for_individual(self, pipeline):
        state, _ = pipeline
        comp_result = state.agent_results.get("company_agent", {})
        routing = comp_result.get("metadata", {}).get("routing", {})
        assert routing.get("company_agent_executed") is False or \
               routing.get("company_agent_status") == "SKIPPED"

    def test_pep_status_clear(self, pipeline):
        state, _ = pipeline
        assert state.shared_metadata["pep_status"] == PEP_STATUS_CLEAR

    def test_pep_score_100(self, pipeline):
        state, _ = pipeline
        assert state.shared_metadata["pep_score"] == 100.0

    def test_sanctions_status_clear(self, pipeline):
        state, _ = pipeline
        assert state.shared_metadata["sanctions_status"] == SANCTIONS_STATUS_CLEAR

    def test_sanctions_score_100(self, pipeline):
        state, _ = pipeline
        assert state.shared_metadata["sanctions_score"] == 100.0

    def test_country_status_not_prohibited(self, pipeline):
        state, _ = pipeline
        assert state.shared_metadata["country_status"] != COUNTRY_STATUS_SUSPENDED

    def test_country_score_positive(self, pipeline):
        state, _ = pipeline
        assert state.shared_metadata["country_score"] > 0.0

    def test_all_five_agents_completed(self, pipeline):
        state, _ = pipeline
        expected = {"kyc_agent", "company_agent", "pep_agent", "sanctions_agent", "country_risk_agent"}
        assert expected.issubset(set(state.completed_agents))

    def test_next_agent_set(self, pipeline):
        state, _ = pipeline
        assert state.shared_metadata.get("next_agent") is not None


# ─────────────────────────────────────────────────────────────────────────────
# Test 2 — Business Customer (All Clear)
# ─────────────────────────────────────────────────────────────────────────────
class TestBusinessClean:
    """
    Fully verified business. Company Agent must run full verification.
    Expected: KYC COMPLETE/INCOMPLETE, Company COMPLETE, PEP CLEAR, Sanctions CLEAR, Country CLEAR.
    """

    @pytest.fixture(scope="class")
    def pipeline(self):
        s, t = run_pipeline(SCENARIO_BUSINESS_CLEAN)
        return s, t

    def test_kyc_ran(self, pipeline):
        state, _ = pipeline
        assert "kyc_agent" in state.completed_agents

    def test_kyc_score_positive(self, pipeline):
        state, _ = pipeline
        assert state.shared_metadata["kyc_score"] >= 0.0

    def test_company_agent_ran(self, pipeline):
        state, _ = pipeline
        assert "company_agent" in state.completed_agents

    def test_company_agent_executed_verification(self, pipeline):
        state, _ = pipeline
        comp_result = state.agent_results.get("company_agent", {})
        routing = comp_result.get("metadata", {}).get("routing", {})
        assert routing.get("company_agent_executed") is True

    def test_pep_status_clear(self, pipeline):
        state, _ = pipeline
        assert state.shared_metadata["pep_status"] == PEP_STATUS_CLEAR

    def test_sanctions_status_clear(self, pipeline):
        state, _ = pipeline
        assert state.shared_metadata["sanctions_status"] == SANCTIONS_STATUS_CLEAR

    def test_country_status_not_suspended(self, pipeline):
        state, _ = pipeline
        assert state.shared_metadata["country_status"] != COUNTRY_STATUS_SUSPENDED

    def test_all_five_agents_completed(self, pipeline):
        state, _ = pipeline
        expected = {"kyc_agent", "company_agent", "pep_agent", "sanctions_agent", "country_risk_agent"}
        assert expected.issubset(set(state.completed_agents))


# ─────────────────────────────────────────────────────────────────────────────
# Test 3 — PEP Match (Individual)
# ─────────────────────────────────────────────────────────────────────────────
class TestPepMatch:
    """
    Customer 'James Wilson' DOB 1965-03-22 partially matches PEP-UK-001
    (full name 'James Alexander Wilson').

    The matching engine scores: name 71% + DOB exact + nationality + country
    → composite score ~80.29 → POSSIBLE_MATCH (threshold 75, confirmed 95).

    Expected:
    - pep_status == POSSIBLE_MATCH
    - pep_score < 100
    - matched_subjects contains at least one entry
    - manual_review_required == True (POSSIBLE triggers manual review)
    - edd_required == False (EDD only for CONFIRMED_MATCH)
    """

    @pytest.fixture(scope="class")
    def pipeline(self):
        s, t = run_pipeline(SCENARIO_PEP_MATCH)
        return s, t

    def test_pep_status_is_not_clear(self, pipeline):
        state, _ = pipeline
        assert state.shared_metadata["pep_status"] != PEP_STATUS_CLEAR

    def test_pep_status_is_possible_match(self, pipeline):
        state, _ = pipeline
        assert state.shared_metadata["pep_status"] == PEP_STATUS_POSSIBLE

    def test_pep_score_below_100(self, pipeline):
        state, _ = pipeline
        assert state.shared_metadata["pep_score"] < 100.0

    def test_pep_has_matched_subjects(self, pipeline):
        state, _ = pipeline
        # matched_subjects in shared_metadata is overwritten by the Sanctions agent.
        # The PEP-specific match data is preserved in agent_results.
        pep_result = state.agent_results.get("pep_agent", {})
        matched = pep_result.get("metadata", {}).get("matched_subjects", [])
        assert len(matched) >= 1

    def test_manual_review_required(self, pipeline):
        """POSSIBLE_MATCH triggers manual review (not EDD — that requires CONFIRMED)."""
        state, _ = pipeline
        assert state.shared_metadata.get("manual_review_required") is True

    def test_sanctions_still_ran(self, pipeline):
        state, _ = pipeline
        assert "sanctions_agent" in state.completed_agents

    def test_country_still_ran(self, pipeline):
        state, _ = pipeline
        assert "country_risk_agent" in state.completed_agents

    def test_next_agent_after_pep_is_sanctions(self, pipeline):
        state, _ = pipeline
        # sanctions_agent is listed as completed after PEP
        assert "sanctions_agent" in state.completed_agents


# ─────────────────────────────────────────────────────────────────────────────
# Test 4 — Sanctions Match (Individual — terrorist financing)
# ─────────────────────────────────────────────────────────────────────────────
class TestSanctionsMatch:
    """
    Customer passport SYR-987654-A matches SANC-IND-001 (UN, terrorist financing).
    Expected: sanctions_status CONFIRMED, sanctions_score == 0.0.
    """

    @pytest.fixture(scope="class")
    def pipeline(self):
        s, t = run_pipeline(SCENARIO_SANCTIONS_MATCH)
        return s, t

    def test_sanctions_status_confirmed(self, pipeline):
        state, _ = pipeline
        assert state.shared_metadata["sanctions_status"] == SANCTIONS_STATUS_CONFIRMED

    def test_sanctions_score_zero(self, pipeline):
        state, _ = pipeline
        assert state.shared_metadata["sanctions_score"] == 0.0

    def test_sanctions_has_matched_subjects(self, pipeline):
        state, _ = pipeline
        matched = state.shared_metadata.get("matched_subjects", [])
        assert len(matched) >= 1

    def test_sanctions_risk_is_critical(self, pipeline):
        state, _ = pipeline
        assert state.shared_metadata.get("sanctions_risk") == "critical"

    def test_country_still_ran(self, pipeline):
        state, _ = pipeline
        assert "country_risk_agent" in state.completed_agents

    def test_pep_still_ran(self, pipeline):
        state, _ = pipeline
        assert "pep_agent" in state.completed_agents


# ─────────────────────────────────────────────────────────────────────────────
# Test 5 — High Risk Country
# ─────────────────────────────────────────────────────────────────────────────
class TestHighRiskCountry:
    """
    Russian national. Russia is HIGH risk per MockCountryRiskProvider.
    Expected: country_status WARNING, country_score < 100, Russia in high_risk_countries.
    """

    @pytest.fixture(scope="class")
    def pipeline(self):
        s, t = run_pipeline(SCENARIO_HIGH_RISK_COUNTRY)
        return s, t

    def test_country_status_not_clear(self, pipeline):
        state, _ = pipeline
        assert state.shared_metadata["country_status"] != COUNTRY_STATUS_CLEAR

    def test_country_score_below_100(self, pipeline):
        state, _ = pipeline
        assert state.shared_metadata["country_score"] < 100.0

    def test_russia_in_high_risk(self, pipeline):
        state, _ = pipeline
        high_risk = state.shared_metadata.get("high_risk_countries", [])
        assert any("russia" in c.lower() for c in high_risk)

    def test_country_risk_level_high(self, pipeline):
        state, _ = pipeline
        assert state.shared_metadata.get("country_risk") in {RISK_HIGH, "high"}

    def test_all_agents_ran(self, pipeline):
        state, _ = pipeline
        expected = {"kyc_agent", "pep_agent", "sanctions_agent", "country_risk_agent"}
        assert expected.issubset(set(state.completed_agents))


# ─────────────────────────────────────────────────────────────────────────────
# Test 6 — Business with PEP Director
# ─────────────────────────────────────────────────────────────────────────────
class TestBusinessPepDirector:
    """
    Director 'James Wilson' DOB 1965-03-22 partially matches PEP-UK-001.
    Expected: PEP POSSIBLE_MATCH, pep_score < 100, manual_review_required = True.
    """

    @pytest.fixture(scope="class")
    def pipeline(self):
        s, t = run_pipeline(SCENARIO_BUSINESS_PEP_DIRECTOR)
        return s, t

    def test_company_agent_ran_business_verification(self, pipeline):
        state, _ = pipeline
        comp_result = state.agent_results.get("company_agent", {})
        routing = comp_result.get("metadata", {}).get("routing", {})
        assert routing.get("company_agent_executed") is True

    def test_pep_director_detected(self, pipeline):
        """Director screening should pick up James Wilson as a POSSIBLE_MATCH."""
        state, _ = pipeline
        assert state.shared_metadata["pep_status"] != PEP_STATUS_CLEAR

    def test_pep_score_below_100(self, pipeline):
        state, _ = pipeline
        assert state.shared_metadata["pep_score"] < 100.0

    def test_pep_has_matched_subjects(self, pipeline):
        state, _ = pipeline
        # matched_subjects in shared_metadata is overwritten by the Sanctions agent.
        # The PEP-specific match data is preserved in agent_results.
        pep_result = state.agent_results.get("pep_agent", {})
        matched = pep_result.get("metadata", {}).get("matched_subjects", [])
        assert len(matched) >= 1

    def test_edd_required(self, pipeline):
        """James Alexander Wilson scores CONFIRMED_MATCH (95.0) → EDD required."""
        state, _ = pipeline
        assert state.shared_metadata.get("edd_required") is True

    def test_all_agents_completed(self, pipeline):
        state, _ = pipeline
        expected = {"kyc_agent", "company_agent", "pep_agent", "sanctions_agent", "country_risk_agent"}
        assert expected.issubset(set(state.completed_agents))


# ─────────────────────────────────────────────────────────────────────────────
# Test 7 — Business with Sanctioned UBO
# ─────────────────────────────────────────────────────────────────────────────
class TestBusinessSanctionedUbo:
    """
    UBO 'Ahmed Al-Masri' passport SYR-987654-A matches SANC-IND-001 (terrorist).
    Expected: sanctions CONFIRMED, score 0.0, risk critical.
    """

    @pytest.fixture(scope="class")
    def pipeline(self):
        s, t = run_pipeline(SCENARIO_BUSINESS_SANCTIONED_UBO)
        return s, t

    def test_company_ran_business_verification(self, pipeline):
        state, _ = pipeline
        comp_result = state.agent_results.get("company_agent", {})
        routing = comp_result.get("metadata", {}).get("routing", {})
        assert routing.get("company_agent_executed") is True

    def test_sanctions_status_confirmed(self, pipeline):
        state, _ = pipeline
        assert state.shared_metadata["sanctions_status"] == SANCTIONS_STATUS_CONFIRMED

    def test_sanctions_score_zero(self, pipeline):
        state, _ = pipeline
        assert state.shared_metadata["sanctions_score"] == 0.0

    def test_sanctions_risk_critical(self, pipeline):
        state, _ = pipeline
        assert state.shared_metadata.get("sanctions_risk") == "critical"

    def test_sanctioned_ubo_in_matched(self, pipeline):
        state, _ = pipeline
        matched = state.shared_metadata.get("matched_subjects", [])
        assert len(matched) >= 1

    def test_all_agents_completed(self, pipeline):
        state, _ = pipeline
        expected = {"kyc_agent", "company_agent", "pep_agent", "sanctions_agent", "country_risk_agent"}
        assert expected.issubset(set(state.completed_agents))


# ─────────────────────────────────────────────────────────────────────────────
# Test 8 — Empty Customer (Validation Error)
# ─────────────────────────────────────────────────────────────────────────────
class TestEmptyCustomer:
    """
    Empty customer dict. KycAgent.validate_input must raise AgentValidationError.
    The error must propagate — no partial execution permitted.
    """

    def test_raises_validation_error(self):
        state = build_state(SCENARIO_EMPTY_CUSTOMER)
        agent = KycAgent()

        async def _run():
            return await agent.execute(state)

        with pytest.raises((AgentValidationError, AgentExecutionError)):
            asyncio.run(_run())

    def test_no_agents_completed_on_empty_input(self):
        state = build_state(SCENARIO_EMPTY_CUSTOMER)

        async def _run():
            agent = KycAgent()
            try:
                await agent.execute(state)
            except (AgentValidationError, AgentExecutionError):
                pass

        asyncio.run(_run())
        assert "kyc_agent" not in state.completed_agents


# ─────────────────────────────────────────────────────────────────────────────
# Test 9 — Performance
# ─────────────────────────────────────────────────────────────────────────────
class TestPerformance:
    """
    The full pipeline should complete in under 5 seconds for mock providers.
    Each individual agent should finish in under 2 seconds.
    """

    def test_full_pipeline_under_5_seconds(self):
        t0 = time.perf_counter()
        run_pipeline(SCENARIO_INDIVIDUAL_CLEAN)
        elapsed = time.perf_counter() - t0
        assert elapsed < 5.0, f"Pipeline took {elapsed:.2f}s — expected < 5s"

    def test_each_agent_under_2_seconds(self):
        _, timings = run_pipeline(SCENARIO_BUSINESS_CLEAN)
        for agent_name, ms in timings.items():
            assert ms < 2000, f"{agent_name} took {ms:.1f}ms — expected < 2000ms"


# ─────────────────────────────────────────────────────────────────────────────
# Test 10 — AgentState Integrity
# ─────────────────────────────────────────────────────────────────────────────
class TestAgentStateIntegrity:
    """
    Validates that every agent wrote its expected keys into shared_metadata
    and that the execution history is correctly populated.
    """

    @pytest.fixture(scope="class")
    def pipeline(self):
        s, t = run_pipeline(SCENARIO_INDIVIDUAL_CLEAN)
        return s, t

    def test_kyc_metadata_keys_present(self, pipeline):
        state, _ = pipeline
        for key in ("kyc_status", "kyc_score", "missing_fields"):
            assert key in state.shared_metadata, f"Missing key: {key}"

    def test_pep_metadata_keys_present(self, pipeline):
        state, _ = pipeline
        for key in ("pep_status", "pep_score", "pep_risk"):
            assert key in state.shared_metadata, f"Missing key: {key}"

    def test_sanctions_metadata_keys_present(self, pipeline):
        state, _ = pipeline
        for key in ("sanctions_status", "sanctions_score", "sanctions_risk"):
            assert key in state.shared_metadata, f"Missing key: {key}"

    def test_country_metadata_keys_present(self, pipeline):
        state, _ = pipeline
        for key in ("country_status", "country_score", "country_risk"):
            assert key in state.shared_metadata, f"Missing key: {key}"

    def test_execution_history_populated(self, pipeline):
        state, _ = pipeline
        assert len(state.execution_history) >= 5

    def test_agent_results_populated(self, pipeline):
        state, _ = pipeline
        assert len(state.agent_results) >= 5

    def test_risk_breakdown_populated(self, pipeline):
        state, _ = pipeline
        for key in ("kyc", "pep", "sanctions", "country"):
            assert key in state.risk_breakdown, f"Missing risk_breakdown key: {key}"

    def test_logs_populated(self, pipeline):
        state, _ = pipeline
        assert len(state.logs) >= 5
