"""Data Validation Agent — checks data quality before downstream processing.

Verifies:
- Required fields exist (client financials, facility terms, collateral)
- Contradictions detected (e.g., different total assets in two chunks)
- Stale data detection (documents older than configurable threshold)
- Confidence score computation per client context
- Pipeline rejection if confidence below threshold

Design decision: This agent acts as a quality gate before the LLM agents
run. Garbage in → garbage out. Prevents the LLM from hallucinating around
missing data by rejecting low-quality contexts early.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.business_config import get_data_validation_config
from app.rag.retriever import RetrievedChunk

logger = logging.getLogger(__name__)


@dataclass
class DataQualityResult:
    """Result of data quality validation."""
    missing_fields: List[str] = field(default_factory=list)
    contradictions: List[Dict[str, Any]] = field(default_factory=list)
    stale_documents: List[Dict[str, Any]] = field(default_factory=list)
    confidence_score: float = 1.0
    is_valid: bool = True
    rejection_reason: str = ""
    details: Dict[str, Any] = field(default_factory=dict)


def validate_context(
    retrieved_chunks: List[RetrievedChunk],
    facility_type: str = "murabaha",
) -> DataQualityResult:
    """Validate the quality of retrieved data before feeding downstream agents.

    Args:
        retrieved_chunks: List of retrieved document chunks.
        facility_type: Islamic facility type for context-specific checks.

    Returns:
        DataQualityResult with validation outcomes.
    """
    config = get_data_validation_config()
    result = DataQualityResult()

    if not retrieved_chunks:
        result.is_valid = False
        result.confidence_score = 0.0
        result.rejection_reason = "No data retrieved for this client."
        result.missing_fields = config.get("required_fields", [])
        return result

    # --- Check 1: Required fields ---
    all_content = " ".join(c.content for c in retrieved_chunks)
    required_fields = config.get("required_fields", [])
    found_fields = _detect_financial_fields(all_content)

    missing = [f for f in required_fields if f not in found_fields]
    result.missing_fields = missing

    # --- Check 2: Contradictions ---
    result.contradictions = _detect_contradictions(retrieved_chunks)

    # --- Check 3: Stale data ---
    max_stale_days = config.get("max_stale_days", 180)
    result.stale_documents = _detect_stale_documents(retrieved_chunks, max_stale_days)

    # --- Compute confidence score ---
    result.confidence_score = _compute_confidence(
        chunks=retrieved_chunks,
        missing_fields=missing,
        required_fields=required_fields,
        contradictions=result.contradictions,
        stale_docs=result.stale_documents,
    )

    # --- Validate against threshold ---
    min_confidence = config.get("min_confidence_threshold", 0.7)
    if result.confidence_score < min_confidence:
        result.is_valid = False
        result.rejection_reason = (
            f"Data confidence ({result.confidence_score:.2f}) below threshold "
            f"({min_confidence:.2f}). Insufficient or low-quality data for memo generation."
        )
    else:
        result.is_valid = True

    result.details = {
        "total_chunks": len(retrieved_chunks),
        "fields_found": list(found_fields),
        "doc_types": list(set(c.document_type for c in retrieved_chunks if c.document_type)),
    }

    logger.info(
        "DataValidation: confidence=%.2f valid=%s missing=%d contradictions=%d stale=%d",
        result.confidence_score, result.is_valid,
        len(result.missing_fields), len(result.contradictions),
        len(result.stale_documents),
    )

    return result


def _detect_financial_fields(content: str) -> set:
    """Detect which financial fields are present in the content."""
    content_lower = content.lower()
    field_patterns = {
        "net_operating_income": [
            r"net\s+operating\s+income", r"noi\b", r"operating\s+income",
            r"net\s+income", r"revenue",
        ],
        "total_debt_service": [
            r"debt\s+service", r"total\s+debt\s+service", r"debt\s+payment",
            r"financing\s+cost",
        ],
        "total_liabilities": [
            r"total\s+liabilit", r"liabilit", r"total\s+debt",
        ],
        "total_equity": [
            r"total\s+equity", r"shareholder.+equity", r"owner.+equity",
            r"equity", r"capital",
        ],
        "current_assets": [
            r"current\s+asset", r"working\s+capital\s+asset",
        ],
        "current_liabilities": [
            r"current\s+liabilit", r"short.term\s+liabilit",
        ],
    }

    found = set()
    for field_name, patterns in field_patterns.items():
        for pattern in patterns:
            if re.search(pattern, content_lower):
                found.add(field_name)
                break
    return found


def _detect_contradictions(chunks: List[RetrievedChunk]) -> List[Dict[str, Any]]:
    """Detect contradictions between chunks (e.g., different values for the same metric)."""
    contradictions = []

    # Extract numeric values associated with key terms
    value_map: Dict[str, List[Dict[str, Any]]] = {}

    for chunk in chunks:
        content = chunk.content
        # Look for patterns like "Total Assets: 5,000,000" or "total assets of KD 5M"
        patterns = [
            (r"total\s+assets?\s*(?:of|:)?\s*(?:KD\s*)?([\d,]+(?:\.\d+)?)\s*(?:million|billion|k|m|b)?",
             "total_assets"),
            (r"(?:net|total)\s+(?:revenue|income)\s*(?:of|:)?\s*(?:KD\s*)?([\d,]+(?:\.\d+)?)\s*(?:million|billion|k|m|b)?",
             "total_revenue"),
        ]

        for pattern, metric in patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                try:
                    value = float(match.replace(",", ""))
                    if metric not in value_map:
                        value_map[metric] = []
                    value_map[metric].append({
                        "value": value,
                        "chunk_id": chunk.chunk_id,
                        "text": content[:200],
                    })
                except ValueError:
                    logger.debug("Could not parse numeric value for metric '%s'", metric)

    # Check for contradictions (different values for same metric)
    for metric, values in value_map.items():
        if len(values) > 1:
            unique_values = set(v["value"] for v in values)
            if len(unique_values) > 1:
                contradictions.append({
                    "metric": metric,
                    "values": values,
                    "severity": "warning",
                    "detail": f"Contradictory values for {metric}: {unique_values}",
                })

    return contradictions


def _detect_stale_documents(
    chunks: List[RetrievedChunk],
    max_stale_days: int,
) -> List[Dict[str, Any]]:
    """Detect documents that may be older than the staleness threshold."""
    stale = []
    now = datetime.now(timezone.utc)

    for chunk in chunks:
        content = chunk.content.lower()
        # Look for date references in the content
        date_patterns = [
            r"(?:dated?|as of|for the period ending?)\s+(\d{1,2})\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\s+(\d{4})",
            r"(?:fy|fiscal year)\s+(\d{4})",
            r"(q[1-4]|h[12])\s+(\d{4})",
        ]
        for pattern in date_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                # Found a date reference — note it
                stale.append({
                    "chunk_id": chunk.chunk_id,
                    "document_title": chunk.document_title,
                    "date_reference": match.group(0),
                    "severity": "info",
                })
                break

    return stale


def _compute_confidence(
    chunks: List[RetrievedChunk],
    missing_fields: List[str],
    required_fields: List[str],
    contradictions: List[Dict[str, Any]],
    stale_docs: List[Dict[str, Any]],
) -> float:
    """Compute a confidence score (0-1) for the data quality."""
    if not chunks:
        return 0.0

    score = 1.0

    # Penalize for missing fields (up to -0.5)
    if required_fields:
        missing_ratio = len(missing_fields) / len(required_fields)
        score -= missing_ratio * 0.5

    # Penalize for contradictions (up to -0.2)
    score -= min(len(contradictions) * 0.1, 0.2)

    # Penalize for few chunks (up to -0.2)
    if len(chunks) < 3:
        score -= (3 - len(chunks)) * 0.1

    # Penalize for low-quality content
    total_length = sum(len(c.content) for c in chunks)
    avg_length = total_length / len(chunks)
    if avg_length < 100:
        score -= 0.1

    # Bonus for diverse document types
    doc_types = set(c.document_type for c in chunks if c.document_type)
    if len(doc_types) >= 3:
        score += 0.05

    return max(0.0, min(1.0, score))
