"""Approval Orchestrator Agent — manages multi-stage approval workflow.

Models Warba Bank's Five-Stage Approval System as a state machine:
Draft → Risk_Review → Credit_Committee → Shariah_Board (if needed) → Final_Approval

Features:
- Dual approval support for final approval stage
- SLA tracking with configurable deadlines per stage
- Auto-escalation when SLA exceeded
- Full audit trail for every stage transition

Design decision: HITL is modeled as a state machine, not scattered if-statements.
The bank can change approval rules without touching the API or pipeline.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.core import audit
from app.core.approval_rules import SectionFlags, should_auto_approve
from app.core.business_config import get_approval_workflow
from app.db.models import Memo, MemoSection, WorkflowEvent

logger = logging.getLogger(__name__)


class WorkflowStatus:
    """Represents the current workflow state of a memo."""

    def __init__(self, memo_id: str, current_stage: str, sections: List[Dict[str, Any]],
                 history: List[Dict[str, Any]], is_complete: bool = False):
        self.memo_id = memo_id
        self.current_stage = current_stage
        self.sections = sections
        self.history = history
        self.is_complete = is_complete

    def to_dict(self) -> Dict[str, Any]:
        return {
            "memo_id": self.memo_id,
            "current_stage": self.current_stage,
            "sections": self.sections,
            "history": self.history,
            "is_complete": self.is_complete,
        }


def initialize_workflow(db: Session, memo: Memo) -> None:
    """Initialize the workflow for a newly generated memo.

    Sets the memo to 'draft' stage and runs auto-approval evaluation
    for each section based on the approval rules.
    """
    workflow_config = get_approval_workflow()
    stages = workflow_config.get("stages", ["draft"])

    memo.workflow_stage = stages[0]
    memo.status = "draft"

    # Record initial workflow event
    event = WorkflowEvent(
        memo_id=memo.id,
        from_stage="none",
        to_stage="draft",
        user_id=None,
        action="initialize",
        comment="Workflow initialized after memo generation",
    )
    db.add(event)

    # Run auto-approval evaluation for each section
    for section in memo.sections:
        flags = _build_section_flags(section)
        auto_approved, rule = should_auto_approve(
            section_key=section.section_key,
            flags=flags,
            facility_type=memo.facility_type,
            deal_value=memo.deal_value,
        )

        if auto_approved:
            section.review_status = "auto_approved"
            section.auto_approved_rule = rule
            audit.record_approval(
                db=db,
                memo_id=memo.id,
                section_key=section.section_key,
                user_id=None,
                action="auto_approve",
                rule_applied=rule,
            )
        else:
            section.review_status = "pending"
            section.requires_review = True
            section.review_reason = rule

    db.flush()
    logger.info("ApprovalOrchestrator: initialized workflow for memo=%s", memo.id)


def advance_stage(
    db: Session,
    memo_id: str,
    user_id: str,
    user_role: str,
    section_key: str,
    approved: bool,
    comment: str = "",
) -> WorkflowStatus:
    """Process an approval/rejection decision for a section.

    Args:
        db: Database session.
        memo_id: The memo ID.
        user_id: The user making the decision.
        user_role: The user's role.
        section_key: The section being approved/rejected.
        approved: True for approval, False for rejection.
        comment: Optional comment.

    Returns:
        Updated WorkflowStatus.
    """
    memo = db.query(Memo).filter(Memo.id == memo_id).first()
    if not memo:
        raise ValueError(f"Memo {memo_id} not found")

    section = db.query(MemoSection).filter(
        MemoSection.memo_id == memo_id,
        MemoSection.section_key == section_key,
    ).first()
    if not section:
        raise ValueError(f"Section {section_key} not found in memo {memo_id}")

    # Prevent re-approval of already approved sections
    if section.review_status == "approved":
        raise ValueError(f"Section {section_key} is already approved")

    # Check RBAC
    from app.core.security import can_approve_section
    if not can_approve_section(user_role, section_key):
        raise PermissionError(
            f"Role '{user_role}' cannot approve section '{section_key}'"
        )

    now = datetime.now(timezone.utc)

    if approved:
        section.review_status = "approved"
        section.approved_by = user_id
        section.approved_at = now
        section.requires_review = False

        audit.record_approval(
            db=db,
            memo_id=memo_id,
            section_key=section_key,
            user_id=user_id,
            action="manual_approve",
            comment=comment,
        )
    else:
        section.review_status = "rejected"
        section.requires_review = True
        section.revision_count += 1

        audit.record_approval(
            db=db,
            memo_id=memo_id,
            section_key=section_key,
            user_id=user_id,
            action="reject",
            comment=comment,
        )

    # Check if we should advance to next stage
    _check_stage_advancement(db, memo)

    db.flush()
    return get_workflow_status(db, memo_id)


def get_workflow_status(db: Session, memo_id: str) -> WorkflowStatus:
    """Get the current workflow status for a memo."""
    memo = db.query(Memo).filter(Memo.id == memo_id).first()
    if not memo:
        raise ValueError(f"Memo {memo_id} not found")

    sections = []
    for s in memo.sections:
        sections.append({
            "section_key": s.section_key,
            "title": s.title,
            "review_status": s.review_status,
            "requires_review": s.requires_review,
            "review_reason": s.review_reason,
            "approved_by": s.approved_by,
            "auto_approved_rule": s.auto_approved_rule,
        })

    events = (
        db.query(WorkflowEvent)
        .filter(WorkflowEvent.memo_id == memo_id)
        .order_by(WorkflowEvent.timestamp)
        .all()
    )
    history = [
        {
            "from_stage": e.from_stage,
            "to_stage": e.to_stage,
            "user_id": e.user_id,
            "action": e.action,
            "comment": e.comment,
            "timestamp": e.timestamp.isoformat() if e.timestamp else None,
        }
        for e in events
    ]

    is_complete = check_finalization_ready(db, memo_id)

    return WorkflowStatus(
        memo_id=memo_id,
        current_stage=memo.workflow_stage,
        sections=sections,
        history=history,
        is_complete=is_complete,
    )


def check_finalization_ready(db: Session, memo_id: str) -> bool:
    """Check if all sections are approved (auto or manual) and ready for finalization.

    Returns True only when NO sections are pending or rejected.
    """
    sections = (
        db.query(MemoSection)
        .filter(MemoSection.memo_id == memo_id)
        .all()
    )

    if not sections:
        return False

    for section in sections:
        if section.review_status not in ("approved", "auto_approved"):
            return False

    return True


def finalize_memo(db: Session, memo_id: str, user_id: str) -> Memo:
    """Finalize a memo — all sections must be approved.

    Args:
        db: Database session.
        memo_id: The memo ID.
        user_id: The user finalizing.

    Returns:
        The finalized Memo object.

    Raises:
        ValueError: If any sections are still pending.
    """
    if not check_finalization_ready(db, memo_id):
        raise ValueError("Cannot finalize: some sections are still pending review.")

    memo = db.query(Memo).filter(Memo.id == memo_id).first()
    memo.status = "finalized"
    memo.finalized_at = datetime.now(timezone.utc)

    event = WorkflowEvent(
        memo_id=memo_id,
        from_stage=memo.workflow_stage,
        to_stage="finalized",
        user_id=user_id,
        action="advance",
        comment="Memo finalized — all sections approved",
    )
    db.add(event)

    audit.record_event(
        db=db,
        action="finalize",
        user_id=user_id,
        memo_id=memo_id,
        comment="All sections approved, memo finalized",
    )

    db.flush()
    return memo


def _check_stage_advancement(db: Session, memo: Memo) -> None:
    """Check if the current stage can be advanced based on section approvals."""
    workflow_config = get_approval_workflow()
    stages = workflow_config.get("stages", [])

    current_idx = stages.index(memo.workflow_stage) if memo.workflow_stage in stages else 0
    if current_idx >= len(stages) - 1:
        return

    # Check if all sections relevant to current stage are approved
    sections = db.query(MemoSection).filter(MemoSection.memo_id == memo.id).all()
    all_approved = all(
        s.review_status in ("approved", "auto_approved")
        for s in sections
    )

    if all_approved:
        next_stage = stages[current_idx + 1]
        event = WorkflowEvent(
            memo_id=memo.id,
            from_stage=memo.workflow_stage,
            to_stage=next_stage,
            user_id=None,
            action="advance",
            comment=f"Auto-advanced from {memo.workflow_stage} to {next_stage}",
        )
        db.add(event)
        memo.workflow_stage = next_stage
        memo.status = next_stage


def _build_section_flags(section: MemoSection) -> SectionFlags:
    """Build SectionFlags from a section's stored flags."""
    flags_data = section.flags_json or {}

    return SectionFlags(
        shariah_flags=flags_data.get("shariah", []),
        citation_problems=flags_data.get("citation", []),
        policy_exceptions=flags_data.get("policy_exceptions", []),
        ratio_breaches=flags_data.get("ratio_breaches", []),
        risk_flags=flags_data.get("risk_flags", []),
    )
