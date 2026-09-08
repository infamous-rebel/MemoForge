"""Reporting Agent — generates operational reports.

Report types:
- pipeline_status_report: Overview of all memos by stage.
- approval_delay_report: Memos with SLA delays.
- ecl_summary_report: ECL computation summary.
- sla_violation_report: Active escalations and SLA breaches.

Output formats: JSON, CSV, PDF (via WeasyPrint).

Design decision: Reports are generated on-demand via API or scheduled via
cron. The agent queries the database directly for real-time data.
"""

from __future__ import annotations

import csv
import io
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import Escalation, Memo, MemoSection, WorkflowEvent

logger = logging.getLogger(__name__)


@dataclass
class Report:
    """A generated report."""
    report_type: str
    format: str
    data: Any = None
    content: str = ""
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    summary: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_type": self.report_type,
            "format": self.format,
            "generated_at": self.generated_at.isoformat(),
            "summary": self.summary,
            "content": self.content,
        }


def generate_report(
    db: Session,
    report_type: str,
    filters: Optional[Dict[str, Any]] = None,
    report_format: str = "json",
    generated_by: Optional[str] = None,
) -> Report:
    """Generate an operational report.

    Args:
        db: Database session.
        report_type: Type of report to generate.
        filters: Optional filters for the report.
        report_format: Output format (json, csv, pdf).
        generated_by: User ID generating the report.

    Returns:
        Report with data and formatted content.
    """
    generators = {
        "pipeline_status": _generate_pipeline_status,
        "approval_delay": _generate_approval_delay,
        "ecl_summary": _generate_ecl_summary,
        "sla_violation": _generate_sla_violation,
    }

    generator = generators.get(report_type)
    if not generator:
        raise ValueError(f"Unknown report type: {report_type}. Valid: {list(generators.keys())}")

    data = generator(db, filters or {})
    report = Report(
        report_type=report_type,
        format=report_format,
        data=data,
        summary=_build_summary(data, report_type),
    )

    if report_format == "json":
        report.content = json.dumps(data, default=str, indent=2)
    elif report_format == "csv":
        report.content = _to_csv(data)
    elif report_format == "pdf":
        html_content = _to_html(data, report_type)
        try:
            import weasyprint
            pdf_bytes = weasyprint.HTML(string=html_content).write_pdf()
            report.content = pdf_bytes.hex()  # hex-encoded for JSON transport
            report.format = "pdf"
        except ImportError:
            raise ValueError(
                "PDF report generation requires WeasyPrint. "
                "Install with: pip install weasyprint. "
                "Alternatively, request report in 'json' or 'csv' format."
            )
        except OSError as e:
            raise ValueError(
                f"WeasyPrint system dependencies unavailable: {e}. "
                "Install system deps (libpango, libcairo) or use 'json'/'csv' format."
            )
    else:
        report.content = json.dumps(data, default=str, indent=2)

    return report


