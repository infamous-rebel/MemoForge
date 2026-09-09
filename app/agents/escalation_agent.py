"""Escalation Agent — escalates stalled approvals per configurable ladder.

Ladder levels (based on SLA elapsed percentage):
- 50% SLA → remind
- 80% SLA → notice
- 100% SLA → escalate to manager
- 125% SLA → escalate to admin/compliance

Configurable per stage via config.json escalation_rules.

Design decision: Escalation is a scheduled check that runs periodically,
not triggered by individual events. This ensures no stalled memo is missed.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.core import audit
from app.core.business_config import get_approval_workflow, get_escalation_rules
from app.db.models import Escalation, Memo, WorkflowEvent

logger = logging.getLogger(__name__)


@dataclass
class EscalationTriggered:
    """Record of an escalation that was triggered."""
    memo_id: str
    stage: str
    level: str
    action: str
    recipient: str
    sla_hours: float
    elapsed_hours: float
    percentage: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "memo_id": self.memo_id,
            "stage": self.stage,
            "level": self.level,
            "action": self.action,
            "recipient": self.recipient,
            "sla_hours": self.sla_hours,
            "elapsed_hours": self.elapsed_hours,
            "percentage": self.percentage,
        }


def check_and_escalate(db: Session) -> List[EscalationTriggered]:
    """Check all active memos for SLA breaches and trigger escalations.

    Returns:
        List of EscalationTriggered for any new escalations.
    """
    workflow_config = get_approval_workflow()
    sla_hours = workflow_config.get("sla_hours", {})
    escalation_rules = get_escalation_rules()

    # Find all memos in active (non-finalized) stages
    active_memos = (
        db.query(Memo)
        .filter(Memo.status.notin_(["finalized", "rejected"]))
        .filter(Memo.workflow_stage != "draft")
        .all()
    )

    triggered = []
    now = datetime.now(timezone.utc)

    for memo in active_memos:
        stage = memo.workflow_stage
        stage_sla = sla_hours.get(stage)

        if stage_sla is None:
            continue

        # Calculate time in current stage
        last_event = (
            db.query(WorkflowEvent)
            .filter(
                WorkflowEvent.memo_id == memo.id,
                WorkflowEvent.to_stage == stage,
            )
            .order_by(WorkflowEvent.timestamp.desc())
            .first()
        )

        if last_event and last_event.timestamp:
            stage_start = last_event.timestamp
            if stage_start.tzinfo is None:
                stage_start = stage_start.replace(tzinfo=timezone.utc)
            elapsed = now - stage_start
            elapsed_hours = elapsed.total_seconds() / 3600
        else:
            elapsed_hours = 0

        if elapsed_hours <= 0:
            continue

        # Check escalation thresholds
        percentage = (elapsed_hours / stage_sla) * 100
        stage_rules = escalation_rules.get(stage, {})

        for threshold_pct, action in sorted(stage_rules.items(), key=lambda x: int(x[0])):
            threshold = int(threshold_pct)
            if percentage >= threshold:
                # Check if this escalation level was already triggered
                existing = (
                    db.query(Escalation)
                    .filter(
                        Escalation.memo_id == memo.id,
                        Escalation.stage == stage,
                        Escalation.level == action,
                        Escalation.status == "active",
                    )
                    .first()
                )

                if existing:
                    continue

                # Determine recipient based on action
                recipient = _get_recipient(action, stage)

                # Create escalation record
                esc = Escalation(
                    memo_id=memo.id,
                    stage=stage,
                    level=action,
                    recipient=recipient,
                    status="active",
                    sla_deadline=stage_start + timedelta(hours=stage_sla) if last_event else None,
                    timestamp=now,
                )
                db.add(esc)

                # Audit log
                audit.record_event(
                    db=db,
                    action="escalate",
                    memo_id=memo.id,
                    payload={
                        "stage": stage,
                        "level": action,
                        "elapsed_hours": round(elapsed_hours, 1),
                        "sla_hours": stage_sla,
                        "percentage": round(percentage, 1),
                    },
                )

                triggered.append(EscalationTriggered(
                    memo_id=memo.id,
                    stage=stage,
                    level=action,
                    action=action,
                    recipient=recipient,
                    sla_hours=stage_sla,
                    elapsed_hours=round(elapsed_hours, 1),
                    percentage=round(percentage, 1),
                ))

                logger.warning(
                    "Escalation: memo=%s stage=%s level=%s elapsed=%.1fh/%dh (%.0f%%)",
                    memo.id, stage, action, elapsed_hours, stage_sla, percentage,
                )

    db.flush()
    return triggered


def get_active_escalations(db: Session) -> List[Escalation]:
    """Get all active escalations."""
    return (
        db.query(Escalation)
        .filter(Escalation.status == "active")
        .order_by(Escalation.timestamp.desc())
        .all()
    )


def resolve_escalation(db: Session, escalation_id: str, user_id: str) -> Escalation:
    """Mark an escalation as resolved."""
    esc = db.query(Escalation).filter(Escalation.id == escalation_id).first()
    if not esc:
        raise ValueError(f"Escalation {escalation_id} not found")

    esc.status = "resolved"
    esc.resolved_at = datetime.now(timezone.utc)

    audit.record_event(
        db=db,
        action="resolve_escalation",
        user_id=user_id,
        memo_id=esc.memo_id,
        payload={"escalation_id": escalation_id, "stage": esc.stage},
    )

    db.flush()
    return esc


def _get_recipient(action: str, stage: str) -> str:
    """Determine the escalation recipient based on action and stage."""
    recipients = {
        "remind": f"rm_assigned_{stage}",
        "notice": f"rm_assigned_{stage}",
        "escalate_to_manager": "manager_credit_risk",
        "escalate_to_admin": "admin_compliance",
    }
    return recipients.get(action, "admin_system")
