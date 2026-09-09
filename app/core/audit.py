"""Audit log with hash-chain tamper evidence.

Every action in the system (generate, approve, reject, finalize, escalate, etc.)
is recorded in the audit log. Each entry includes the hash of the previous entry,
creating a chain that makes tampering detectable.

The hash covers: action, user_id, memo_id, section_key, rule_applied,
comment, payload_json, timestamp, and previous_hash.

Design decision: Hash-chaining is a lightweight tamper-evidence mechanism.
It doesn't prevent tampering by someone with DB write access, but it makes
tampering detectable during an audit — the chain will be broken.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.db.models import AuditLog

logger = logging.getLogger(__name__)


def _compute_hash(
    action: str,
    user_id: Optional[str],
    memo_id: Optional[str],
    section_key: Optional[str],
    rule_applied: Optional[str],
    comment: Optional[str],
    payload_json: Optional[Dict[str, Any]],
    timestamp: datetime,
    previous_hash: Optional[str],
) -> str:
    """Compute SHA-256 hash of the audit entry fields."""
    # Normalize timestamp: ensure timezone-aware (UTC) for consistent hashing.
    # SQLite strips tzinfo, so we must re-attach UTC when reading back.
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    data = {
        "action": action,
        "user_id": user_id,
        "memo_id": memo_id,
        "section_key": section_key,
        "rule_applied": rule_applied,
        "comment": comment,
        "payload": json.dumps(payload_json or {}, sort_keys=True, default=str),
        "timestamp": timestamp.isoformat(),
        "previous_hash": previous_hash or "genesis",
    }
    serialized = json.dumps(data, sort_keys=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _get_last_hash(db: Session, memo_id: Optional[str] = None) -> Optional[str]:
    """Get the hash of the most recent audit log entry."""
    query = db.query(AuditLog).order_by(desc(AuditLog.id))
    if memo_id:
        query = query.filter(AuditLog.memo_id == memo_id)
    last = query.first()
    return last.entry_hash if last else None


def record_event(
    db: Session,
    action: str,
    user_id: Optional[str] = None,
    memo_id: Optional[str] = None,
    section_key: Optional[str] = None,
    rule_applied: Optional[str] = None,
    comment: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
) -> AuditLog:
    """Record an audit event with hash-chain integrity.

    Args:
        db: Database session.
        action: The action being recorded (e.g., 'generate_memo', 'auto_approve').
        user_id: The user performing the action (None for system actions).
        memo_id: The memo this action relates to.
        section_key: The specific section (if applicable).
        rule_applied: The rule that was applied (for auto-approvals).
        comment: Optional human comment.
        payload: Additional structured data.

    Returns:
        The created AuditLog entry.
    """
    now = datetime.now(timezone.utc)
    previous_hash = _get_last_hash(db)

    entry_hash = _compute_hash(
        action=action,
        user_id=user_id,
        memo_id=memo_id,
        section_key=section_key,
        rule_applied=rule_applied,
        comment=comment,
        payload_json=payload,
        timestamp=now,
        previous_hash=previous_hash,
    )

    entry = AuditLog(
        memo_id=memo_id,
        action=action,
        user_id=user_id,
        section_key=section_key,
        rule_applied=rule_applied,
        comment=comment,
        payload_json=payload or {},
        timestamp=now,
        previous_hash=previous_hash,
        entry_hash=entry_hash,
    )
    db.add(entry)
    db.flush()

    logger.info(
        "Audit: action=%s memo=%s user=%s section=%s rule=%s",
        action, memo_id, user_id, section_key, rule_applied,
    )
    return entry


def record_approval(
    db: Session,
    memo_id: str,
    section_key: str,
    user_id: Optional[str],
    action: str,
    rule_applied: Optional[str] = None,
    comment: Optional[str] = None,
) -> AuditLog:
    """Convenience wrapper for recording approval decisions.

    Args:
        db: Database session.
        memo_id: The memo ID.
        section_key: The section being approved/rejected.
        user_id: The user (None for auto-approvals).
        action: 'auto_approve', 'manual_approve', or 'reject'.
        rule_applied: The rule that was applied.
        comment: Optional comment.

    Returns:
        The created AuditLog entry.
    """
    return record_event(
        db=db,
        action=action,
        user_id=user_id,
        memo_id=memo_id,
        section_key=section_key,
        rule_applied=rule_applied,
        comment=comment,
        payload={"action_type": action},
    )


def verify_chain(db: Session, memo_id: Optional[str] = None) -> bool:
    """Verify the integrity of the audit log hash chain.

    Args:
        db: Database session.
        memo_id: Optional memo ID to verify only that memo's entries.

    Returns:
        True if the chain is intact, False if tampering detected.
    """
    query = db.query(AuditLog).order_by(AuditLog.id)
    if memo_id:
        query = query.filter(AuditLog.memo_id == memo_id)

    entries = query.all()
    if not entries:
        return True

    for i, entry in enumerate(entries):
        if i == 0:
            expected_prev = None
        else:
            expected_prev = entries[i - 1].entry_hash

        if entry.previous_hash != expected_prev:
            logger.error(
                "Audit chain broken at entry %d: expected prev=%s, got=%s",
                entry.id, expected_prev, entry.previous_hash,
            )
            return False

        computed = _compute_hash(
            action=entry.action,
            user_id=entry.user_id,
            memo_id=entry.memo_id,
            section_key=entry.section_key,
            rule_applied=entry.rule_applied,
            comment=entry.comment,
            payload_json=entry.payload_json,
            timestamp=entry.timestamp,
            previous_hash=entry.previous_hash,
        )
        if computed != entry.entry_hash:
            logger.error("Audit entry %d hash mismatch", entry.id)
            return False

    return True


def get_audit_log(
    db: Session,
    memo_id: Optional[str] = None,
    action: Optional[str] = None,
    limit: int = 100,
) -> list[AuditLog]:
    """Retrieve audit log entries with optional filtering.

    Args:
        db: Database session.
        memo_id: Filter by memo ID.
        action: Filter by action type.
        limit: Maximum entries to return.

    Returns:
        List of AuditLog entries, most recent first.
    """
    query = db.query(AuditLog).order_by(desc(AuditLog.id))
    if memo_id:
        query = query.filter(AuditLog.memo_id == memo_id)
    if action:
        query = query.filter(AuditLog.action == action)
    return query.limit(limit).all()
