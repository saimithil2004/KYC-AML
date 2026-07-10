import time
from uuid import UUID
from app.core.celery_app import celery_app
from app.core.database import SessionLocalSync
from app.models.models import Customer, Document, KYCProfile
from app.services.screening_service import ScreeningService

@celery_app.task(name="tasks.kyc_tasks.run_aml_kyc_pipeline")
def run_aml_kyc_pipeline(customer_id: str):
    """
    Executes the main LangGraph Agentic Pipeline.
    Invokes all agents, runs Risk Engine, and writes decisions to database.
    """
    print(f"[CELERY] Starting Agentic AML + KYC pipeline execution for customer: {customer_id}")
    try:
        result = ScreeningService.run_screening(customer_id)
        print(f"[CELERY] Pipeline completed for customer: {customer_id}. Results: {result}")
        return result
    except Exception as e:
        print(f"[CELERY] Pipeline execution failed: {e}")
        raise e

@celery_app.task(name="tasks.kyc_tasks.extract_document_ocr")
def extract_document_ocr(document_id: str):
    """
    Simulates calling OCR pipeline to extract document values.
    Writes results back to Document.ocr_data and triggers re-screening.
    """
    print(f"[CELERY] Beginning OCR scan on document ID: {document_id}")
    time.sleep(2)  # Simulate document extraction latency
    
    db = SessionLocalSync()
    try:
        doc_uuid = UUID(document_id)
        doc = db.query(Document).filter(Document.id == doc_uuid).first()
        if not doc:
            print(f"[CELERY] Document {document_id} not found in database.")
            return {"status": "error", "reason": "document_not_found"}
            
        customer = db.query(Customer).filter(Customer.id == doc.customer_id).first()
        kyc = db.query(KYCProfile).filter(KYCProfile.customer_id == doc.customer_id).first()
        
        if kyc:
            full_name = kyc.full_name
            # Introduce a mock mismatch for Isabella Thomas (Isabella Thompson) for testing mismatch detection
            if "isabella" in full_name.lower():
                ocr_name = full_name.replace("Thomas", "Thompson")
            else:
                ocr_name = full_name
                
            doc.ocr_data = {
                "full_name": ocr_name,
                "dob": str(kyc.date_of_birth),
                "nationality": kyc.nationality,
                "document_number": f"GB{time.time_ns() % 100000000}"
            }
        else:
            doc.ocr_data = {
                "full_name": customer.first_name + " " + customer.last_name if customer else "Unknown Declarant",
                "dob": str(customer.dob) if customer else None,
                "document_number": f"GB{time.time_ns() % 100000000}"
            }
            
        doc.verification_status = "verified"
        db.commit()
        print(f"[CELERY] OCR successfully extracted details for doc {document_id}. Status set to verified.")
        
        # Trigger customer compliance re-screening pipeline now that documents are verified
        celery_app.send_task(
            "tasks.kyc_tasks.run_aml_kyc_pipeline",
            args=[str(doc.customer_id)]
        )
        return {"status": "verified", "document_id": document_id}
    except Exception as e:
        db.rollback()
        print(f"[CELERY] Error executing OCR extraction: {e}")
        raise e
    finally:
        db.close()
