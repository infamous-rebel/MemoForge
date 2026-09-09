"""SQLAlchemy ORM models for MemoForge.

Models:
- Memo: Top-level credit memo entity.
- MemoSection: Individual sections of a memo (borrower overview, financial analysis, etc.).
- Document: Source documents ingested into the RAG system.
- Chunk: Document chunks with embeddings for vector search.
- AuditLog: Immutable, hash-chained audit trail.
- Notification: Notification records for event-driven alerts.
- WorkflowEvent: Approval workflow stage transitions.
- Escalation: Escalation records for SLA breaches.
- Report: Generated report records.
- ComplianceResult: Compliance check results per memo section.
- UserAccount: Authenticated users with roles and hashed passwords.

Design decision: All state transitions and decisions are persisted to enable
full audit trail reconstruction. The AuditLog uses hash-chaining for tamper
evidence (each entry includes the hash of the previous entry).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


# Portable JSON column type: JSONB on PostgreSQL (indexed, binary storage),
# plain JSON on SQLite (tests and local development).
JSONVariant = JSON().with_variant(JSONB(), "postgresql")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return str(uuid.uuid4())


def _new_memo_id() -> str:
    """Generate a human-readable memo ID: MEM-YYYY-NNN.

    Uses a random 3-digit suffix. Collision risk is negligible for
    production volumes (<10k memos per year). The seed script sets
    explicit IDs so this only applies to runtime-generated memos.
    """
    import random
    year = datetime.now(timezone.utc).year
    seq = random.randint(100, 999)
    return f"MEM-{year}-{seq:03d}"


# =============================================================================
# Memo & Sections
# =============================================================================

class Memo(Base):
    """Top-level credit memo entity."""
    __tablename__ = "memos"

    id = Column(String(36), primary_key=True, default=_new_memo_id)
    client_id = Column(String(255), nullable=False, index=True)
    client_name = Column(String(500), nullable=True)
    facility_type = Column(String(50), nullable=False)
    bank_type = Column(String(50), nullable=False, default="islamic")
    deal_value = Column(Float, nullable=False, default=0.0)
    currency = Column(String(10), nullable=False, default="KWD")
    status = Column(String(50), nullable=False, default="draft")
    # Status values: draft, generating, review, risk_review, credit_committee,
    #                shariah_board, final_approval, finalized, rejected
    workflow_stage = Column(String(50), nullable=False, default="draft")
    created_by = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)
    finalized_at = Column(DateTime(timezone=True), nullable=True)
    output_file_path = Column(String(1000), nullable=True)
    metadata_json = Column(JSONVariant, nullable=True, default=dict)

    # Relationships
    sections = relationship("MemoSection", back_populates="memo", cascade="all, delete-orphan")
    audit_entries = relationship("AuditLog", back_populates="memo", cascade="all, delete-orphan")
    workflow_events = relationship("WorkflowEvent", back_populates="memo", cascade="all, delete-orphan")
    compliance_results = relationship("ComplianceResult", back_populates="memo", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="memo", cascade="all, delete-orphan")
    escalations = relationship("Escalation", back_populates="memo", cascade="all, delete-orphan")


class MemoSection(Base):
    """Individual section of a credit memo."""
    __tablename__ = "memo_sections"
    __table_args__ = (
        UniqueConstraint("memo_id", "section_key", name="uq_memo_section"),
    )

    id = Column(String(36), primary_key=True, default=_new_id)
    memo_id = Column(String(36), ForeignKey("memos.id", ondelete="CASCADE"), nullable=False)
    section_key = Column(String(100), nullable=False)
    # section_key values: borrower_overview, financial_analysis, risk_and_mitigants,
    #                     policy_exceptions, recommendation, shariah_flags, sukuk_facility
    title = Column(String(500), nullable=True)
    content = Column(Text, nullable=True)
    citations_json = Column(JSONVariant, nullable=True, default=list)
    requires_review = Column(Boolean, nullable=False, default=False)
    review_reason = Column(String(500), nullable=True)
    review_status = Column(String(50), nullable=False, default="pending")
    # review_status values: pending, auto_approved, approved, rejected, needs_revision
    approved_by = Column(String(255), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    auto_approved_rule = Column(String(500), nullable=True)
    flags_json = Column(JSONVariant, nullable=True, default=dict)
    revision_count = Column(Integer, nullable=False, default=0)

    memo = relationship("Memo", back_populates="sections")


# =============================================================================
# RAG: Documents & Chunks
# =============================================================================

class Document(Base):
    """Source document ingested into the RAG system."""
    __tablename__ = "documents"

    id = Column(String(36), primary_key=True, default=_new_id)
    title = Column(String(500), nullable=False)
    document_type = Column(String(100), nullable=False)
    # document_type: financial_statement, facility_agreement, correspondence, etc.
    client_id = Column(String(255), nullable=True, index=True)
    source_system = Column(String(255), nullable=True)
    acl_groups = Column(JSONVariant, nullable=True, default=list)
    file_path = Column(String(1000), nullable=True)
    content_hash = Column(String(128), nullable=True)
    ingested_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    metadata_json = Column(JSONVariant, nullable=True, default=dict)

    chunks = relationship("Chunk", back_populates="document", cascade="all, delete-orphan")


class Chunk(Base):
    """Document chunk with embedding for vector search."""
    __tablename__ = "chunks"

    id = Column(String(36), primary_key=True, default=_new_id)
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    client_id = Column(String(255), nullable=True, index=True)
    acl_groups = Column(JSONVariant, nullable=True, default=list)
    # Embedding stored as JSON array (for pgvector, use pgvector extension)
    embedding = Column(JSONVariant, nullable=True)
    token_count = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    document = relationship("Document", back_populates="chunks")


# =============================================================================
# Audit Log (hash-chained for tamper evidence)
# =============================================================================

class AuditLog(Base):
    """Immutable, hash-chained audit trail.

    Each entry includes the hash of the previous entry, creating a chain
    that makes tampering detectable. The hash covers: action, user_id,
    memo_id, payload, timestamp, and the previous hash.
    """
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    memo_id = Column(String(36), ForeignKey("memos.id", ondelete="SET NULL"), nullable=True, index=True)
    action = Column(String(100), nullable=False, index=True)
    # action values: generate_memo, auto_approve, manual_approve, reject, finalize,
    #                stage_change, escalate, notify, compliance_check, ecl_compute
    user_id = Column(String(255), nullable=True)
    section_key = Column(String(100), nullable=True)
    rule_applied = Column(String(500), nullable=True)
    comment = Column(Text, nullable=True)
    payload_json = Column(JSONVariant, nullable=True, default=dict)
    timestamp = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    previous_hash = Column(String(128), nullable=True)
    entry_hash = Column(String(128), nullable=False)

    memo = relationship("Memo", back_populates="audit_entries")


# =============================================================================
# Workflow & Notifications
# =============================================================================

class WorkflowEvent(Base):
    """Records every approval workflow stage transition."""
    __tablename__ = "workflow_events"

    id = Column(String(36), primary_key=True, default=_new_id)
    memo_id = Column(String(36), ForeignKey("memos.id", ondelete="CASCADE"), nullable=False, index=True)
    from_stage = Column(String(50), nullable=False)
    to_stage = Column(String(50), nullable=False)
    user_id = Column(String(255), nullable=True)
    action = Column(String(50), nullable=False)
    # action: advance, reject, skip, escalate
    comment = Column(Text, nullable=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    memo = relationship("Memo", back_populates="workflow_events")


class Notification(Base):
    """Notification records for event-driven alerts."""
    __tablename__ = "notifications"

    id = Column(String(36), primary_key=True, default=_new_id)
    memo_id = Column(String(36), ForeignKey("memos.id", ondelete="SET NULL"), nullable=True, index=True)
    event_type = Column(String(100), nullable=False)
    # event_type: memo_generated, section_requires_review, approval_stage_changed,
    #             finalization_ready, sla_breach
    recipient = Column(String(255), nullable=False)
    channel = Column(String(50), nullable=False)
    # channel: email, sms, whatsapp, in_app
    status = Column(String(50), nullable=False, default="pending")
    # status: pending, sent, failed, read
    subject = Column(String(500), nullable=True)
    body = Column(Text, nullable=True)
    payload_json = Column(JSONVariant, nullable=True, default=dict)
    timestamp = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)

    memo = relationship("Memo", back_populates="notifications")


class Escalation(Base):
    """Escalation records for SLA breaches."""
    __tablename__ = "escalations"

    id = Column(String(36), primary_key=True, default=_new_id)
    memo_id = Column(String(36), ForeignKey("memos.id", ondelete="CASCADE"), nullable=False, index=True)
    stage = Column(String(50), nullable=False)
    level = Column(String(50), nullable=False)
    # level: remind, notice, escalate_to_manager, escalate_to_admin
    recipient = Column(String(255), nullable=False)
    status = Column(String(50), nullable=False, default="active")
    # status: active, resolved, dismissed
    sla_deadline = Column(DateTime(timezone=True), nullable=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    memo = relationship("Memo", back_populates="escalations")


class Report(Base):
    """Generated report records."""
    __tablename__ = "reports"

    id = Column(String(36), primary_key=True, default=_new_id)
    report_type = Column(String(100), nullable=False)
    # report_type: pipeline_status, approval_delay, ecl_summary, sla_violation
    filters_json = Column(JSONVariant, nullable=True, default=dict)
    format = Column(String(10), nullable=False, default="json")
    # format: pdf, csv, json
    generated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    file_path = Column(String(1000), nullable=True)
    summary_json = Column(JSONVariant, nullable=True, default=dict)
    generated_by = Column(String(255), nullable=True)


class ComplianceResult(Base):
    """Compliance check results per memo section."""
    __tablename__ = "compliance_results"

    id = Column(String(36), primary_key=True, default=_new_id)
    memo_id = Column(String(36), ForeignKey("memos.id", ondelete="CASCADE"), nullable=False, index=True)
    section_key = Column(String(100), nullable=False)
    flags_json = Column(JSONVariant, nullable=True, default=list)
    severity = Column(String(50), nullable=False, default="none")
    # severity: none, low, medium, high, critical
    required_role = Column(String(100), nullable=True)
    recommended_action = Column(String(500), nullable=True)
    checked_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    memo = relationship("Memo", back_populates="compliance_results")


class UserAccount(Base):
    """User accounts for authentication and RBAC.

    Passwords are stored as salted PBKDF2-SHA256 hashes (stdlib hashlib,
    no external dependency). Users are provisioned by Admins via the
    /v1/users endpoints or bootstrapped by the seed script.
    """
    __tablename__ = "user_accounts"

    id = Column(String(36), primary_key=True, default=_new_id)
    username = Column(String(255), nullable=False, unique=True, index=True)
    full_name = Column(String(500), nullable=False)
    email = Column(String(500), nullable=True)
    role = Column(String(50), nullable=False, default="RM")
    # role: RM, Risk, CreditCommittee, ShariahBoard, Admin
    password_hash = Column(String(500), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    last_login_at = Column(DateTime(timezone=True), nullable=True)
