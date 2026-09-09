"""Evaluation metric implementations.

Each metric function takes pipeline output and reference annotations,
computes a score, and returns a result dict with the score plus
traceable evidence (failures, breakdowns).

All metrics are configurable via the `evaluation` section of config.json.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_div(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Division that returns *default* when denominator is zero."""
    return numerator / denominator if denominator else default


def _within_tolerance(extracted: float, reference: float, pct: float) -> bool:
    """Return True if *extracted* is within ±pct of *reference*."""
    if reference == 0:
        return abs(extracted) < 1.0
    return abs(extracted - reference) / abs(reference) <= pct


# ---------------------------------------------------------------------------
# 1. Source Extraction Accuracy
# ---------------------------------------------------------------------------

def measure_source_extraction_accuracy(
    extracted_financials: Dict[str, Any],
    reference_financials: Dict[str, Any],
    tolerance_pct: float = 0.02,
) -> Dict[str, Any]:
    """Compare extracted financial figures against ground-truth annotations.

    A value is *correct* when it matches the reference within ±tolerance_pct.

    Args:
        extracted_financials: Key-value pairs extracted by the data agent.
        reference_financials: Ground-truth values from human analysts.
        tolerance_pct: Acceptable relative tolerance (default 2 %).

    Returns:
        Dict with score, correct/total counts, and per-field failures.
    """
    correct = 0
    total = 0
    failures: List[Dict[str, Any]] = []

    for field, ref_value in reference_financials.items():
        if not isinstance(ref_value, (int, float)):
            continue
        total += 1
        ext_value = extracted_financials.get(field)
        if ext_value is not None and isinstance(ext_value, (int, float)):
            if _within_tolerance(ext_value, ref_value, tolerance_pct):
                correct += 1
            else:
                failures.append({
                    "field": field,
                    "extracted": ext_value,
                    "reference": ref_value,
                })
        else:
            failures.append({
                "field": field,
                "extracted": None,
                "reference": ref_value,
            })

    score = _safe_div(correct, total)
    return {
        "score": round(score, 4),
        "correct": correct,
        "total": total,
        "failures": failures,
    }


# ---------------------------------------------------------------------------
# 2. Ratio Accuracy
# ---------------------------------------------------------------------------

def measure_ratio_accuracy(
    computed_ratios: Dict[str, float],
    reference_ratios: Dict[str, float],
) -> Dict[str, Any]:
    """Compare computed ratios against reference using normalised MAE.

    score = 1 − mean(|computed − reference| / |reference|)

    Args:
        computed_ratios: e.g. {"dscr": 1.45, "leverage_ratio": 2.1, ...}
        reference_ratios: Ground-truth ratio values.

    Returns:
        Dict with overall score and per-ratio MAE breakdown.
    """
    per_ratio_mae: Dict[str, float] = {}
    errors: List[float] = []

    for name, ref_val in reference_ratios.items():
        comp_val = computed_ratios.get(name)
        if comp_val is None or ref_val == 0:
            continue
        mae = abs(comp_val - ref_val) / abs(ref_val)
        per_ratio_mae[name] = round(mae, 4)
        errors.append(mae)

    mean_mae = sum(errors) / len(errors) if errors else 0.0
    score = max(0.0, 1.0 - mean_mae)

    result: Dict[str, Any] = {"score": round(score, 4)}
    result.update({f"{k}_mae": v for k, v in per_ratio_mae.items()})
    return result


# ---------------------------------------------------------------------------
# 3. ECL Accuracy
# ---------------------------------------------------------------------------

def measure_ecl_accuracy(
    computed_ecl: Dict[str, float],
    reference_ecl: Dict[str, float],
) -> Dict[str, Any]:
    """Compare ECL values against reference.

    score per stage = 1 − |computed − reference| / |reference|
    Overall = weighted average across stages.

    Args:
        computed_ecl: {"stage1_ecl": ..., "stage2_ecl": ..., "stage3_ecl": ..., "total_ecl": ...}
        reference_ecl: Same keys from a human-validated model.

    Returns:
        Dict with score and per-stage MAE.
    """
    stage_keys = ["stage1_ecl", "stage2_ecl", "stage3_ecl"]
    per_stage: Dict[str, float] = {}
    scores: List[float] = []

    for sk in stage_keys:
        comp = computed_ecl.get(sk, 0.0)
        ref = reference_ecl.get(sk, 0.0)
        if ref == 0:
            continue
        accuracy = max(0.0, 1.0 - abs(comp - ref) / abs(ref))
        per_stage[sk] = round(accuracy, 4)
        scores.append(accuracy)

    overall = sum(scores) / len(scores) if scores else 0.0

    result: Dict[str, Any] = {"score": round(overall, 4)}
    result.update({f"{k}_accuracy": v for k, v in per_stage.items()})
    return result


