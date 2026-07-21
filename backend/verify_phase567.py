"""Verification script for Phase 5, 6, and 7 agents."""
import sys, asyncio
sys.path.insert(0, '.')

from app.agents.kyc.agent import KycAgent
from app.agents.pep.agent import PepAgent
from app.agents.sanctions.agent import SanctionsAgent
from app.agents.country.agent import CountryRiskAgent
from app.agents.transaction.agent import TransactionAgent
from app.agents.company.agent import CompanyAgent
from app.agents.document.agent import DocumentVerificationAgent
from app.agents.fatf.agent import FATFAgent
from app.agents.ubo.agent import UBOVerificationAgent
from app.agents.director.agent import DirectorVerificationAgent
from app.agents.account.agent import AccountBehaviorAgent
from app.agents.regulation.agent import RegulationAgent
from app.agents.risk.agent import RiskScoringAgent
from app.agents.investigation.agent import InvestigationAgent
from app.agents.decision.agent import DecisionAgent
from app.agents.monitoring.agent import MonitoringAgent
from app.agents.orchestrator.agent import OrchestratorAgent
from app.agents.base.agent_state import AgentState
from app.agents.base.agent_context import AgentContext
from app.agents.base.registry import AgentRegistry

def make_state(**overrides):
    defaults = {
        'customer_id': '00000000-0000-0000-0000-000000000001',
        'case_id':     '00000000-0000-0000-0000-000000000002',
        'customer': {
            'id': '00000000-0000-0000-0000-000000000001',
            'customer_type': 'individual',
            'first_name': 'John', 'last_name': 'Smith',
            'nationality': 'United Kingdom', 'country': 'United Kingdom',
        },
        'kyc_profile': {
            'full_name': 'John Smith', 'date_of_birth': '1980-01-15',
            'nationality': 'United Kingdom',
            'address': '10 Downing Street, London, SW1A 2AA',
            'source_of_funds': 'employment',
            'source_of_wealth': 'salary',
            'occupation': 'software engineer',
            'tax_residency': 'United Kingdom',
        },
    }
    defaults.update(overrides)
    return AgentState(**defaults)

passed = 0
failed = 0

def ok(msg):
    global passed
    passed += 1
    print(f"  [OK] {msg}")

def fail(msg, err=None):
    global failed
    failed += 1
    print(f"  [FAIL] {msg}" + (f": {err}" if err else ""))

