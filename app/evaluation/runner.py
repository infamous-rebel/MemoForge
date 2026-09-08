"""Shadow-mode evaluation runner.

Loads a corpus of test cases, runs the full MemoForge pipeline on each,
measures 8 metrics against reference annotations, and produces an
auditable benchmark report.

The runner operates in *shadow mode* — it does not affect production
decisions or memo approvals.
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.business_config import load_config
from app.evaluation.metrics import (
    PipelineTimer,
    measure_citation_correctness,
    measure_ecl_accuracy,
    measure_final_memo_quality,
    measure_human_override_frequency,
    measure_processing_time,
    measure_ratio_accuracy,
    measure_shariah_classification,
    measure_source_extraction_accuracy,
)

logger = logging.getLogger(__name__)

_CORPUS_ROOT = Path(__file__).resolve().parent.parent.parent / "data" / "evaluation" / "corpus"


# ---------------------------------------------------------------------------
# Corpus loading
# ---------------------------------------------------------------------------

def load_corpus(corpus_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Load evaluation test cases from the corpus directory.

    Each case directory must contain:
    - client_profile.json
    - facility_details.json
    - reference_annotations.json

    Args:
        corpus_path: Override path (defaults to data/evaluation/corpus/).

    Returns:
        List of case dicts ready for pipeline execution.
    """
    root = Path(corpus_path) if corpus_path else _CORPUS_ROOT
    if not root.exists():
        logger.warning("Corpus directory not found: %s", root)
        return []

    cases: List[Dict[str, Any]] = []
    for case_dir in sorted(root.iterdir()):
        if not case_dir.is_dir():
            continue
        try:
            client = _load_json(case_dir / "client_profile.json")
            facility = _load_json(case_dir / "facility_details.json")
            reference = _load_json(case_dir / "reference_annotations.json")
            cases.append({
                "case_id": case_dir.name,
                "client_profile": client,
                "facility_details": facility,
                "reference": reference,
            })
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning("Skipping invalid case %s: %s", case_dir.name, e)

    return cases


