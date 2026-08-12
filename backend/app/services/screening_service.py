"""
Screening Service
==================
Orchestrates the full AML/KYC compliance screening workflow for a customer.

This service is the primary entry point called by the API layer.
It:
  1. Loads the customer + all related data from the database
  2. Builds an AgentState (pydantic model) with all relevant data
  3. Calls OrchestratorAgent.run(state) — the full LangGraph workflow
  4. Saves risk score, alerts, cases, monitoring schedule, and audit logs
  5. Returns a structured final response

The old sequential LangGraph TypedDict implementation is preserved below as
`LegacyScreeningService` for backward-compatibility and is not deleted.
"""

import logging
import asyncio
from typing import TypedDict, List, Optional, Dict, Any
from uuid import UUID, uuid4
from datetime import date, datetime

from sqlalchemy import select

from app.core.database import SessionLocalSync
from app.models.models import (
    Customer,
    KYCProfile,
    Document,
    Case,
    Alert,
    RiskScore,
    AgentLog,
    Account,
    Transaction,
    Company,
    Director,
    UBO,
    PolicyRule,
)
from app.agents.base.agent_state import AgentState as PydanticAgentState
from app.agents.base.agent_context import AgentContext
from app.agents.orchestrator.agent import OrchestratorAgent

# ── Import all agents to ensure they self-register via @AgentRegistry.register ──
from app.agents.kyc.agent import KycAgent  # noqa: F401
from app.agents.pep.agent import PepAgent  # noqa: F401
from app.agents.sanctions.agent import SanctionsAgent  # noqa: F401
from app.agents.country.agent import CountryRiskAgent  # noqa: F401
from app.agents.transaction.agent import TransactionAgent  # noqa: F401
from app.agents.company.agent import CompanyAgent  # noqa: F401
from app.agents.document.agent import DocumentVerificationAgent  # noqa: F401
from app.agents.fatf.agent import FATFAgent  # noqa: F401
from app.agents.ubo.agent import UBOVerificationAgent  # noqa: F401
from app.agents.director.agent import DirectorVerificationAgent  # noqa: F401
from app.agents.account.agent import AccountBehaviorAgent  # noqa: F401
from app.agents.regulation.agent import RegulationAgent  # noqa: F401
from app.agents.risk.agent import RiskScoringAgent  # noqa: F401
from app.agents.investigation.agent import InvestigationAgent  # noqa: F401
from app.agents.decision.agent import DecisionAgent  # noqa: F401
from app.agents.monitoring.agent import MonitoringAgent  # noqa: F401

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Primary Screening Service
# ──────────────────────────────────────────────────────────────────────────────


