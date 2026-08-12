import time
from uuid import UUID
from celery import shared_task
from app.core.database import SessionLocalSync
from app.models.models import Customer, Document, KYCProfile
from app.services.screening_service import ScreeningService
from app.services.document_verification import DocumentVerificationService


@shared_task(name="tasks.kyc_tasks.run_aml_kyc_pipeline")
def run_aml_kyc_pipeline(customer_id: str):
    """
    Executes the main LangGraph Agentic Pipeline.
    Invokes all agents, runs Risk Engine, and writes decisions to database.
    """
    print(
        f"[CELERY] Starting Agentic AML + KYC pipeline execution for customer: {customer_id}"
    )
    try:
        result = ScreeningService.run_screening(customer_id)
        print(
            f"[CELERY] Pipeline completed for customer: {customer_id}. Results: {result}"
        )
        return result
    except Exception as e:
        print(f"[CELERY] Pipeline execution failed: {e}")
        raise e


@shared_task(name="tasks.kyc_tasks.extract_document_ocr")
def extract_document_ocr(document_id: str):
    """
    Triggers Stage A of the production document verification pipeline:
    Duplicate checks, classification agent, quality agent, modular OCR.
    """
    print(f"[CELERY] Beginning OCR scan on document ID: {document_id}")

    db = SessionLocalSync()
    try:
        doc_uuid = UUID(document_id)
        res = DocumentVerificationService.run_pre_ocr_checks(db, doc_uuid)
        print(f"[CELERY] OCR pre-checks finished. Result: {res}")
        return {
            "status": "success",
            "document_id": document_id,
            "stage": "pre_ocr_completed",
        }
    except Exception as e:
        db.rollback()
        print(f"[CELERY] Error executing OCR extraction task: {e}")
        raise e
    finally:
        db.close()
