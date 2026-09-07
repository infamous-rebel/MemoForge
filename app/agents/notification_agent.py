"""Notification Agent — sends alerts via configurable channels.

Trigger events: memo_generated, section_requires_review, approval_stage_changed,
finalization_ready, sla_breach.

Channels: email, SMS, WhatsApp, in-app. Each has a provider pattern
that can be configured or mocked for demos.

Design decision: Notifications are logged to the audit trail for compliance.
The channel provider pattern allows swapping implementations without
changing agent code.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.core import audit
from app.core.business_config import get_notification_channels
from app.db.models import Notification

logger = logging.getLogger(__name__)


@dataclass
class NotificationRecord:
    """Record of a sent notification."""
    id: str = ""
    event_type: str = ""
    recipient: str = ""
    channel: str = ""
    status: str = "pending"
    subject: str = ""
    body: str = ""
    sent_at: Optional[datetime] = None
    error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "event_type": self.event_type,
            "recipient": self.recipient,
            "channel": self.channel,
            "status": self.status,
            "subject": self.subject,
            "body": self.body,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
        }


def send_notification(
    db: Session,
    event_type: str,
    recipient: str,
    memo_id: Optional[str] = None,
    data: Optional[Dict[str, Any]] = None,
    override_channels: Optional[List[str]] = None,
) -> List[NotificationRecord]:
    """Send notifications for an event through configured channels.

    Args:
        db: Database session.
        event_type: The event triggering the notification.
        recipient: User ID or email of the recipient.
        memo_id: Optional memo ID for context.
        data: Additional context data.
        override_channels: Override default channels for this event.

    Returns:
        List of NotificationRecord for each channel attempt.
    """
    channel_config = get_notification_channels()
    channels = override_channels or channel_config.get(event_type, ["in_app"])
    records = []

    for channel in channels:
        record = _send_via_channel(
            db=db,
            event_type=event_type,
            recipient=recipient,
            channel=channel,
            memo_id=memo_id,
            data=data or {},
        )
        records.append(record)

    # Audit log the notification
    audit.record_event(
        db=db,
        action="notify",
        memo_id=memo_id,
        user_id=recipient,
        payload={
            "event_type": event_type,
            "channels": channels,
            "recipient": recipient,
        },
    )

    return records


def get_pending_notifications(db: Session, user_id: str) -> List[Notification]:
    """Get pending/unread notifications for a user."""
    return (
        db.query(Notification)
        .filter(
            Notification.recipient == user_id,
            Notification.status.in_(["pending", "sent"]),
        )
        .order_by(Notification.timestamp.desc())
        .all()
    )


def _send_via_channel(
    db: Session,
    event_type: str,
    recipient: str,
    channel: str,
    memo_id: Optional[str],
    data: Dict[str, Any],
) -> NotificationRecord:
    """Send a notification through a specific channel."""
    now = datetime.now(timezone.utc)
    subject, body = _generate_content(event_type, data)

    record = NotificationRecord(
        event_type=event_type,
        recipient=recipient,
        channel=channel,
        subject=subject,
        body=body,
    )

    try:
        if channel == "email":
            _send_email(recipient, subject, body)
        elif channel == "sms":
            _send_sms(recipient, body)
        elif channel == "whatsapp":
            _send_whatsapp(recipient, body)
        elif channel == "in_app":
            pass  # In-app notifications are stored in DB only
        else:
            logger.warning("Unknown notification channel: %s", channel)

        record.status = "sent"
        record.sent_at = now

    except Exception as e:
        logger.error("Notification failed via %s: %s", channel, e)
        record.status = "failed"
        record.error = str(e)[:200]

    # Persist to database
    notification = Notification(
        memo_id=memo_id,
        event_type=event_type,
        recipient=recipient,
        channel=channel,
        status=record.status,
        subject=subject,
        body=body,
        payload_json=data,
        timestamp=now,
        sent_at=record.sent_at,
        error_message=record.error,
    )
    db.add(notification)
    db.flush()
    record.id = notification.id

    return record


def _generate_content(event_type: str, data: Dict[str, Any]) -> tuple:
    """Generate notification subject and body."""
    templates = {
        "memo_generated": (
            "New Memo Generated",
            f"A new credit memo has been generated for client {data.get('client_id', 'unknown')}. "
            f"Facility type: {data.get('facility_type', 'N/A')}. Please review.",
        ),
        "section_requires_review": (
            "Section Requires Review",
            f"Section '{data.get('section_key', 'unknown')}' in memo {data.get('memo_id', 'N/A')} "
            f"requires your review. Reason: {data.get('reason', 'Flagged for review')}.",
        ),
        "approval_stage_changed": (
            "Approval Stage Changed",
            f"Memo {data.get('memo_id', 'N/A')} has moved to stage: {data.get('new_stage', 'N/A')}.",
        ),
        "finalization_ready": (
            "Memo Ready for Finalization",
            f"Memo {data.get('memo_id', 'N/A')} is ready for finalization. "
            f"All sections have been approved.",
        ),
        "sla_breach": (
            "SLA Breach Alert",
            f"SLA breach detected for memo {data.get('memo_id', 'N/A')} at stage "
            f"'{data.get('stage', 'N/A')}'. Immediate attention required.",
        ),
    }

    subject, body = templates.get(event_type, (
        f"MemoForge Alert: {event_type}",
        f"Event: {event_type}\nData: {data}",
    ))

    return subject, body


def _send_email(recipient: str, subject: str, body: str) -> None:
    """Send email notification (logs in demo mode)."""
    logger.info("EMAIL → %s | Subject: %s | Body: %s", recipient, subject, body[:100])


def _send_sms(recipient: str, body: str) -> None:
    """Send SMS notification (logs in demo mode)."""
    logger.info("SMS → %s | Body: %s", recipient, body[:100])


def _send_whatsapp(recipient: str, body: str) -> None:
    """Send WhatsApp notification (logs in demo mode)."""
    logger.info("WHATSAPP → %s | Body: %s", recipient, body[:100])
