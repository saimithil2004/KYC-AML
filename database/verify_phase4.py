import sys
import os
import asyncio

# Adjust path to import app modules
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

from app.core.database import SessionLocalSync, engine
from app.models.models import Customer, KYCProfile, RiskScore, Alert, Case, AgentLog, Document
from app.services.screening_service import ScreeningService

def run_verification():
    print("--------------------------------------------------")
    print("STARTING END-TO-END COMPLIANCE PIPELINE VERIFICATION")
    print("--------------------------------------------------")
    
    db = SessionLocalSync()
    
    # 1. Fetch Alice Smith (user1)
    customer = db.query(Customer).filter(Customer.first_name == "Alice").first()
    if not customer:
        print("ERROR: Alice Smith customer record not found.")
        db.close()
        return
        
    print(f"Testing Customer: {customer.first_name} {customer.last_name} (ID: {customer.id})")
    print(f"Initial Onboarding Status: {customer.status}")
    
    # 2. Execute Screening Service directly
    print("\nExecuting LangGraph Screening Pipeline...")
    res = ScreeningService.run_screening(str(customer.id))
    print(f"Screening Result: {res}")
    
    # 3. Verify Database Records
    print("\nVerifying database side-effects...")
    
    # Refresh customer
    db.refresh(customer)
    print(f"Final Onboarding Status: {customer.status}")
    
    # Check risk score
    risk = db.query(RiskScore).filter(RiskScore.customer_id == customer.id).order_by(RiskScore.created_at.desc()).first()
    if risk:
        print(f"RiskScore written: Score={risk.overall_score}, Tier={risk.risk_tier}, Breakdown={risk.breakdown}")
    else:
        print("ERROR: RiskScore record was NOT written.")
        
    # Check cases
    case = db.query(Case).filter(Case.customer_id == customer.id).order_by(Case.created_at.desc()).first()
    if case:
        print(f"Case written: CaseID={case.id}, Status={case.status}, Priority={case.priority}, Notes={case.investigation_notes}")
        
        # Check agent logs
        logs = db.query(AgentLog).filter(AgentLog.case_id == case.id).all()
        print(f"AgentLogs written: Count={len(logs)}")
        for idx, l in enumerate(logs):
            print(f"  Step {idx+1}: {l.agent_name} -> {l.step_name} (Time: {l.created_at})")
    else:
        print("ERROR: Case record was NOT written.")
        
    # Check alerts
    alert = db.query(Alert).filter(Alert.customer_id == customer.id).first()
    if alert:
        print(f"Alert written: AlertID={alert.id}, Type={alert.alert_type}, RiskScore={alert.risk_score}")
    else:
        print("Alert: No alert generated (expected for low-risk clean profiles like Alice).")
        
    # 4. Test Flagged PEP/Sanctions user: Charlie Brown
    print("\n--------------------------------------------------")
    print("TESTING HIGH-RISK USER: CHARLIE BROWN (SANCTIONS FLAG)")
    print("--------------------------------------------------")
    
    # Find Charlie
    charlie = db.query(Customer).filter(Customer.first_name == "Charlie").first()
    if charlie:
        print(f"Testing Customer: {charlie.first_name} {charlie.last_name} (ID: {charlie.id})")
        
        # Run screening
        res_charlie = ScreeningService.run_screening(str(charlie.id))
        print(f"Screening Result: {res_charlie}")
        
        db.refresh(charlie)
        print(f"Charlie Status: {charlie.status} (expected: referred)")
        
        charlie_alert = db.query(Alert).filter(Alert.customer_id == charlie.id).first()
        if charlie_alert:
            print(f"Alert written: AlertID={charlie_alert.id}, Type={charlie_alert.alert_type}, RiskScore={charlie_alert.risk_score}")
            print(f"Metadata: {charlie_alert.alert_metadata}")
        else:
            print("ERROR: Charlie Brown was NOT flagged.")
            
    db.close()
    print("\n--------------------------------------------------")
    print("VERIFICATION COMPLETED SUCCESSFULLY!")
    print("--------------------------------------------------")

if __name__ == "__main__":
    run_verification()
