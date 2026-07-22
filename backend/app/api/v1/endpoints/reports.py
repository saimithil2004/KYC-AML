"""
Reports API Router — Phase 13
=============================
Provides REST endpoints for compliance report templates, schedules,
execution histories, and file download exports (PDF, Excel, CSV, JSON).
Only accessible to compliance officers and administrators.
"""

import os
from uuid import UUID, uuid4
from datetime import datetime, timedelta
from typing import List, Optional, Any, Dict
from fastapi import APIRouter, Depends, HTTPException, Query, status, Response
from fastapi.responses import StreamingResponse, FileResponse
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.schema_helpers import ensure_phase13_schema
from app.dependencies.auth import (
    get_current_user,
    verify_compliance_officer,
    verify_admin,
)
from app.models.models import (
    User,
    Report,
    ReportTemplate,
    ScheduledReport,
    ReportExecution,
)
from app.services.report_service import ReportService
from app.services.audit_service import AuditService
from app.schemas.schemas import (
    ReportTemplateCreate,
    ReportTemplateResponse,
    ReportCreate,
    ReportResponse,
    ScheduledReportCreate,
    ScheduledReportResponse,
    ScheduledReportUpdate,
)

router = APIRouter()


@router.get("/", response_model=List[ReportResponse])
async def list_reports(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(verify_compliance_officer),
    db: AsyncSession = Depends(get_db),
):
    """List compliance generated reports."""
    await ensure_phase13_schema(db)
    res = await db.execute(
        select(Report)
        .order_by(desc(Report.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return res.scalars().all()


@router.post("/generate", response_model=ReportResponse)
async def generate_report(
    payload: ReportCreate,
    current_user: User = Depends(verify_compliance_officer),
    db: AsyncSession = Depends(get_db),
):
    """Instantiate report compilation and save metadata and local file."""
    await ensure_phase13_schema(db)

    # 1. Compile report data rows
    report_type = payload.filters.get("report_type", "customer_summary")
    data = await ReportService.compile_report_data(db, report_type, payload.filters)

    # 2. Setup storage path
    reports_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "generated_reports"
    )
    os.makedirs(reports_dir, exist_ok=True)

    file_id = uuid4()
    filename = f"{payload.name.lower().replace(' ', '_')}_{file_id}.{payload.format}"
    filepath = os.path.join(reports_dir, filename)

    # 3. Write bytes to file based on format
    if payload.format == "csv":
        content = ReportService.generate_csv_bytes(data)
    elif payload.format == "excel":
        content = ReportService.generate_excel_bytes(data, payload.name)
    elif payload.format == "json":
        content = ReportService.generate_json_bytes(data)
    else:  # default pdf
        content = ReportService.generate_pdf_bytes(data, payload.name, payload.filters)

    with open(filepath, "wb") as f:
        f.write(content)

    # 4. Create database record
    rep = Report(
        id=file_id,
        name=payload.name,
        template_id=payload.template_id,
        generated_by=current_user.id,
        status="completed",
        format=payload.format,
        file_path=filepath,
        filters=payload.filters,
    )
    db.add(rep)

    await AuditService.log(
        db=db,
        user_id=current_user.id,
        action="REPORT_GENERATED",
        entity_name="report",
        entity_id=rep.id,
        new_values={"name": payload.name, "format": payload.format},
    )
    await db.commit()
    await db.refresh(rep)

    return rep


@router.get("/{id}")
async def get_report(
    id: UUID,
    download: bool = False,
    current_user: User = Depends(verify_compliance_officer),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve report metadata or trigger file download."""
    await ensure_phase13_schema(db)
    res = await db.execute(select(Report).where(Report.id == id))
    rep = res.scalars().first()
    if not rep:
        raise HTTPException(status_code=404, detail="Report not found.")

    if download and rep.file_path and os.path.exists(rep.file_path):
        return FileResponse(
            rep.file_path,
            media_type="application/octet-stream",
            filename=os.path.basename(rep.file_path),
        )

    return rep


@router.delete("/{id}", status_code=200)
async def delete_report(
    id: UUID,
    current_user: User = Depends(verify_compliance_officer),
    db: AsyncSession = Depends(get_db),
):
    """Remove report record and purge local document file."""
    await ensure_phase13_schema(db)
    res = await db.execute(select(Report).where(Report.id == id))
    rep = res.scalars().first()
    if not rep:
        raise HTTPException(status_code=404, detail="Report not found.")

    # Purge file
    if rep.file_path and os.path.exists(rep.file_path):
        try:
            os.remove(rep.file_path)
        except Exception as e:
            logger.error(f"Error deleting report file: {e}")

    await db.delete(rep)
    await AuditService.log(
        db=db,
        user_id=current_user.id,
        action="REPORT_DELETED",
        entity_name="report",
        entity_id=id,
    )
    await db.commit()
    return {"status": "success", "message": "Report file and database record deleted."}


# ─── Report Templates CRUD ───


@router.get("/templates", response_model=List[ReportTemplateResponse])
async def list_templates(
    current_user: User = Depends(verify_compliance_officer),
    db: AsyncSession = Depends(get_db),
):
    """List custom report builder templates."""
    await ensure_phase13_schema(db)
    res = await db.execute(
        select(ReportTemplate).order_by(desc(ReportTemplate.created_at))
    )
    return res.scalars().all()


@router.post("/templates", response_model=ReportTemplateResponse)
async def create_template(
    payload: ReportTemplateCreate,
    current_user: User = Depends(verify_compliance_officer),
    db: AsyncSession = Depends(get_db),
):
    """Save custom report builder templates."""
    await ensure_phase13_schema(db)
    template = ReportTemplate(
        id=uuid4(),
        name=payload.name,
        description=payload.description,
        config=payload.config,
        created_by=current_user.id,
    )
    db.add(template)

    await AuditService.log(
        db=db,
        user_id=current_user.id,
        action="TEMPLATE_SAVED",
        entity_name="report_template",
        entity_id=template.id,
        new_values={"name": payload.name},
    )
    await db.commit()
    await db.refresh(template)
    return template


@router.put("/templates/{id}", response_model=ReportTemplateResponse)
async def update_template(
    id: UUID,
    payload: ReportTemplateCreate,
    current_user: User = Depends(verify_compliance_officer),
    db: AsyncSession = Depends(get_db),
):
    """Edit report template details."""
    await ensure_phase13_schema(db)
    res = await db.execute(select(ReportTemplate).where(ReportTemplate.id == id))
    template = res.scalars().first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found.")

    template.name = payload.name
    template.description = payload.description
    template.config = payload.config
    template.updated_at = datetime.utcnow()

    await AuditService.log(
        db=db,
        user_id=current_user.id,
        action="TEMPLATE_MODIFIED",
        entity_name="report_template",
        entity_id=id,
        new_values={"name": payload.name},
    )
    await db.commit()
    await db.refresh(template)
    return template


@router.delete("/templates/{id}", status_code=200)
async def delete_template(
    id: UUID,
    current_user: User = Depends(verify_compliance_officer),
    db: AsyncSession = Depends(get_db),
):
    """Remove saved report template."""
    await ensure_phase13_schema(db)
    res = await db.execute(select(ReportTemplate).where(ReportTemplate.id == id))
    template = res.scalars().first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found.")

    await db.delete(template)
    await AuditService.log(
        db=db,
        user_id=current_user.id,
        action="TEMPLATE_DELETED",
        entity_name="report_template",
        entity_id=id,
    )
    await db.commit()
    return {"status": "success", "message": "Template deleted."}


# ─── Report Schedules CRUD ───


@router.get("/schedules", response_model=List[ScheduledReportResponse])
async def list_schedules(
    current_user: User = Depends(verify_compliance_officer),
    db: AsyncSession = Depends(get_db),
):
    """List scheduled reports."""
    await ensure_phase13_schema(db)
    res = await db.execute(
        select(ScheduledReport).order_by(desc(ScheduledReport.created_at))
    )
    return res.scalars().all()


@router.post("/schedules", response_model=ScheduledReportResponse)
async def create_schedule(
    payload: ScheduledReportCreate,
    current_user: User = Depends(verify_compliance_officer),
    db: AsyncSession = Depends(get_db),
):
    """Register daily/weekly/monthly report schedules."""
    await ensure_phase13_schema(db)

    # Calculate initial next_run based on cron_expression
    # daily, weekly, monthly
    next_run = datetime.utcnow()
    expr = payload.cron_expression.lower()
    if expr == "daily":
        next_run += timedelta(days=1)
    elif expr == "weekly":
        next_run += timedelta(weeks=1)
    elif expr == "monthly":
        next_run += timedelta(days=30)
    else:  # default to hourly or immediate manual buffer
        next_run += timedelta(hours=1)

    schedule = ScheduledReport(
        id=uuid4(),
        name=payload.name,
        template_id=payload.template_id,
        cron_expression=payload.cron_expression,
        next_run=next_run,
        status="active",
        created_by=current_user.id,
    )
    db.add(schedule)

    await AuditService.log(
        db=db,
        user_id=current_user.id,
        action="SCHEDULE_CREATED",
        entity_name="scheduled_report",
        entity_id=schedule.id,
        new_values={"name": payload.name, "cron": payload.cron_expression},
    )
    await db.commit()
    await db.refresh(schedule)
    return schedule


@router.put("/schedules/{id}", response_model=ScheduledReportResponse)
async def update_schedule(
    id: UUID,
    payload: ScheduledReportUpdate,
    current_user: User = Depends(verify_compliance_officer),
    db: AsyncSession = Depends(get_db),
):
    """Pause, resume, or edit scheduler details."""
    await ensure_phase13_schema(db)
    res = await db.execute(select(ScheduledReport).where(ScheduledReport.id == id))
    schedule = res.scalars().first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found.")

    if payload.status:
        schedule.status = payload.status
    if payload.cron_expression:
        schedule.cron_expression = payload.cron_expression

    await AuditService.log(
        db=db,
        user_id=current_user.id,
        action="SCHEDULE_MODIFIED",
        entity_name="scheduled_report",
        entity_id=id,
        new_values={"status": payload.status},
    )
    await db.commit()
    await db.refresh(schedule)
    return schedule


@router.delete("/schedules/{id}", status_code=200)
async def delete_schedule(
    id: UUID,
    current_user: User = Depends(verify_compliance_officer),
    db: AsyncSession = Depends(get_db),
):
    """Delete scheduled report."""
    await ensure_phase13_schema(db)
    res = await db.execute(select(ScheduledReport).where(ScheduledReport.id == id))
    schedule = res.scalars().first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found.")

    await db.delete(schedule)
    await AuditService.log(
        db=db,
        user_id=current_user.id,
        action="SCHEDULE_DELETED",
        entity_name="scheduled_report",
        entity_id=id,
    )
    await db.commit()
    return {"status": "success", "message": "Scheduled report removed."}


# ─── Instant Export Endpoints ───


@router.post("/export/pdf")
async def export_pdf(
    filters: Dict[str, Any],
    current_user: User = Depends(verify_compliance_officer),
    db: AsyncSession = Depends(get_db),
):
    """Generate and return styled PDF export bytes directly."""
    report_type = filters.get("report_type", "customer_summary")
    data = await ReportService.compile_report_data(db, report_type, filters)
    pdf_bytes = ReportService.generate_pdf_bytes(
        data, f"Compliance Audit: {report_type.title()}", filters
    )

    await AuditService.log(
        db=db,
        user_id=current_user.id,
        action="REPORT_EXPORTED",
        entity_name="report",
        entity_id=uuid4(),
        new_values={"format": "pdf", "type": report_type},
    )
    await db.commit()

    return Response(content=pdf_bytes, media_type="application/pdf")


@router.post("/export/excel")
async def export_excel(
    filters: Dict[str, Any],
    current_user: User = Depends(verify_compliance_officer),
    db: AsyncSession = Depends(get_db),
):
    """Generate and return Excel bytes directly."""
    report_type = filters.get("report_type", "customer_summary")
    data = await ReportService.compile_report_data(db, report_type, filters)
    xlsx_bytes = ReportService.generate_excel_bytes(
        data, f"Excel Export: {report_type}"
    )

    await AuditService.log(
        db=db,
        user_id=current_user.id,
        action="REPORT_EXPORTED",
        entity_name="report",
        entity_id=uuid4(),
        new_values={"format": "excel", "type": report_type},
    )
    await db.commit()

    return Response(
        content=xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={report_type}.xlsx"},
    )


@router.post("/export/csv")
async def export_csv(
    filters: Dict[str, Any],
    current_user: User = Depends(verify_compliance_officer),
    db: AsyncSession = Depends(get_db),
):
    """Generate and return CSV bytes directly."""
    report_type = filters.get("report_type", "customer_summary")
    data = await ReportService.compile_report_data(db, report_type, filters)
    csv_bytes = ReportService.generate_csv_bytes(data)

    await AuditService.log(
        db=db,
        user_id=current_user.id,
        action="REPORT_EXPORTED",
        entity_name="report",
        entity_id=uuid4(),
        new_values={"format": "csv", "type": report_type},
    )
    await db.commit()

    return Response(
        content=csv_bytes,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={report_type}.csv"},
    )