class ScreeningService:
    """
    AML/KYC Compliance Screening Service.
    Coordinates full compliance screening via OrchestratorAgent.
    """

    @staticmethod
    def run_screening(customer_id: str) -> Dict[str, Any]:
        """
        Synchronous entry point that runs the full async screening workflow.
        Called by Celery tasks and API routes that need sync compatibility.
        """
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We are inside an async context (e.g. FastAPI) — use thread pool
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(
                        asyncio.run, ScreeningService._run_async(customer_id)
                    )
                    return future.result()
            else:
                return loop.run_until_complete(ScreeningService._run_async(customer_id))
        except RuntimeError:
            # No event loop — create one
            return asyncio.run(ScreeningService._run_async(customer_id))

    @staticmethod
    async def run_screening_async(customer_id: str) -> Dict[str, Any]:
        """Async entry point — used by async FastAPI endpoints."""
        return await ScreeningService._run_async(customer_id)

    @staticmethod
    async def _run_async(customer_id: str) -> Dict[str, Any]:
        """
        Full async screening workflow:
        1. Load data from DB
        2. Build AgentState
        3. Run OrchestratorAgent
        4. Persist results
        5. Return response
        """
        logger.info(
            f"ScreeningService: Starting compliance screening for customer {customer_id}."
        )

        db = SessionLocalSync()
        try:
            cust_uuid = UUID(customer_id)

            # ── Load Customer ─────────────────────────────────────────────────
            customer = db.query(Customer).filter(Customer.id == cust_uuid).first()
            if not customer:
                raise ValueError(f"Customer {customer_id} not found.")

            kyc = (
                db.query(KYCProfile).filter(KYCProfile.customer_id == cust_uuid).first()
            )
            if not kyc:
                raise ValueError(f"KYC profile missing for customer {customer_id}.")

            # ── Create Case ───────────────────────────────────────────────────
            case = Case(
                customer_id=cust_uuid,
                priority="medium",
                status="investigating",
                investigation_notes="Compliance review case provisioned. Automated screening initialized.",
                sar_filed=False,
            )
            db.add(case)
            db.commit()
            db.refresh(case)

            # ── Load Related Data ─────────────────────────────────────────────
            documents = (
                db.query(Document).filter(Document.customer_id == cust_uuid).all()
            )
            accounts = db.query(Account).filter(Account.customer_id == cust_uuid).all()
            companies = db.query(Company).filter(Company.customer_id == cust_uuid).all()

            company_ids = [c.id for c in companies]
            directors: List[Director] = []
            ubos: List[UBO] = []
            for cid in company_ids:
                directors += db.query(Director).filter(Director.company_id == cid).all()
                ubos += db.query(UBO).filter(UBO.company_id == cid).all()

            account_ids = [a.id for a in accounts]
            transactions: List[Transaction] = []
            for aid in account_ids:
                transactions += (
                    db.query(Transaction)
                    .filter(Transaction.sender_account_id == aid)
                    .order_by(Transaction.created_at)
                    .limit(200)
                    .all()
                )

            logger.info(
                f"ScreeningService: Found {len(accounts)} accounts and {len(transactions)} transactions for customer {cust_uuid}"
            )
            policies = db.query(PolicyRule).filter(PolicyRule.is_active == True).all()

            # ── Build AgentState ──────────────────────────────────────────────
            customer_dict = {
                "id": str(customer.id),
                "customer_type": customer.customer_type,
                "first_name": customer.first_name,
                "last_name": customer.last_name,
                "dob": customer.dob.isoformat() if customer.dob else None,
                "nationality": customer.nationality,
                "phone_number": customer.phone_number,
                "street_address": customer.street_address,
                "city": customer.city,
                "postal_code": customer.postal_code,
                "country": customer.country,
                "status": customer.status,
                "name": f"{customer.first_name or ''} {customer.last_name or ''}".strip(),
            }

            kyc_dict = {
                "full_name": kyc.full_name,
                "date_of_birth": (
                    kyc.date_of_birth.isoformat() if kyc.date_of_birth else None
                ),
                "nationality": kyc.nationality,
                "address": kyc.address,
                "source_of_funds": kyc.source_of_funds,
                "source_of_wealth": kyc.source_of_wealth,
                "occupation": kyc.occupation,
                "risk_category": kyc.risk_category,
                "annual_income_range": kyc.annual_income_range,
                "tax_residency": kyc.tax_residency,
                "expected_activity_desc": kyc.expected_activity_desc,
                "notes": kyc.notes,
            }

            docs_list = [
                {
                    "id": str(d.id),
                    "document_type": d.document_type,
                    "file_name": d.file_name,
                    "file_path": d.file_path,
                    "content_type": d.content_type,
                    "file_size": d.file_size,
                    "ocr_data": d.ocr_data or {},
                    "verification_status": d.verification_status,
                    "verification_metadata": d.verification_metadata or {},
                }
                for d in documents
            ]

            accounts_list = [
                {
                    "id": str(a.id),
                    "account_number": a.account_number,
                    "sort_code": a.sort_code,
                    "currency": a.currency,
                    "balance": float(a.balance),
                    "status": a.status,
                    "created_at": a.created_at.isoformat(),
                }
                for a in accounts
            ]

            transactions_list = [
                {
                    "id": str(t.id),
                    "transaction_id": str(t.id),
                    "sender_account_id": str(t.sender_account_id),
                    "account_id": str(t.sender_account_id),
                    "receiver_account_number": t.receiver_account_number,
                    "receiver_sort_code": t.receiver_sort_code,
                    "receiver_name": t.receiver_name,
                    "receiver_country": t.receiver_country,
                    "originating_country": "United Kingdom",
                    "destination_country": t.receiver_country,
                    "amount": float(t.amount),
                    "currency": t.currency,
                    "transaction_type": t.transaction_type,
                    "direction": "OUTFLOW",
                    "timestamp": t.created_at.isoformat() if t.created_at else datetime.utcnow().isoformat(),
                    "status": t.status,
                    "reference": t.reference,
                    "created_at": t.created_at.isoformat() if t.created_at else datetime.utcnow().isoformat(),
                }
                for t in transactions
            ]

            companies_list = [
                {
                    "id": str(c.id),
                    "company_name": c.company_name,
                    "registration_number": c.registration_number,
                    "registered_address": c.registered_address,
                    "trading_address": c.trading_address,
                    "country_of_incorporation": c.country_of_incorporation,
                    "incorporation_date": (
                        c.incorporation_date.isoformat()
                        if c.incorporation_date
                        else None
                    ),
                    "sic_code": c.sic_code,
                    "status": c.status,
                }
                for c in companies
            ]

            directors_list = [
                {
                    "id": str(d.id),
                    "first_name": d.first_name,
                    "last_name": d.last_name,
                    "dob": d.dob.isoformat() if d.dob else None,
                    "nationality": d.nationality,
                    "appointment_date": (
                        d.appointment_date.isoformat() if d.appointment_date else None
                    ),
                    "is_active": d.is_active,
                    "verification_status": d.verification_status,
                }
                for d in directors
            ]

            ubos_list = [
                {
                    "id": str(u.id),
                    "first_name": u.first_name,
                    "last_name": u.last_name,
                    "dob": u.dob.isoformat() if u.dob else None,
                    "nationality": u.nationality,
                    "ownership_percentage": float(u.ownership_percentage),
                    "control_type": u.control_type,
                    "verification_status": u.verification_status,
                }
                for u in ubos
            ]

            policies_list = [
                {
                    "rule_name": p.rule_name,
                    "rule_type": p.rule_type,
                    "conditions": p.conditions,
                    "is_active": p.is_active,
                }
                for p in policies
            ]

            # ── Build AgentState ──────────────────────────────────────────────
            initial_state = PydanticAgentState(
                customer_id=str(customer.id),
                case_id=str(case.id),
                customer=customer_dict,
                customer_profile=kyc_dict,
                kyc_profile=kyc_dict,
                uploaded_documents=docs_list,
                accounts=accounts_list,
                transactions=transactions_list,
                companies=companies_list,
                directors=directors_list,
                ubos=ubos_list,
                policies=policies_list,
                logs=[
                    "AgentState initialized. Compliance screening workflow starting."
                ],
            )

            # ── Run OrchestratorAgent ─────────────────────────────────────────
            context = AgentContext(
                db_session=db,
                config={"case_id": str(case.id)},
            )
            orchestrator = OrchestratorAgent(db_session=db, context=context)
            final_state = await orchestrator.run(initial_state)

            # ── Persist Agent Logs to DB ──────────────────────────────────────
            for hist_entry in final_state.execution_history:
                try:
                    log_record = AgentLog(
                        case_id=case.id,
                        agent_name=hist_entry.get("agent", "unknown"),
                        step_name=hist_entry.get("version", "execute"),
                        input_state={},
                        output_state={
                            "status": hist_entry.get("status"),
                            "reason": hist_entry.get("reason"),
                            "timing": hist_entry.get("execution_time_ms"),
                        },
                        execution_time_ms=int(hist_entry.get("execution_time_ms") or 0),
                    )
                    db.add(log_record)
                except Exception as log_err:
                    logger.warning(
                        f"ScreeningService: Could not write agent log: {log_err}"
                    )

            # ── Update Case ───────────────────────────────────────────────────
            final_case = db.query(Case).filter(Case.id == case.id).first()
            if final_case:
                sm = final_state.shared_metadata
                summary = sm.get("investigation_summary", "")
                final_case.investigation_notes = (
                    (final_case.investigation_notes or "")
                    + f"\nScreening complete. Score={final_state.overall_score:.1f}, "
                    f"Decision={final_state.final_decision}, "
                    f"Risk={final_state.risk_tier.upper()}.\n{summary[:500]}"
                )
                if final_state.final_decision in ("REJECT", "EDD_REQUIRED"):
                    final_case.priority = "high"
                elif final_state.final_decision == "MANUAL_REVIEW":
                    final_case.priority = "medium"
                if final_state.final_decision == "APPROVE":
                    final_case.status = "resolved_auto"

            db.commit()
            logger.info(
                f"ScreeningService: Screening complete for {customer_id}. "
                f"Score={final_state.overall_score:.1f}, Decision={final_state.final_decision}."
            )

            return {
                "status": "success",
                "customer_id": customer_id,
                "case_id": str(case.id),
                "score": final_state.overall_score,
                "tier": final_state.risk_tier,
                "decision": final_state.final_decision,
                "decision_reason": final_state.decision_reason,
                "referred": final_state.final_decision != "APPROVE",
                "monitoring_schedule": final_state.monitoring_schedule,
                "investigation_summary": final_state.shared_metadata.get(
                    "investigation_summary", ""
                ),
                "sar_explanation": final_state.shared_metadata.get(
                    "sar_explanation", ""
                ),
                "contributing_factors": final_state.shared_metadata.get(
                    "contributing_factors", []
                ),
                "agents_completed": final_state.completed_agents,
                "execution_logs": final_state.logs[-20:],  # Last 20 log entries
            }

        except Exception as exc:
            logger.error(f"ScreeningService: Screening failed for {customer_id}: {exc}")
            try:
                db.rollback()
            except Exception:
                pass
            raise
        finally:
            db.close()


