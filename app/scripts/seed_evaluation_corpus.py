"""Seed evaluation corpus with realistic test cases.

Generates 100 test cases under data/evaluation/corpus/, each containing:
- client_profile.json
- facility_details.json
- reference_annotations.json

Usage:
    python -m app.scripts.seed_evaluation_corpus [--cases N]
"""

from __future__ import annotations

import json
import logging
import os
import random
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

_CORPUS_ROOT = Path(__file__).resolve().parent.parent.parent / "data" / "evaluation" / "corpus"

# Realistic Kuwaiti corporate client templates
_CLIENT_TEMPLATES = [
    {"sector": "real_estate", "sub_sector": "commercial_development", "risk_rating": "BBB+"},
    {"sector": "construction", "sub_sector": "infrastructure", "risk_rating": "BBB"},
    {"sector": "trading", "sub_sector": "general_trading", "risk_rating": "A-"},
    {"sector": "healthcare", "sub_sector": "private_hospital", "risk_rating": "BBB+"},
    {"sector": "education", "sub_sector": "private_university", "risk_rating": "A-"},
    {"sector": "oil_and_gas", "sub_sector": "oilfield_services", "risk_rating": "BBB"},
    {"sector": "food_and_beverage", "sub_sector": "food_processing", "risk_rating": "BB+"},
    {"sector": "technology", "sub_sector": "fintech", "risk_rating": "BB"},
    {"sector": "logistics", "sub_sector": "warehousing", "risk_rating": "BBB"},
    {"sector": "manufacturing", "sub_sector": "building_materials", "risk_rating": "BBB+"},
]

_FACILITY_TYPES = ["murabaha", "ijara", "musharakah", "tawarruq"]


def _generate_financials(seed: int) -> Dict[str, float]:
    """Generate realistic financial figures for a client."""
    rng = random.Random(seed)
    revenue = rng.uniform(5_000_000, 150_000_000)
    noi_margin = rng.uniform(0.10, 0.35)
    debt_service = revenue * rng.uniform(0.3, 0.7)
    return {
        "net_operating_income": round(revenue * noi_margin, 2),
        "total_debt_service": round(debt_service, 2),
        "total_liabilities": round(revenue * rng.uniform(1.0, 4.0), 2),
        "total_equity": round(revenue * rng.uniform(0.5, 2.0), 2),
        "current_assets": round(revenue * rng.uniform(0.3, 0.8), 2),
        "current_liabilities": round(revenue * rng.uniform(0.2, 0.5), 2),
    }


def _generate_ratios(financials: Dict[str, float], seed: int) -> Dict[str, float]:
    """Compute reference ratios from financials with slight noise."""
    rng = random.Random(seed + 1000)
    noi = financials["net_operating_income"]
    ds = financials["total_debt_service"]
    ta = financials["total_assets"] if "total_assets" in financials else financials["current_assets"] * 2
    tl = financials["total_liabilities"]
    te = financials["total_equity"]
    ca = financials["current_assets"]
    cl = financials["current_liabilities"]

    return {
        "dscr": round(noi / ds if ds > 0 else 1.5, 2),
        "leverage_ratio": round(tl / te if te > 0 else 2.0, 2),
        "current_ratio": round(ca / cl if cl > 0 else 1.5, 2),
    }


def _generate_ecl_reference(deal_value: float, facility_type: str, seed: int) -> Dict[str, float]:
    """Generate reference ECL values."""
    rng = random.Random(seed + 2000)
    pd = rng.uniform(0.01, 0.05)
    lgd = rng.uniform(0.40, 0.60)
    stage1 = deal_value * pd * lgd * 0.1  # 12-month portion
    stage2 = deal_value * pd * 2 * lgd * 0.3  # Lifetime, higher PD
    stage3 = deal_value * 0.02 * lgd  # Small defaulted portion
    return {
        "stage1_ecl": round(stage1, 2),
        "stage2_ecl": round(stage2, 2),
        "stage3_ecl": round(stage3, 2),
        "total_ecl": round(stage1 + stage2 + stage3, 2),
    }


def _generate_case(case_num: int) -> Dict[str, Dict[str, Any]]:
    """Generate a single evaluation test case."""
    seed = case_num * 42
    rng = random.Random(seed)

    template = _CLIENT_TEMPLATES[case_num % len(_CLIENT_TEMPLATES)]
    facility_type = _FACILITY_TYPES[case_num % len(_FACILITY_TYPES)]
    deal_value = round(rng.uniform(200_000, 10_000_000), 2)

    financials = _generate_financials(seed)
    ratios = _generate_ratios(financials, seed)
    ecl = _generate_ecl_reference(deal_value, facility_type, seed)

    client_profile = {
        "client_id": f"EVAL-{case_num:04d}",
        "legal_name": f"Evaluation Client {case_num:04d} W.L.L.",
        "trade_name": f"EvalClient-{case_num}",
        "client_type": "corporate",
        "sector": template["sector"],
        "sub_sector": template["sub_sector"],
        "risk_rating": template["risk_rating"],
        "rm_name": "rm_ahmad",
        "financials": financials,
    }

    facility_details = {
        "facility_type": facility_type,
        "deal_value": deal_value,
        "collateral_type": rng.choice(["real_estate", "guarantees", "securities"]),
        "collateral_value": round(deal_value * rng.uniform(0.5, 1.5), 2),
        "days_past_due": 0,
        "maturity_years": round(rng.uniform(1.0, 7.0), 1),
    }

    reference_annotations = {
        "financials": financials,
        "ratios": ratios,
        "ecl": ecl,
        "facility_type": facility_type,
        "shariah_flags": [],
        "expected_citations": [f"chunk_{case_num:04d}_{i:03d}" for i in range(5)],
        "quality_scores": {
            "clarity": round(rng.uniform(3.5, 5.0), 1),
            "completeness": round(rng.uniform(3.0, 5.0), 1),
            "accuracy": round(rng.uniform(3.5, 5.0), 1),
            "compliance": round(rng.uniform(3.5, 5.0), 1),
        },
    }

    return {
        "client_profile": client_profile,
        "facility_details": facility_details,
        "reference_annotations": reference_annotations,
    }


def seed_corpus(num_cases: int = 100, output_dir: Path | None = None) -> None:
    """Generate the evaluation corpus.

    Args:
        num_cases: Number of test cases to generate.
        output_dir: Override output directory.
    """
    root = output_dir or _CORPUS_ROOT
    root.mkdir(parents=True, exist_ok=True)

    for i in range(1, num_cases + 1):
        case_dir = root / f"case_{i:04d}"
        case_dir.mkdir(exist_ok=True)

        case = _generate_case(i)

        _write_json(case_dir / "client_profile.json", case["client_profile"])
        _write_json(case_dir / "facility_details.json", case["facility_details"])
        _write_json(case_dir / "reference_annotations.json", case["reference_annotations"])

    logger.info("Seeded %d evaluation cases in %s", num_cases, root)


def _write_json(path: Path, data: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    import argparse
    import sys

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description="Seed evaluation corpus")
    parser.add_argument("--cases", type=int, default=100, help="Number of test cases (default: 100)")
    parser.add_argument("--output", type=str, default=None, help="Output directory")
    args = parser.parse_args()

    output = Path(args.output) if args.output else None
    seed_corpus(num_cases=args.cases, output_dir=output)
    print(f"Done. {args.cases} cases generated.")