def _load_json(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Pipeline execution (shadow mode)
# ---------------------------------------------------------------------------

def _run_pipeline_shadow(
    db: Session,
    case: Dict[str, Any],
    timer: PipelineTimer,
) -> Dict[str, Any]:
    """Run the full pipeline on a single case in shadow mode.

    Returns a dict with all intermediate results for metric measurement.
    """
    client = case["client_profile"]
    facility = case["facility_details"]

    client_id = client.get("client_id", "eval_client")
    facility_type = facility.get("facility_type", "murabaha")
    deal_value = facility.get("deal_value", 1_000_000)

    timer.start_total()

    # Step 1: Data retrieval
    timer.start_step("data_agent")
    from app.agents.data_agent import run_data_agent
    data_result = run_data_agent(
        db=db,
        client_id=client_id,
        facility_type=facility_type,
        deal_value=deal_value,
    )
    timer.end_step()

    # Step 2: Ratio computation
    timer.start_step("ratio_agent")
    from app.agents.ratio_agent import run_ratio_agent
    ratio_result = run_ratio_agent(
        retrieved_context=data_result.retrieved_context_text,
        client_id=client_id,
    )
    timer.end_step()

    # Step 3: ECL computation
    timer.start_step("ecl_engine")
    ecl_result = None
    try:
        from app.risk.ecl_engine import compute_ecl
        from app.risk.synthetic_portfolio import generate_synthetic_portfolio
        portfolio = generate_synthetic_portfolio()
        ecl_obj = compute_ecl(portfolio)
        ecl_results = ecl_obj.to_dict()
    except Exception as e:
        logger.warning("ECL computation failed for case %s: %s", case["case_id"], e)
        ecl_results = {}
    timer.end_step()

    # Step 4: Narrative generation
    timer.start_step("narrative_agent")
    from app.agents.narrative_agent import run_narrative_agent
    narrative_result = run_narrative_agent(
        client_id=client_id,
        facility_type=facility_type,
        deal_value=deal_value,
        retrieved_context=data_result.retrieved_context_text,
        ratio_result=ratio_result,
        valid_chunk_ids=set(data_result.chunk_ids),
    )
    timer.end_step()

    # Step 5: Compliance checking
    timer.start_step("compliance_agent")
    from app.agents.compliance_agent import check_section
    compliance_results = []
    for section_draft in narrative_result.sections:
        cr = check_section(
            section_key=section_draft.section_key,
            content=section_draft.content,
            facility_type=facility_type,
            valid_chunk_ids=set(data_result.chunk_ids),
        )
        compliance_results.append(cr)
    timer.end_step()

    # Step 6: Compiler
    timer.start_step("compiler")
    timer.end_step()

    total_time = timer.end_total()

    # Build output for metric measurement
    return {
        "case_id": case["case_id"],
        "extracted_financials": _extract_financials_from_context(data_result.retrieved_context_text),
        "computed_ratios": ratio_result.to_dict() if ratio_result else {},
        "ecl_results": ecl_results or {},
        "narrative_sections": [
            {
                "section_key": s.section_key,
                "content": s.content,
                "shariah_flags": s.shariah_flags,
                "citations": s.citations,
                "requires_review": s.requires_review,
                "review_status": "pending",
                "approved_by": "",
                "flags": s.flags,
            }
            for s in narrative_result.sections
        ],
        "chunk_ids": data_result.chunk_ids,
        "timer": timer,
        "total_time": total_time,
    }


def _extract_financials_from_context(context: str) -> Dict[str, Any]:
    """Best-effort extraction of financial figures from retrieved context.

    Uses regex to find common financial figures. In production, this would
    be replaced by the data agent's structured extraction output.
    """
    import re
    financials: Dict[str, Any] = {}
    patterns = {
        "net_operating_income": r"(?:net\s+operating\s+income|NOI)[:\s]*\$?([\d,]+(?:\.\d+)?)",
        "total_debt_service": r"(?:total\s+debt\s+service|debt\s+service)[:\s]*\$?([\d,]+(?:\.\d+)?)",
        "total_liabilities": r"(?:total\s+liabilities|liabilities)[:\s]*\$?([\d,]+(?:\.\d+)?)",
        "total_equity": r"(?:total\s+equity|equity)[:\s]*\$?([\d,]+(?:\.\d+)?)",
        "current_assets": r"(?:current\s+assets)[:\s]*\$?([\d,]+(?:\.\d+)?)",
        "current_liabilities": r"(?:current\s+liabilities)[:\s]*\$?([\d,]+(?:\.\d+)?)",
    }
    for field, pattern in patterns.items():
        match = re.search(pattern, context, re.IGNORECASE)
        if match:
            try:
                financials[field] = float(match.group(1).replace(",", ""))
            except ValueError:
                pass
    return financials


# ---------------------------------------------------------------------------
# Report aggregation
# ---------------------------------------------------------------------------

def _aggregate_metrics(
    all_metrics: List[Dict[str, Any]],
    eval_config: Dict[str, Any],
) -> Dict[str, Any]:
    """Aggregate per-case metrics into a final benchmark report."""
    metric_configs = eval_config.get("metrics", {})
    aggregated: Dict[str, Any] = {}

    for metric_name, mconfig in metric_configs.items():
        if not mconfig.get("enabled", True):
            continue

        scores = [m[metric_name]["score"] for m in all_metrics if metric_name in m and "score" in m[metric_name]]
        if not scores:
            # Non-scoring metrics
            if metric_name == "processing_time":
                times = [m[metric_name]["total_seconds"] for m in all_metrics if metric_name in m]
                max_sec = mconfig.get("max_seconds", 300)
                avg_time = sum(times) / len(times) if times else 0
                aggregated[metric_name] = {
                    "avg_seconds": round(avg_time, 2),
                    "max_seconds": max_sec,
                    "pass": avg_time <= max_sec,
                }
            elif metric_name == "human_override_frequency":
                rates = [m[metric_name]["override_rate"] for m in all_metrics if metric_name in m]
                max_rate = mconfig.get("max_override_rate", 0.20)
                avg_rate = sum(rates) / len(rates) if rates else 0
                aggregated[metric_name] = {
                    "override_rate": round(avg_rate, 4),
                    "max": max_rate,
                    "pass": avg_rate <= max_rate,
                }
            continue

        avg_score = sum(scores) / len(scores)
        threshold = mconfig.get("threshold", 0.0)
        aggregated[metric_name] = {
            "score": round(avg_score, 4),
            "threshold": threshold,
            "pass": avg_score >= threshold,
            "cases_measured": len(scores),
        }

    return aggregated


def _determine_overall_status(aggregated: Dict[str, Any]) -> str:
    """Determine PASS/FAIL based on all metric results."""
    if not aggregated:
        return "NO_DATA"
    all_pass = all(m.get("pass", True) for m in aggregated.values())
    return "PASS" if all_pass else "FAIL"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_evaluation(
    db: Session,
    corpus_path: Optional[str] = None,
    max_cases: Optional[int] = None,
) -> Dict[str, Any]:
    """Run the full evaluation benchmark.

    Args:
        db: Database session.
        corpus_path: Override corpus directory.
        max_cases: Limit number of cases (for quick runs).

    Returns:
        Complete benchmark report dict.
    """
    config = load_config()
    eval_config = config.get("evaluation", {})

    if not eval_config.get("enabled", True):
        return {"status": "disabled", "message": "Evaluation framework is disabled in config.json"}

    cases = load_corpus(corpus_path)
    if max_cases:
        cases = cases[:max_cases]

    if not cases:
        return {
            "status": "no_data",
            "message": "No evaluation corpus found. Run app/scripts/seed_evaluation_corpus.py first.",
        }

    logger.info("Evaluation: running %d cases in shadow mode", len(cases))
    all_metrics: List[Dict[str, Any]] = []
    tolerances = eval_config.get("tolerances", {})
    amount_tol = tolerances.get("amount_pct", 0.02)

    for i, case in enumerate(cases):
        logger.info("Evaluation: case %d/%d — %s", i + 1, len(cases), case["case_id"])
        timer = PipelineTimer()

        try:
            output = _run_pipeline_shadow(db, case, timer)
        except Exception as e:
            logger.error("Pipeline failed for case %s: %s", case["case_id"], e)
            continue

        reference = case["reference"]
        case_metrics: Dict[str, Any] = {"case_id": case["case_id"]}

        # 1. Source extraction accuracy
        case_metrics["source_extraction_accuracy"] = measure_source_extraction_accuracy(
            output["extracted_financials"],
            reference.get("financials", {}),
            tolerance_pct=amount_tol,
        )

        # 2. Ratio accuracy
        case_metrics["ratio_accuracy"] = measure_ratio_accuracy(
            output["computed_ratios"],
            reference.get("ratios", {}),
        )

        # 3. ECL accuracy
        case_metrics["ecl_accuracy"] = measure_ecl_accuracy(
            output["ecl_results"],
            reference.get("ecl", {}),
        )

        # 4. Shariah classification
        pred_flags = []
        for s in output["narrative_sections"]:
            pred_flags.extend(s.get("shariah_flags", []))
        case_metrics["shariah_classification"] = measure_shariah_classification(
            pred_flags,
            reference.get("shariah_flags", []),
            case["facility_details"].get("facility_type", "murabaha"),
            reference.get("facility_type", case["facility_details"].get("facility_type", "murabaha")),
        )

        # 5. Citation correctness
        all_content = " ".join(s.get("content", "") for s in output["narrative_sections"])
        case_metrics["citation_correctness"] = measure_citation_correctness(
            all_content,
            set(output["chunk_ids"]),
        )

        # 6. Human override frequency (shadow — no real overrides yet)
        case_metrics["human_override_frequency"] = measure_human_override_frequency(
            output["narrative_sections"],
        )

        # 7. Final memo quality
        case_metrics["final_memo_quality"] = measure_final_memo_quality(
            output["narrative_sections"],
            reference.get("quality_scores"),
        )

        # 8. Processing time
        case_metrics["processing_time"] = measure_processing_time(
            timer,
            max_seconds=eval_config.get("metrics", {}).get("processing_time", {}).get("max_seconds", 300),
        )

        all_metrics.append(case_metrics)

    # Aggregate
    aggregated = _aggregate_metrics(all_metrics, eval_config)
    overall = _determine_overall_status(aggregated)

    report = {
        "status": "completed",
        "overall_status": overall,
        "cases_processed": len(all_metrics),
        "cases_total": len(cases),
        "shadow_mode": eval_config.get("shadow_mode", True),
        "metrics": aggregated,
    }

    # Save report
    output_dir = Path(__file__).resolve().parent.parent.parent / "output"
    output_dir.mkdir(exist_ok=True)
    report_path = output_dir / "evaluation_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)

    report["report_path"] = str(report_path)
    logger.info("Evaluation complete: %s — report saved to %s", overall, report_path)

    return report
