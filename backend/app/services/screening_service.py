import logging
from typing import TypedDict, List, Optional, Dict, Any
from uuid import UUID, uuid4
from datetime import date, datetime
from sqlalchemy.future import select
from langgraph.graph import StateGraph, END

from app.core.database import SessionLocalSync
from app.models.models import (
    Customer, KYCProfile, Document, Case, Alert, RiskScore, AgentLog
)

logger = logging.getLogger(__name__)

class AgentState(TypedDict):
    customer_id: str
    case_id: str
    
    # Customer Details
    full_name: str
    dob: Optional[date]
    nationality: str
    country: str
    address: str
    source_of_funds: str
    source_of_wealth: str
    occupation: Optional[str]
    
    # Agent Outputs
    pep_match: bool
    pep_details: Optional[str]
    
    sanctions_match: bool
    sanctions_details: Optional[str]
    
    country_risk_tier: str  # "low", "medium", "high"
    country_risk_reason: Optional[str]
    
    doc_match: bool
    doc_match_details: Optional[str]
    
    # Risk Engine Outputs
    overall_score: float
    risk_tier: str
    risk_breakdown: Dict[str, Any]
    
    # Control/Audit parameters
    alert_triggered: bool
    logs: List[str]


def log_agent_step(db, case_id: str, agent_name: str, step_name: str, input_state: dict, output_state: dict):
    """Utility to write execution logs into the agent_logs table."""
    try:
        log_record = AgentLog(
            case_id=UUID(case_id),
            agent_name=agent_name,
            step_name=step_name,
            input_state=input_state,
            output_state=output_state,
            execution_time_ms=100
        )
        db.add(log_record)
        db.commit()
    except Exception as e:
        logger.error(f"Failed to write agent log: {e}")
        db.rollback()


# --- AGENTS IMPLEMENTATION ---

def country_risk_agent(state: AgentState) -> Dict[str, Any]:
    db = SessionLocalSync()
    log_msg = "Country Risk Agent: Evaluation started."
    
    high_risk_countries = {"iran", "north korea", "syria", "russia", "cuba"}
    med_risk_countries = {"spain", "italy", "australia", "colombia", "panama"}
    
    nationality_clean = (state["nationality"] or "").strip().lower()
    country_clean = (state["country"] or "").strip().lower()
    
    tier = "low"
    reason = "Low geographic risk."
    
    if nationality_clean in high_risk_countries or country_clean in high_risk_countries:
        tier = "high"
        reason = f"High-risk jurisdiction exposure detected (Nationality: {state['nationality']}, Resident Country: {state['country']})."
    elif nationality_clean in med_risk_countries or country_clean in med_risk_countries:
        tier = "medium"
        reason = f"Medium-risk jurisdiction exposure detected (Nationality: {state['nationality']}, Resident Country: {state['country']})."
        
    log_msg = f"Country Risk Agent completed. Risk: {tier.upper()} ({reason})"
    
    output = {
        "country_risk_tier": tier,
        "country_risk_reason": reason,
        "logs": state["logs"] + [log_msg]
    }
    
    log_agent_step(
        db=db,
        case_id=state["case_id"],
        agent_name="CountryRiskAgent",
        step_name="AssessJurisdictionRisk",
        input_state={"nationality": state["nationality"], "country": state["country"]},
        output_state={"tier": tier, "reason": reason}
    )
    db.close()
    return output


def pep_agent(state: AgentState) -> Dict[str, Any]:
    db = SessionLocalSync()
    pep_match = False
    details = "No PEP flags identified."
    
    occupation_clean = (state["occupation"] or "").strip().lower()
    full_name_clean = (state["full_name"] or "").strip().lower()
    
    # Occupation contains typical political keywords, or name matches dummy PEP
    pep_keywords = {"politician", "minister", "senator", "governor", "diplomat", "ambassador"}
    
    if any(kw in occupation_clean for kw in pep_keywords):
        pep_match = True
        details = f"Flagged due to high-risk PEP occupation: '{state['occupation']}'."
    elif "jack roberts" in full_name_clean:
        pep_match = True
        details = "Flagged: Name matched simulated PEP registry record for Jack Roberts."
        
    log_msg = f"PEP Agent completed. Match: {pep_match} ({details})"
    
    output = {
        "pep_match": pep_match,
        "pep_details": details,
        "logs": state["logs"] + [log_msg]
    }
    
    log_agent_step(
        db=db,
        case_id=state["case_id"],
        agent_name="PEPAgent",
        step_name="ScreenRegistry",
        input_state={"full_name": state["full_name"], "occupation": state["occupation"]},
        output_state={"pep_match": pep_match, "details": details}
    )
    db.close()
    return output


