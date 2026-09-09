"""Narrative Agent — drafts memo sections with citations.

Generates the following memo sections using LLM with citation requirements:
- Borrower Overview
- Financial Analysis
- Risk & Mitigants
- Policy Exceptions
- Recommendation

Each section includes citations referencing retrieved document chunks.
The agent runs Shariah screening and citation validation on each section.

Design decision: The LLM generates narrative text with embedded citations,
but all facts are validated against the retrieved context by the citation
validator. The Shariah filter ensures Islamic finance terminology compliance.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from app.agents.llm_client import get_llm_client
from app.agents.ratio_agent import RatioAgentResult
from app.core.approval_rules import SectionFlags
from app.guardrails.shariah_filter import check_shariah_compliance, get_compliance_summary
from app.guardrails.validators import validate_citations

logger = logging.getLogger(__name__)

SECTION_KEYS = [
    "borrower_overview",
    "financial_analysis",
    "risk_and_mitigants",
    "policy_exceptions",
    "recommendation",
]


@dataclass
class MemoSectionDraft:
    """Draft of a single memo section."""
    section_key: str
    title: str
    content: str
    citations: List[Dict[str, Any]] = field(default_factory=list)
    shariah_flags: List[Dict[str, Any]] = field(default_factory=list)
    citation_problems: List[Dict[str, Any]] = field(default_factory=list)
    requires_review: bool = False
    review_reason: str = ""
    flags: Dict[str, Any] = field(default_factory=dict)


@dataclass
class NarrativeAgentResult:
    """Result from the narrative agent."""
    sections: List[MemoSectionDraft] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


def run_narrative_agent(
    client_id: str,
    facility_type: str,
    deal_value: float,
    retrieved_context: str,
    ratio_result: RatioAgentResult,
    valid_chunk_ids: Set[str],
) -> NarrativeAgentResult:
    """Generate all memo sections with citations and compliance checks.

    Args:
        client_id: Client identifier.
        facility_type: Islamic facility type.
        deal_value: Deal value in KD.
        retrieved_context: Concatenated retrieved document text.
        ratio_result: Financial ratios from the ratio agent.
        valid_chunk_ids: Set of valid chunk IDs for citation validation.

    Returns:
        NarrativeAgentResult with section drafts and compliance flags.
    """
    logger.info("NarrativeAgent: generating sections for client=%s facility=%s", client_id, facility_type)
    result = NarrativeAgentResult()
    llm = get_llm_client()

    for section_key in SECTION_KEYS:
        try:
            draft = _generate_section(
                llm=llm,
                section_key=section_key,
                client_id=client_id,
                facility_type=facility_type,
                deal_value=deal_value,
                retrieved_context=retrieved_context,
                ratio_result=ratio_result,
                valid_chunk_ids=valid_chunk_ids,
            )
            result.sections.append(draft)
        except Exception as e:
            logger.error("NarrativeAgent: failed to generate %s: %s", section_key, e)
            result.errors.append(f"Failed to generate {section_key}: {str(e)[:200]}")
            result.sections.append(MemoSectionDraft(
                section_key=section_key,
                title=section_key.replace("_", " ").title(),
                content=f"[Section generation failed — manual review required]",
                requires_review=True,
                review_reason=f"Generation error: {str(e)[:100]}",
            ))

    return result


def _generate_section(
    llm,
    section_key: str,
    client_id: str,
    facility_type: str,
    deal_value: float,
    retrieved_context: str,
    ratio_result: RatioAgentResult,
    valid_chunk_ids: Set[str],
) -> MemoSectionDraft:
    """Generate a single memo section."""

    title_map = {
        "borrower_overview": "Borrower Overview",
        "financial_analysis": "Financial Analysis",
        "risk_and_mitigants": "Risk Assessment & Mitigants",
        "policy_exceptions": "Policy Exceptions",
        "recommendation": "Recommendation",
    }

    # Build section-specific prompt
    prompt = _build_prompt(
        section_key=section_key,
        client_id=client_id,
        facility_type=facility_type,
        deal_value=deal_value,
        retrieved_context=retrieved_context,
        ratio_result=ratio_result,
    )

    response = llm.complete(prompt, system=_system_prompt(facility_type))
    content = response.content

    # Run Shariah compliance check
    shariah_flags = check_shariah_compliance(content, facility_type)
    shariah_dicts = [f.to_dict() for f in shariah_flags]

    # Run citation validation
    citation_valid, citation_problems = validate_citations(content, valid_chunk_ids)

    # Determine if review is needed
    requires_review = False
    review_reasons = []

    if any(f["severity"] == "error" for f in shariah_dicts):
        requires_review = True
        review_reasons.append("Shariah compliance flags detected")

    if not citation_valid:
        requires_review = True
        review_reasons.append("Citation validation failed")

    draft = MemoSectionDraft(
        section_key=section_key,
        title=title_map.get(section_key, section_key.replace("_", " ").title()),
        content=content,
        citations=[{"chunk_id": cid} for cid in _extract_chunk_refs(content)],
        shariah_flags=shariah_dicts,
        citation_problems=[p.to_dict() for p in citation_problems],
        requires_review=requires_review,
        review_reason="; ".join(review_reasons),
        flags={
            "shariah": shariah_dicts,
            "citation": [p.to_dict() for p in citation_problems],
        },
    )

    return draft


def _build_prompt(
    section_key: str,
    client_id: str,
    facility_type: str,
    deal_value: float,
    retrieved_context: str,
    ratio_result: RatioAgentResult,
) -> str:
    """Build a section-specific prompt for the LLM."""
    ratio_section = ""
    if ratio_result.dscr is not None:
        ratio_section = (
            f"\nFinancial Ratios:\n"
            f"- DSCR: {ratio_result.dscr:.2f}x\n"
            f"- Leverage Ratio: {ratio_result.leverage_ratio:.2f}x\n"
            f"- Current Ratio: {ratio_result.current_ratio:.2f}x\n"
        )
        if ratio_result.breaches:
            ratio_section += "- RATIO BREACHES DETECTED:\n"
            for b in ratio_result.breaches:
                ratio_section += f"  * {b.detail}\n"

    prompts = {
        "borrower_overview": (
            f"Write a professional Borrower Overview section for a credit memo.\n"
            f"Client ID: {client_id}\n"
            f"Facility Type: {facility_type}\n"
            f"Deal Value: KD {deal_value:,.0f}\n\n"
            f"Include the client's business description, ownership structure, "
            f"key management, and industry position. Cite sources using [ref:chunk_id].\n\n"
            f"Context:\n{retrieved_context}"
        ),
        "financial_analysis": (
            f"Write a professional Financial Analysis section for a credit memo.\n"
            f"Client ID: {client_id}\n{ratio_section}\n"
            f"Analyze the client's financial performance, key ratios, trends, and "
            f"debt service capacity. Use {facility_type} terminology. "
            f"Cite sources using [ref:chunk_id].\n\n"
            f"Context:\n{retrieved_context}"
        ),
        "risk_and_mitigants": (
            f"Write a professional Risk Assessment & Mitigants section.\n"
            f"Client ID: {client_id}\n"
            f"Identify key risks, assess their severity, and propose mitigants. "
            f"Consider collateral, guarantees, and covenants. "
            f"Use {facility_type} Islamic finance terminology. "
            f"Cite sources using [ref:chunk_id].\n\n"
            f"Context:\n{retrieved_context}"
        ),
        "policy_exceptions": (
            f"Write a Policy Exceptions section for the credit memo.\n"
            f"Client ID: {client_id}\n"
            f"Identify any policy exceptions, waivers, or deviations from standard "
            f"banking policy required for this facility. If none, state clearly that "
            f"no exceptions are required. Use {facility_type} terminology.\n\n"
            f"Context:\n{retrieved_context}"
        ),
        "recommendation": (
            f"Write a Recommendation section for the credit memo.\n"
            f"Client ID: {client_id}\n"
            f"Facility Type: {facility_type}\n"
            f"Deal Value: KD {deal_value:,.0f}\n"
            f"Provide a clear recommendation (approve/decline/conditional) with "
            f"supporting rationale. Reference the key findings from the analysis. "
            f"Use {facility_type} Islamic finance terminology.\n\n"
            f"Context:\n{retrieved_context}"
        ),
    }

    return prompts.get(section_key, f"Generate a {section_key} section based on:\n{retrieved_context}")


def _system_prompt(facility_type: str) -> str:
    """System prompt for all section generation."""
    return (
        f"You are a senior credit analyst at Warba Bank, a 100% Shariah-compliant Islamic bank in Kuwait. "
        f"You are writing sections of a credit memo for a {facility_type} facility. "
        f"Use correct Islamic finance terminology throughout. "
        f"Every factual claim must be cited using [ref:chunk_id] format. "
        f"Write in a professional, objective tone suitable for credit committee review. "
        f"Do not invent data — only use information from the provided context."
    )


def _extract_chunk_refs(content: str) -> List[str]:
    """Extract chunk IDs from citation markers in content."""
    import re
    pattern = re.compile(r'\[ref:([a-zA-Z0-9_-]+)\]')
    return pattern.findall(content)
