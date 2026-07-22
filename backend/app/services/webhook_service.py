"""
Webhook Service — Phase 14
============================
Dispatches outgoing webhook events to registered external endpoints.

Security:
  - Payloads are signed using HMAC SHA256
  - Signature delivered in X-Webhook-Signature header
  - Format: sha256=<hex_digest>

Retry Logic:
  - Failed dispatches are logged in WebhookLog with retry_count
  - Celery task retries up to endpoint.retries times

Supported Events:
  - customer.created       - customer.approved    - customer.rejected
  - alert.created          - case.created         - case.closed
  - sar.submitted          - screening.completed  - sync.completed
  - notification.sent
"""

import hashlib
import hmac
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4, UUID

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import WebhookEndpoint, WebhookLog
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)

# Supported outgoing event types
WEBHOOK_EVENTS = [
    "customer.created",
    "customer.approved",
    "customer.rejected",
    "alert.created",
    "case.created",
    "case.closed",
    "sar.submitted",
    "screening.completed",
    "sync.completed",
    "notification.sent",
    "policy.updated",
    "monitoring.triggered",
]


def sign_payload(secret: str, payload_bytes: bytes) -> str:
    """Generate HMAC SHA256 signature for a payload."""
    return (
        "sha256="
        + hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
    )


def verify_signature(secret: str, payload_bytes: bytes, signature: str) -> bool:
    """Verify that an incoming signature matches the expected HMAC."""
    expected = sign_payload(secret, payload_bytes)
    return hmac.compare_digest(expected, signature)


class WebhookService:
    """Handles outgoing webhook dispatch, signing, logging, and retries."""

    @staticmethod
    async def dispatch_event(
        db: AsyncSession,
        event: str,
        payload: Dict[str, Any],
        user_id: Optional[UUID] = None,
    ) -> List[Dict[str, Any]]:
        """
        Dispatch a webhook event to all active, subscribed endpoints.
        Signs each request with HMAC SHA256 and logs the attempt.
        """
        # Find all enabled endpoints that subscribe to this event
        res = await db.execute(
            select(WebhookEndpoint).where(WebhookEndpoint.enabled == True)
        )
        endpoints = res.scalars().all()

        # Enrich payload with metadata
        enriched = {
            "event": event,
            "timestamp": datetime.utcnow().isoformat(),
            "id": str(uuid4()),
            "data": payload,
        }
        payload_bytes = json.dumps(enriched, default=str).encode("utf-8")

        results = []
        for ep in endpoints:
            # Check if endpoint subscribes to this event
            ep_events = ep.events if isinstance(ep.events, list) else []
            if ep_events and event not in ep_events:
                continue

            signature = sign_payload(ep.secret, payload_bytes)
            log = WebhookLog(
                id=uuid4(),
                endpoint_id=ep.id,
                event=event,
                payload=enriched,
                signature=signature,
                status="pending",
                retry_count=0,
                created_at=datetime.utcnow(),
            )
            db.add(log)
            await db.flush()

            try:
                import httpx

                headers = {
                    "Content-Type": "application/json",
                    "X-Webhook-Signature": signature,
                    "X-Webhook-Event": event,
                    "User-Agent": "AML-Platform-Webhook/1.0",
                }
                async with httpx.AsyncClient(timeout=15) as client:
                    resp = await client.post(
                        ep.url,
                        content=payload_bytes,
                        headers=headers,
                    )
                log.response_code = resp.status_code
                log.response_body = resp.text[:2000]  # cap response body
                if 200 <= resp.status_code < 300:
                    log.status = "success"
                    logger.info(
                        f"[WEBHOOK] Delivered {event} -> {ep.url} [{resp.status_code}]"
                    )
                else:
                    log.status = "failed"
                    logger.warning(
                        f"[WEBHOOK] Delivery failed {event} -> {ep.url} [{resp.status_code}]"
                    )

            except Exception as exc:
                log.status = "failed"
                log.response_body = str(exc)[:2000]
                logger.error(f"[WEBHOOK] Dispatch error for {ep.url}: {exc}")

            # Audit
            await AuditService.log(
                db=db,
                user_id=user_id,
                action=(
                    "WEBHOOK_TRIGGERED" if log.status == "success" else "WEBHOOK_FAILED"
                ),
                entity_name="webhook_log",
                entity_id=log.id,
                new_values={"event": event, "endpoint": ep.url, "status": log.status},
            )

            results.append(
                {
                    "endpoint_id": str(ep.id),
                    "url": ep.url,
                    "event": event,
                    "status": log.status,
                    "response_code": log.response_code,
                    "log_id": str(log.id),
                }
            )

        await db.commit()
        return results

    @staticmethod
    async def retry_failed_webhooks(db: AsyncSession) -> int:
        """Re-queue and re-dispatch failed webhook logs respecting max retries."""
        # Fetch failed logs with remaining retries
        from sqlalchemy import text as sa_text

        res = await db.execute(
            select(WebhookLog, WebhookEndpoint)
            .join(WebhookEndpoint, WebhookLog.endpoint_id == WebhookEndpoint.id)
            .where(WebhookLog.status == "failed")
        )
        rows = res.all()

        retried = 0
        for log, ep in rows:
            if log.retry_count >= ep.retries:
                continue
            log.retry_count += 1
            log.status = "retry"

            try:
                payload_bytes = json.dumps(log.payload, default=str).encode("utf-8")
                signature = sign_payload(ep.secret, payload_bytes)
                import httpx

                headers = {
                    "Content-Type": "application/json",
                    "X-Webhook-Signature": signature,
                    "X-Webhook-Event": log.event,
                    "User-Agent": "AML-Platform-Webhook/1.0",
                }
                async with httpx.AsyncClient(timeout=15) as client:
                    resp = await client.post(
                        ep.url, content=payload_bytes, headers=headers
                    )
                log.response_code = resp.status_code
                log.response_body = resp.text[:2000]
                log.status = "success" if 200 <= resp.status_code < 300 else "failed"
                retried += 1
            except Exception as exc:
                log.status = "failed"
                log.response_body = str(exc)[:2000]
                logger.error(f"[WEBHOOK RETRY] Still failing for {ep.url}: {exc}")

        await db.commit()
        return retried

    @staticmethod
    async def get_logs(
        db: AsyncSession,
        endpoint_id: Optional[UUID] = None,
        event: Optional[str] = None,
        limit: int = 50,
    ) -> List[WebhookLog]:
        """Retrieve webhook execution logs with optional filters."""
        q = select(WebhookLog).order_by(desc(WebhookLog.created_at)).limit(limit)
        if endpoint_id:
            q = q.where(WebhookLog.endpoint_id == endpoint_id)
        if event:
            q = q.where(WebhookLog.event == event)
        res = await db.execute(q)
        return res.scalars().all()
