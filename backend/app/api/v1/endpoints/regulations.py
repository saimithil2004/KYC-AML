"""
Regulations & Policy Rule Extraction API — Phase 10
===================================================
Handles CRUD operations, text extraction, version control,
Gemini rule extraction, and rollback of regulation documents.
"""

import json
import os
import shutil
import logging
from datetime import date, datetime
from typing import List, Optional
from uuid import UUID, uuid4

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    UploadFile,
    File,
    Form,
    Request,
    status,
)
from sqlalchemy import func, and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.config import settings
from app.core.schema_helpers import ensure_phase10_schema
from app.dependencies.auth import (
    get_current_user,
    verify_compliance_officer,
    verify_admin,
)
from app.models.models import User, Regulation, PolicyRule, RegulationVersion
from app.schemas.schemas import (
    RegulationResponse,
    PaginatedRegulations,
    RegulationUpdate,
    RegulationVersionResponse,
    RollbackRequest,
    PolicyRuleResponse,
)
from app.services.audit_service import AuditService
from app.services.text_extraction_service import TextExtractionService
from app.services.rule_extraction_service import RuleExtractionService

logger = logging.getLogger(__name__)
router = APIRouter()


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    return (
        forwarded.split(",")[0].strip()
        if forwarded
        else (request.client.host if request.client else "unknown")
    )


# ── GET /regulations ──────────────────────────────────────────────────────────


