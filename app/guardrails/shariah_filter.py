"""Shariah compliance filter — rules engine for Islamic finance terminology.

Validates that generated memo content uses correct Islamic finance terminology
for the given facility type (Murabaha, Ijara, Musharakah, Sukuk, Tawarruq).

Two modes of checking:
1. Positive checks: Required terms that SHOULD appear for the facility type.
2. Negative checks: Prohibited terms that MUST NOT appear (conventional finance terms).

Special handling for APR exemption: "annual percentage rate" is allowed when it
refers to a profit rate on an Islamic contract, not conventional interest.

Design decision: The filter is conservative — when in doubt, flag for human
Shariah Board review rather than allowing the LLM to self-adjudicate.
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.core.business_config import get_shariah_terminology

logger = logging.getLogger(__name__)


@dataclass
class ShariahFlag:
    """A Shariah compliance flag raised during content review."""

    term: str
    flag_type: str  # "prohibited", "missing_required", "ambiguous"
    severity: str  # "error", "warning", "info"
    suggestion: str
    context: str = ""  # The sentence where the term was found

    def to_dict(self) -> Dict[str, Any]:
        return {
            "term": self.term,
            "flag_type": self.flag_type,
            "severity": self.severity,
            "suggestion": self.suggestion,
            "detail": self.suggestion,
            "context": self.context,
        }


# APR exemption: "annual percentage rate" in context of Islamic profit rate is OK
_APR_EXEMPTION_PATTERN = re.compile(
    r"annual\s+percentage\s+rate.*profit",
    re.IGNORECASE,
)
_PROFIT_RATE_DISCLOSURE_PATTERN = re.compile(
    r"(profit\s+rate|annual\s+profit\s+rate).*\d+(\.\d+)?%",
    re.IGNORECASE,
)


def check_shariah_compliance(
    content: str,
    facility_type: str,
) -> List[ShariahFlag]:
    """Check content for Shariah compliance against the configured terminology rules.

    Args:
        content: The text content to check.
        facility_type: Islamic facility type (murabaha, ijara, musharakah, sukuk, tawarruq).

    Returns:
        List of ShariahFlag objects. Empty list means fully compliant.
    """
    try:
        terminology = get_shariah_terminology(facility_type)
    except ValueError as e:
        logger.warning("Unknown facility type for Shariah check: %s", e)
        # Return an error-severity flag to force human Shariah Board review
        return [
            ShariahFlag(
                term=f"unknown_facility_type:{facility_type}",
                flag_type="missing_required",
                severity="error",
                suggestion=(
                    f"Facility type '{facility_type}' is not recognized. "
                    f"Manual Shariah Board review is required before this content "
                    f"can be approved."
                ),
                context="",
            )
        ]

    flags: List[ShariahFlag] = []
    content_lower = content.lower()

    # --- Negative checks: prohibited terms ---
    prohibited_terms = terminology.get("prohibited_terms", [])
    for term in prohibited_terms:
        pattern = re.compile(r'\b' + re.escape(term.lower()) + r'\b')
        matches = list(pattern.finditer(content_lower))

        if matches:
            for match in matches:
                # Check APR exemption
                start = max(0, match.start() - 50)
                end = min(len(content), match.end() + 50)
                context = content[start:end]

                if term.lower() in ("interest rate", "annual percentage rate"):
                    if _APR_EXEMPTION_PATTERN.search(context) or \
                       _PROFIT_RATE_DISCLOSURE_PATTERN.search(context):
                        # APR is being used in context of Islamic profit rate — exempt
                        continue

                flags.append(ShariahFlag(
                    term=term,
                    flag_type="prohibited",
                    severity="error",
                    suggestion=(
                        f"Remove or replace '{term}' — this is a conventional finance term "
                        f"incompatible with {facility_type} structure. "
                        f"Use appropriate Islamic terminology instead."
                    ),
                    context=context.strip(),
                ))

    # --- Positive checks: required terms ---
    required_terms = terminology.get("required_terms", [])
    missing_required = []
    for term in required_terms:
        if term.lower() not in content_lower:
            missing_required.append(term)

    # Only flag missing terms as warning (not error) — the content might be
    # a subsection that doesn't require all terms
    if missing_required:
        flags.append(ShariahFlag(
            term=", ".join(missing_required),
            flag_type="missing_required",
            severity="warning",
            suggestion=(
                f"Consider including the following {facility_type}-specific terms "
                f"where appropriate: {', '.join(missing_required)}"
            ),
            context="",
        ))

    # --- Additional Shariah-specific checks ---
    # Check for "riba" mentions without context
    if "riba" in content_lower and "prohibited" not in content_lower and \
       "avoid" not in content_lower and "free from" not in content_lower:
        # Riba mentioned but not in context of prohibition
        idx = content_lower.find("riba")
        context = content[max(0, idx - 30):min(len(content), idx + 30)]
        flags.append(ShariahFlag(
            term="riba",
            flag_type="ambiguous",
            severity="warning",
            suggestion="Ensure 'riba' is mentioned in context of prohibition/compliance, not as a feature.",
            context=context.strip(),
        ))

    # Check for "gharar" (excessive uncertainty) mentions
    if "gharar" in content_lower:
        idx = content_lower.find("gharar")
        context = content[max(0, idx - 30):min(len(content), idx + 30)]
        flags.append(ShariahFlag(
            term="gharar",
            flag_type="ambiguous",
            severity="info",
            suggestion="Verify that gharar reference is in compliance context.",
            context=context.strip(),
        ))

    return flags


def is_compliant(flags: List[ShariahFlag]) -> bool:
    """Check if content is Shariah compliant based on flags.

    Content is considered compliant if there are no 'error' severity flags.
    Warnings and info flags require human review but don't block processing.
    """
    return not any(f.severity == "error" for f in flags)


def get_compliance_summary(flags: List[ShariahFlag]) -> Dict[str, Any]:
    """Generate a summary of Shariah compliance flags."""
    errors = [f for f in flags if f.severity == "error"]
    warnings = [f for f in flags if f.severity == "warning"]
    infos = [f for f in flags if f.severity == "info"]

    return {
        "is_compliant": is_compliant(flags),
        "total_flags": len(flags),
        "errors": len(errors),
        "warnings": len(warnings),
        "infos": len(infos),
        "requires_shariah_review": len(errors) > 0 or len(warnings) > 2,
        "flags": [f.to_dict() for f in flags],
    }