def _generate_pipeline_status(db: Session, filters: Dict[str, Any]) -> Dict[str, Any]:
    """Generate pipeline status report."""
    query = db.query(Memo)

    if filters.get("status"):
        query = query.filter(Memo.status == filters["status"])
    if filters.get("facility_type"):
        query = query.filter(Memo.facility_type == filters["facility_type"])

    memos = query.all()

    # Group by stage
    by_stage: Dict[str, int] = {}
    by_status: Dict[str, int] = {}
    total_deal_value = 0.0

    for memo in memos:
        by_stage[memo.workflow_stage] = by_stage.get(memo.workflow_stage, 0) + 1
        by_status[memo.status] = by_status.get(memo.status, 0) + 1
        total_deal_value += memo.deal_value or 0

    # Average approval time across finalized memos (created → finalized).
    finalized = [m for m in memos if m.finalized_at and m.created_at]
    avg_approval_hours = None
    if finalized:
        total_hours = 0.0
        for m in finalized:
            created = m.created_at
            fin = m.finalized_at
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            if fin.tzinfo is None:
                fin = fin.replace(tzinfo=timezone.utc)
            total_hours += (fin - created).total_seconds() / 3600
        avg_approval_hours = round(total_hours / len(finalized), 1)

    return {
        "total_memos": len(memos),
        "by_stage": by_stage,
        "by_status": by_status,
        "total_deal_value_kd": total_deal_value,
        "finalized_count": len(finalized),
        "avg_approval_hours": avg_approval_hours,
        "memos": [
            {
                "id": m.id,
                "client_id": m.client_id,
                "facility_type": m.facility_type,
                "deal_value": m.deal_value,
                "status": m.status,
                "stage": m.workflow_stage,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in memos[:50]
        ],
    }


def _generate_approval_delay(db: Session, filters: Dict[str, Any]) -> Dict[str, Any]:
    """Generate approval delay report."""
    from app.core.business_config import get_approval_workflow
    sla_hours = get_approval_workflow().get("sla_hours", {})

    active_memos = (
        db.query(Memo)
        .filter(Memo.status.notin_(["finalized", "rejected"]))
        .all()
    )

    delays = []
    now = datetime.now(timezone.utc)

    for memo in active_memos:
        stage = memo.workflow_stage
        sla = sla_hours.get(stage, 48)

        last_event = (
            db.query(WorkflowEvent)
            .filter(
                WorkflowEvent.memo_id == memo.id,
                WorkflowEvent.to_stage == stage,
            )
            .order_by(WorkflowEvent.timestamp.desc())
            .first()
        )

        elapsed_hours = 0
        if last_event and last_event.timestamp:
            ts = last_event.timestamp
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            elapsed_hours = (now - ts).total_seconds() / 3600

        if elapsed_hours > sla:
            delays.append({
                "memo_id": memo.id,
                "client_id": memo.client_id,
                "stage": stage,
                "sla_hours": sla,
                "elapsed_hours": round(elapsed_hours, 1),
                "overdue_hours": round(elapsed_hours - sla, 1),
            })

    return {
        "total_delays": len(delays),
        "delays": delays,
    }


def _generate_ecl_summary(db: Session, filters: Dict[str, Any]) -> Dict[str, Any]:
    """Generate ECL summary report (from stored memo metadata)."""
    memos = db.query(Memo).filter(Memo.status == "finalized").all()

    return {
        "total_finalized_memos": len(memos),
        "note": "ECL detailed breakdown available via /v1/risk/ecl endpoint",
    }


def _generate_sla_violation(db: Session, filters: Dict[str, Any]) -> Dict[str, Any]:
    """Generate SLA violation report."""
    escalations = (
        db.query(Escalation)
        .filter(Escalation.status == "active")
        .order_by(Escalation.timestamp.desc())
        .all()
    )

    return {
        "total_active_escalations": len(escalations),
        "escalations": [
            {
                "id": e.id,
                "memo_id": e.memo_id,
                "stage": e.stage,
                "level": e.level,
                "recipient": e.recipient,
                "timestamp": e.timestamp.isoformat() if e.timestamp else None,
            }
            for e in escalations
        ],
    }


def _build_summary(data: Dict[str, Any], report_type: str) -> Dict[str, Any]:
    """Build a summary from report data."""
    summary = {"report_type": report_type}

    if report_type == "pipeline_status":
        summary["total_memos"] = data.get("total_memos", 0)
        summary["avg_approval_hours"] = data.get("avg_approval_hours")
    elif report_type == "approval_delay":
        summary["total_delays"] = data.get("total_delays", 0)
    elif report_type == "sla_violation":
        summary["active_escalations"] = data.get("total_active_escalations", 0)

    return summary


def _to_csv(data: Dict[str, Any]) -> str:
    """Convert report data to CSV format."""
    output = io.StringIO()

    # Find the first list in the data
    items = None
    for key, value in data.items():
        if isinstance(value, list) and value:
            items = value
            break

    if items and isinstance(items[0], dict):
        writer = csv.DictWriter(output, fieldnames=items[0].keys())
        writer.writeheader()
        writer.writerows(items)
    else:
        writer = csv.writer(output)
        for key, value in data.items():
            writer.writerow([key, str(value)])

    return output.getvalue()


def _to_html(data: Dict[str, Any], report_type: str) -> str:
    """Convert report data to a simple HTML document for PDF rendering."""
    title = report_type.replace("_", " ").title()
    rows_html = ""
    for key, value in data.items():
        if isinstance(value, list):
            if value and isinstance(value[0], dict):
                headers = list(value[0].keys())
                header_row = "".join(f"<th>{h}</th>" for h in headers)
                body_rows = ""
                for item in value:
                    cells = "".join(f"<td>{item.get(h, '')}</td>" for h in headers)
                    body_rows += f"<tr>{cells}</tr>\n"
                rows_html += f"<h3>{key}</h3><table><thead><tr>{header_row}</tr></thead><tbody>{body_rows}</tbody></table>"
            else:
                rows_html += f"<h3>{key}</h3><ul>" + "".join(f"<li>{v}</li>" for v in value) + "</ul>"
        elif not isinstance(value, dict):
            rows_html += f"<p><strong>{key}:</strong> {value}</p>"

    return (
        f"<!DOCTYPE html><html><head><meta charset='utf-8'>"
        f"<title>{title} Report</title>"
        f"<style>body{{font-family:sans-serif;margin:2em}}"
        f"table{{border-collapse:collapse;width:100%;margin:1em 0}}"
        f"th,td{{border:1px solid #ccc;padding:6px 10px;text-align:left;font-size:12px}}"
        f"th{{background:#f0f0f0}}</style></head>"
        f"<body><h1>{title} Report</h1>{rows_html}</body></html>"
    )
