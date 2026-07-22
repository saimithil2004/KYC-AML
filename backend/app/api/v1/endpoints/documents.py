from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from uuid import UUID
from typing import Dict, Any

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.models import User, Customer, Document
from app.schemas.schemas import DocumentResponse
from app.schemas.document_schemas import (
    DocumentVerificationDetailsResponse,
    ReprocessResponse,
)
from app.core.celery_app import celery_app
from app.services.upload_service import UploadService
from app.services.document_verification import DocumentVerificationService

router = APIRouter()


@router.post(
    "/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED
)
async def upload_document(
    customer_id: str = Form(...),
    document_type: str = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        cust_uuid = UUID(customer_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid customer ID formatting.")

    result = await db.execute(select(Customer).where(Customer.id == cust_uuid))
    customer = result.scalars().first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found.")

    if customer.user_id != current_user.id and current_user.role not in [
        "compliance_officer",
        "admin",
    ]:
        raise HTTPException(
            status_code=403, detail="Unauthorized access for this profile."
        )

    file_path, file_size = UploadService.save_customer_document(cust_uuid, file)

    document = Document(
        customer_id=cust_uuid,
        document_type=document_type,
        file_name=file.filename,
        file_path=file_path,
        content_type=file.content_type,
        file_size=file_size,
        verification_status="uploaded",
        verification_metadata={
            "history": [{"timestamp": "now", "event": "file_uploaded"}]
        },
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)

    # Launch OCR analysis asynchronously (Step 11 Workflow: Queue Job)
    celery_app.send_task(
        "tasks.kyc_tasks.extract_document_ocr", args=[str(document.id)]
    )

    return document


@router.get("/customer/{customer_id}", response_model=list[DocumentResponse])
async def list_customer_documents(
    customer_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Customer).where(Customer.id == customer_id))
    customer = result.scalars().first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found.")

    if customer.user_id != current_user.id and current_user.role not in [
        "compliance_officer",
        "admin",
    ]:
        raise HTTPException(
            status_code=403, detail="Unauthorized access for this profile."
        )

    docs_result = await db.execute(
        select(Document)
        .where(Document.customer_id == customer_id)
        .order_by(Document.created_at.desc())
    )
    return docs_result.scalars().all()


@router.get("/{document_id}", response_model=DocumentVerificationDetailsResponse)
async def get_document_by_id(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalars().first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found.")

    # Authorization check
    cust_result = await db.execute(
        select(Customer).where(Customer.id == document.customer_id)
    )
    customer = cust_result.scalars().first()
    if (
        customer
        and customer.user_id != current_user.id
        and current_user.role not in ["compliance_officer", "admin"]
    ):
        raise HTTPException(status_code=403, detail="Unauthorized.")

    metadata = document.verification_metadata or {}
    validation = metadata.get("validation", {})
    matching = metadata.get("matching", {})
    risk = metadata.get("risk", {})
    history = metadata.get("history", [])

    return DocumentVerificationDetailsResponse(
        document_id=document.id,
        verification_status=document.verification_status,
        ocr_data=document.ocr_data,
        validation=validation if validation else None,
        matching=matching if matching else None,
        risk=risk if risk else None,
        metadata=metadata,
        history=history,
    )


@router.get("/status/{document_id}")
async def get_document_status(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalars().first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found.")
    return {"document_id": str(document.id), "status": document.verification_status}


@router.post("/verify", response_model=DocumentVerificationDetailsResponse)
async def verify_ocr_results(
    payload: Dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    POST /documents/verify:
    Accepts document_id and confirmed ocr_data payload.
    Triggers Stage B: Matching, Validation, Fraud, Risk Scoring, and triggers downstream screening.
    """
    doc_id_str = payload.get("document_id")
    confirmed_data = payload.get("ocr_data")
    if not doc_id_str or not confirmed_data:
        raise HTTPException(
            status_code=400, detail="Missing document_id or ocr_data in payload."
        )

    try:
        doc_id = UUID(doc_id_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document_id formatting.")

    result = await db.execute(select(Document).where(Document.id == doc_id))
    document = result.scalars().first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found.")

    # Run verification pipeline synchronously
    # (Using run_sync inside async session since it performs commits)
    verification_metadata = await db.run_sync(
        lambda sync_session: DocumentVerificationService.run_post_ocr_verification(
            sync_session, doc_id, confirmed_data
        )
    )

    # Reload document to return latest fields
    await db.refresh(document)

    return DocumentVerificationDetailsResponse(
        document_id=document.id,
        verification_status=document.verification_status,
        ocr_data=document.ocr_data,
        validation=verification_metadata.get("validation"),
        matching=verification_metadata.get("matching"),
        risk=verification_metadata.get("risk"),
        metadata=verification_metadata,
        history=verification_metadata.get("history", []),
    )


@router.post("/{document_id}/reprocess", response_model=ReprocessResponse)
async def reprocess_document(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalars().first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found.")

    document.verification_status = "reprocessing"
    await db.commit()

    # Re-queue Celery task
    celery_app.send_task(
        "tasks.kyc_tasks.extract_document_ocr", args=[str(document.id)]
    )

    return ReprocessResponse(
        document_id=document.id,
        status="reprocessing",
        message="Reprocessing job submitted successfully.",
    )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalars().first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found.")

    cust_result = await db.execute(
        select(Customer).where(Customer.id == document.customer_id)
    )
    customer = cust_result.scalars().first()
    if (
        customer
        and customer.user_id != current_user.id
        and current_user.role != "admin"
    ):
        raise HTTPException(status_code=403, detail="Unauthorized.")

    await db.delete(document)
    await db.commit()
    return None
