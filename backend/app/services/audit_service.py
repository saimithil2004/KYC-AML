"""
Audit Service
=============
Centralised helper for creating immutable audit log entries.
Every compliance operation (create/update/delete on transactions, alerts, cases)
calls `AuditService.log()` to produce an `AuditLog` row.

Supports both async (FastAPI endpoints) and sync (Celery tasks) callers.
"""

import logging
from typing import Optional, Any, Dict
from uuid import UUID
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.models.models import AuditLog

logger = logging.getLogger(__name__)


class AuditService:
    """Helper that writes AuditLog rows."""

    # ── Async version (used by FastAPI endpoint handlers) ────────────────────

    @staticmethod
    async def log(
        db: AsyncSession,
        user_id: Optional[UUID],
        action: str,
        entity_name: str,
        entity_id: Any,
        old_values: Optional[Dict] = None,
        new_values: Optional[Dict] = None,
        ip_address: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> AuditLog:
        """
        Create an audit log entry (async).

        Parameters
        ----------
        db:           AsyncSession — the active DB session (caller commits)
        user_id:      UUID of the acting user (None for system actions)
        action:       Short verb, e.g. "CREATE_TRANSACTION", "UPDATE_CASE_STATUS"
        entity_name:  Model name, e.g. "transaction", "alert", "case"
        entity_id:    UUID or str of the affected entity
        old_values:   Dict of previous values (for updates/deletes)
        new_values:   Dict of new values (for creates/updates)
        ip_address:   Caller IP for traceability
        reason:       Human-readable reason (for decisions, escalations, etc.)
        """
        try:
            entity_uuid = entity_id if isinstance(entity_id, UUID) else UUID(str(entity_id))

            # Merge reason into new_values if provided
            if reason and new_values is not None:
                new_values = {**new_values, "_reason": reason}
            elif reason:
                new_values = {"_reason": reason}

            log = AuditLog(
                user_id=user_id,
                action=action,
                entity_name=entity_name,
                entity_id=entity_uuid,
                old_values=old_values,
                new_values=new_values,
                ip_address=ip_address,
            )
            db.add(log)
            # Caller is responsible for commit — we only add
            return log
        except Exception as exc:
            logger.error(f"AuditService: Failed to create audit log: {exc}")
            # Never let audit failures break the main flow
            return None  # type: ignore

    # ── Sync version (used by Celery tasks / ScreeningService) ───────────────

    @staticmethod
    def log_sync(
        db: Session,
        user_id: Optional[UUID],
        action: str,
        entity_name: str,
        entity_id: Any,
        old_values: Optional[Dict] = None,
        new_values: Optional[Dict] = None,
        ip_address: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> Optional[AuditLog]:
        """Create an audit log entry (synchronous)."""
        try:
            entity_uuid = entity_id if isinstance(entity_id, UUID) else UUID(str(entity_id))
            if reason and new_values is not None:
                new_values = {**new_values, "_reason": reason}
            elif reason:
                new_values = {"_reason": reason}

            log = AuditLog(
                user_id=user_id,
                action=action,
                entity_name=entity_name,
                entity_id=entity_uuid,
                old_values=old_values,
                new_values=new_values,
                ip_address=ip_address,
            )
            db.add(log)
            db.commit()
            return log
        except Exception as exc:
            logger.error(f"AuditService.log_sync: Failed: {exc}")
            try:
                db.rollback()
            except Exception:
                pass
            return None
