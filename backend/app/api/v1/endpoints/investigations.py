"""
Investigations Endpoint Router — Phase 12
=========================================
Implements the 15 routes for full-fidelity investigations, evidence uploads,
notes audit tracking, investigator assignments, chronological timelines,
SAR generators, and workload metrics panels. Enforces strict compliance-level RBAC.
"""

from uuid import UUID
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.models import User, Investigation, Evidence, CaseNote, SAR, TimelineEvent
from app.services.investigation_service import InvestigationService
from app.schemas.schemas import (
    InvestigationResponse,
    PaginatedInvestigations,
    InvestigationWorkspacePayload,
    AssignmentResponse,
    AssignmentCreate,
    CaseNoteResponse,
    CaseNoteCreate,
    CaseNoteUpdate,
    SARResponse,
    SARCreate,
    SARUpdate,
    CaseActionRequest,
    TimelineEventResponse,
    InvestigationDashboardMetrics,
    EvidenceResponse
)

router = APIRouter()


def verify_compliance_or_admin(current_user: User):
    """Enforce strict Compliance Officer and Admin RBAC constraints."""
    if current_user.role not in ("compliance_officer", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="RBAC privilege check failed. Investigation workspace access is restricted to compliance personnel."
        )


@router.get("/", response_model=PaginatedInvestigations)
async def list_investigations(
    page: int = 1,
    page_size: int = 15,
    status_filter: Optional[str] = None,
    risk_filter: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List case investigations with filters and pagination."""
    verify_compliance_or_admin(current_user)
    await ensure_schemas(db)

    from sqlalchemy import select, func
    from app.models.models import Investigation

    offset = (page - 1) * page_size
    query = select(Investigation)

    if status_filter:
        query = query.where(Investigation.status == status_filter)
    if risk_filter:
        query = query.where(Investigation.risk_level == risk_filter)

    # Count total
    count_q = select(func.count(Investigation.id))
    if status_filter:
        count_q = count_q.where(Investigation.status == status_filter)
    if risk_filter:
        count_q = count_q.where(Investigation.risk_level == risk_filter)

    total = (await db.execute(count_q)).scalar_one() or 0

    res = await db.execute(query.order_by(Investigation.created_at.desc()).offset(offset).limit(page_size))
    items = res.scalars().all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": items
    }


@router.get("/dashboard", response_model=InvestigationDashboardMetrics)
async def get_investigation_dashboard_metrics(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get dashboard stats for compliance workspace (Part 13)."""
    verify_compliance_or_admin(current_user)
    await ensure_schemas(db)

    metrics = await InvestigationService.get_dashboard_metrics(db)
    return metrics


@router.get("/{id}", response_model=InvestigationWorkspacePayload)
async def get_investigation_workspace(
    id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get the full structured detail panels of an investigation workspace."""
    verify_compliance_or_admin(current_user)
    await ensure_schemas(db)

    try:
        data = await InvestigationService.get_investigation_details(db, id)
        return data
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.put("/{id}", response_model=InvestigationResponse)
async def update_investigation(
    id: UUID,
    status_val: Optional[str] = Form(None, alias="status"),
    risk_level_val: Optional[str] = Form(None, alias="risk_level"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update investigation status and/or risk level."""
    verify_compliance_or_admin(current_user)
    await ensure_schemas(db)

    res = await db.execute(select(Investigation).where(Investigation.id == id))
    inv = res.scalars().first()
    if not inv:
        raise HTTPException(status_code=404, detail="Investigation workspace not found.")

    if status_val:
        inv.status = status_val
    if risk_level_val:
        inv.risk_level = risk_level_val

    await db.commit()
    await db.refresh(inv)
    return inv


@router.post("/{id}/assign", response_model=AssignmentResponse)
async def assign_investigation_role(
    id: UUID,
    payload: AssignmentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Assign or reassign investigator or supervisor (Part 4)."""
    verify_compliance_or_admin(current_user)
    await ensure_schemas(db)

    try:
        assign = await InvestigationService.assign_case(
            db=db,
            investigation_id=id,
            assignee_id=payload.assigned_to,
            role=payload.role,
            current_user_id=current_user.id
        )
        return assign
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/{id}/note", response_model=CaseNoteResponse)
async def add_investigator_note(
    id: UUID,
    payload: CaseNoteCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Add new rich note to case file."""
    verify_compliance_or_admin(current_user)
    await ensure_schemas(db)

    note = await InvestigationService.add_note(
        db=db,
        investigation_id=id,
        author_id=current_user.id,
        note_text=payload.note_text
    )
    return note


@router.put("/{id}/note/{note_id}", response_model=CaseNoteResponse)
async def update_investigator_note(
    id: UUID,
    note_id: UUID,
    payload: CaseNoteUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Edit case note content."""
    verify_compliance_or_admin(current_user)
    await ensure_schemas(db)

    try:
        note = await InvestigationService.edit_note(
            db=db,
            note_id=note_id,
            author_id=current_user.id,
            new_text=payload.note_text
        )
        return note
    except (ValueError, PermissionError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{id}/note/{note_id}", status_code=status.HTTP_200_OK)
async def delete_investigator_note(
    id: UUID,
    note_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a note from investigation workspace history."""
    verify_compliance_or_admin(current_user)
    await ensure_schemas(db)

    try:
        success = await InvestigationService.delete_note(db, note_id, current_user.id)
        if not success:
            raise HTTPException(status_code=404, detail="Note not found.")
        return {"status": "success", "message": "Note deleted successfully."}
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@router.post("/{id}/evidence", response_model=EvidenceResponse)
async def upload_evidence_file(
    id: UUID,
    description: Optional[str] = Form(None),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Upload case evidence file (Part 2)."""
    verify_compliance_or_admin(current_user)
    await ensure_schemas(db)

    # Validate file type extension
    file_ext = file.filename.split(".")[-1].lower()
    allowed_exts = ("pdf", "docx", "png", "jpg", "jpeg", "csv", "zip", "mp3", "wav", "mp4", "avi", "mov")
    if file_ext not in allowed_exts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported evidence file format. Supported extensions: {', '.join(allowed_exts)}"
        )

    content = await file.read()
    evidence = await InvestigationService.add_evidence(
        db=db,
        investigation_id=id,
        file_name=file.filename,
        evidence_type=file_ext,
        file_content=content,
        uploaded_by=current_user.id,
        description=description
    )
    return evidence


@router.delete("/{id}/evidence/{evidence_id}", status_code=status.HTTP_200_OK)
async def delete_evidence_file(
    id: UUID,
    evidence_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Remove evidence document from workspace."""
    verify_compliance_or_admin(current_user)
    await ensure_schemas(db)

    success = await InvestigationService.delete_evidence(db, evidence_id, current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Evidence not found.")
    return {"status": "success", "message": "Evidence file purged."}


@router.get("/{id}/timeline", response_model=List[TimelineEventResponse])
async def get_investigation_timeline(
    id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get the chronological logs history of timeline events (Part 5)."""
    verify_compliance_or_admin(current_user)
    await ensure_schemas(db)

    from sqlalchemy import select
    res = await db.execute(
        select(TimelineEvent)
        .where(TimelineEvent.investigation_id == id)
        .order_by(TimelineEvent.timestamp.asc())
    )
    return res.scalars().all()


@router.post("/{id}/sar", response_model=SARResponse)
async def generate_sar_draft(
    id: UUID,
    payload: SARCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create draft Suspicious Activity Report (SAR) narrative."""
    verify_compliance_or_admin(current_user)
    await ensure_schemas(db)

    sar = await InvestigationService.generate_sar(
        db=db,
        investigation_id=id,
        narrative=payload.narrative,
        reason=payload.reason,
        risk_indicators=payload.risk_indicators,
        recommendation=payload.recommendation,
        created_by=current_user.id
    )
    return sar


@router.get("/{id}/sar", response_model=List[SARResponse])
async def list_investigation_sars(
    id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List all SAR drafts/reports linked to the investigation."""
    verify_compliance_or_admin(current_user)
    await ensure_schemas(db)

    from sqlalchemy import select
    res = await db.execute(
        select(SAR).where(SAR.investigation_id == id).order_by(SAR.created_at.desc())
    )
    return res.scalars().all()


@router.put("/{id}/sar", response_model=SARResponse)
async def update_sar_details(
    id: UUID,
    payload: SARUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update active/latest SAR workflow status (Part 6)."""
    verify_compliance_or_admin(current_user)
    await ensure_schemas(db)

    # Load latest SAR for this investigation
    from sqlalchemy import desc
    res = await db.execute(
        select(SAR)
        .where(SAR.investigation_id == id)
        .order_by(desc(SAR.created_at))
        .limit(1)
    )
    sar = res.scalars().first()
    if not sar:
        raise HTTPException(status_code=404, detail="No active SAR records found for investigation.")

    updated_sar = await InvestigationService.update_sar_status(
        db=db,
        sar_id=sar.id,
        status=payload.status,
        actor_id=current_user.id
    )
    return updated_sar


@router.post("/{id}/close", response_model=InvestigationResponse)
async def close_investigation(
    id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Resolve and close case files (Part 8)."""
    verify_compliance_or_admin(current_user)
    await ensure_schemas(db)

    try:
        inv = await InvestigationService.transition_case_status(db, id, "close", current_user.id)
        return inv
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/{id}/reopen", response_model=InvestigationResponse)
async def reopen_investigation(
    id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Reopen closed case files (Part 8)."""
    verify_compliance_or_admin(current_user)
    await ensure_schemas(db)

    try:
        inv = await InvestigationService.transition_case_status(db, id, "reopen", current_user.id)
        return inv
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/{id}/escalate", response_model=InvestigationResponse)
async def escalate_investigation(
    id: UUID,
    payload: CaseActionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Perform escalations, returns, and EDD status switches."""
    verify_compliance_or_admin(current_user)
    await ensure_schemas(db)

    if payload.action not in ("escalate", "return", "edd_required"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid escalation action. Supported: escalate, return, edd_required"
        )

    try:
        inv = await InvestigationService.transition_case_status(db, id, payload.action, current_user.id)
        return inv
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


async def ensure_schemas(db: AsyncSession):
    """Util database helpers verification."""
    from app.core.schema_helpers import ensure_phase12_schema
    await ensure_phase12_schema(db)
