"""
Notification Service — Phase 14
=================================
Dispatches notifications across all supported channels:
  - Email (mock SMTP / real SMTP via smtplib)
  - Slack (Incoming Webhook)
  - Microsoft Teams (Incoming Webhook)
  - In-App (stored in notifications table)

Features:
  - Template variable rendering ({{variable_name}} placeholders)
  - Priority levels: low, medium, high, urgent
  - Retry logic tracked in DB
  - Full delivery history
  - Audit logging
  - Mock mode for all channels when credentials are absent
"""

import logging
import smtplib
import json
import re
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional
from uuid import uuid4, UUID

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Notification, NotificationTemplate, IntegrationSetting
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)

# ─── Default built-in templates ───────────────────────────────────────────────

DEFAULT_TEMPLATES: Dict[str, Dict[str, str]] = {
    "customer.approved": {
        "subject": "Your KYC application has been approved",
        "body": "Dear {{customer_name}},\n\nWe are pleased to inform you that your KYC application has been approved.\n\nRisk Level: {{risk_level}}\nDecision Date: {{decision_date}}\n\nYou may now access all platform services.\n\nRegards,\nCompliance Team",
    },
    "edd.required": {
        "subject": "Enhanced Due Diligence Required",
        "body": "Dear {{customer_name}},\n\nWe require additional documentation for Enhanced Due Diligence (EDD).\n\nCase Reference: {{case_id}}\nDeadline: {{deadline}}\n\nPlease submit the required documents at your earliest convenience.\n\nRegards,\nCompliance Team",
    },
    "manual.review": {
        "subject": "Your Account is Under Manual Review",
        "body": "Dear {{customer_name}},\n\nYour account has been flagged for manual compliance review.\n\nCase ID: {{case_id}}\nExpected Resolution: {{resolution_time}}\n\nOur team will contact you shortly.\n\nRegards,\nCompliance Team",
    },
    "customer.rejected": {
        "subject": "KYC Application Outcome",
        "body": "Dear {{customer_name}},\n\nUnfortunately, we are unable to onboard you at this time.\n\nReason: {{rejection_reason}}\n\nIf you believe this is in error, please contact support.\n\nRegards,\nCompliance Team",
    },
    "alert.high_risk": {
        "subject": "HIGH RISK Alert — Immediate Action Required",
        "body": "COMPLIANCE ALERT\n\nCustomer: {{customer_name}}\nRisk Score: {{risk_score}}\nAlert Type: {{alert_type}}\nTriggered At: {{triggered_at}}\n\nImmediate review required. Please investigate Case {{case_id}}.\n\nCompliance System",
    },
    "investigation.assigned": {
        "subject": "Investigation Assigned to You",
        "body": "You have been assigned a new investigation.\n\nCase ID: {{case_id}}\nCustomer: {{customer_name}}\nRisk Level: {{risk_level}}\nPriority: {{priority}}\n\nPlease log in to the investigation workspace to begin review.\n\nCompliance System",
    },
    "sar.submitted": {
        "subject": "SAR Filed — Reference {{sar_number}}",
        "body": "A Suspicious Activity Report has been filed.\n\nSAR Number: {{sar_number}}\nCase ID: {{case_id}}\nSubmitted By: {{submitted_by}}\nSubmitted At: {{submitted_at}}\n\nPlease retain this reference for your records.\n\nCompliance System",
    },
    "monitoring.reminder": {
        "subject": "Compliance Monitoring Reminder",
        "body": "This is a scheduled compliance monitoring reminder.\n\nCustomer: {{customer_name}}\nNext Review Date: {{next_review_date}}\nCurrent Risk Score: {{risk_score}}\n\nPlease complete the periodic review by the deadline.\n\nCompliance System",
    },
    "report.generated": {
        "subject": "Scheduled Report Generated — {{report_name}}",
        "body": "Your scheduled compliance report is ready.\n\nReport Name: {{report_name}}\nGenerated At: {{generated_at}}\nFormat: {{format}}\n\nPlease log in to download the report.\n\nCompliance System",
    },
    "policy.updated": {
        "subject": "Compliance Policy Updated — {{policy_name}}",
        "body": "A compliance policy has been updated.\n\nPolicy: {{policy_name}}\nUpdated By: {{updated_by}}\nUpdated At: {{updated_at}}\nVersion: {{version}}\n\nPlease review the updated policy at your earliest convenience.\n\nCompliance System",
    },
}