@router.get("/", response_model=PaginatedRegulations)
async def list_regulations(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    search: Optional[str] = Query(None, description="Search by title or authority"),
    country: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    current_user: User = Depends(verify_compliance_officer),
    db: AsyncSession = Depends(get_db),
):
    """List all regulations with pagination and filters."""
    await ensure_phase10_schema(db)

    q = select(Regulation)
    if search:
        q = q.where(
            or_(
                Regulation.title.ilike(f"%{search}%"),
                Regulation.authority.ilike(f"%{search}%"),
                Regulation.description.ilike(f"%{search}%"),
            )
        )
    if country:
        q = q.where(Regulation.country == country)
    if status:
        q = q.where(Regulation.status == status)

    total = (
        await db.execute(select(func.count()).select_from(q.subquery()))
    ).scalar_one()
    items = (
        (
            await db.execute(
                q.order_by(Regulation.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .scalars()
        .all()
    )

    return PaginatedRegulations(
        total=total, page=page, page_size=page_size, items=items
    )


# ── POST /regulations ─────────────────────────────────────────────────────────


@router.post("/", response_model=RegulationResponse, status_code=201)
async def upload_regulation(
    request: Request,
    title: str = Form(...),
    authority: str = Form(...),
    description: Optional[str] = Form(None),
    country: Optional[str] = Form(None),
    jurisdiction: Optional[str] = Form(None),
    regulator: Optional[str] = Form(None),
    regulation_type: Optional[str] = Form(None),
    version: str = Form("1.0.0"),
    effective_date: Optional[str] = Form(None),
    expiry_date: Optional[str] = Form(None),
    file: UploadFile = File(...),
    current_user: User = Depends(verify_admin),  # Only admin can upload
    db: AsyncSession = Depends(get_db),
):
    """Uploads a regulation file, extracts text, and registers it in the DB."""
    await ensure_phase10_schema(db)

    # 1. Secure file upload storage
    upload_dir = settings.UPLOAD_DIR
    if not os.path.exists(upload_dir):
        # Fallback to local workspace uploads directory if target mount is missing
        upload_dir = os.path.join(os.getcwd(), "uploads")
        os.makedirs(upload_dir, exist_ok=True)

    file_uuid = uuid4()
    file_ext = os.path.splitext(file.filename)[1]
    saved_filename = f"reg_{file_uuid}{file_ext}"
    saved_path = os.path.join(upload_dir, saved_filename)

    with open(saved_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # 2. Extract Text
    try:
        extracted_text = TextExtractionService.extract_text(saved_path)
    except Exception as exc:
        if os.path.exists(saved_path):
            os.remove(saved_path)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not extract text from document: {str(exc)}",
        )

    # Parse dates
    eff_date = date.fromisoformat(effective_date) if effective_date else None
    exp_date = date.fromisoformat(expiry_date) if expiry_date else None

    # 3. Create database entry
    regulation = Regulation(
        id=file_uuid,
        title=title,
        authority=authority,
        upload_path=saved_path,
        uploaded_by_id=current_user.id,
        description=description,
        country=country,
        jurisdiction=jurisdiction,
        regulator=regulator,
        regulation_type=regulation_type,
        version=version,
        effective_date=eff_date,
        expiry_date=exp_date,
        status="active",
        extracted_text=extracted_text,
        document_metadata={
            "original_filename": file.filename,
            "size": os.path.getsize(saved_path),
        },
    )
    db.add(regulation)
    await db.flush()

    # Create initial version log
    initial_version = RegulationVersion(
        id=uuid4(),
        regulation_id=regulation.id,
        version=version,
        title=title,
        extracted_text=extracted_text,
        rules_snapshot={},
        change_description="Initial upload and ingestion",
        author_id=current_user.id,
    )
    db.add(initial_version)

    # Audit log
    await AuditService.log(
        db=db,
        user_id=current_user.id,
        action="UPLOAD_REGULATION",
        entity_name="regulation",
        entity_id=regulation.id,
        new_values={"title": title, "version": version, "file_name": file.filename},
        ip_address=_get_client_ip(request),
    )

    await db.commit()
    await db.refresh(regulation)
    return regulation


# ── GET /regulations/{id} ─────────────────────────────────────────────────────


@router.get("/{regulation_id}", response_model=RegulationResponse)
async def get_regulation(
    regulation_id: UUID,
    current_user: User = Depends(verify_compliance_officer),
    db: AsyncSession = Depends(get_db),
):
    await ensure_phase10_schema(db)
    result = await db.execute(select(Regulation).where(Regulation.id == regulation_id))
    regulation = result.scalars().first()
    if not regulation:
        raise HTTPException(status_code=404, detail="Regulation not found.")
    return regulation


# ── PUT /regulations/{id} ─────────────────────────────────────────────────────


@router.put("/{regulation_id}", response_model=RegulationResponse)
async def update_regulation(
    regulation_id: UUID,
    req_body: RegulationUpdate,
    request: Request,
    current_user: User = Depends(verify_admin),  # Only admin can update metadata
    db: AsyncSession = Depends(get_db),
):
    await ensure_phase10_schema(db)
    result = await db.execute(select(Regulation).where(Regulation.id == regulation_id))
    regulation = result.scalars().first()
    if not regulation:
        raise HTTPException(status_code=404, detail="Regulation not found.")

    old_values = {"title": regulation.title, "status": regulation.status}
    update_data = req_body.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(regulation, field, value)

    # Write version log if text or version changes
    if "extracted_text" in update_data or "version" in update_data:
        new_version = RegulationVersion(
            id=uuid4(),
            regulation_id=regulation.id,
            version=regulation.version,
            title=regulation.title,
            extracted_text=regulation.extracted_text or "",
            rules_snapshot={},
            change_description=f"Manual update: {list(update_data.keys())}",
            author_id=current_user.id,
        )
        db.add(new_version)

    await AuditService.log(
        db=db,
        user_id=current_user.id,
        action="UPDATE_REGULATION",
        entity_name="regulation",
        entity_id=regulation.id,
        old_values=old_values,
        new_values=update_data,
        ip_address=_get_client_ip(request),
    )

    await db.commit()
    await db.refresh(regulation)
    return regulation


# ── DELETE /regulations/{id} ──────────────────────────────────────────────────


@router.delete("/{regulation_id}", status_code=204)
async def delete_regulation(
    regulation_id: UUID,
    request: Request,
    current_user: User = Depends(verify_admin),  # Only admin can delete
    db: AsyncSession = Depends(get_db),
):
    await ensure_phase10_schema(db)
    result = await db.execute(select(Regulation).where(Regulation.id == regulation_id))
    regulation = result.scalars().first()
    if not regulation:
        raise HTTPException(status_code=404, detail="Regulation not found.")

    # Remove physical document if exists
    if regulation.upload_path and os.path.exists(regulation.upload_path):
        try:
            os.remove(regulation.upload_path)
        except Exception:
            pass

    await AuditService.log(
        db=db,
        user_id=current_user.id,
        action="DELETE_REGULATION",
        entity_name="regulation",
        entity_id=regulation_id,
        old_values={"title": regulation.title},
        ip_address=_get_client_ip(request),
    )

    await db.delete(regulation)
    await db.commit()
    return None


# ── POST /regulations/{id}/extract-rules ──────────────────────────────────────


@router.post("/{regulation_id}/extract-rules", response_model=List[PolicyRuleResponse])
async def extract_regulation_rules(
    regulation_id: UUID,
    request: Request,
    current_user: User = Depends(verify_admin),  # Only admin can run rule extraction
    db: AsyncSession = Depends(get_db),
):
    """Triggers AI or deterministic rule extraction and populates PolicyRules table."""
    await ensure_phase10_schema(db)

    result = await db.execute(select(Regulation).where(Regulation.id == regulation_id))
    regulation = result.scalars().first()
    if not regulation:
        raise HTTPException(status_code=404, detail="Regulation not found.")

    # 1. Extract rules
    extracted_rules = await RuleExtractionService.extract_rules(
        regulation.extracted_text
    )

    # 2. De-activate old rules from this regulation (overwrite model)
    await db.execute(
        select(PolicyRule).where(PolicyRule.regulation_id == regulation_id)
    )
    old_rules_res = await db.execute(
        select(PolicyRule).where(PolicyRule.regulation_id == regulation_id)
    )
    for r in old_rules_res.scalars().all():
        await db.delete(r)

    created_rules = []
    # 3. Add new rules to database
    for rule_data in extracted_rules:
        rule = PolicyRule(
            id=uuid4(),
            regulation_id=regulation_id,
            rule_name=rule_data.get("rule_name", "UNNAMED_RULE"),
            rule_type=rule_data.get("rule_type", "threshold"),
            conditions=rule_data.get("conditions") or {},
            is_active=True,
            severity=rule_data.get("severity", "medium"),
            description=rule_data.get("description"),
            expression=rule_data.get("expression"),
            threshold=rule_data.get("threshold"),
            country=rule_data.get("country") or regulation.country,
            version=regulation.version,
        )
        db.add(rule)
        created_rules.append(rule)

    await db.flush()

    # Update version snapshot in RegulationVersion
    snapshot = {r.rule_name: r.conditions for r in created_rules}
    latest_version_res = await db.execute(
        select(RegulationVersion)
        .where(RegulationVersion.regulation_id == regulation_id)
        .order_by(RegulationVersion.created_at.desc())
        .limit(1)
    )
    latest_version = latest_version_res.scalars().first()
    if latest_version:
        # Update current snapshot
        latest_version.rules_snapshot = snapshot
    else:
        new_version = RegulationVersion(
            id=uuid4(),
            regulation_id=regulation_id,
            version=regulation.version,
            title=regulation.title,
            extracted_text=regulation.extracted_text or "",
            rules_snapshot=snapshot,
            change_description="Extracted policy rules snapshot",
            author_id=current_user.id,
        )
        db.add(new_version)

    await AuditService.log(
        db=db,
        user_id=current_user.id,
        action="EXTRACT_REGULATION_RULES",
        entity_name="regulation",
        entity_id=regulation_id,
        new_values={"rules_count": len(created_rules)},
        ip_address=_get_client_ip(request),
    )

    await db.commit()
    return created_rules


# ── GET /regulations/{id}/versions ────────────────────────────────────────────


@router.get("/{regulation_id}/versions", response_model=List[RegulationVersionResponse])
async def list_regulation_versions(
    regulation_id: UUID,
    current_user: User = Depends(verify_compliance_officer),
    db: AsyncSession = Depends(get_db),
):
    await ensure_phase10_schema(db)
    result = await db.execute(
        select(RegulationVersion)
        .where(RegulationVersion.regulation_id == regulation_id)
        .order_by(RegulationVersion.created_at.desc())
    )
    return result.scalars().all()


# ── POST /regulations/{id}/rollback ───────────────────────────────────────────


@router.post("/{regulation_id}/rollback", response_model=RegulationResponse)
async def rollback_regulation(
    regulation_id: UUID,
    rollback_req: RollbackRequest,
    request: Request,
    current_user: User = Depends(verify_admin),  # Only admin can roll back
    db: AsyncSession = Depends(get_db),
):
    """Rolls back the regulation and its active rules to a historical snapshot."""
    await ensure_phase10_schema(db)

    # 1. Fetch regulation
    reg_result = await db.execute(
        select(Regulation).where(Regulation.id == regulation_id)
    )
    regulation = reg_result.scalars().first()
    if not regulation:
        raise HTTPException(status_code=404, detail="Regulation not found.")

    # 2. Fetch history version
    ver_result = await db.execute(
        select(RegulationVersion).where(
            and_(
                RegulationVersion.id == rollback_req.version_id,
                RegulationVersion.regulation_id == regulation_id,
            )
        )
    )
    historical = ver_result.scalars().first()
    if not historical:
        raise HTTPException(status_code=404, detail="Version snapshot not found.")

    old_version = regulation.version

    # 3. Rollback metadata and text
    regulation.title = historical.title
    regulation.extracted_text = historical.extracted_text
    regulation.version = historical.version

    # 4. Rollback policy rules to the snapshot
    # Clear current policy rules
    old_rules_res = await db.execute(
        select(PolicyRule).where(PolicyRule.regulation_id == regulation_id)
    )
    for r in old_rules_res.scalars().all():
        await db.delete(r)

    # Recreate from rules snapshot
    restored_rules = []
    for name, conditions in historical.rules_snapshot.items():
        rule = PolicyRule(
            id=uuid4(),
            regulation_id=regulation_id,
            rule_name=name,
            rule_type=(
                conditions.get("rule_type", "threshold")
                if isinstance(conditions, dict)
                else "threshold"
            ),
            conditions=conditions if isinstance(conditions, dict) else {},
            is_active=True,
            severity="medium",
            version=historical.version,
            country=regulation.country,
        )
        db.add(rule)
        restored_rules.append(rule)

    # 5. Append new version entry for the rollback action itself
    rollback_version = RegulationVersion(
        id=uuid4(),
        regulation_id=regulation_id,
        version=historical.version,
        title=historical.title,
        extracted_text=historical.extracted_text,
        rules_snapshot=historical.rules_snapshot,
        change_description=f"Rollback from version {old_version} to {historical.version}. Reason: {rollback_req.reason}",
        author_id=current_user.id,
    )
    db.add(rollback_version)

    await AuditService.log(
        db=db,
        user_id=current_user.id,
        action="ROLLBACK_REGULATION",
        entity_name="regulation",
        entity_id=regulation_id,
        old_values={"version": old_version},
        new_values={"version": historical.version, "reason": rollback_req.reason},
        ip_address=_get_client_ip(request),
    )

    await db.commit()
    await db.refresh(regulation)
    return regulation
