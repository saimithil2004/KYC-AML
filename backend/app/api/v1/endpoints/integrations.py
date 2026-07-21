"""
Integrations API Router — Phase 14
=====================================
REST endpoints for:
  - Integration Settings CRUD
  - Manual / Scheduled Provider Synchronization
  - Sync Status & History
  - Provider Health Checks
  - Notification Templates CRUD
  - Notification History
  - Webhook Endpoint Management (CRUD)
  - Webhook Logs
  - Provider Versions

RBAC:
  - Admins: Full management (settings, templates, webhooks, sync, history)
  - Compliance Officers: View sync logs, run manual sync, view notifications
  - Customers: 403 Forbidden on all routes
"""

import logging
from uuid import UUID, uuid4
from datetime import datetime
from typing import List, Optional, Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.schema_helpers import ensure_phase14_schema
from app.dependencies.auth import get_current_user, verify_compliance_officer, verify_admin
from app.models.models import (
    User, IntegrationSetting, SyncHistory, NotificationTemplate,
    Notification, WebhookEndpoint, WebhookLog
)
from app.services.integration_service import IntegrationService, ALL_PROVIDER_NAMES
from app.services.notification_service import NotificationService
from app.services.webhook_service import WebhookService, WEBHOOK_EVENTS
from app.services.audit_service import AuditService
from app.schemas.schemas import (
    IntegrationSettingCreate, IntegrationSettingUpdate, IntegrationSettingResponse,
    SyncHistoryResponse, NotificationTemplateCreate, NotificationTemplateResponse,
    NotificationResponse, WebhookEndpointCreate, WebhookEndpointUpdate,
    WebhookEndpointResponse, WebhookLogResponse, ManualSyncRequest, SendNotificationRequest,
)

router = APIRouter()
logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════════════════
# INTEGRATION SETTINGS
# ════════════════════════════════════════════════════════════════════════════

@router.get("/settings", response_model=List[IntegrationSettingResponse])
async def list_integration_settings(
    current_user: User = Depends(verify_compliance_officer),
    db: AsyncSession = Depends(get_db),
):
    """List all integration provider settings. Compliance Officers and Admins only."""
    await ensure_phase14_schema(db)
    res = await db.execute(select(IntegrationSetting).order_by(IntegrationSetting.provider_name))
    settings = res.scalars().all()
    # Mask sensitive keys in response
    result = []
    for s in settings:
        item = IntegrationSettingResponse.model_validate(s)
        result.append(item)
    return result


@router.post("/settings", response_model=IntegrationSettingResponse, status_code=201)
async def create_integration_setting(
    payload: IntegrationSettingCreate,
    current_user: User = Depends(verify_admin),
    db: AsyncSession = Depends(get_db),
):
    """Create a new integration provider setting. Admins only."""
    await ensure_phase14_schema(db)

    # Check uniqueness
    res = await db.execute(
        select(IntegrationSetting).where(IntegrationSetting.provider_name == payload.provider_name)
    )
    if res.scalars().first():
        raise HTTPException(status_code=409, detail=f"Provider '{payload.provider_name}' already configured.")

    setting = IntegrationSetting(
        id=uuid4(),
        provider_name=payload.provider_name,
        provider_type=payload.provider_type,
        base_url=payload.base_url,
        api_key=payload.api_key,
        api_secret=payload.api_secret,
        enabled=payload.enabled,
        timeout=payload.timeout,
        configuration=payload.configuration,
    )
    db.add(setting)
    await AuditService.log(
        db=db, user_id=current_user.id, action="INTEGRATION_CREATED",
        entity_name="integration_setting", entity_id=setting.id,
        new_values={"provider": payload.provider_name, "type": payload.provider_type},
    )
    await db.commit()
    await db.refresh(setting)
    return setting


@router.put("/settings/{id}", response_model=IntegrationSettingResponse)
async def update_integration_setting(
    id: UUID,
    payload: IntegrationSettingUpdate,
    current_user: User = Depends(verify_admin),
    db: AsyncSession = Depends(get_db),
):
    """Update an existing integration setting. Admins only."""
    await ensure_phase14_schema(db)
    res = await db.execute(select(IntegrationSetting).where(IntegrationSetting.id == id))
    setting = res.scalars().first()
    if not setting:
        raise HTTPException(status_code=404, detail="Integration setting not found.")

    if payload.base_url is not None:
        setting.base_url = payload.base_url
    if payload.api_key is not None:
        setting.api_key = payload.api_key
    if payload.api_secret is not None:
        setting.api_secret = payload.api_secret
    if payload.enabled is not None:
        setting.enabled = payload.enabled
    if payload.timeout is not None:
        setting.timeout = payload.timeout
    if payload.configuration is not None:
        setting.configuration = payload.configuration
    setting.updated_at = datetime.utcnow()

    await AuditService.log(
        db=db, user_id=current_user.id, action="INTEGRATION_UPDATED",
        entity_name="integration_setting", entity_id=id,
        new_values={"enabled": setting.enabled},
    )
    await db.commit()
    await db.refresh(setting)
    return setting