def render_template(body: str, variables: Dict[str, Any]) -> str:
    """Replace {{variable_name}} placeholders with actual values."""
    for key, value in variables.items():
        body = body.replace(f"{{{{{key}}}}}", str(value) if value is not None else "")
    return body


# ─── Channel Senders ──────────────────────────────────────────────────────────

async def _send_email(
    to_email: str,
    subject: str,
    body: str,
    smtp_setting: Optional[IntegrationSetting] = None,
) -> bool:
    """Send email via SMTP or mock."""
    if smtp_setting is None or not smtp_setting.api_key:
        logger.info(f"[EMAIL MOCK] To: {to_email} | Subject: {subject}")
        logger.debug(f"[EMAIL MOCK] Body: {body}")
        return True  # Mock success

    try:
        cfg = smtp_setting.configuration or {}
        host = cfg.get("smtp_host", "smtp.gmail.com")
        port = int(cfg.get("smtp_port", 587))
        username = smtp_setting.api_key
        password = smtp_setting.api_secret or ""

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = username
        msg["To"] = to_email
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP(host, port, timeout=10) as srv:
            srv.ehlo()
            srv.starttls()
            srv.login(username, password)
            srv.sendmail(username, [to_email], msg.as_string())
        logger.info(f"[EMAIL] Sent to {to_email}: {subject}")
        return True
    except Exception as exc:
        logger.error(f"[EMAIL] Failed for {to_email}: {exc}")
        return False


async def _send_slack(
    message: str,
    slack_setting: Optional[IntegrationSetting] = None,
) -> bool:
    """Post message to Slack Incoming Webhook or mock."""
    if slack_setting is None or not slack_setting.base_url:
        logger.info(f"[SLACK MOCK] Message: {message[:120]}...")
        return True

    try:
        import httpx
        payload = {"text": message}
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(slack_setting.base_url, json=payload)
            if resp.status_code == 200:
                logger.info(f"[SLACK] Message sent successfully.")
                return True
            logger.warning(f"[SLACK] Unexpected status {resp.status_code}")
            return False
    except Exception as exc:
        logger.error(f"[SLACK] Send failed: {exc}")
        return False


async def _send_teams(
    title: str,
    message: str,
    teams_setting: Optional[IntegrationSetting] = None,
) -> bool:
    """Post message to MS Teams Incoming Webhook or mock."""
    if teams_setting is None or not teams_setting.base_url:
        logger.info(f"[TEAMS MOCK] Title: {title} | Message: {message[:120]}...")
        return True

    try:
        import httpx
        payload = {
            "@type": "MessageCard",
            "@context": "http://schema.org/extensions",
            "themeColor": "0076D7",
            "summary": title,
            "sections": [{"activityTitle": title, "activityText": message}]
        }
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(teams_setting.base_url, json=payload)
            if resp.status_code in (200, 202):
                logger.info(f"[TEAMS] Message sent successfully.")
                return True
            return False
    except Exception as exc:
        logger.error(f"[TEAMS] Send failed: {exc}")
        return False


# ─── Notification Service ─────────────────────────────────────────────────────

