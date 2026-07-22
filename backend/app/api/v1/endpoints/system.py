"""
System Administration Router — Phase 15
========================================
Exposes system controls, metrics logging history, and backup management:
  - GET /system/backups (List backups)
  - POST /system/backups (Trigger backup)
  - POST /system/backups/{id}/verify (Verify checksum integrity)
  - DELETE /system/backups/{id} (Purge backup)
  - GET /system/metrics/history (Metric timeseries log)
"""

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from uuid import UUID
from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.database import get_db
from app.dependencies.auth import verify_admin
from app.models.models import BackupRecord, SystemMetric, User
from app.schemas.schemas import BackupRecordResponse, SystemMetricResponse
from app.services.backup_service import BackupService

router = APIRouter()


@router.get("/backups", response_model=List[BackupRecordResponse])
async def list_backups(
    current_user: User = Depends(verify_admin), db: AsyncSession = Depends(get_db)
):
    """Retrieve history of backups (Admin only)."""
    result = await db.execute(
        select(BackupRecord).order_by(BackupRecord.created_at.desc()).limit(50)
    )
    return result.scalars().all()


@router.post(
    "/backups", response_model=BackupRecordResponse, status_code=status.HTTP_201_CREATED
)
async def trigger_backup(
    background_tasks: BackgroundTasks,
    backup_type: str = "database",
    current_user: User = Depends(verify_admin),
    db: AsyncSession = Depends(get_db),
):
    """Creates a new compressed backup archive (Admin only)."""
    if backup_type not in ("database", "documents", "config", "full"):
        raise HTTPException(
            status_code=400,
            detail="Invalid backup type. Choose from: database, documents, config, full",
        )

    # Run the backup creation
    record = await BackupService.create_backup(
        db, backup_type=backup_type, triggered_by="manual"
    )
    return record


@router.post("/backups/{backup_id}/verify")
async def verify_backup(
    backup_id: UUID,
    current_user: User = Depends(verify_admin),
    db: AsyncSession = Depends(get_db),
):
    """Verify SHA-256 integrity checksum for a backup (Admin only)."""
    success = await BackupService.verify_backup_integrity(backup_id, db)
    if not success:
        raise HTTPException(
            status_code=400,
            detail="Backup verification failed. Checksum mismatch or file missing.",
        )
    return {"status": "verified", "message": "Backup integrity verified successfully."}


@router.delete("/backups/{backup_id}")
async def delete_backup(
    backup_id: UUID,
    current_user: User = Depends(verify_admin),
    db: AsyncSession = Depends(get_db),
):
    """Permanently delete a backup archive from storage and database (Admin only)."""
    record = await db.get(BackupRecord, backup_id)
    if not record:
        raise HTTPException(status_code=404, detail="Backup record not found.")

    try:
        from app.services.backup_service import _storage

        # Delete file from storage
        _storage.delete(record.file_path)
        # Delete row from db
        await db.delete(record)
        await db.commit()
        return {"detail": "Backup deleted successfully."}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to delete backup: {exc}")


@router.get("/metrics/history", response_model=List[SystemMetricResponse])
async def get_metrics_history(
    metric_name: str = "cpu_percent",
    limit: int = 100,
    current_user: User = Depends(verify_admin),
    db: AsyncSession = Depends(get_db),
):
    """Get time-series historical logs for a given metric (Admin only)."""
    result = await db.execute(
        select(SystemMetric)
        .where(SystemMetric.metric_name == metric_name)
        .order_by(SystemMetric.timestamp.desc())
        .limit(limit)
    )
    return result.scalars().all()