@router.delete("/settings/{id}", status_code=200)
async def delete_integration_setting(
    id: UUID,
    current_user: User = Depends(verify_admin),
    db: AsyncSession = Depends(get_db),
):
    """Delete an integration setting. Admins only."""
    await ensure_phase14_schema(db)
    res = await db.execute(select(IntegrationSetting).where(IntegrationSetting.id == id))
    setting = res.scalars().first()
    if not setting:
        raise HTTPException(status_code=404, detail="Integration setting not found.")

    await db.delete(setting)
    await AuditService.log(
        db=db, user_id=current_user.id, action="INTEGRATION_DELETED",
        entity_name="integration_setting", entity_id=id,
    )
    await db.commit()
    return {"status": "success", "message": "Integration setting deleted."}


# ════════════════════════════════════════════════════════════════════════════
# SYNCHRONIZATION
# ════════════════════════════════════════════════════════════════════════════

@router.post("/sync/manual")
async def manual_sync(
    payload: ManualSyncRequest,
    current_user: User = Depends(verify_compliance_officer),
    db: AsyncSession = Depends(get_db),
):
    """Trigger a manual synchronization for a specific provider."""
    await ensure_phase14_schema(db)
    if payload.provider not in ALL_PROVIDER_NAMES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown provider '{payload.provider}'. Valid: {ALL_PROVIDER_NAMES}"
        )

    result = await IntegrationService.run_sync(
        db=db, provider_name=payload.provider,
        sync_type="manual", user_id=current_user.id,
    )
    return result


@router.post("/sync/all")
async def sync_all_providers(
    current_user: User = Depends(verify_compliance_officer),
    db: AsyncSession = Depends(get_db),
):
    """Trigger synchronization for ALL compliance providers."""
    await ensure_phase14_schema(db)
    results = await IntegrationService.run_all_syncs(db=db, sync_type="manual", user_id=current_user.id)
    return {"providers_synced": len(results), "results": results}


