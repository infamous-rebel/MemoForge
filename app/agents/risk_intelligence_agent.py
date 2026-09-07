"""Risk Intelligence Agent — synthesizes quantitative and qualitative risk.

Combines:
- ECL output (quantitative risk from the ECL engine)
- Ratio breaches (from the ratio agent)
- Qualitative risk factors (industry, concentration, covenants)
- Retrieved context (client history, market data)

Produces a structured risk narrative with key risks, mitigants,
covenant breach flags, and concentration risk analysis.

Design decision: Separates quantitative ECL from qualitative risk assessment.
Both are needed for a credible credit memo. This agent turns MemoForge from
a "data generator" into a "credit analyst."
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.agents.ratio_agent import RatioAgentResult, RatioBreach

logger = logging.getLogger(__name__)


@dataclass
class RiskFactor:
    """An identified risk factor."""
    risk: str
    severity: str  # low, medium, high, critical
    category: str  # credit, market, operational, concentration, shariah
    detail: str
    citation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "risk": self.risk,
            "severity": self.severity,
            "category": self.category,
            "detail": self.detail,
            "citation": self.citation,
        }


@dataclass
class Mitigant:
    """An identified risk mitigant."""
    mitigant: str
    effectiveness: str  # strong, moderate, weak
    detail: str
    citation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mitigant": self.mitigant,
            "effectiveness": self.effectiveness,
            "detail": self.detail,
            "citation": self.citation,
        }


@dataclass
class RiskAnalysis:
    """Result from the risk intelligence agent."""
    key_risks: List[RiskFactor] = field(default_factory=list)
    mitigants: List[Mitigant] = field(default_factory=list)
    covenant_breaches: List[Dict[str, Any]] = field(default_factory=list)
    concentration_flags: List[Dict[str, Any]] = field(default_factory=list)
    overall_risk_rating: str = "medium"  # low, medium, high, critical
    risk_narrative: str = ""


def analyze_risk(
    ratio_result: RatioAgentResult,
    ecl_result: Optional[Dict[str, Any]] = None,
    retrieved_context: str = "",
    facility_type: str = "murabaha",
) -> RiskAnalysis:
    """Analyze risk from multiple sources and produce structured output.

    Args:
        ratio_result: Financial ratios and breaches from the ratio agent.
        ecl_result: ECL computation results (optional, from ECL engine).
        retrieved_context: Retrieved document text for qualitative analysis.
        facility_type: Islamic facility type.

    Returns:
        RiskAnalysis with key risks, mitigants, and narrative.
    """
    logger.info("RiskIntelligenceAgent: analyzing risk for facility=%s", facility_type)
    analysis = RiskAnalysis()

    # 1. Analyze ratio breaches
    if ratio_result.breaches:
        for breach in ratio_result.breaches:
            analysis.key_risks.append(RiskFactor(
                risk=f"{breach.ratio_name} Breach",
                severity="high" if breach.direction == "below_minimum" and "DSCR" in breach.ratio_name else "medium",
                category="credit",
                detail=breach.detail,
            ))

    # 2. Analyze ratio levels even without breaches
    if ratio_result.dscr is not None and ratio_result.dscr < 1.5:
        analysis.key_risks.append(RiskFactor(
            risk="Tight DSCR Coverage",
            severity="medium",
            category="credit",
            detail=f"DSCR of {ratio_result.dscr:.2f}x provides limited headroom above the {1.2}x minimum threshold.",
        ))

    if ratio_result.leverage_ratio is not None and ratio_result.leverage_ratio > 2.0:
        analysis.key_risks.append(RiskFactor(
            risk="Elevated Leverage",
            severity="medium",
            category="credit",
            detail=f"Leverage ratio of {ratio_result.leverage_ratio:.2f}x indicates significant debt relative to equity.",
        ))

    # 3. Analyze ECL results if available
    if ecl_result:
        stage3_ecl = ecl_result.get("stage3_ecl", 0)
        total_ecl = ecl_result.get("total_ecl", 1)
        if total_ecl > 0 and (stage3_ecl / total_ecl) > 0.5:
            analysis.key_risks.append(RiskFactor(
                risk="High Stage 3 ECL Concentration",
                severity="high",
                category="credit",
                detail=f"Stage 3 ECL represents {(stage3_ecl/total_ecl)*100:.1f}% of total ECL, indicating significant credit deterioration.",
            ))

    # 4. Identify mitigants from ratios
    if ratio_result.dscr is not None and ratio_result.dscr >= 1.5:
        analysis.mitigants.append(Mitigant(
            mitigant="Strong Debt Service Coverage",
            effectiveness="strong",
            detail=f"DSCR of {ratio_result.dscr:.2f}x indicates robust capacity to service debt obligations.",
        ))

    if ratio_result.current_ratio is not None and ratio_result.current_ratio >= 1.5:
        analysis.mitigants.append(Mitigant(
            mitigant="Healthy Short-term Liquidity",
            effectiveness="strong",
            detail=f"Current ratio of {ratio_result.current_ratio:.2f}x demonstrates adequate working capital.",
        ))

    if ratio_result.leverage_ratio is not None and ratio_result.leverage_ratio <= 1.5:
        analysis.mitigants.append(Mitigant(
            mitigant="Conservative Leverage",
            effectiveness="strong",
            detail=f"Leverage ratio of {ratio_result.leverage_ratio:.2f}x indicates prudent debt management.",
        ))

    # 5. Qualitative risk from context
    _analyze_qualitative_risk(analysis, retrieved_context, facility_type)

    # 6. Determine overall risk rating
    analysis.overall_risk_rating = _compute_overall_risk(analysis)

    # 7. Generate risk narrative
    analysis.risk_narrative = _generate_risk_narrative(analysis, facility_type)

    logger.info(
        "RiskIntelligenceAgent: risks=%d mitigants=%d rating=%s",
        len(analysis.key_risks), len(analysis.mitigants),
        analysis.overall_risk_rating,
    )

    return analysis


def _analyze_qualitative_risk(
    analysis: RiskAnalysis,
    context: str,
    facility_type: str,
) -> None:
    """Analyze qualitative risk factors from retrieved context."""
    context_lower = context.lower()

    # Check for sector concentration
    sectors = ["real estate", "construction", "trading", "manufacturing", "services"]
    found_sectors = [s for s in sectors if s in context_lower]
    if len(found_sectors) <= 1:
        analysis.concentration_flags.append({
            "type": "sector_concentration",
            "detail": f"Client appears concentrated in {found_sectors[0] if found_sectors else 'unknown'} sector.",
            "severity": "medium",
        })

    # Check for covenant-related language
    covenant_terms = ["covenant", "financial covenant", "debt covenant", "maintenance covenant"]
    if any(term in context_lower for term in covenant_terms):
        # Check for potential breaches
        breach_terms = ["breach", "violation", "non-compliance", "default"]
        if any(term in context_lower for term in breach_terms):
            analysis.covenant_breaches.append({
                "type": "potential_breach",
                "detail": "Potential covenant breach detected in retrieved documents.",
                "severity": "high",
            })


def _compute_overall_risk(analysis: RiskAnalysis) -> str:
    """Compute overall risk rating from all factors."""
    high_risks = sum(1 for r in analysis.key_risks if r.severity in ("high", "critical"))
    medium_risks = sum(1 for r in analysis.key_risks if r.severity == "medium")

    if high_risks >= 2:
        return "critical"
    if high_risks >= 1 or medium_risks >= 3:
        return "high"
    if medium_risks >= 1:
        return "medium"
    return "low"


def _generate_risk_narrative(analysis: RiskAnalysis, facility_type: str) -> str:
    """Generate a risk narrative summarizing findings."""
    parts = []

    if analysis.key_risks:
        parts.append(f"Key risks identified ({len(analysis.key_risks)}):")
        for risk in analysis.key_risks:
            parts.append(f"  • {risk.risk} ({risk.severity}): {risk.detail}")
    else:
        parts.append("No significant risk factors identified.")

    if analysis.mitigants:
        parts.append(f"\nMitigants ({len(analysis.mitigants)}):")
        for m in analysis.mitigants:
            parts.append(f"  • {m.mitigant} ({m.effectiveness}): {m.detail}")

    if analysis.concentration_flags:
        parts.append(f"\nConcentration flags:")
        for cf in analysis.concentration_flags:
            parts.append(f"  • {cf['detail']}")

    if analysis.covenant_breaches:
        parts.append(f"\nCovenant concerns:")
        for cb in analysis.covenant_breaches:
            parts.append(f"  • {cb['detail']}")

    parts.append(f"\nOverall risk assessment: {analysis.overall_risk_rating.upper()}")

    return "\n".join(parts)
