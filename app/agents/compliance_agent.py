"""Compliance Agent — centralized compliance gate for every generated section.

Validates every memo section against:
- Shariah terminology per facility type
- Citation grounding (factual claims cite real chunks)
- Policy exception detection
- RBAC-aware flagging for required review roles

Returns structured ComplianceResult with flags, severity, recommended action,
and required role for approval.

Design decision: Compliance is decoupled from generation. The bank's Shariah
Board can review this one module without touching the LLM code.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from app.core.approval_rules import SectionFlags, get_required_review_role
from app.core.business_config import get_section_approval_roles
from app.guardrails.shariah_filter import check_shariah_compliance, get_compliance_summary
from app.guardrails.validators import validate_citations

logger = logging.getLogger(__name__)


@dataclass
class ComplianceResult:
    """Result from compliance checking a memo section."""
    section_key: str
    flags: List[Dict[str, Any]] = field(default_factory=list)
    severity: str = "none"  # none, low, medium, high, critical
    recommended_action: str = ""
    required_roles: List[str] = field(default_factory=list)
    shariah_summary: Dict[str, Any] = field(default_factory=dict)
    citation_valid: bool = True
    citation_problems: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "section_key": self.section_key,
            "flags": self.flags,
            "severity": self.severity,
            "recommended_action": self.recommended_action,
            "required_roles": self.required_roles,
            "shariah_summary": self.shariah_summary,
            "citation_valid": self.citation_valid,
            "citation_problems": self.citation_problems,
        }


def check_section(
    section_key: str,
    content: str,
    facility_type: str,
    valid_chunk_ids: Set[str],
    section_flags: Optional[SectionFlags] = None,
    citations_json: Optional[List[Dict[str, Any]]] = None,
) -> ComplianceResult:
    """Run comprehensive compliance checks on a memo section.

    Args:
        section_key: The section identifier.
        content: The section content to check.
        facility_type: Islamic facility type.
        valid_chunk_ids: Valid chunk IDs from retrieved context.
        section_flags: Optional pre-computed section flags.
        citations_json: Optional structured citations.

    Returns:
        ComplianceResult with all findings.
    """
    result = ComplianceResult(section_key=section_key)

    # 1. Shariah terminology validation
    shariah_flags = check_shariah_compliance(content, facility_type)
    result.shariah_summary = get_compliance_summary(shariah_flags)
    result.flags.extend(result.shariah_summary.get("flags", []))

    # 2. Citation validation
    citation_valid, citation_problems = validate_citations(
        content, valid_chunk_ids, citations_json
    )
    result.citation_valid = citation_valid
    result.citation_problems = [p.to_dict() for p in citation_problems]
    for p in citation_problems:
        result.flags.append(p.to_dict())

    # 3. Determine severity
    result.severity = _determine_severity(result)

    # 4. Determine required roles
    flags_obj = section_flags or _build_flags_from_result(result)
    result.required_roles = get_required_review_role(section_key, flags_obj)

    # 5. Recommended action
    result.recommended_action = _get_recommended_action(result)

    logger.info(
        "ComplianceAgent: section=%s severity=%s flags=%d roles=%s",
        section_key, result.severity, len(result.flags), result.required_roles,
    )

    return result


def check_all_sections(
    sections: List[Dict[str, str]],
    facility_type: str,
    valid_chunk_ids: Set[str],
) -> List[ComplianceResult]:
    """Run compliance checks on all sections at once.

    Args:
        sections: List of dicts with 'section_key' and 'content'.
        facility_type: Islamic facility type.
        valid_chunk_ids: Valid chunk IDs.

    Returns:
        List of ComplianceResult, one per section.
    """
    results = []
    for section in sections:
        cr = check_section(
            section_key=section["section_key"],
            content=section["content"],
            facility_type=facility_type,
            valid_chunk_ids=valid_chunk_ids,
        )
        results.append(cr)
    return results


def _determine_severity(result: ComplianceResult) -> str:
    """Determine the overall severity level."""
    has_shariah_errors = any(
        f.get("flag_type") == "prohibited" and f.get("severity") == "error"
        for f in result.flags
    )
    has_citation_errors = not result.citation_valid

    if has_shariah_errors:
        return "critical"
    if has_citation_errors:
        return "high"

    shariah_warnings = result.shariah_summary.get("warnings", 0)
    if shariah_warnings > 2:
        return "medium"
    if shariah_warnings > 0 or result.citation_problems:
        return "low"

    return "none"


def _build_flags_from_result(result: ComplianceResult) -> SectionFlags:
    """Build SectionFlags from compliance result for role determination."""
    shariah = [f for f in result.flags if f.get("flag_type") in ("prohibited", "missing_required")]
    citation = result.citation_problems

    return SectionFlags(
        shariah_flags=shariah,
        citation_problems=citation,
    )


def _get_recommended_action(result: ComplianceResult) -> str:
    """Generate a recommended action based on severity."""
    actions = {
        "critical": "Immediate Shariah Board review required. Section cannot be approved until resolved.",
        "high": "Citation issues detected. Review and correct citations before approval.",
        "medium": "Multiple warnings detected. Review recommended before approval.",
        "low": "Minor issues found. Review at discretion.",
        "none": "No issues detected. Section passes compliance checks.",
    }
    return actions.get(result.severity, "Review at discretion.")