def sanctions_agent(state: AgentState) -> Dict[str, Any]:
    db = SessionLocalSync()
    sanctions_match = False
    details = "Clean status: No sanctions matches found."
    
    full_name_clean = (state["full_name"] or "").strip().lower()
    
    if "charlie brown" in full_name_clean:
        sanctions_match = True
        details = "Sanctions Match Flag: Charlie Brown is registered on the UK Consolidated Sanctions target list."
    elif state["country_risk_tier"] == "high":
        sanctions_match = True
        details = f"Sanctions Match Flag: Risk associated with high-risk jurisdiction residency ({state['country']})."
        
    log_msg = f"Sanctions Agent completed. Match: {sanctions_match} ({details})"
    
    output = {
        "sanctions_match": sanctions_match,
        "sanctions_details": details,
        "logs": state["logs"] + [log_msg]
    }
    
    log_agent_step(
        db=db,
        case_id=state["case_id"],
        agent_name="SanctionsAgent",
        step_name="ScreenOFAC_OFSI",
        input_state={"full_name": state["full_name"], "country_risk_tier": state["country_risk_tier"]},
        output_state={"sanctions_match": sanctions_match, "details": details}
    )
    db.close()
    return output


def doc_match_agent(state: AgentState) -> Dict[str, Any]:
    db = SessionLocalSync()
    doc_match = True
    details = "All uploaded document OCR details match customer declarations."
    
    cust_uuid = UUID(state["customer_id"])
    docs = db.query(Document).filter(
        Document.customer_id == cust_uuid,
        Document.verification_status == "verified"
    ).all()
    
    if not docs:
        doc_match = False
        details = "No verified documents uploaded for verification check."
    else:
        for doc in docs:
            if doc.ocr_data:
                ocr_name = (doc.ocr_data.get("full_name") or "").strip().lower()
                decl_name = state["full_name"].strip().lower()
                
                # Check for name discrepancies
                if ocr_name and ocr_name != decl_name:
                    doc_match = False
                    details = f"Name mismatch on document ({doc.document_type}): declared '{state['full_name']}' but OCR read '{doc.ocr_data.get('full_name')}'."
                    break
                    
                # Check for DOB discrepancies
                ocr_dob = doc.ocr_data.get("dob")
                decl_dob = state["dob"]
                
                if ocr_dob and decl_dob:
                    # Convert string to date for comparison if needed
                    if isinstance(ocr_dob, str):
                        try:
                            ocr_dob = datetime.strptime(ocr_dob, "%Y-%m-%d").date()
                        except ValueError:
                            pass
                    if ocr_dob != decl_dob:
                        doc_match = False
                        details = f"DOB mismatch on document ({doc.document_type}): declared {state['dob']} but OCR read {doc.ocr_data.get('dob')}."
                        break
                        
    log_msg = f"Document Match Agent completed. Match: {doc_match} ({details})"
    
    output = {
        "doc_match": doc_match,
        "doc_match_details": details,
        "logs": state["logs"] + [log_msg]
    }
    
    log_agent_step(
        db=db,
        case_id=state["case_id"],
        agent_name="DocumentMatchAgent",
        step_name="CrossCheckOCR",
        input_state={"full_name": state["full_name"], "dob": str(state["dob"])},
        output_state={"doc_match": doc_match, "details": details}
    )
    db.close()
    return output


