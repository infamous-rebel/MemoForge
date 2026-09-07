"""ECL Validation — validates engine output against real Warba Bank figures.

Reference data from Warba Bank's public financial disclosures:
- 30 Jun 2024 (Cash facilities): Stage1 KD 2,627k, Stage2 KD 2,107k, Stage3 KD 15,945k, Total KD 20,679k
- 31 Dec 2023 (Cash facilities): Stage1 KD 2,249k, Stage2 KD 2,959k, Stage3 KD 3,768k, Total KD 8,976k

Validates that the ECL engine produces plausible results on synthetic data
by comparing stage proportions to real bank disclosures.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.risk.ecl_engine import ECLResult
from app.risk.synthetic_portfolio import generate_synthetic_portfolio

logger = logging.getLogger(__name__)


# Real Warba Bank ECL figures (KD thousands)
WARBA_REFERENCE = {
    "jun_2024_cash": {
        "stage1": 2_627_000,
        "stage2": 2_107_000,
        "stage3": 15_945_000,
        "total": 20_679_000,
        "stage3_pct_of_total": 0.771,  # 77.1%
    },
    "dec_2023_cash": {
        "stage1": 2_249_000,
        "stage2": 2_959_000,
        "stage3": 3_768_000,
        "total": 8_976_000,
        "stage3_pct_of_total": 0.420,
    },
    "jan_2023_cash": {
        "stage1": 2_067_000,
        "stage2": 2_687_000,
        "stage3": 4_498_000,
        "total": 9_252_000,
        "stage3_pct_of_total": 0.486,
    },
}


@dataclass
class ValidationResult:
    """Result of ECL validation against reference data."""
    is_valid: bool = True
    issues: List[str] = field(default_factory=list)
    reference_period: str = ""
    computed: Dict[str, float] = field(default_factory=dict)
    reference: Dict[str, float] = field(default_factory=dict)
    stage_proportions: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "issues": self.issues,
            "reference_period": self.reference_period,
            "computed": self.computed,
            "reference": self.reference,
            "stage_proportions": self.stage_proportions,
        }


def validate_ecl_result(
    ecl_result: ECLResult,
    reference_period: str = "jun_2024_cash",
    tolerance_pct: float = 0.30,
) -> ValidationResult:
    """Validate ECL result against real bank reference data.

    Args:
        ecl_result: The computed ECL result.
        reference_period: Which reference period to compare against.
        tolerance_pct: Maximum allowed deviation from reference proportions.

    Returns:
        ValidationResult with issues and comparison data.
    """
    ref = WARBA_REFERENCE.get(reference_period)
    if not ref:
        return ValidationResult(
            is_valid=False,
            issues=[f"Unknown reference period: {reference_period}"],
        )

    result = ValidationResult(reference_period=reference_period)

    # Compute stage proportions from ECL result
    total = ecl_result.total_ecl
    if total <= 0:
        result.is_valid = False
        result.issues.append("Total ECL is zero or negative — invalid result")
        return result

    computed_props = {
        "stage1_pct": ecl_result.stage1_ecl / total,
        "stage2_pct": ecl_result.stage2_ecl / total,
        "stage3_pct": ecl_result.stage3_ecl / total,
    }

    ref_props = {
        "stage1_pct": ref["stage1"] / ref["total"],
        "stage2_pct": ref["stage2"] / ref["total"],
        "stage3_pct": ref["stage3"] / ref["total"],
    }

    result.computed = {
        "stage1_ecl": ecl_result.stage1_ecl,
        "stage2_ecl": ecl_result.stage2_ecl,
        "stage3_ecl": ecl_result.stage3_ecl,
        "total_ecl": ecl_result.total_ecl,
    }
    result.reference = ref
    result.stage_proportions = computed_props

    # Compare proportions
    for key in ["stage1_pct", "stage2_pct", "stage3_pct"]:
        computed_val = computed_props[key]
        ref_val = ref_props[key]
        diff = abs(computed_val - ref_val)

        if diff > tolerance_pct:
            result.is_valid = False
            result.issues.append(
                f"{key}: computed={computed_val:.3f}, reference={ref_val:.3f}, "
                f"diff={diff:.3f} exceeds tolerance {tolerance_pct:.3f}"
            )

    # Check Stage 3 dominance (should be the largest component)
    if ecl_result.stage3_ecl < ecl_result.stage1_ecl:
        result.issues.append(
            "Warning: Stage 3 ECL is less than Stage 1 — may indicate "
            "insufficient defaulted facilities in portfolio"
        )

    if result.is_valid:
        logger.info("ECL validation passed against %s", reference_period)
    else:
        logger.warning("ECL validation issues: %s", result.issues)

    return result


def run_validation_suite() -> Dict[str, ValidationResult]:
    """Run the full ECL validation suite against all reference periods.

    Returns:
        Dict mapping period names to ValidationResult objects.
    """
    portfolio = generate_synthetic_portfolio()
    from app.risk.ecl_engine import compute_ecl

    ecl_result = compute_ecl(portfolio)
    results = {}

    for period in WARBA_REFERENCE:
        results[period] = validate_ecl_result(ecl_result, reference_period=period)

    return results
