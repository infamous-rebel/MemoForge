"""Deterministic approval rules engine.

This module is the single source of truth for deciding whether a memo section
can be auto-approved or requires human review. The decision is based on:
- Facility type (e.g., sukuk always requires review)
- Deal value threshold
- Presence of flags (Shariah, citation, policy, ratio breaches)
- Section-specific rules from config

Design decision: Approval decisions are pure functions of inputs + config,
making them deterministic, testable, and auditable. Every decision returns
the rule that was applied, which is recorded in the audit log.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from app.core.business_config import get_hitl_rules


@dataclass
class SectionFlags:
    """Aggregated flags for a memo section."""

    shariah_flags: List[Dict[str, Any]] = field(default_factory=list)
    citation_problems: List[Dict[str, Any]] = field(default_factory=list)
    policy_exceptions: List[Dict[str, Any]] = field(default_factory=list)
    ratio_breaches: List[Dict[str, Any]] = field(default_factory=list)
    risk_flags: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def has_any_flags(self) -> bool:
        return bool(
            self.shariah_flags
            or self.citation_problems
            or self.policy_exceptions
            or self.ratio_breaches
            or self.risk_flags
        )

    @property
    def has_shariah_flags(self) -> bool:
        return len(self.shariah_flags) > 0

    @property
    def has_citation_problems(self) -> bool:
        return len(self.citation_problems) > 0

    @property
    def has_policy_exceptions(self) -> bool:
        return len(self.policy_exceptions) > 0

    @property
    def has_ratio_breaches(self) -> bool:
        return len(self.ratio_breaches) > 0

    @property
    def has_risk_flags(self) -> bool:
        return len(self.risk_flags) > 0


def should_auto_approve(
    section_key: str,
    flags: SectionFlags,
    facility_type: str,
    deal_value: float,
) -> Tuple[bool, str]:
    """Determine if a section can be auto-approved.

    Args:
        section_key: The memo section identifier.
        flags: Aggregated flags for this section.
        facility_type: Islamic facility type (murabaha, ijara, etc.).
        deal_value: Deal value in KD.

    Returns:
        Tuple of (can_auto_approve: bool, rule_applied: str).
        The rule_applied string is recorded in the audit log.
    """
    hitl = get_hitl_rules()

    # 0. Sections that must NEVER be auto-approved (e.g., policy_exceptions)
    never_auto = hitl.get("sections_never_auto_approve", [])
    if section_key in never_auto:
        return False, f"never_auto_approve_section:{section_key}"

    # 1. Always review specific facility types (e.g., sukuk)
    if facility_type in hitl.get("always_review_facility_types", []):
        return False, f"required_review_facility_type:{facility_type}"

    # 2. Always review if deal value exceeds threshold
    threshold = hitl.get("always_review_if_deal_value_exceeds")
    if threshold and deal_value > threshold:
        return False, f"required_review_above_threshold:{deal_value}>{threshold}"

    # 3. Review if any flags exist (Shariah, citation, policy, ratio, risk)
    if (flags.shariah_flags or flags.citation_problems or
            flags.policy_exceptions or flags.ratio_breaches or flags.risk_flags):
        return False, "required_review_flags_present"

    # 4. Auto-approve if no flags and configured
    if hitl.get("auto_approve_if_no_flags", True):
        return True, "auto_approved_no_flags"

    return False, "required_review_auto_approve_disabled"


def get_required_review_role(section_key: str, flags: SectionFlags) -> List[str]:
    """Determine which roles must review a section based on its flags.

    Args:
        section_key: The memo section identifier.
        flags: Aggregated flags for this section.

    Returns:
        List of role names that must review the section.
    """
    from app.core.business_config import get_section_approval_roles

    roles = set()

    # Shariah flags require ShariahBoard review
    if flags.has_shariah_flags:
        roles.add("ShariahBoard")

    # Ratio breaches or risk flags require Risk/CreditCommittee
    if flags.has_ratio_breaches or flags.has_risk_flags:
        roles.update(["Risk", "CreditCommittee"])

    # Policy exceptions require CreditCommittee
    if flags.has_policy_exceptions:
        roles.add("CreditCommittee")

    # If no specific flags, use the default matrix
    if not roles:
        roles = set(get_section_approval_roles(section_key))

    return sorted(roles)


def evaluate_risk_level(flags: SectionFlags) -> str:
    """Evaluate the overall risk level of a section based on its flags.

    Returns:
        One of 'low', 'medium', 'high', 'critical'.
    """
    if flags.has_shariah_flags or flags.has_policy_exceptions:
        return "critical"
    if flags.has_ratio_breaches and len(flags.ratio_breaches) > 2:
        return "high"
    if flags.has_any_flags:
        return "medium"
    return "low"