def risk_engine(state: AgentState) -> Dict[str, Any]:
    db = SessionLocalSync()
    score = 0.0
    breakdown = {}
    
    # 1. Sanctions component (35%)
    if state["sanctions_match"]:
        score += 35.0
        breakdown["sanctions"] = 35.0
    else:
        breakdown["sanctions"] = 0.0
        
    # 2. PEP component (25%)
    if state["pep_match"]:
        score += 25.0
        breakdown["pep"] = 25.0
    else:
        breakdown["pep"] = 0.0
        
    # 3. Geographic risk component (20%)
    if state["country_risk_tier"] == "high":
        score += 20.0
        breakdown["jurisdiction"] = 20.0
    elif state["country_risk_tier"] == "medium":
        score += 10.0
        breakdown["jurisdiction"] = 10.0
    else:
        breakdown["jurisdiction"] = 0.0
        
    # 4. Document Verification integrity (20%)
    if not state["doc_match"]:
        score += 20.0
        breakdown["documents"] = 20.0
    else:
        breakdown["documents"] = 0.0
        
    # 5. Incremental risks: funds source
    funds_source = (state["source_of_funds"] or "").strip().lower()
    if funds_source in ["cryptocurrency", "gambling", "cash"]:
        score += 10.0
        breakdown["source_of_funds"] = 10.0
        
    # Clamp score to max 100
    score = min(score, 100.0)
    
    tier = "low"
    if score >= 70.0:
        tier = "high"
    elif score >= 40.0:
        tier = "medium"
        
    log_msg = f"Risk Engine completed. Score: {score}, Tier: {tier.upper()}"
    
    output = {
        "overall_score": score,
        "risk_tier": tier,
        "risk_breakdown": breakdown,
        "logs": state["logs"] + [log_msg]
    }
    
    log_agent_step(
        db=db,
        case_id=state["case_id"],
        agent_name="RiskEngine",
        step_name="CalculateRiskWeights",
        input_state={
            "sanctions": state["sanctions_match"],
            "pep": state["pep_match"],
            "country_risk": state["country_risk_tier"],
            "doc_match": state["doc_match"]
        },
        output_state={"overall_score": score, "risk_tier": tier, "breakdown": breakdown}
    )
    db.close()
    return output


def alert_engine(state: AgentState) -> Dict[str, Any]:
    db = SessionLocalSync()
    alert_triggered = False
    
    cust_uuid = UUID(state["customer_id"])
    customer = db.query(Customer).filter(Customer.id == cust_uuid).first()
    
    # Trigger threshold for alerts and manual case escalation
    if state["overall_score"] >= 50.0 or state["pep_match"] or state["sanctions_match"]:
        alert_triggered = True
        
        # 1. Create Alert record
        alert_type = "high_risk_score"
        if state["pep_match"] or state["sanctions_match"]:
            alert_type = "pep_sanctions_match"
            
        alert = Alert(
            customer_id=cust_uuid,
            alert_type=alert_type,
            risk_score=state["overall_score"],
            status="open",
            alert_metadata={
                "breakdown": state["risk_breakdown"],
                "pep": state["pep_details"],
                "sanctions": state["sanctions_details"],
                "country_risk": state["country_risk_reason"],
                "doc_match": state["doc_match_details"]
            }
        )
        db.add(alert)
        
        # 2. Escalated Case details
        case = db.query(Case).filter(Case.id == UUID(state["case_id"])).first()
        if case:
            case.priority = "high" if state["overall_score"] >= 70.0 else "medium"
            case.status = "open"
            case.investigation_notes = f"Auto-escalated due to triggers: {state['country_risk_reason']} {state['pep_details']} {state['sanctions_details']} {state['doc_match_details']}"
            
        # 3. Update customer compliance status
        if customer:
            customer.status = "referred"
            
    else:
        # Auto-approved
        if customer:
            customer.status = "approved"
            
        case = db.query(Case).filter(Case.id == UUID(state["case_id"])).first()
        if case:
            case.status = "resolved_auto"
            case.investigation_notes = "Auto-resolved: Customer risk profile matches auto-onboarding compliance threshold."
            
    # 4. Save RiskScore record
    risk_score_record = RiskScore(
        customer_id=cust_uuid,
        overall_score=state["overall_score"],
        risk_tier=state["risk_tier"],
        breakdown=state["risk_breakdown"]
    )
    db.add(risk_score_record)
    
    # 5. Write KYC profile risk category sync
    kyc_profile = db.query(KYCProfile).filter(KYCProfile.customer_id == cust_uuid).first()
    if kyc_profile:
        kyc_profile.risk_category = state["risk_tier"]
        kyc_profile.screening_completed_at = datetime.utcnow()
        
    db.commit()
    
    log_msg = f"Alert Engine finalized. Alert Triggered: {alert_triggered}. Customer status set to: {customer.status if customer else 'Unknown'}"
    
    output = {
        "alert_triggered": alert_triggered,
        "logs": state["logs"] + [log_msg]
    }
    
    log_agent_step(
        db=db,
        case_id=state["case_id"],
        agent_name="AlertEngine",
        step_name="CommitDecisions",
        input_state={"overall_score": state["overall_score"], "alert_triggered": alert_triggered},
        output_state={"customer_status": customer.status if customer else "None"}
    )
    db.close()
    return output