# ---------------------------------------------------------------------------
# 4. Shariah Classification
# ---------------------------------------------------------------------------

def measure_shariah_classification(
    predicted_flags: List[Dict[str, Any]],
    reference_flags: List[Dict[str, Any]],
    predicted_facility_type: str,
    reference_facility_type: str,
) -> Dict[str, Any]:
    """Measure Shariah classification accuracy.

    Accuracy = correct_classifications / total_classifications.
    Also computes false-positive and false-negative rates.

    Args:
        predicted_flags: Flags from the pipeline's Shariah filter.
        reference_flags: Ground-truth Shariah flags.
        predicted_facility_type: Facility type assigned by pipeline.
        reference_facility_type: Correct facility type.

    Returns:
        Dict with score, FPR, FNR, and misclassifications.
    """
    # Facility type classification
    type_correct = predicted_facility_type.lower() == reference_facility_type.lower()
    total_classifications = 1
    correct = 1 if type_correct else 0

    # Flag-level analysis
    pred_terms = {f.get("term", "") for f in predicted_flags}
    ref_terms = {f.get("term", "") for f in reference_flags}

    # False positives: flagged but shouldn't have been
    fp = len(pred_terms - ref_terms)
    # False negatives: should have been flagged but weren't
    fn = len(ref_terms - pred_terms)
    # True positives
    tp = len(pred_terms & ref_terms)

    total_positives = tp + fn
    fpr = _safe_div(fp, fp + (len(pred_terms) - fp), 0.0) if pred_terms else 0.0
    fnr = _safe_div(fn, total_positives, 0.0) if total_positives > 0 else 0.0

    misclassifications: List[Dict[str, str]] = []
    if not type_correct:
        misclassifications.append({
            "type": "facility_type",
            "predicted": predicted_facility_type,
            "reference": reference_facility_type,
        })

    score = _safe_div(correct, total_classifications)
    return {
        "score": round(score, 4),
        "false_positive_rate": round(fpr, 4),
        "false_negative_rate": round(fnr, 4),
        "misclassifications": misclassifications,
    }


# ---------------------------------------------------------------------------
# 5. Citation Correctness
# ---------------------------------------------------------------------------

def measure_citation_correctness(
    content: str,
    valid_chunk_ids: set,
) -> Dict[str, Any]:
    """Verify that every [ref:chunk_id] in content references a real chunk.

    Args:
        content: Generated memo section content.
        valid_chunk_ids: Set of chunk IDs that actually exist.

    Returns:
        Dict with score, valid/total counts, orphan and missing citation lists.
    """
    pattern = re.compile(r'\[ref:([a-zA-Z0-9_-]+)\]')
    citations = pattern.findall(content)

    valid_count = 0
    orphan_citations: List[str] = []

    for cid in citations:
        if cid in valid_chunk_ids:
            valid_count += 1
        else:
            orphan_citations.append(cid)

    total = len(citations)
    score = _safe_div(valid_count, total, 1.0) if total > 0 else 1.0

    return {
        "score": round(score, 4),
        "valid_citations": valid_count,
        "total_citations": total,
        "orphan_citations": orphan_citations,
        "missing_citations": [],
    }


# ---------------------------------------------------------------------------
# 6. Human Override Frequency
# ---------------------------------------------------------------------------

