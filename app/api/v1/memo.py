"""MemoForge FastAPI endpoints for credit memo management.

Endpoints:
- POST /v1/auth/token: Authenticate against the user store and get a JWT
- POST /v1/generate-memo: Generate a new credit memo
- GET  /v1/memos: List memos with pipeline + SLA summaries
- GET  /v1/memo/{id}: Get memo details
- POST /v1/memo/{id}/approve: Approve a section
- POST /v1/memo/{id}/reject: Reject a section
- POST /v1/memo/{id}/finalize: Finalize the memo
- GET  /v1/memo/{id}/workflow: Get workflow status (stages + SLA config)
- GET  /v1/memo/{id}/audit-log: Get audit trail for a memo
- POST /v1/memo/{id}/notify: Re-send notifications (admin)
- GET  /v1/reports/{report_type}: Generate on-demand report
- GET  /v1/notifications: List notifications for the current user
- POST /v1/notifications/{id}/read: Mark a notification as read
- GET  /v1/escalations: List active escalations
- POST /v1/escalations/check: Run the escalation check (admin)
- GET  /v1/audit-log: Global hash-chained audit log
- GET  /v1/users: List user accounts (admin)
- POST /v1/users: Create a user account (admin)
- GET  /v1/clients: Client directory from the CRM connector
- POST /v1/risk/ecl: Compute ECL for a portfolio
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.agents.approval_orchestrator import (
    advance_stage,
    check_finalization_ready,
    finalize_memo,
    get_workflow_status,
)
from app.agents.compiler_agent import run_compiler_agent
from app.agents.escalation_agent import check_and_escalate, get_active_escalations
from app.agents.graph import run_pipeline_up_to_review
from app.agents.notification_agent import send_notification
from app.agents.reporting_agent import generate_report
from app.core import audit, users
from app.core.business_config import get_approval_workflow
from app.core.security import (
    UserIdentity,
    can_approve_section,
    get_current_user,
    require_roles,
)
from app.db.models import Escalation, Memo, MemoSection, Notification, UserAccount, WorkflowEvent
from app.db.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["MemoForge"])


# =============================================================================
# Request/Response Models
# =============================================================================

class GenerateMemoRequest(BaseModel):
    client_id: str = Field(..., description="Client identifier")
    client_name: str = Field("", description="Client display name")
    facility_type: str = Field("murabaha", description="Islamic facility type")
    deal_value: float = Field(0.0, description="Deal value in KD")
    bank_type: str = Field("islamic", description="Bank type")


class GenerateMemoResponse(BaseModel):
    memo_id: str
    status: str
    sections: List[Dict[str, Any]]
    workflow_stage: str


class SectionApprovalRequest(BaseModel):
    section_key: str
    comment: str = ""


class MemoDetailResponse(BaseModel):
    id: str
    client_id: str
    client_name: Optional[str]
    facility_type: str
    deal_value: float
    status: str
    workflow_stage: str
    created_by: str
    created_at: Optional[str]
    finalized_at: Optional[str] = None
    output_file_path: Optional[str] = None
    sections: List[Dict[str, Any]]
    metadata: Optional[Dict[str, Any]] = None


class TokenRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    role: str
    full_name: str


class CreateUserRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=255)
    full_name: str = Field(..., min_length=1, max_length=500)
    email: str = Field("", max_length=500)
    role: str = Field(..., description="RM, Risk, CreditCommittee, ShariahBoard, Admin")
    password: str = Field(..., min_length=8, max_length=255)


class ECLRequest(BaseModel):
    portfolio_size: int = Field(200, description="Number of facilities")
    total_gross_financing: float = Field(4_150_000_000, description="Total gross financing in KD")
    npl_ratio: float = Field(0.0145, description="NPL ratio")


# =============================================================================
# Helpers
# =============================================================================

def _tz(ts: Optional[datetime]) -> Optional[datetime]:
    """Normalize a datetime to timezone-aware UTC (SQLite returns naive)."""
    if ts is not None and ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts


def _notification_to_dict(n: Notification) -> Dict[str, Any]:
    return {
        "id": n.id,
        "memo_id": n.memo_id,
        "event_type": n.event_type,
        "recipient": n.recipient,
        "channel": n.channel,
        "status": n.status,
        "subject": n.subject,
        "body": n.body,
        "timestamp": n.timestamp.isoformat() if n.timestamp else None,
        "sent_at": n.sent_at.isoformat() if n.sent_at else None,
    }


def _user_to_dict(u: UserAccount) -> Dict[str, Any]:
    return {
        "id": u.id,
        "username": u.username,
        "full_name": u.full_name,
        "email": u.email,
        "role": u.role,
        "is_active": u.is_active,
        "created_at": u.created_at.isoformat() if u.created_at else None,
        "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
    }


def _escalation_to_dict(e: Escalation, client_name: Optional[str] = None) -> Dict[str, Any]:
    # Compute SLA breach percentage from timestamp and sla_deadline
    sla_breach_pct = 0.0
    if e.timestamp and e.sla_deadline:
        ts = e.timestamp
        dl = e.sla_deadline
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        if dl.tzinfo is None:
            dl = dl.replace(tzinfo=timezone.utc)
        total_sla_seconds = (dl - ts).total_seconds()
        if total_sla_seconds > 0:
            elapsed = (datetime.now(timezone.utc) - ts).total_seconds()
            sla_breach_pct = round((elapsed / total_sla_seconds) * 100, 1)

    # Map level string to numeric escalation level
    _level_map = {"remind": 1, "notice": 2, "escalate_to_manager": 3, "escalate_to_admin": 4}
    escalation_level = _level_map.get(e.level, 1) if isinstance(e.level, str) else 1

    return {
        "id": e.id,
        "memo_id": e.memo_id,
        "client_name": client_name,
        "escalation_level": escalation_level,
        "escalation_reason": e.stage,
        "sla_breach_pct": sla_breach_pct,
        "stage": e.stage,
        "level": e.level,
        "recipient": e.recipient,
        "status": e.status,
        "sla_deadline": e.sla_deadline.isoformat() if e.sla_deadline else None,
        "created_at": e.timestamp.isoformat() if e.timestamp else None,
        "timestamp": e.timestamp.isoformat() if e.timestamp else None,
        "resolved_at": e.resolved_at.isoformat() if e.resolved_at else None,
    }


# =============================================================================
# Auth & Users
# =============================================================================

@router.post("/auth/token", response_model=TokenResponse)
def get_auth_token(request: TokenRequest, db: Session = Depends(get_db)):
    """Authenticate a user and return a signed JWT.

    Credentials are validated against the user_accounts table (PBKDF2
    hashed passwords). The default user directory is bootstrapped on
    first login if the table is empty.
    """
    from app.core.security import create_access_token

    user = users.authenticate_user(db, request.username, request.password)
    if not user:
        audit.record_event(
            db=db,
            action="login_failed",
            user_id=request.username,
            payload={"username": request.username},
        )
        db.commit()
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token = create_access_token(
        user_id=user.username,
        username=user.username,
        full_name=user.full_name,
        role=user.role,
        acl_groups=["corporate_banking", "credit_analysis"],
    )

    audit.record_event(
        db=db,
        action="login",
        user_id=user.username,
        payload={"role": user.role},
    )
    db.commit()

    return TokenResponse(
        access_token=token,
        user_id=user.username,
        username=user.username,
        role=user.role,
        full_name=user.full_name,
    )


@router.get("/users")
def list_users(
    db: Session = Depends(get_db),
    user: UserIdentity = Depends(require_roles("Admin")),
):
    """List all user accounts (admin only)."""
    accounts = db.query(UserAccount).order_by(UserAccount.created_at).all()
    return {"total": len(accounts), "users": [_user_to_dict(u) for u in accounts]}


@router.post("/users", status_code=status.HTTP_201_CREATED)
def create_user(
    request: CreateUserRequest,
    db: Session = Depends(get_db),
    user: UserIdentity = Depends(require_roles("Admin")),
):
    """Create a new user account (admin only)."""
    try:
        account = users.create_user(
            db=db,
            username=request.username,
            full_name=request.full_name,
            email=request.email or None,
            role=request.role,
            password=request.password,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    audit.record_event(
        db=db,
        action="create_user",
        user_id=user.user_id,
        payload={"new_user": account.username, "role": account.role},
    )
    db.commit()

    return _user_to_dict(account)


# =============================================================================
# Clients (CRM directory)
# =============================================================================

@router.get("/clients")
def list_clients(
    query: str = Query("", description="Search by name, client ID, or sector"),
    db: Session = Depends(get_db),
    user: UserIdentity = Depends(get_current_user),
):
    """List clients from the CRM connector (mock or live per INTEGRATION_MODE)."""
    from app.integrations.factory import get_crm_connector

    try:
        crm = get_crm_connector()
        profiles = crm.search_clients(query, limit=100)
    except Exception as e:
        logger.error("CRM connector failed: %s", e)
        raise HTTPException(status_code=502, detail=f"CRM connector unavailable: {e}")

    return {
        "total": len(profiles),
        "clients": [
            {
                "client_id": p.client_id,
                "legal_name": p.legal_name,
                "trade_name": p.trade_name,
                "client_type": p.client_type,
                "sector": p.sector,
                "sub_sector": p.sub_sector,
                "risk_rating": p.risk_rating,
                "rm_name": p.rm_name,
            }
            for p in profiles
        ],
    }


# =============================================================================
# Memo Generation & Management
# =============================================================================

@router.post("/generate-memo", response_model=GenerateMemoResponse)
def generate_memo(
    request: GenerateMemoRequest,
    db: Session = Depends(get_db),
    user: UserIdentity = Depends(require_roles("RM", "Admin")),
):
    """Generate a new credit memo for a client.

    Only RM and Admin roles may initiate memo generation.
    Risk, CreditCommittee, and ShariahBoard roles are restricted to
    review/approval only.

    Runs the full pipeline: Data → Validation → Ratios → ECL → Risk →
    Narrative → Compliance → Auto-approval evaluation.
    """
    memo = run_pipeline_up_to_review(
        db=db,
        client_id=request.client_id,
        client_name=request.client_name or request.client_id,
        facility_type=request.facility_type,
        deal_value=request.deal_value,
        bank_type=request.bank_type,
        rm_acl_groups=user.acl_groups,
        created_by=user.user_id,
    )

    # Send notification
    try:
        send_notification(
            db=db,
            event_type="memo_generated",
            recipient=user.user_id,
            memo_id=memo.id,
            data={
                "client_id": request.client_id,
                "facility_type": request.facility_type,
                "memo_id": memo.id,
            },
        )
        db.commit()
    except Exception as e:
        logger.warning("Failed to send notification: %s", e)

    # Build response
    sections = []
    for s in memo.sections:
        sections.append({
            "section_key": s.section_key,
            "title": s.title,
            "review_status": s.review_status,
            "requires_review": s.requires_review,
            "review_reason": s.review_reason,
            "auto_approved_rule": s.auto_approved_rule,
        })

    return GenerateMemoResponse(
        memo_id=memo.id,
        status=memo.status,
        sections=sections,
        workflow_stage=memo.workflow_stage,
    )


@router.get("/memos")
def list_memos(
    status: Optional[str] = Query(None, description="Filter by memo status"),
    stage: Optional[str] = Query(None, description="Filter by workflow stage"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: UserIdentity = Depends(get_current_user),
):
    """List memos with pipeline summaries and live SLA status.

    Each memo includes section counts, shariah flag counts, and the
    SLA status for the current workflow stage computed from workflow
    events and the configured per-stage SLA hours.
    """
    query = db.query(Memo).order_by(Memo.created_at.desc())
    if status:
        query = query.filter(Memo.status == status)
    if stage:
        query = query.filter(Memo.workflow_stage == stage)
    memos = query.limit(limit).all()

    workflow_config = get_approval_workflow()
    sla_hours = workflow_config.get("sla_hours", {})
    now = datetime.now(timezone.utc)

    # Latest stage-entry timestamp per (memo, stage) in a single query.
    stage_entry: Dict[tuple, datetime] = {}
    memo_ids = [m.id for m in memos]
    if memo_ids:
        events = (
            db.query(WorkflowEvent)
            .filter(WorkflowEvent.memo_id.in_(memo_ids))
            .order_by(WorkflowEvent.timestamp.desc())
            .all()
        )
        for e in events:
            key = (e.memo_id, e.to_stage)
            ts = _tz(e.timestamp)
            if key not in stage_entry or stage_entry[key] < ts:
                stage_entry[key] = ts

    result = []
    for m in memos:
        pending_sections = sum(
            1 for s in m.sections if s.requires_review and s.review_status == "pending"
        )
        shariah_flag_count = sum(
            len((s.flags_json or {}).get("shariah", [])) for s in m.sections
        )

        entered_at = stage_entry.get((m.id, m.workflow_stage)) or _tz(m.created_at)
        stage_sla = sla_hours.get(m.workflow_stage)

        if m.status in ("finalized", "rejected"):
            sla_status = None
            remaining_hours = None
        elif stage_sla and entered_at:
            elapsed = (now - entered_at).total_seconds() / 3600
            remaining_hours = stage_sla - elapsed
            if remaining_hours < 0:
                sla_status = "Overdue"
            elif elapsed / stage_sla >= 0.8:
                sla_status = "At Risk"
            else:
                sla_status = "On Track"
        else:
            sla_status = "On Track"
            remaining_hours = None

        # Count citation problems across all sections for this memo
        citation_flag_count = sum(
            len((s.flags_json or {}).get("citation", []))
            + len((s.flags_json or {}).get("citations", []))
            for s in m.sections
        )

        result.append({
            "id": m.id,
            "client_id": m.client_id,
            "client_name": m.client_name or m.client_id,
            "facility_type": m.facility_type,
            "deal_value": m.deal_value,
            "status": m.status,
            "workflow_stage": m.workflow_stage,
            "created_by": m.created_by,
            "created_at": m.created_at.isoformat() if m.created_at else None,
            "finalized_at": m.finalized_at.isoformat() if m.finalized_at else None,
            "section_count": len(m.sections),
            "pending_review_count": pending_sections,
            "shariah_flag_count": shariah_flag_count,
            "citation_flag_count": citation_flag_count,
            "sla_status": sla_status,
            "sla_hours_remaining": round(remaining_hours, 1) if remaining_hours is not None else None,
            "stage_entered_at": entered_at.isoformat() if entered_at else None,
            "stage_sla_hours": stage_sla,
        })

    return {"total": len(result), "memos": result}


@router.get("/memo/{memo_id}", response_model=MemoDetailResponse)
def get_memo(
    memo_id: str,
    db: Session = Depends(get_db),
    user: UserIdentity = Depends(get_current_user),
):
    """Get full memo details including all sections."""
    memo = db.query(Memo).filter(Memo.id == memo_id).first()
    if not memo:
        raise HTTPException(status_code=404, detail="Memo not found")

    sections = []
    for s in memo.sections:
        sections.append({
            "section_key": s.section_key,
            "title": s.title,
            "content": s.content,
            "review_status": s.review_status,
            "requires_review": s.requires_review,
            "review_reason": s.review_reason,
            "approved_by": s.approved_by,
            "auto_approved_rule": s.auto_approved_rule,
            "flags": s.flags_json,
            "citations": s.citations_json,
        })

    return MemoDetailResponse(
        id=memo.id,
        client_id=memo.client_id,
        client_name=memo.client_name,
        facility_type=memo.facility_type,
        deal_value=memo.deal_value,
        status=memo.status,
        workflow_stage=memo.workflow_stage,
        created_by=memo.created_by,
        created_at=memo.created_at.isoformat() if memo.created_at else None,
        finalized_at=memo.finalized_at.isoformat() if memo.finalized_at else None,
        output_file_path=memo.output_file_path,
        sections=sections,
        metadata=memo.metadata_json,
    )


@router.post("/memo/{memo_id}/approve")
def approve_section(
    memo_id: str,
    request: SectionApprovalRequest,
    db: Session = Depends(get_db),
    user: UserIdentity = Depends(get_current_user),
):
    """Approve a specific section of a memo.

    Requires the user's role to be authorized for this section type.
    """
    # Check RBAC
    if not can_approve_section(user.role, request.section_key):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Role '{user.role}' cannot approve section '{request.section_key}'",
        )

    try:
        workflow = advance_stage(
            db=db,
            memo_id=memo_id,
            user_id=user.user_id,
            user_role=user.role,
            section_key=request.section_key,
            approved=True,
            comment=request.comment,
        )
        db.commit()

        # Notify the memo creator that a section was approved
        try:
            memo = db.query(Memo).filter(Memo.id == memo_id).first()
            recipient = memo.created_by if memo else user.user_id
            send_notification(
                db=db,
                event_type="approval_stage_changed",
                recipient=recipient,
                memo_id=memo_id,
                data={
                    "section_key": request.section_key,
                    "action": "approved",
                    "memo_id": memo_id,
                    "approved_by": user.user_id,
                },
            )
            db.commit()
        except Exception as notify_err:
            logger.warning("Notification after approval failed: %s", notify_err)

        return {"status": "approved", "section_key": request.section_key, "workflow": workflow.to_dict()}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.post("/memo/{memo_id}/reject")
def reject_section(
    memo_id: str,
    request: SectionApprovalRequest,
    db: Session = Depends(get_db),
    user: UserIdentity = Depends(get_current_user),
):
    """Reject a specific section of a memo with a comment."""
    if not can_approve_section(user.role, request.section_key):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Role '{user.role}' cannot reject section '{request.section_key}'",
        )

    try:
        workflow = advance_stage(
            db=db,
            memo_id=memo_id,
            user_id=user.user_id,
            user_role=user.role,
            section_key=request.section_key,
            approved=False,
            comment=request.comment,
        )
        db.commit()
        return {"status": "rejected", "section_key": request.section_key, "workflow": workflow.to_dict()}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.post("/memo/{memo_id}/finalize")
def finalize(
    memo_id: str,
    db: Session = Depends(get_db),
    user: UserIdentity = Depends(require_roles("CreditCommittee", "Admin")),
):
    """Finalize a memo — all sections must be approved.

    Generates the final PDF/HTML output. Only CreditCommittee and Admin
    roles may finalize a memo.
    """
    try:
        memo = finalize_memo(db=db, memo_id=memo_id, user_id=user.user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Compile the final document
    sections_for_compiler = []
    for s in memo.sections:
        sections_for_compiler.append({
            "title": s.title or s.section_key,
            "content": s.content or "",
            "flags": s.flags_json.get("shariah", []) if s.flags_json else [],
            "approved_by": s.approved_by or s.auto_approved_rule,
        })

    # Get ratios from metadata
    ratios = None
    if memo.metadata_json:
        ratios = memo.metadata_json.get("ratios")

    try:
        compiler_result = run_compiler_agent(
            memo_id=memo.id,
            client_name=memo.client_name or memo.client_id,
            facility_type=memo.facility_type,
            deal_value=memo.deal_value,
            sections=sections_for_compiler,
            ratios=ratios,
            output_dir="output",
        )
        # Prefer PDF path; fall back to HTML if PDF generation was skipped
        output_path = compiler_result.pdf_path
        if not output_path and compiler_result.html_content:
            output_path = f"output/memo_{memo.id}.html"
        if not output_path:
            # Compilation produced no artifact — do NOT finalize
            raise HTTPException(
                status_code=500,
                detail="Memo finalization failed: compiler produced no output artifact (PDF/HTML). "
                       "Memo status remains unchanged.",
            )
        memo.output_file_path = output_path
        if compiler_result.errors:
            logger.info("Compiler warnings for memo %s: %s", memo.id, compiler_result.errors)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Compiler failed: %s", e)
        raise HTTPException(
            status_code=500,
            detail=f"Memo finalization failed: compiler error — {str(e)[:300]}. "
                   "Memo status remains unchanged.",
        )

    # Notify
    try:
        send_notification(
            db=db,
            event_type="finalization_ready",
            recipient=memo.created_by,
            memo_id=memo.id,
            data={"memo_id": memo.id},
        )
    except Exception as notify_err:
        logger.warning("Notification after finalization failed: %s", notify_err)

    db.commit()

    return {
        "status": "finalized",
        "memo_id": memo.id,
        "output_path": memo.output_file_path,
        "finalized_at": memo.finalized_at.isoformat() if memo.finalized_at else None,
    }


@router.get("/memo/{memo_id}/workflow")
def get_workflow(
    memo_id: str,
    db: Session = Depends(get_db),
    user: UserIdentity = Depends(get_current_user),
):
    """Get the current approval workflow status for a memo.

    Includes the configured stage list and per-stage SLA hours so clients
    can render progress and countdowns.
    """
    try:
        workflow = get_workflow_status(db, memo_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    result = workflow.to_dict()
    workflow_config = get_approval_workflow()
    result["stages"] = workflow_config.get("stages", [])
    result["sla_hours"] = workflow_config.get("sla_hours", {})
    return result


@router.get("/memo/{memo_id}/audit-log")
def get_audit_log(
    memo_id: str,
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    user: UserIdentity = Depends(get_current_user),
):
    """Get the audit trail for a memo."""
    entries = audit.get_audit_log(db, memo_id=memo_id, limit=limit)
    return {
        "memo_id": memo_id,
        "entries": [
            {
                "id": e.id,
                "action": e.action,
                "user_id": e.user_id,
                "section_key": e.section_key,
                "rule_applied": e.rule_applied,
                "comment": e.comment,
                "timestamp": e.timestamp.isoformat() if e.timestamp else None,
                "entry_hash": e.entry_hash,
            }
            for e in entries
        ],
    }


@router.post("/memo/{memo_id}/notify")
def resend_notifications(
    memo_id: str,
    db: Session = Depends(get_db),
    user: UserIdentity = Depends(require_roles("Admin")),
):
    """Re-send notifications for a memo (admin only)."""
    memo = db.query(Memo).filter(Memo.id == memo_id).first()
    if not memo:
        raise HTTPException(status_code=404, detail="Memo not found")

    records = send_notification(
        db=db,
        event_type="memo_generated",
        recipient=memo.created_by,
        memo_id=memo.id,
        data={"client_id": memo.client_id, "memo_id": memo.id},
    )
    db.commit()

    return {
        "memo_id": memo_id,
        "notifications_sent": len(records),
        "records": [r.to_dict() for r in records],
    }


# =============================================================================
# Reports
# =============================================================================

@router.get("/reports/{report_type}")
def get_report(
    report_type: str,
    report_format: str = Query("json", description="Output format: json, csv"),
    status: Optional[str] = Query(None, description="Filter memos by status (pipeline_status)"),
    facility_type: Optional[str] = Query(None, description="Filter memos by facility type"),
    db: Session = Depends(get_db),
    user: UserIdentity = Depends(get_current_user),
):
    """Generate an on-demand operational report.

    Report types: pipeline_status, approval_delay, ecl_summary, sla_violation.
    """
    filters = {}
    if status:
        filters["status"] = status
    if facility_type:
        filters["facility_type"] = facility_type

    try:
        report = generate_report(
            db=db,
            report_type=report_type,
            filters=filters,
            report_format=report_format,
            generated_by=user.user_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return report.to_dict()


# =============================================================================
# Notifications
# =============================================================================

@router.get("/notifications")
def list_notifications(
    limit: int = Query(50, ge=1, le=200),
    unread_only: bool = Query(False, description="Only pending/unread notifications"),
    db: Session = Depends(get_db),
    user: UserIdentity = Depends(get_current_user),
):
    """List notifications for the current user, newest first."""
    query = db.query(Notification).filter(Notification.recipient == user.user_id)
    if unread_only:
        query = query.filter(Notification.status.in_(["pending", "sent"]))
    notifications = query.order_by(Notification.timestamp.desc()).limit(limit).all()

    unread_count = (
        db.query(Notification)
        .filter(
            Notification.recipient == user.user_id,
            Notification.status.in_(["pending", "sent"]),
        )
        .count()
    )

    return {
        "unread_count": unread_count,
        "total": len(notifications),
        "notifications": [_notification_to_dict(n) for n in notifications],
    }


@router.post("/notifications/{notification_id}/read")
def mark_notification_read(
    notification_id: str,
    db: Session = Depends(get_db),
    user: UserIdentity = Depends(get_current_user),
):
    """Mark a notification as read. Users may only mark their own
    notifications; Admins may mark any."""
    notification = db.query(Notification).filter(Notification.id == notification_id).first()
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    if notification.recipient != user.user_id and user.role != "Admin":
        raise HTTPException(status_code=403, detail="Cannot mark another user's notification")

    notification.status = "read"
    db.commit()
    return {"id": notification.id, "status": "read"}


# =============================================================================
# Escalations
# =============================================================================

@router.get("/escalations")
def list_escalations(
    db: Session = Depends(get_db),
    user: UserIdentity = Depends(require_roles("RM", "Admin", "Risk", "CreditCommittee", "ShariahBoard")),
):
    """List active escalations with client context."""
    escalations = get_active_escalations(db)

    memo_ids = list({e.memo_id for e in escalations})
    memo_names: Dict[str, Optional[str]] = {}
    if memo_ids:
        rows = db.query(Memo).filter(Memo.id.in_(memo_ids)).all()
        memo_names = {m.id: (m.client_name or m.client_id) for m in rows}

    return {
        "total": len(escalations),
        "escalations": [
            _escalation_to_dict(e, memo_names.get(e.memo_id)) for e in escalations
        ],
    }


@router.post("/escalations/check")
def run_escalation_check(
    db: Session = Depends(get_db),
    user: UserIdentity = Depends(require_roles("Admin")),
):
    """Run the SLA escalation check across all active memos (admin only).

    Evaluates each active memo's stage elapsed time against the configured
    escalation ladder (50% remind → 80% notice → 100% manager → 125% admin)
    and sends an sla_breach notification for every newly triggered level.
    """
    try:
        triggered = check_and_escalate(db)
    except Exception as e:
        logger.error("Escalation check failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Escalation check failed: {e}")

    notifications_sent = 0
    for t in triggered:
        records = send_notification(
            db=db,
            event_type="sla_breach",
            recipient=t.recipient,
            memo_id=t.memo_id,
            data={
                "memo_id": t.memo_id,
                "stage": t.stage,
                "level": t.level,
                "elapsed_hours": t.elapsed_hours,
                "sla_hours": t.sla_hours,
                "percentage": t.percentage,
            },
        )
        notifications_sent += len(records)

    db.commit()

    return {
        "escalations_triggered": len(triggered),
        "notifications_sent": notifications_sent,
        "triggered": [t.to_dict() for t in triggered],
    }


# =============================================================================
# Global Audit Log
# =============================================================================

@router.get("/audit-log")
def get_global_audit_log(
    memo_id: Optional[str] = Query(None, description="Filter by memo ID"),
    action: Optional[str] = Query(None, description="Filter by action type"),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    user: UserIdentity = Depends(get_current_user),
):
    """Global hash-chained audit log across all memos and system actions."""
    entries = audit.get_audit_log(db, memo_id=memo_id, action=action, limit=limit)
    chain_verified = audit.verify_chain(db, memo_id=memo_id)

    return {
        "chain_verified": chain_verified,
        "total": len(entries),
        "entries": [
            {
                "id": e.id,
                "action": e.action,
                "user_id": e.user_id,
                "memo_id": e.memo_id,
                "section_key": e.section_key,
                "rule_applied": e.rule_applied,
                "comment": e.comment,
                "timestamp": e.timestamp.isoformat() if e.timestamp else None,
                "entry_hash": e.entry_hash,
            }
            for e in entries
        ],
    }


# =============================================================================
# Risk / ECL
# =============================================================================

@router.post("/risk/ecl")
def compute_ecl_endpoint(
    request: ECLRequest,
    user: UserIdentity = Depends(require_roles("RM", "Admin", "Risk", "CreditCommittee", "ShariahBoard")),
):
    """Compute ECL for a synthetic portfolio."""
    from app.risk.ecl_engine import compute_ecl
    from app.risk.synthetic_portfolio import generate_synthetic_portfolio

    portfolio = generate_synthetic_portfolio(
        total_gross_financing=request.total_gross_financing,
        npl_ratio=request.npl_ratio,
        num_facilities=request.portfolio_size,
    )
    result = compute_ecl(portfolio)
    return result.to_dict()


# =============================================================================
# Evaluation & Benchmark Framework
# =============================================================================

class EvaluationRequest(BaseModel):
    corpus_path: Optional[str] = Field(None, description="Override corpus directory path")
    max_cases: Optional[int] = Field(None, ge=1, description="Limit number of cases to evaluate")


@router.post("/evaluation/run")
def run_evaluation_endpoint(
    request: EvaluationRequest = EvaluationRequest(),
    db: Session = Depends(get_db),
    user: UserIdentity = Depends(require_roles("Admin")),
):
    """Run the shadow-mode evaluation benchmark.

    Executes the full MemoForge pipeline against a corpus of test cases,
    measures 8 quantitative metrics, and produces an auditable report.
    Admin only.
    """
    from app.evaluation.runner import run_evaluation

    report = run_evaluation(
        db=db,
        corpus_path=request.corpus_path,
        max_cases=request.max_cases,
    )
    return report