# --- SERVICE DEFINITION ---

class ScreeningService:
    @staticmethod
    def run_screening(customer_id: str) -> Dict[str, Any]:
        """
        Orchestrates the entire screening execution using LangGraph.
        Reads profile, spins up nodes, updates PostgreSQL sync.
        """
        logger.info(f"Setting up LangGraph AML loop for customer {customer_id}...")
        
        db = SessionLocalSync()
        cust_uuid = UUID(customer_id)
        
        customer = db.query(Customer).filter(Customer.id == cust_uuid).first()
        if not customer:
            db.close()
            raise ValueError(f"Customer with ID {customer_id} not found in database.")
            
        kyc = db.query(KYCProfile).filter(KYCProfile.customer_id == cust_uuid).first()
        if not kyc:
            db.close()
            raise ValueError(f"KYC profile declarations missing for customer {customer_id}.")
            
        # Create an onboarding Case to capture agent logs and case files
        case = Case(
            customer_id=cust_uuid,
            priority="medium",
            status="investigating",
            investigation_notes="Compliance review case provisioned. Automated screening initialized.",
            sar_filed=False
        )
        db.add(case)
        db.commit()
        db.refresh(case)
        
        # Build initial state
        initial_state = AgentState(
            customer_id=str(customer.id),
            case_id=str(case.id),
            full_name=kyc.full_name,
            dob=kyc.date_of_birth,
            nationality=kyc.nationality,
            country=customer.country or kyc.nationality,
            address=kyc.address,
            source_of_funds=kyc.source_of_funds,
            source_of_wealth=kyc.source_of_wealth,
            occupation=kyc.occupation,
            
            # Default placeholders
            pep_match=False,
            pep_details=None,
            sanctions_match=False,
            sanctions_details=None,
            country_risk_tier="low",
            country_risk_reason=None,
            doc_match=True,
            doc_match_details=None,
            overall_score=0.0,
            risk_tier="low",
            risk_breakdown={},
            alert_triggered=False,
            logs=["State Initialized. Onboarding review Case created."]
        )
        
        # Compile StateGraph
        workflow = StateGraph(AgentState)
        
        workflow.add_node("country_risk", country_risk_agent)
        workflow.add_node("pep_agent", pep_agent)
        workflow.add_node("sanctions_agent", sanctions_agent)
        workflow.add_node("doc_match_agent", doc_match_agent)
        workflow.add_node("risk_engine", risk_engine)
        workflow.add_node("alert_engine", alert_engine)
        
        workflow.set_entry_point("country_risk")
        workflow.add_edge("country_risk", "pep_agent")
        workflow.add_edge("pep_agent", "sanctions_agent")
        workflow.add_edge("sanctions_agent", "doc_match_agent")
        workflow.add_edge("doc_match_agent", "risk_engine")
        workflow.add_edge("risk_engine", "alert_engine")
        workflow.add_edge("alert_engine", END)
        
        graph_app = workflow.compile()
        
        # Execute Graph
        logger.info(f"Invoking graph workflow for Case {case.id}...")
        final_state = graph_app.invoke(initial_state)
        
        # Commit logs update back to case
        case_refreshed = db.query(Case).filter(Case.id == case.id).first()
        if case_refreshed:
            case_refreshed.investigation_notes = (
                case_refreshed.investigation_notes or ""
            ) + f"\nScreening Summary: Score={final_state['overall_score']}, Tier={final_state['risk_tier'].upper()}, Alert={final_state['alert_triggered']}"
            db.commit()
            
        db.close()
        return {
            "status": "success",
            "score": final_state["overall_score"],
            "tier": final_state["risk_tier"],
            "referred": final_state["alert_triggered"],
            "case_id": str(case.id)
        }