def measure_human_override_frequency(
    sections: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Measure how often sections required human correction.

    A section counts as *overridden* when its review_status indicates
    manual intervention (e.g. "approved" after being "pending", or
    "rejected" then re-approved).

    Args:
        sections: List of section dicts from the memo (with review_status).

    Returns:
        Dict with override_rate, counts, and per-reason breakdown.
    """
    total_sections = len(sections)
    overrides = 0
    reasons: Dict[str, int] = {}

    for s in sections:
        status = s.get("review_status", "")
        requires_review = s.get("requires_review", False)
        approved_by = s.get("approved_by", "")

        # Count as override if it required review AND was eventually approved
        # by a human (not auto-approved)
        if requires_review and status in ("approved",) and approved_by:
            overrides += 1
            reason = s.get("review_reason", "unknown")
            reasons[reason] = reasons.get(reason, 0) + 1

    override_rate = _safe_div(overrides, total_sections)
    return {
        "override_rate": round(override_rate, 4),
        "total_overrides": overrides,
        "total_sections": total_sections,
        "reasons": reasons,
    }


# ---------------------------------------------------------------------------
# 7. Final Memo Quality
# ---------------------------------------------------------------------------

def measure_final_memo_quality(
    memo_sections: List[Dict[str, Any]],
    reference_scores: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """Estimate final memo quality from structural signals.

    When pre-scored reference data is available, compares against it.
    Otherwise, derives a heuristic quality score from:
    - Section completeness (all 5 sections present with content)
    - Citation density (citations per section)
    - Flag absence (fewer flags = higher quality)

    Args:
        memo_sections: List of section dicts from the final memo.
        reference_scores: Optional pre-scored {"clarity": 4.5, ...}.

    Returns:
        Dict with composite score and sub-scores.
    """
    if reference_scores:
        return {
            "score": round(sum(reference_scores.values()) / len(reference_scores) / 5.0, 4),
            **{k: round(v / 5.0, 4) for k, v in reference_scores.items()},
        }

    # Heuristic scoring
    expected_keys = {
        "borrower_overview", "financial_analysis", "risk_and_mitigants",
        "policy_exceptions", "recommendation",
    }
    present_keys = {s.get("section_key", "") for s in memo_sections}
    completeness = _safe_div(len(present_keys & expected_keys), len(expected_keys))

    # Citation density: average citations per section
    total_citations = 0
    for s in memo_sections:
        content = s.get("content", "")
        total_citations += len(re.findall(r'\[ref:[a-zA-Z0-9_-]+\]', content))
    citation_density = min(1.0, _safe_div(total_citations, max(len(memo_sections) * 5, 1)))

    # Flag absence: fewer flags = higher quality
    total_flags = sum(
        len((s.get("flags", {}) or {}).get("shariah", []))
        for s in memo_sections
    )
    flag_score = max(0.0, 1.0 - total_flags * 0.1)

    # Content completeness: each section should have >100 chars
    content_scores = []
    for s in memo_sections:
        length = len(s.get("content", ""))
        content_scores.append(min(1.0, length / 500.0))
    content_score = sum(content_scores) / len(content_scores) if content_scores else 0.0

    composite = (completeness * 0.3 + citation_density * 0.3 +
                 flag_score * 0.2 + content_score * 0.2)

    return {
        "score": round(composite, 4),
        "completeness": round(completeness, 4),
        "citation_density": round(citation_density, 4),
        "flag_absence": round(flag_score, 4),
        "content_quality": round(content_score, 4),
    }


# ---------------------------------------------------------------------------
# 8. Processing Time
# ---------------------------------------------------------------------------

class PipelineTimer:
    """Context-manager timer for pipeline steps."""

    def __init__(self) -> None:
        self.step_times: Dict[str, float] = {}
        self._current_step: Optional[str] = None
        self._start: float = 0.0
        self._total_start: float = 0.0

    def start_total(self) -> None:
        self._total_start = time.monotonic()

    def start_step(self, step_name: str) -> None:
        self._current_step = step_name
        self._start = time.monotonic()

    def end_step(self) -> None:
        if self._current_step:
            elapsed = time.monotonic() - self._start
            self.step_times[self._current_step] = round(elapsed, 3)
            self._current_step = None

    def end_total(self) -> float:
        return round(time.monotonic() - self._total_start, 3)

    def result(self) -> Dict[str, Any]:
        total = self.end_total()
        result: Dict[str, Any] = {"total_seconds": total}
        result.update(self.step_times)
        return result


def measure_processing_time(
    timer: PipelineTimer,
    max_seconds: float = 300.0,
) -> Dict[str, Any]:
    """Evaluate processing time against the configured maximum.

    Args:
        timer: PipelineTimer that recorded step durations.
        max_seconds: Maximum acceptable total time.

    Returns:
        Dict with total_seconds, per-step breakdown, and max_seconds.
    """
    result = timer.result()
    result["max_seconds"] = max_seconds
    return result
