"""Ratio Agent — structured financial extraction and ratio computation.

Uses LLM structured output to extract financial figures from retrieved
document chunks, then computes key financial ratios deterministically.

Ratios computed:
- DSCR (Debt Service Coverage Ratio) = Net Operating Income / Total Debt Service
- Leverage Ratio = Total Liabilities / Total Equity
- Current Ratio = Current Assets / Current Liabilities

Design decision: Ratios are computed deterministically in Python (not by the
LLM) to ensure accuracy and auditability. The LLM only extracts the raw
figures; the math is done in code.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.agents.llm_client import get_llm_client
from app.core.business_config import get_risk_thresholds

logger = logging.getLogger(__name__)


@dataclass
class RatioBreach:
    """A ratio that breaches policy thresholds."""
    ratio_name: str
    value: float
    threshold: float
    direction: str  # "below_minimum" or "above_maximum"
    detail: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ratio_name": self.ratio_name,
            "value": self.value,
            "threshold": self.threshold,
            "direction": self.direction,
            "detail": self.detail,
        }


@dataclass
class RatioAgentResult:
    """Result from the ratio agent."""
    # Raw extracted financials
    net_operating_income: float = 0.0
    total_debt_service: float = 0.0
    total_liabilities: float = 0.0
    total_equity: float = 0.0
    current_assets: float = 0.0
    current_liabilities: float = 0.0

    # Source attributions
    source_chunk_ids: Dict[str, str] = field(default_factory=dict)

    # Computed ratios
    dscr: Optional[float] = None
    leverage_ratio: Optional[float] = None
    current_ratio: Optional[float] = None

    # Breaches
    breaches: List[RatioBreach] = field(default_factory=list)
    extraction_notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to a JSON-serializable dictionary."""
        return {
            "net_operating_income": self.net_operating_income,
            "total_debt_service": self.total_debt_service,
            "total_liabilities": self.total_liabilities,
            "total_equity": self.total_equity,
            "current_assets": self.current_assets,
            "current_liabilities": self.current_liabilities,
            "source_chunk_ids": self.source_chunk_ids,
            "dscr": self.dscr,
            "leverage_ratio": self.leverage_ratio,
            "current_ratio": self.current_ratio,
            "breaches": [b.to_dict() for b in self.breaches],
            "extraction_notes": self.extraction_notes,
        }


# JSON schema for structured extraction
_FINANCIAL_SCHEMA = {
    "type": "object",
    "properties": {
        "net_operating_income": {"type": "number", "description": "Net operating income in KD"},
        "total_debt_service": {"type": "number", "description": "Total debt service in KD"},
        "total_liabilities": {"type": "number", "description": "Total liabilities in KD"},
        "total_equity": {"type": "number", "description": "Total equity in KD"},
        "current_assets": {"type": "number", "description": "Current assets in KD"},
        "current_liabilities": {"type": "number", "description": "Current liabilities in KD"},
        "source_chunk_ids": {
            "type": "object",
            "additionalProperties": {"type": "string"},
            "description": "Maps each field to its source chunk_id",
        },
    },
    "required": [
        "net_operating_income",
        "total_debt_service",
        "total_liabilities",
        "total_equity",
        "current_assets",
        "current_liabilities",
        "source_chunk_ids",
    ],
}


def run_ratio_agent(
    retrieved_context: str,
    client_id: str,
) -> RatioAgentResult:
    """Extract financials and compute ratios.

    Args:
        retrieved_context: Concatenated text from retrieved chunks.
        client_id: Client identifier.

    Returns:
        RatioAgentResult with extracted figures, computed ratios, and breaches.
    """
    logger.info("RatioAgent: extracting financials for client=%s", client_id)
    result = RatioAgentResult()

    # Extract financials using LLM structured output
    try:
        llm = get_llm_client()
        prompt = (
            f"Extract the following financial figures for the client from the provided context. "
            f"All values should be in Kuwaiti Dinar (KD). If a figure is not available, use 0.\n\n"
            f"Client: {client_id}\n\n"
            f"Context:\n{retrieved_context}\n\n"
            f"Extract: net_operating_income, total_debt_service, total_liabilities, "
            f"total_equity, current_assets, current_liabilities. "
            f"Also map each field to its source chunk_id."
        )

        response = llm.complete_structured(prompt, _FINANCIAL_SCHEMA)
        data = response.data

        result.net_operating_income = float(data.get("net_operating_income", 0) or 0)
        result.total_debt_service = float(data.get("total_debt_service", 0) or 0)
        result.total_liabilities = float(data.get("total_liabilities", 0) or 0)
        result.total_equity = float(data.get("total_equity", 0) or 0)
        result.current_assets = float(data.get("current_assets", 0) or 0)
        result.current_liabilities = float(data.get("current_liabilities", 0) or 0)
        result.source_chunk_ids = data.get("source_chunk_ids", {})

    except Exception as e:
        logger.error("RatioAgent: extraction failed: %s", e)
        result.extraction_notes = f"Extraction failed: {str(e)[:200]}"
        return result

    # Compute ratios deterministically
    if result.total_debt_service > 0:
        result.dscr = result.net_operating_income / result.total_debt_service
    if result.total_equity > 0:
        result.leverage_ratio = result.total_liabilities / result.total_equity
    if result.current_liabilities > 0:
        result.current_ratio = result.current_assets / result.current_liabilities

    # Check against thresholds
    thresholds = get_risk_thresholds()
    result.breaches = _check_breaches(result, thresholds)

    logger.info(
        "RatioAgent: DSCR=%.2f Leverage=%.2f Current=%.2f Breaches=%d",
        result.dscr or 0, result.leverage_ratio or 0,
        result.current_ratio or 0, len(result.breaches),
    )

    return result


def _check_breaches(
    result: RatioAgentResult,
    thresholds: Dict[str, float],
) -> List[RatioBreach]:
    """Check computed ratios against policy thresholds."""
    breaches = []

    if result.dscr is not None:
        min_dscr = thresholds.get("min_dscr", 1.2)
        if result.dscr < min_dscr:
            breaches.append(RatioBreach(
                ratio_name="DSCR",
                value=result.dscr,
                threshold=min_dscr,
                direction="below_minimum",
                detail=f"DSCR {result.dscr:.2f}x is below minimum threshold of {min_dscr:.2f}x",
            ))

    if result.leverage_ratio is not None:
        max_leverage = thresholds.get("max_leverage_ratio", 3.0)
        if result.leverage_ratio > max_leverage:
            breaches.append(RatioBreach(
                ratio_name="Leverage Ratio",
                value=result.leverage_ratio,
                threshold=max_leverage,
                direction="above_maximum",
                detail=f"Leverage ratio {result.leverage_ratio:.2f}x exceeds maximum of {max_leverage:.2f}x",
            ))

    if result.current_ratio is not None:
        min_current = thresholds.get("min_current_ratio", 1.0)
        if result.current_ratio < min_current:
            breaches.append(RatioBreach(
                ratio_name="Current Ratio",
                value=result.current_ratio,
                threshold=min_current,
                direction="below_minimum",
                detail=f"Current ratio {result.current_ratio:.2f}x is below minimum of {min_current:.2f}x",
            ))

    return breaches