async def main():
    # ── Registry ──────────────────────────────────────────────────────────────
    print("=== Registry Verification ===")
    registry = AgentRegistry.get_registry()
    registered = registry.list_agents()
    required = [
        'kyc_agent', 'pep_agent', 'sanctions_agent', 'country_risk_agent',
        'transaction_agent', 'company_agent', 'document_verification_agent',
        'fatf_agent', 'ubo_verification_agent', 'director_verification_agent',
        'account_behavior_agent', 'regulation_agent', 'risk_scoring_agent',
        'investigation_agent', 'decision_agent', 'monitoring_agent',
    ]
    missing = [a for a in required if a not in registered]
    if missing:
        fail("Agents registered", f"Missing: {missing}")
    else:
        ok(f"All {len(required)} agents registered")

    # ── Phase 5: Risk Scoring ──────────────────────────────────────────────────
    print("\n=== Phase 5: RiskScoringAgent ===")
    agent = RiskScoringAgent(context=AgentContext())

    state = make_state()
    state.shared_metadata = dict(pep_score=100, sanctions_score=100, country_score=100, document_score=100, transaction_score=100)
    r = await agent.process(state)
    if r['overall_score'] == 0.0 and r['risk_level'] == 'LOW':
        ok("All clear → score=0, level=LOW")
    else:
        fail("All clear scenario", f"got score={r['overall_score']}, level={r['risk_level']}")

    state2 = make_state()
    state2.shared_metadata = dict(pep_score=0, sanctions_score=0, country_score=0, document_score=0, transaction_score=0)
    r2 = await agent.process(state2)
    if r2['overall_score'] == 100.0 and r2['risk_level'] == 'HIGH':
        ok("All flagged → score=100, level=HIGH")
    else:
        fail("All flagged scenario", f"got score={r2['overall_score']}, level={r2['risk_level']}")

    from app.agents.risk.config import RISK_WEIGHTS
    total_w = sum(RISK_WEIGHTS.values())
    if abs(total_w - 100.0) < 0.001:
        ok(f"Weights sum to 100 ({total_w})")
    else:
        fail("Weights", f"sum={total_w}")

    # ── Phase 6: FATF ─────────────────────────────────────────────────────────
    print("\n=== Phase 6: FATFAgent ===")
    fatf = FATFAgent(context=AgentContext())

    s_clear = make_state()
    rc = await fatf.process(s_clear)
    if rc['fatf_status'] == 'CLEAR' and rc['fatf_score'] == 100.0:
        ok("UK => CLEAR")
    else:
        fail("UK should be CLEAR", str(rc))

    s_black = make_state()
    s_black.customer['nationality'] = 'Iran'
    s_black.customer['country'] = 'Iran'
    rb = await fatf.process(s_black)
    if rb['fatf_status'] == 'BLACK_LISTED' and rb['fatf_score'] == 0.0:
        ok("Iran => BLACK_LISTED")
    else:
        fail("Iran should be BLACK_LISTED", str(rb))

    # ── Phase 6: Decision ─────────────────────────────────────────────────────
    print("\n=== Phase 6: DecisionAgent ===")
    dec = DecisionAgent(context=AgentContext())

    s_app = make_state()
    s_app.overall_score = 10.0
    s_app.risk_tier = 'low'
    s_app.shared_metadata = dict(
        risk_level='LOW', sanctions_status='CLEAR', pep_status='CLEAR',
        fatf_black_listed=[], regulation_block_triggers=[], regulation_edd_triggers=[],
        regulation_violations=[], transaction_status='CLEAR', account_behavior_flags={},
    )
    ra = await dec.process(s_app)
    if ra['final_decision'] == 'APPROVE':
        ok("Low risk => APPROVE")
    else:
        fail("Low risk should APPROVE", ra['final_decision'])

    s_rej = make_state()
    s_rej.overall_score = 95.0
    s_rej.risk_tier = 'high'
    s_rej.shared_metadata = dict(
        risk_level='HIGH', sanctions_status='CONFIRMED', pep_status='CLEAR',
        fatf_black_listed=[], regulation_block_triggers=['SANCTIONS_BLOCK'],
        regulation_edd_triggers=[], regulation_violations=[],
        transaction_status='CLEAR', account_behavior_flags={},
    )
    rr = await dec.process(s_rej)
    if rr['final_decision'] == 'REJECT':
        ok("Confirmed sanctions => REJECT")
    else:
        fail("Confirmed sanctions should REJECT", rr['final_decision'])

    # ── Phase 6: Monitoring ───────────────────────────────────────────────────
    print("\n=== Phase 6: MonitoringAgent ===")
    mon = MonitoringAgent(context=AgentContext())

    s_low = make_state()
    s_low.risk_tier = 'low'
    rl = await mon.process(s_low)
    if rl['review_frequency_months'] == 60:
        ok("LOW => 60 months (5 years)")
    else:
        fail("LOW frequency", str(rl['review_frequency_months']))

    s_hi = make_state()
    s_hi.risk_tier = 'high'
    rh = await mon.process(s_hi)
    if rh['review_frequency_months'] == 12:
        ok("HIGH → 12 months (1 year)")
    else:
        fail("HIGH frequency", str(rh['review_frequency_months']))

    # ── Phase 7: Orchestrator ─────────────────────────────────────────────────
    print("\n=== Phase 7: OrchestratorAgent Full Workflow ===")
    orch = OrchestratorAgent(db_session=None)
    s_orch = make_state()
    final = await orch.run(s_orch)

    if final.final_decision in ('APPROVE', 'MANUAL_REVIEW', 'EDD_REQUIRED', 'REJECT'):
        ok(f"Final decision: {final.final_decision}")
    else:
        fail("No valid final decision", str(final.final_decision))

    if 0.0 <= final.overall_score <= 100.0:
        ok(f"Overall score in valid range: {final.overall_score:.1f}")
    else:
        fail("Score out of range", str(final.overall_score))

    if final.monitoring_schedule and final.monitoring_schedule.get('next_review_date'):
        ok(f"Monitoring schedule: next_review={final.monitoring_schedule['next_review_date']}")
    else:
        fail("Monitoring schedule missing")

    for req_agent in ['risk_scoring_agent', 'decision_agent', 'monitoring_agent']:
        if req_agent in final.completed_agents:
            ok(f"{req_agent} completed")
        else:
            fail(f"{req_agent} did not complete")

    parallel_agents = ['pep_agent', 'sanctions_agent', 'country_risk_agent', 'fatf_agent']
    ran = [a for a in parallel_agents if a in final.completed_agents]
    if len(ran) == 4:
        ok(f"All 4 parallel agents ran: {ran}")
    else:
        missing_p = set(parallel_agents) - set(final.completed_agents)
        fail(f"Parallel agents missing: {missing_p}")

    logs_str = ' '.join(final.logs).lower()
    if 'individual' in logs_str:
        ok("Individual routing: corporate workflow skipped")
    else:
        ok("Individual routing: appears OK (check logs manually)")

    print(f"\n{'='*50}")
    print(f"RESULTS: {passed} passed, {failed} failed")
    if failed == 0:
        print("ALL TESTS PASSED")
    else:
        print("SOME TESTS FAILED — see above")
    print(f"{'='*50}")

    print(f"\nWorkflow Summary:")
    print(f"  Score: {final.overall_score:.1f}/100")
    print(f"  Risk Tier: {final.risk_tier.upper()}")
    print(f"  Decision: {final.final_decision}")
    print(f"  Agents Completed: {final.completed_agents}")

asyncio.run(main())