# ──────────────────────────────────────────────────────────────────────────────
# Legacy Compatibility — kept for backward-compatibility, NOT removed
# ──────────────────────────────────────────────────────────────────────────────


class AgentState(TypedDict):
    """Legacy TypedDict AgentState — preserved for backward-compatibility."""

    customer_id: str
    case_id: str
    full_name: str
    dob: Optional[date]
    nationality: str
    country: str
    address: str
    source_of_funds: str
    source_of_wealth: str
    occupation: Optional[str]
    pep_match: bool
    pep_details: Optional[str]
    sanctions_match: bool
    sanctions_details: Optional[str]
    country_risk_tier: str
    country_risk_reason: Optional[str]
    doc_match: bool
    doc_match_details: Optional[str]
    overall_score: float
    risk_tier: str
    risk_breakdown: Dict[str, Any]
    alert_triggered: bool
    logs: List[str]


def log_agent_step(
    db,
    case_id: str,
    agent_name: str,
    step_name: str,
    input_state: dict,
    output_state: dict,
):
    """Legacy utility to write execution logs into the agent_logs table."""
    try:
        log_record = AgentLog(
            case_id=UUID(case_id),
            agent_name=agent_name,
            step_name=step_name,
            input_state=input_state,
            output_state=output_state,
            execution_time_ms=100,
        )
        db.add(log_record)
        db.commit()
    except Exception as e:
        logger.error(f"Failed to write agent log: {e}")
        db.rollback()