class NotificationService:
    """Orchestrates multi-channel notification dispatch."""

    @staticmethod
    async def _load_setting(db: AsyncSession, provider_name: str) -> Optional[IntegrationSetting]:
        res = await db.execute(
            select(IntegrationSetting).where(IntegrationSetting.provider_name == provider_name)
        )
        return res.scalars().first()

    @staticmethod
    async def get_template(
        db: AsyncSession,
        event_type: str,
        channel: str = "email",
    ) -> Optional[Dict[str, str]]:
        """Load template from DB or fall back to built-in defaults."""
        res = await db.execute(
            select(NotificationTemplate).where(
                NotificationTemplate.event_type == event_type,
                NotificationTemplate.channel == channel,
                NotificationTemplate.active == True,
            )
        )
        tmpl = res.scalars().first()
        if tmpl:
            return {"subject": tmpl.subject or "", "body": tmpl.body, "template_id": str(tmpl.id)}

        # Fall back to built-in templates
        fallback = DEFAULT_TEMPLATES.get(event_type)
        if fallback:
            return {"subject": fallback["subject"], "body": fallback["body"], "template_id": None}
        return None

    @staticmethod
    async def send(
        db: AsyncSession,
        event_type: str,
        channels: List[str],
        variables: Dict[str, Any],
        user_id: Optional[UUID] = None,
        to_email: Optional[str] = None,
        priority: str = "medium",
    ) -> List[Dict[str, Any]]:
        """
        Dispatch a notification across the requested channels.
        Returns a list of dispatch results per channel.
        """
        results = []

        smtp_setting = await NotificationService._load_setting(db, "smtp_email")
        slack_setting = await NotificationService._load_setting(db, "slack")
        teams_setting = await NotificationService._load_setting(db, "teams")

        for channel in channels:
            tmpl = await NotificationService.get_template(db, event_type, channel)
            if not tmpl:
                # Fallback to email template for all channels
                tmpl = DEFAULT_TEMPLATES.get(event_type, {
                    "subject": f"Compliance Alert: {event_type}",
                    "body": f"Event: {event_type}\n\nDetails: {variables}"
                })
                tmpl["template_id"] = None

            subject = render_template(tmpl.get("subject", ""), variables)
            body = render_template(tmpl.get("body", ""), variables)
            title = subject or event_type.replace(".", " ").title()

            success = False
            try:
                if channel == "email":
                    success = await _send_email(
                        to_email=to_email or variables.get("email", "compliance@platform.local"),
                        subject=subject,
                        body=body,
                        smtp_setting=smtp_setting,
                    )
                elif channel == "slack":
                    slack_msg = f"*{title}*\n{body}"
                    success = await _send_slack(slack_msg, slack_setting)
                elif channel == "teams":
                    success = await _send_teams(title, body, teams_setting)
                elif channel == "in_app":
                    success = True  # always success for in-app (stored below)
                else:
                    logger.warning(f"Unknown notification channel: {channel}")
                    success = False

            except Exception as exc:
                logger.error(f"[NOTIFICATION] Channel {channel} failed: {exc}")
                success = False

            # Persist notification log
            notif = Notification(
                id=uuid4(),
                user_id=user_id,
                template_id=UUID(tmpl["template_id"]) if tmpl.get("template_id") else None,
                channel=channel,
                title=title,
                message=body,
                priority=priority,
                status="sent" if success else "failed",
                sent_at=datetime.utcnow() if success else None,
                retry_count=0,
                metadata_=variables,
            )
            db.add(notif)

            # Audit
            action = "NOTIFICATION_SENT" if success else "NOTIFICATION_FAILED"
            await AuditService.log(
                db=db,
                user_id=user_id,
                action=action,
                entity_name="notification",
                entity_id=notif.id,
                new_values={"channel": channel, "event_type": event_type, "priority": priority},
            )

            results.append({
                "channel": channel,
                "success": success,
                "notification_id": str(notif.id),
            })

        await db.commit()
        return results

    @staticmethod
    async def retry_failed(db: AsyncSession, max_retries: int = 3) -> int:
        """Retry all failed notifications that haven't exceeded retry limit."""
        res = await db.execute(
            select(Notification).where(
                Notification.status == "failed",
                Notification.retry_count < max_retries,
            )
        )
        failed = res.scalars().all()
        retried = 0
        for notif in failed:
            notif.retry_count += 1
            notif.status = "retry"
            retried += 1

        await db.commit()
        return retried

    @staticmethod
    async def get_history(
        db: AsyncSession,
        user_id: Optional[UUID] = None,
        channel: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[Notification]:
        """Fetch notification history with optional filters."""
        q = select(Notification).order_by(desc(Notification.created_at)).limit(limit)
        if user_id:
            q = q.where(Notification.user_id == user_id)
        if channel:
            q = q.where(Notification.channel == channel)
        if status:
            q = q.where(Notification.status == status)
        res = await db.execute(q)
        return res.scalars().all()

    @staticmethod
    async def get_unread_count(db: AsyncSession, user_id: UUID) -> int:
        """Count unread in-app notifications for a user."""
        from sqlalchemy import func
        res = await db.execute(
            select(func.count(Notification.id)).where(
                Notification.user_id == user_id,
                Notification.channel == "in_app",
                Notification.status == "sent",
            )
        )
        return res.scalar() or 0