@router.get("/sync/status", response_model=List[SyncHistoryResponse])
async def get_sync_status(
    provider: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(verify_compliance_officer),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve recent synchronization history, optionally filtered by provider."""
    await ensure_phase14_schema(db)
    return await IntegrationService.get_sync_history(db=db, provider=provider, limit=limit)


# ════════════════════════════════════════════════════════════════════════════
# PROVIDER HEALTH
# ════════════════════════════════════════════════════════════════════════════

@router.get("/health/providers")
async def provider_health(
    current_user: User = Depends(verify_compliance_officer),
    db: AsyncSession = Depends(get_db),
):
    """Return health status and version information for all compliance data providers."""
    await ensure_phase14_schema(db)
    return await IntegrationService.get_all_health(db=db)


@router.get("/providers/versions")
async def provider_versions(
    current_user: User = Depends(verify_compliance_officer),
    db: AsyncSession = Depends(get_db),
):
    """Return current data version for each provider."""
    await ensure_phase14_schema(db)
    health = await IntegrationService.get_all_health(db=db)
    return [{"provider": h["provider"], "version": h.get("version"), "mock_mode": h.get("mock_mode")} for h in health]


# ════════════════════════════════════════════════════════════════════════════
# NOTIFICATION TEMPLATES
# ════════════════════════════════════════════════════════════════════════════

@router.get("/notification-templates", response_model=List[NotificationTemplateResponse])
async def list_notification_templates(
    event_type: Optional[str] = Query(None),
    channel: Optional[str] = Query(None),
    current_user: User = Depends(verify_compliance_officer),
    db: AsyncSession = Depends(get_db),
):
    """List notification templates. Filterable by event_type and channel."""
    await ensure_phase14_schema(db)
    q = select(NotificationTemplate).order_by(desc(NotificationTemplate.created_at))
    if event_type:
        q = q.where(NotificationTemplate.event_type == event_type)
    if channel:
        q = q.where(NotificationTemplate.channel == channel)
    res = await db.execute(q)
    return res.scalars().all()


@router.post("/notification-templates", response_model=NotificationTemplateResponse, status_code=201)
async def create_notification_template(
    payload: NotificationTemplateCreate,
    current_user: User = Depends(verify_admin),
    db: AsyncSession = Depends(get_db),
):
    """Create a new notification template. Admins only."""
    await ensure_phase14_schema(db)
    tmpl = NotificationTemplate(
        id=uuid4(),
        name=payload.name,
        event_type=payload.event_type,
        channel=payload.channel,
        subject=payload.subject,
        body=payload.body,
        variables=payload.variables,
        active=payload.active,
    )
    db.add(tmpl)
    await AuditService.log(
        db=db, user_id=current_user.id, action="TEMPLATE_CREATED",
        entity_name="notification_template", entity_id=tmpl.id,
        new_values={"name": payload.name, "event_type": payload.event_type, "channel": payload.channel},
    )
    await db.commit()
    await db.refresh(tmpl)
    return tmpl


@router.put("/notification-templates/{id}", response_model=NotificationTemplateResponse)
async def update_notification_template(
    id: UUID,
    payload: NotificationTemplateCreate,
    current_user: User = Depends(verify_admin),
    db: AsyncSession = Depends(get_db),
):
    """Update a notification template. Admins only."""
    await ensure_phase14_schema(db)
    res = await db.execute(select(NotificationTemplate).where(NotificationTemplate.id == id))
    tmpl = res.scalars().first()
    if not tmpl:
        raise HTTPException(status_code=404, detail="Notification template not found.")

    tmpl.name = payload.name
    tmpl.event_type = payload.event_type
    tmpl.channel = payload.channel
    tmpl.subject = payload.subject
    tmpl.body = payload.body
    tmpl.variables = payload.variables
    tmpl.active = payload.active
    tmpl.updated_at = datetime.utcnow()

    await AuditService.log(
        db=db, user_id=current_user.id, action="TEMPLATE_UPDATED",
        entity_name="notification_template", entity_id=id,
        new_values={"name": payload.name, "event_type": payload.event_type},
    )
    await db.commit()
    await db.refresh(tmpl)
    return tmpl


@router.delete("/notification-templates/{id}", status_code=200)
async def delete_notification_template(
    id: UUID,
    current_user: User = Depends(verify_admin),
    db: AsyncSession = Depends(get_db),
):
    """Delete a notification template. Admins only."""
    await ensure_phase14_schema(db)
    res = await db.execute(select(NotificationTemplate).where(NotificationTemplate.id == id))
    tmpl = res.scalars().first()
    if not tmpl:
        raise HTTPException(status_code=404, detail="Notification template not found.")

    await db.delete(tmpl)
    await AuditService.log(
        db=db, user_id=current_user.id, action="TEMPLATE_DELETED",
        entity_name="notification_template", entity_id=id,
    )
    await db.commit()
    return {"status": "success", "message": "Notification template deleted."}


# ════════════════════════════════════════════════════════════════════════════
# NOTIFICATION DISPATCH & HISTORY
# ════════════════════════════════════════════════════════════════════════════

@router.post("/notifications/send")
async def send_notification(
    payload: SendNotificationRequest,
    current_user: User = Depends(verify_compliance_officer),
    db: AsyncSession = Depends(get_db),
):
    """Dispatch a notification across specified channels."""
    await ensure_phase14_schema(db)
    results = await NotificationService.send(
        db=db,
        event_type=payload.event_type,
        channels=payload.channels,
        variables=payload.variables,
        user_id=payload.user_id,
        to_email=payload.to_email,
        priority=payload.priority,
    )
    return {"dispatched": len(results), "results": results}


@router.get("/notifications/history", response_model=List[NotificationResponse])
async def notification_history(
    channel: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(verify_compliance_officer),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve notification delivery history."""
    await ensure_phase14_schema(db)
    return await NotificationService.get_history(db=db, channel=channel, status=status, limit=limit)


@router.get("/notifications/unread-count")
async def unread_count(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return count of unread in-app notifications for the current user."""
    await ensure_phase14_schema(db)
    count = await NotificationService.get_unread_count(db=db, user_id=current_user.id)
    return {"unread_count": count}


# ════════════════════════════════════════════════════════════════════════════
# WEBHOOK ENDPOINTS
# ════════════════════════════════════════════════════════════════════════════

@router.get("/webhooks", response_model=List[WebhookEndpointResponse])
async def list_webhooks(
    current_user: User = Depends(verify_compliance_officer),
    db: AsyncSession = Depends(get_db),
):
    """List all registered outgoing webhook endpoints."""
    await ensure_phase14_schema(db)
    res = await db.execute(select(WebhookEndpoint).order_by(desc(WebhookEndpoint.created_at)))
    return res.scalars().all()


@router.post("/webhooks", response_model=WebhookEndpointResponse, status_code=201)
async def create_webhook(
    payload: WebhookEndpointCreate,
    current_user: User = Depends(verify_admin),
    db: AsyncSession = Depends(get_db),
):
    """Register a new outgoing webhook endpoint. Admins only."""
    await ensure_phase14_schema(db)
    ep = WebhookEndpoint(
        id=uuid4(),
        name=payload.name,
        url=payload.url,
        secret=payload.secret,
        enabled=payload.enabled,
        events=payload.events,
        retries=payload.retries,
    )
    db.add(ep)
    await AuditService.log(
        db=db, user_id=current_user.id, action="WEBHOOK_ADDED",
        entity_name="webhook_endpoint", entity_id=ep.id,
        new_values={"name": payload.name, "url": payload.url, "events": payload.events},
    )
    await db.commit()
    await db.refresh(ep)
    return ep


@router.put("/webhooks/{id}", response_model=WebhookEndpointResponse)
async def update_webhook(
    id: UUID,
    payload: WebhookEndpointUpdate,
    current_user: User = Depends(verify_admin),
    db: AsyncSession = Depends(get_db),
):
    """Update a webhook endpoint. Admins only."""
    await ensure_phase14_schema(db)
    res = await db.execute(select(WebhookEndpoint).where(WebhookEndpoint.id == id))
    ep = res.scalars().first()
    if not ep:
        raise HTTPException(status_code=404, detail="Webhook endpoint not found.")

    if payload.name is not None:
        ep.name = payload.name
    if payload.url is not None:
        ep.url = payload.url
    if payload.enabled is not None:
        ep.enabled = payload.enabled
    if payload.events is not None:
        ep.events = payload.events
    if payload.retries is not None:
        ep.retries = payload.retries
    ep.updated_at = datetime.utcnow()

    await AuditService.log(
        db=db, user_id=current_user.id, action="WEBHOOK_UPDATED",
        entity_name="webhook_endpoint", entity_id=id,
        new_values={"enabled": ep.enabled},
    )
    await db.commit()
    await db.refresh(ep)
    return ep


@router.delete("/webhooks/{id}", status_code=200)
async def delete_webhook(
    id: UUID,
    current_user: User = Depends(verify_admin),
    db: AsyncSession = Depends(get_db),
):
    """Delete a webhook endpoint. Admins only."""
    await ensure_phase14_schema(db)
    res = await db.execute(select(WebhookEndpoint).where(WebhookEndpoint.id == id))
    ep = res.scalars().first()
    if not ep:
        raise HTTPException(status_code=404, detail="Webhook endpoint not found.")

    await db.delete(ep)
    await AuditService.log(
        db=db, user_id=current_user.id, action="WEBHOOK_DELETED",
        entity_name="webhook_endpoint", entity_id=id,
    )
    await db.commit()
    return {"status": "success", "message": "Webhook endpoint removed."}


@router.post("/webhooks/{id}/test")
async def test_webhook(
    id: UUID,
    current_user: User = Depends(verify_admin),
    db: AsyncSession = Depends(get_db),
):
    """Send a test event to a webhook endpoint. Admins only."""
    await ensure_phase14_schema(db)
    res = await db.execute(select(WebhookEndpoint).where(WebhookEndpoint.id == id))
    ep = res.scalars().first()
    if not ep:
        raise HTTPException(status_code=404, detail="Webhook endpoint not found.")

    results = await WebhookService.dispatch_event(
        db=db,
        event="customer.approved",
        payload={
            "test": True,
            "customer_id": "00000000-0000-0000-0000-000000000001",
            "customer_name": "Test Customer",
            "risk_score": 25,
        },
        user_id=current_user.id,
    )
    return {"test_dispatched": True, "results": results}


# ════════════════════════════════════════════════════════════════════════════
# WEBHOOK LOGS
# ════════════════════════════════════════════════════════════════════════════

@router.get("/webhooks/{id}/logs", response_model=List[WebhookLogResponse])
async def webhook_logs(
    id: UUID,
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(verify_compliance_officer),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve webhook execution logs for a specific endpoint."""
    await ensure_phase14_schema(db)
    return await WebhookService.get_logs(db=db, endpoint_id=id, limit=limit)


@router.get("/webhooks/logs/all", response_model=List[WebhookLogResponse])
async def all_webhook_logs(
    event: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(verify_compliance_officer),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve all webhook execution logs."""
    await ensure_phase14_schema(db)
    return await WebhookService.get_logs(db=db, event=event, limit=limit)


@router.get("/webhooks/events/list")
async def list_webhook_events(
    current_user: User = Depends(verify_compliance_officer),
):
    """List all supported webhook event types."""
    return {"events": WEBHOOK_EVENTS}
