from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from uuid import UUID
from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.models import User, Customer, Document
from app.schemas.schemas import DocumentResponse
from app.core.celery_app import celery_app
from app.services.upload_service import UploadService

router = APIRouter()

@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    customer_id: str = Form(...),
    document_type: str = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:
        cust_uuid = UUID(customer_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid customer ID formatting.")

    result = await db.execute(select(Customer).where(Customer.id == cust_uuid))
    customer = result.scalars().first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found.")

    if customer.user_id != current_user.id and current_user.role not in ["compliance_officer", "admin"]:
        raise HTTPException(status_code=403, detail="Unauthorized access for this profile.")

    file_path, file_size = UploadService.save_customer_document(cust_uuid, file)

    document = Document(
        customer_id=cust_uuid,
        document_type=document_type,
        file_name=file.filename,
        file_path=file_path,
        content_type=file.content_type,
        file_size=file_size,
        verification_status="uploaded"
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)

    # Launch OCR analysis asynchronously
    celery_app.send_task(
        "tasks.kyc_tasks.extract_document_ocr",
        args=[str(document.id)]
    )

    return document
