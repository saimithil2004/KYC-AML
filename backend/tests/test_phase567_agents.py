"""
Comprehensive unit tests for all Phase 5, 6, and 7 agents.
Run with: python -m pytest backend/tests/test_phase567_agents.py -v
"""

import asyncio
import pytest
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def make_state(**kwargs):
    """Helper to create a minimal AgentState for testing."""
    from app.agents.base.agent_state import AgentState
    defaults = {
        "customer_id": "00000000-0000-0000-0000-000000000001",
        "case_id":     "00000000-0000-0000-0000-000000000002",
        "customer": {
            "id":            "00000000-0000-0000-0000-000000000001",
            "customer_type": "individual",
            "first_name":    "John",
            "last_name":     "Smith",
            "nationality":   "United Kingdom",
            "country":       "United Kingdom",
        },
        "kyc_profile": {
            "full_name":        "John Smith",
            "date_of_birth":    "1980-01-15",
            "nationality":      "United Kingdom",
            "address":          "10 Downing Street, London, SW1A 2AA",
            "source_of_funds":  "employment",
            "source_of_wealth": "salary",
            "occupation":       "software engineer",
            "tax_residency":    "United Kingdom",
        },
    }
    defaults.update(kwargs)
    return AgentState(**defaults)


def run_async(coro):
    """Run an async coroutine synchronously in tests."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    if loop.is_closed():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


# ─────────────────────────────────────────────────────────────────────────────
# Phase 5 — Risk Scoring Agent
# ─────────────────────────────────────────────────────────────────────────────

class TestRiskScoringAgent:

    def test_registration(self):
        from app.agents.base.registry import AgentRegistry
        from app.agents.risk.agent import RiskScoringAgent  # noqa
        registry = AgentRegistry.get_registry()
        assert "risk_scoring_agent" in registry.list_agents()

    def test_low_risk_score(self):
        from app.agents.risk.agent import RiskScoringAgent
        from app.agents.base.agent_context import AgentContext
        state = make_state()
        # Set all agent scores to 100 (all clear)
        state.shared_metadata = {
            "pep_score": 100.0,
            "sanctions_score": 100.0,
            "country_score": 100.0,
            "document_score": 100.0,
            "transaction_score": 100.0,
        }
        agent = RiskScoringAgent(context=AgentContext())
        result = run_async(agent.process(state))
        assert result["overall_score"] == 0.0
        assert result["risk_level"] == "LOW"

    def test_high_risk_score(self):
        from app.agents.risk.agent import RiskScoringAgent
        from app.agents.base.agent_context import AgentContext
        state = make_state()
        # Set all agent scores to 0 (all flagged)
        state.shared_metadata = {
            "pep_score": 0.0,
            "sanctions_score": 0.0,
            "country_score": 0.0,
            "document_score": 0.0,
            "transaction_score": 0.0,
        }
        agent = RiskScoringAgent(context=AgentContext())
        result = run_async(agent.process(state))
        assert result["overall_score"] == 100.0
        assert result["risk_level"] == "HIGH"

    def test_medium_risk_score(self):
        from app.agents.risk.agent import RiskScoringAgent
        from app.agents.base.agent_context import AgentContext
        from app.agents.risk.config import get_risk_level
        state = make_state()
        # Sanctions flagged (weight=40), others clear
        state.shared_metadata = {
            "pep_score": 100.0,
            "sanctions_score": 50.0,  # Possible match
            "country_score": 100.0,
            "document_score": 100.0,
            "transaction_score": 100.0,
        }
        agent = RiskScoringAgent(context=AgentContext())
        result = run_async(agent.process(state))
        assert result["overall_score"] > 0
        assert result["risk_level"] in ("LOW", "MEDIUM", "HIGH")

    def test_configurable_weights(self):
        from app.agents.risk.config import RISK_WEIGHTS
        # Weights must sum to 100
        total = sum(RISK_WEIGHTS.values())
        assert abs(total - 100.0) < 0.001, f"Weights must sum to 100, got {total}"

    def test_contributing_factors_populated(self):
        from app.agents.risk.agent import RiskScoringAgent
        from app.agents.base.agent_context import AgentContext
        state = make_state()
        state.shared_metadata = {
            "pep_score": 80.0,
            "sanctions_score": 60.0,
            "country_score": 90.0,
            "document_score": 100.0,
            "transaction_score": 75.0,
        }
        agent = RiskScoringAgent(context=AgentContext())
        result = run_async(agent.process(state))
        factors = result["contributing_factors"]
        assert len(factors) == 5
        for f in factors:
            assert "signal" in f
            assert "weight" in f
            assert "contribution" in f


# ─────────────────────────────────────────────────────────────────────────────
# Phase 6 — Document Verification Agent
# ─────────────────────────────────────────────────────────────────────────────

class TestDocumentVerificationAgent:

    def test_registration(self):
        from app.agents.base.registry import AgentRegistry
        from app.agents.document.agent import DocumentVerificationAgent  # noqa
        registry = AgentRegistry.get_registry()
        assert "document_verification_agent" in registry.list_agents()

    def test_no_documents(self):
        from app.agents.document.agent import DocumentVerificationAgent
        from app.agents.base.agent_context import AgentContext
        state = make_state()
        state.uploaded_documents = []
        agent = DocumentVerificationAgent(context=AgentContext())
        result = run_async(agent.process(state))
        assert result["document_score"] == 0.0
        assert len(result["errors"]) > 0

    def test_verified_documents(self):
        from app.agents.document.agent import DocumentVerificationAgent
        from app.agents.base.agent_context import AgentContext
        state = make_state()
        state.uploaded_documents = [{
            "document_type": "passport",
            "file_name":     "passport_john_smith.jpg",
            "file_size":     50000,
            "verification_status": "verified",
            "ocr_data": {
                "full_name":      "john smith",
                "date_of_birth":  "1980-01-15",
            },
        }]
        agent = DocumentVerificationAgent(context=AgentContext())
        result = run_async(agent.process(state))
        assert result["document_score"] > 0
        assert result["name_mismatches"] == 0

    def test_name_mismatch_detected(self):
        from app.agents.document.agent import DocumentVerificationAgent
        from app.agents.base.agent_context import AgentContext
        state = make_state()
        state.uploaded_documents = [{
            "document_type": "passport",
            "file_name":     "passport.jpg",
            "file_size":     50000,
            "verification_status": "verified",
            "ocr_data": {"full_name": "COMPLETELY DIFFERENT PERSON"},
        }]
        agent = DocumentVerificationAgent(context=AgentContext())
        result = run_async(agent.process(state))
        assert result["name_mismatches"] == 1
        assert result["document_score"] < 100

    def test_duplicate_detection(self):
        from app.agents.document.agent import DocumentVerificationAgent
        from app.agents.base.agent_context import AgentContext
        state = make_state()
        doc = {
            "document_type": "passport",
            "file_name":     "same_file.jpg",
            "file_size":     50000,
            "verification_status": "verified",
            "ocr_data": {"full_name": "john smith"},
        }
        state.uploaded_documents = [doc, dict(doc)]
        agent = DocumentVerificationAgent(context=AgentContext())
        result = run_async(agent.process(state))
        assert result["duplicate_count"] == 1


# ─────────────────────────────────────────────────────────────────────────────
# Phase 6 — FATF Agent
# ─────────────────────────────────────────────────────────────────────────────

class TestFATFAgent:

    def test_registration(self):
        from app.agents.base.registry import AgentRegistry
        from app.agents.fatf.agent import FATFAgent  # noqa
        registry = AgentRegistry.get_registry()
        assert "fatf_agent" in registry.list_agents()

    def test_clear_country(self):
        from app.agents.fatf.agent import FATFAgent
        from app.agents.base.agent_context import AgentContext
        state = make_state()
        agent = FATFAgent(context=AgentContext())
        result = run_async(agent.process(state))
        assert result["fatf_status"] == "CLEAR"
        assert result["fatf_score"] == 100.0

    def test_black_listed_country(self):
        from app.agents.fatf.agent import FATFAgent
        from app.agents.base.agent_context import AgentContext
        state = make_state(customer={
            "id": "00000000-0000-0000-0000-000000000001",
            "customer_type": "individual",
            "first_name": "Ali",
            "last_name": "Hassan",
            "nationality": "Iran",
            "country": "Iran",
        })
        agent = FATFAgent(context=AgentContext())
        result = run_async(agent.process(state))
        assert result["fatf_status"] == "BLACK_LISTED"
        assert result["fatf_score"] == 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Phase 6 — UBO Verification Agent
# ─────────────────────────────────────────────────────────────────────────────

class TestUBOVerificationAgent:

    def test_registration(self):
        from app.agents.base.registry import AgentRegistry
        from app.agents.ubo.agent import UBOVerificationAgent  # noqa
        registry = AgentRegistry.get_registry()
        assert "ubo_verification_agent" in registry.list_agents()

    def test_skips_individual(self):
        from app.agents.ubo.agent import UBOVerificationAgent
        from app.agents.base.agent_context import AgentContext
        state = make_state()
        agent = UBOVerificationAgent(context=AgentContext())
        result = run_async(agent.process(state))
        assert result["skipped"] is True
        assert result["ubo_score"] == 100.0

    def test_no_ubos_for_corporate(self):
        from app.agents.ubo.agent import UBOVerificationAgent
        from app.agents.base.agent_context import AgentContext
        state = make_state()
        state.customer["customer_type"] = "corporate"
        state.ubos = []
        agent = UBOVerificationAgent(context=AgentContext())
        result = run_async(agent.process(state))
        assert result["ubo_score"] == 0.0
        assert len(result["errors"]) > 0

    def test_valid_ubo_disclosure(self):
        from app.agents.ubo.agent import UBOVerificationAgent
        from app.agents.base.agent_context import AgentContext
        state = make_state()
        state.customer["customer_type"] = "corporate"
        state.ubos = [
            {"first_name": "Jane", "last_name": "Doe", "ownership_percentage": 80.0, "control_type": "direct", "verification_status": "verified"},
        ]
        agent = UBOVerificationAgent(context=AgentContext())
        result = run_async(agent.process(state))
        assert result["ubo_score"] == 100.0


# ─────────────────────────────────────────────────────────────────────────────
# Phase 6 — Account Behavior Agent
# ─────────────────────────────────────────────────────────────────────────────

class TestAccountBehaviorAgent:

    def test_registration(self):
        from app.agents.base.registry import AgentRegistry
        from app.agents.account.agent import AccountBehaviorAgent  # noqa
        registry = AgentRegistry.get_registry()
        assert "account_behavior_agent" in registry.list_agents()

    def test_no_transactions(self):
        from app.agents.account.agent import AccountBehaviorAgent
        from app.agents.base.agent_context import AgentContext
        state = make_state()
        state.transactions = []
        agent = AccountBehaviorAgent(context=AgentContext())
        result = run_async(agent.process(state))
        assert result["account_behavior_score"] == 80.0

    def test_clean_transactions(self):
        from app.agents.account.agent import AccountBehaviorAgent
        from app.agents.base.agent_context import AgentContext
        state = make_state()
        state.transactions = [
            {"amount": 500, "transaction_type": "credit", "created_at": "2025-01-01T10:00:00", "receiver_account_number": "12345678"},
            {"amount": 200, "transaction_type": "debit",  "created_at": "2025-02-01T10:00:00", "receiver_account_number": "87654321"},
        ]
        agent = AccountBehaviorAgent(context=AgentContext())
        result = run_async(agent.process(state))
        assert result["account_behavior_score"] == 100.0


# ─────────────────────────────────────────────────────────────────────────────
# Phase 6 — Decision Agent
# ─────────────────────────────────────────────────────────────────────────────

class TestDecisionAgent:

    def test_registration(self):
        from app.agents.base.registry import AgentRegistry
        from app.agents.decision.agent import DecisionAgent  # noqa
        registry = AgentRegistry.get_registry()
        assert "decision_agent" in registry.list_agents()

    def test_approve_low_risk(self):
        from app.agents.decision.agent import DecisionAgent
        from app.agents.base.agent_context import AgentContext
        state = make_state()
        state.overall_score = 10.0
        state.risk_tier = "low"
        state.shared_metadata = {
            "risk_level": "LOW",
            "sanctions_status": "CLEAR",
            "pep_status": "CLEAR",
            "fatf_black_listed": [],
            "regulation_block_triggers": [],
            "regulation_edd_triggers": [],
            "regulation_violations": [],
            "transaction_status": "CLEAR",
            "account_behavior_flags": {},
        }
        agent = DecisionAgent(context=AgentContext())
        result = run_async(agent.process(state))
        assert result["final_decision"] == "APPROVE"

    def test_reject_confirmed_sanctions(self):
        from app.agents.decision.agent import DecisionAgent
        from app.agents.base.agent_context import AgentContext
        state = make_state()
        state.overall_score = 95.0
        state.risk_tier = "high"
        state.shared_metadata = {
            "risk_level": "HIGH",
            "sanctions_status": "CONFIRMED",
            "pep_status": "CLEAR",
            "fatf_black_listed": [],
            "regulation_block_triggers": ["SANCTIONS_BLOCK"],
            "regulation_edd_triggers": [],
            "regulation_violations": [],
            "transaction_status": "CLEAR",
            "account_behavior_flags": {},
        }
        agent = DecisionAgent(context=AgentContext())
        result = run_async(agent.process(state))
        assert result["final_decision"] == "REJECT"

    def test_edd_required_high_score(self):
        from app.agents.decision.agent import DecisionAgent
        from app.agents.base.agent_context import AgentContext
        state = make_state()
        state.overall_score = 80.0
        state.risk_tier = "high"
        state.shared_metadata = {
            "risk_level": "HIGH",
            "sanctions_status": "CLEAR",
            "pep_status": "CONFIRMED_PEP",
            "fatf_black_listed": [],
            "regulation_block_triggers": [],
            "regulation_edd_triggers": ["PEP_EDD"],
            "regulation_violations": [],
            "transaction_status": "CLEAR",
            "account_behavior_flags": {},
        }
        agent = DecisionAgent(context=AgentContext())
        result = run_async(agent.process(state))
        assert result["final_decision"] == "EDD_REQUIRED"


# ─────────────────────────────────────────────────────────────────────────────
# Phase 6 — Monitoring Agent
# ─────────────────────────────────────────────────────────────────────────────

class TestMonitoringAgent:

    def test_registration(self):
        from app.agents.base.registry import AgentRegistry
        from app.agents.monitoring.agent import MonitoringAgent  # noqa
        registry = AgentRegistry.get_registry()
        assert "monitoring_agent" in registry.list_agents()

    def test_low_risk_frequency(self):
        from app.agents.monitoring.agent import MonitoringAgent, MONITORING_FREQUENCY
        from app.agents.base.agent_context import AgentContext
        state = make_state()
        state.risk_tier = "low"
        agent = MonitoringAgent(context=AgentContext())
        result = run_async(agent.process(state))
        assert result["review_frequency_months"] == MONITORING_FREQUENCY["low"]  # 60 months

    def test_high_risk_frequency(self):
        from app.agents.monitoring.agent import MonitoringAgent, MONITORING_FREQUENCY
        from app.agents.base.agent_context import AgentContext
        state = make_state()
        state.risk_tier = "high"
        agent = MonitoringAgent(context=AgentContext())
        result = run_async(agent.process(state))
        assert result["review_frequency_months"] == MONITORING_FREQUENCY["high"]  # 12 months

    def test_schedule_created(self):
        from app.agents.monitoring.agent import MonitoringAgent
        from app.agents.base.agent_context import AgentContext
        state = make_state()
        state.risk_tier = "medium"
        agent = MonitoringAgent(context=AgentContext())
        result = run_async(agent.process(state))
        sched = result["monitoring_schedule"]
        assert sched["next_review_date"] is not None
        assert sched["review_frequency_months"] == 36  # 3 years


# ─────────────────────────────────────────────────────────────────────────────
# Phase 6 — Regulation Agent
# ─────────────────────────────────────────────────────────────────────────────

class TestRegulationAgent:

    def test_registration(self):
        from app.agents.base.registry import AgentRegistry
        from app.agents.regulation.agent import RegulationAgent  # noqa
        registry = AgentRegistry.get_registry()
        assert "regulation_agent" in registry.list_agents()

    def test_no_violations_clean_state(self):
        from app.agents.regulation.agent import RegulationAgent
        from app.agents.base.agent_context import AgentContext
        state = make_state()
        state.overall_score = 10.0
        state.shared_metadata = {
            "sanctions_status": "CLEAR",
            "fatf_black_listed": [],
            "pep_status": "CLEAR",
            "high_risk_countries": [],
        }
        agent = RegulationAgent(context=AgentContext())
        result = run_async(agent.process(state))
        assert len(result["violations"]) == 0

    def test_sanctions_block_violation(self):
        from app.agents.regulation.agent import RegulationAgent
        from app.agents.base.agent_context import AgentContext
        state = make_state()
        state.shared_metadata = {"sanctions_status": "CONFIRMED", "fatf_black_listed": []}
        agent = RegulationAgent(context=AgentContext())
        result = run_async(agent.process(state))
        block_violations = [v for v in result["violations"] if v.get("rule_type") == "block"]
        assert len(block_violations) > 0


# ─────────────────────────────────────────────────────────────────────────────
# Phase 6 — Investigation Agent
# ─────────────────────────────────────────────────────────────────────────────

class TestInvestigationAgent:

    def test_registration(self):
        from app.agents.base.registry import AgentRegistry
        from app.agents.investigation.agent import InvestigationAgent  # noqa
        registry = AgentRegistry.get_registry()
        assert "investigation_agent" in registry.list_agents()

    def test_deterministic_summary_generated(self):
        from app.agents.investigation.agent import InvestigationAgent
        from app.agents.base.agent_context import AgentContext
        state = make_state()
        state.overall_score = 25.0
        state.risk_tier = "low"
        state.shared_metadata = {
            "risk_level": "LOW",
            "pep_status": "CLEAR",
            "sanctions_status": "CLEAR",
            "country_status": "CLEAR",
            "fatf_status": "CLEAR",
            "document_score": 100.0,
            "transaction_status": "CLEAR",
            "regulation_violations": [],
            "regulation_block_triggers": [],
            "regulation_edd_triggers": [],
            "account_behavior_flags": {},
        }
        agent = InvestigationAgent(context=AgentContext())
        result = run_async(agent.process(state))
        assert state.shared_metadata["investigation_summary"] != ""
        assert state.shared_metadata["sar_explanation"] != ""
        assert state.shared_metadata["compliance_narrative"] != ""
        assert result["ai_used"] is False


# ─────────────────────────────────────────────────────────────────────────────
# Phase 7 — Agent Registry Verification
# ─────────────────────────────────────────────────────────────────────────────

class TestAgentRegistry:

    def test_all_agents_registered(self):
        # Import all agents to trigger self-registration
        from app.agents.kyc.agent import KycAgent                          # noqa
        from app.agents.pep.agent import PepAgent                          # noqa
        from app.agents.sanctions.agent import SanctionsAgent              # noqa
        from app.agents.country.agent import CountryRiskAgent              # noqa
        from app.agents.transaction.agent import TransactionAgent          # noqa
        from app.agents.company.agent import CompanyAgent                  # noqa
        from app.agents.document.agent import DocumentVerificationAgent    # noqa
        from app.agents.fatf.agent import FATFAgent                        # noqa
        from app.agents.ubo.agent import UBOVerificationAgent              # noqa
        from app.agents.director.agent import DirectorVerificationAgent    # noqa
        from app.agents.account.agent import AccountBehaviorAgent          # noqa
        from app.agents.regulation.agent import RegulationAgent            # noqa
        from app.agents.risk.agent import RiskScoringAgent                 # noqa
        from app.agents.investigation.agent import InvestigationAgent      # noqa
        from app.agents.decision.agent import DecisionAgent                # noqa
        from app.agents.monitoring.agent import MonitoringAgent            # noqa

        from app.agents.base.registry import AgentRegistry
        registry = AgentRegistry.get_registry()
        registered = registry.list_agents()

        required_agents = [
            "kyc_agent", "pep_agent", "sanctions_agent", "country_risk_agent",
            "transaction_agent", "company_agent", "document_verification_agent",
            "fatf_agent", "ubo_verification_agent", "director_verification_agent",
            "account_behavior_agent", "regulation_agent", "risk_scoring_agent",
            "investigation_agent", "decision_agent", "monitoring_agent",
        ]
        missing = [a for a in required_agents if a not in registered]
        assert missing == [], f"Missing registered agents: {missing}"

    def test_orchestrator_importable(self):
        from app.agents.orchestrator.agent import OrchestratorAgent
        assert OrchestratorAgent is not None


# ─────────────────────────────────────────────────────────────────────────────
# Phase 7 — Orchestrator Workflow
# ─────────────────────────────────────────────────────────────────────────────

class TestOrchestratorAgent:

    def test_individual_workflow_completes(self):
        """Test that the orchestrator runs successfully for an individual customer."""
        # Import all agents first
        from app.agents.kyc.agent import KycAgent                          # noqa
        from app.agents.pep.agent import PepAgent                          # noqa
        from app.agents.sanctions.agent import SanctionsAgent              # noqa
        from app.agents.country.agent import CountryRiskAgent              # noqa
        from app.agents.transaction.agent import TransactionAgent          # noqa
        from app.agents.company.agent import CompanyAgent                  # noqa
        from app.agents.document.agent import DocumentVerificationAgent    # noqa
        from app.agents.fatf.agent import FATFAgent                        # noqa
        from app.agents.ubo.agent import UBOVerificationAgent              # noqa
        from app.agents.director.agent import DirectorVerificationAgent    # noqa
        from app.agents.account.agent import AccountBehaviorAgent          # noqa
        from app.agents.regulation.agent import RegulationAgent            # noqa
        from app.agents.risk.agent import RiskScoringAgent                 # noqa
        from app.agents.investigation.agent import InvestigationAgent      # noqa
        from app.agents.decision.agent import DecisionAgent                # noqa
        from app.agents.monitoring.agent import MonitoringAgent            # noqa
        from app.agents.orchestrator.agent import OrchestratorAgent

        state = make_state()
        orchestrator = OrchestratorAgent(db_session=None)
        final_state = run_async(orchestrator.run(state))

        assert final_state.final_decision is not None
        assert final_state.final_decision in ("APPROVE", "MANUAL_REVIEW", "EDD_REQUIRED", "REJECT")
        assert final_state.monitoring_schedule is not None
        assert "risk_scoring_agent" in final_state.completed_agents
        assert "decision_agent" in final_state.completed_agents
        assert "monitoring_agent" in final_state.completed_agents

    def test_individual_skips_corporate_agents(self):
        """Verify that corporate agents are skipped for individual customers."""
        from app.agents.orchestrator.agent import OrchestratorAgent
        state = make_state()  # individual by default
        orchestrator = OrchestratorAgent(db_session=None)
        final_state = run_async(orchestrator.run(state))
        # Company agent should be in completed (it skips gracefully) or not run
        # Director and UBO should not have been fully executed for individuals
        logs_joined = " ".join(final_state.logs)
        assert "individual" in logs_joined.lower() or "skipping company" in logs_joined.lower()

    def test_risk_score_generated(self):
        """Risk score must be populated after orchestration."""
        from app.agents.orchestrator.agent import OrchestratorAgent
        state = make_state()
        orchestrator = OrchestratorAgent(db_session=None)
        final_state = run_async(orchestrator.run(state))
        assert isinstance(final_state.overall_score, float)
        assert 0.0 <= final_state.overall_score <= 100.0

    def test_parallel_branches_execute(self):
        """Verify that parallel agents (PEP, Sanctions, Country, FATF) all run."""
        from app.agents.orchestrator.agent import OrchestratorAgent
        state = make_state()
        orchestrator = OrchestratorAgent(db_session=None)
        final_state = run_async(orchestrator.run(state))
        completed = final_state.completed_agents
        parallel_agents = ["pep_agent", "sanctions_agent", "country_risk_agent", "fatf_agent"]
        ran = [a for a in parallel_agents if a in completed]
        assert len(ran) == len(parallel_agents), f"Not all parallel agents ran: missing {set(parallel_agents) - set(ran)}"


if __name__ == "__main__":
    # Run basic smoke tests
    print("Running Phase 5/6/7 smoke tests...")

    # Registry check
    t = TestAgentRegistry()
    t.test_all_agents_registered()
    print("✓ All agents registered")

    # Risk scoring
    t2 = TestRiskScoringAgent()
    t2.test_low_risk_score()
    t2.test_high_risk_score()
    t2.test_configurable_weights()
    print("✓ RiskScoringAgent tests passed")

    # Decision
    t3 = TestDecisionAgent()
    t3.test_approve_low_risk()
    t3.test_reject_confirmed_sanctions()
    print("✓ DecisionAgent tests passed")

    # Monitoring
    t4 = TestMonitoringAgent()
    t4.test_low_risk_frequency()
    t4.test_high_risk_frequency()
    print("✓ MonitoringAgent tests passed")

    # Orchestrator
    t5 = TestOrchestratorAgent()
    t5.test_individual_workflow_completes()
    t5.test_risk_score_generated()
    t5.test_parallel_branches_execute()
    print("✓ OrchestratorAgent tests passed")

    print("\n✅ All Phase 5/6/7 tests PASSED")
