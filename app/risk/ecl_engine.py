"""ECL Engine — CBK/IFRS 9-compliant Expected Credit Loss computation.

Implements the three-stage ECL model as mandated by the Central Bank of Kuwait (CBK)
and IFRS 9, with parameters validated against Warba Bank's public financial disclosures.

CBK-validated parameters:
- Stage 1 PD floor: 1.0% (100 bps)
- LGD floor (senior unsecured): 50%
- LGD floor (subordinated): 75%
- CCF (utilized cash/non-cash): 100%
- Stage 2 trigger: 30+ DPD or rating downgrade (2 grades IG, 1 grade non-IG)
- Stage 3: 100% LGD on net defaulted exposure after collateral haircuts
- Scenarios: 3 (base, upside, downside) with user-defined probabilities

Design decision: Every calculation is fully auditable — each facility's ECL
includes the exact CBK rules applied (e.g., "pd_floor_applied", "stage2_due_to_30_dpd").
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# =============================================================================
# CBK Parameters (default values — can be overridden)
# =============================================================================

DEFAULT_CKB_PARAMS = {
    "pd_floor_stage1": 0.01,           # 1% (100 bps) CBK minimum
    "lgd_floor_senior": 0.50,          # 50% for senior unsecured
    "lgd_floor_subordinated": 0.75,    # 75% for subordinated
    "lgd_stage3": 1.00,                # 100% on net exposure
    "ccf_utilized": 1.00,              # 100% for utilized facilities
    "ccf_unutilized_cash": 0.20,       # 20% for unutilized cash facilities
    "ccf_unutilized_noncash": 0.50,    # 50% for unutilized non-cash (e.g., guarantees)
    "stage2_dpd_threshold": 30,        # 30+ days past due triggers Stage 2
    "stage2_rating_downgrade_ig": 2,   # 2-notch downgrade for IG → Stage 2
    "stage2_rating_downgrade_nig": 1,  # 1-notch downgrade for non-IG → Stage 2
    "stage2_min_maturity_years": 7,    # CBK minimum maturity for Stage 2
    "collateral_haircuts": {
        "cash": 0.00,                  # No haircut on cash collateral
        "real_estate": 0.40,           # 40% haircut
        "guarantees": 0.20,            # 20% haircut
        "receivables": 0.30,           # 30% haircut
        "securities": 0.25,            # 25% haircut
    },
}

# Scenario weights (default — can be customized)
DEFAULT_SCENARIO_WEIGHTS = {
    "base": 0.50,
    "upside": 0.25,
    "downside": 0.25,
}

# Scenario PD multipliers
DEFAULT_SCENARIO_PD_MULTIPLIERS = {
    "base": 1.0,
    "upside": 0.7,
    "downside": 1.5,
}


@dataclass
class Facility:
    """A single credit facility for ECL computation."""
    facility_id: str
    client_id: str
    facility_type: str  # murabaha, ijara, musharakah, sukuk, tawarruq
    gross_exposure: float  # Gross carrying amount (KD)
    utilized_amount: float = 0.0
    unutilized_amount: float = 0.0
    pd_1yr: float = 0.01  # 1-year probability of default
    lgd: float = 0.50  # Loss given default
    days_past_due: int = 0
    internal_rating: str = "BBB"
    is_investment_grade: bool = True
    rating_at_origination: str = "BBB"
    collateral_type: str = "real_estate"
    collateral_value: float = 0.0
    seniority: str = "senior"  # senior, subordinated
    maturity_years: float = 5.0
    is_defaulted: bool = False
    # Shariah-native ECL fields (Warba Bank dual-prerogative alignment)
    profit_margin: float = 0.0          # Unearned profit portion of gross exposure (stripped from EAD)
    asset_recovery_rate: float = 0.0    # Expected recovery % of tangible asset (for Ijara/Musharaka)
    penalty_amount: float = 0.0         # Gharamah – excluded from income/cash flows
    shariah_non_compliant: bool = False # Triggers Stage 2 SICR


@dataclass
class FacilityECL:
    """ECL result for a single facility."""
    facility_id: str
    stage: int  # 1, 2, or 3
    ead: float  # Exposure at default
    pd: float  # Probability of default (with floor)
    lgd: float  # Loss given default (with floor and collateral)
    ecl: float  # Expected credit loss
    rules_applied: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "facility_id": self.facility_id,
            "stage": self.stage,
            "ead": round(self.ead, 2),
            "pd": round(self.pd, 6),
            "lgd": round(self.lgd, 4),
            "ecl": round(self.ecl, 2),
            "rules_applied": self.rules_applied,
        }


@dataclass
class ECLResult:
    """Aggregated ECL result for a portfolio."""
    stage1_ecl: float = 0.0
    stage2_ecl: float = 0.0
    stage3_ecl: float = 0.0
    total_ecl: float = 0.0
    provision_coverage_ratio: float = 0.0
    stage_breakdown: List[Dict[str, Any]] = field(default_factory=list)
    audit_trail: List[str] = field(default_factory=list)
    total_gross_exposure: float = 0.0
    total_net_exposure: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stage1_ecl": round(self.stage1_ecl, 2),
            "stage2_ecl": round(self.stage2_ecl, 2),
            "stage3_ecl": round(self.stage3_ecl, 2),
            "total_ecl": round(self.total_ecl, 2),
            "provision_coverage_ratio": round(self.provision_coverage_ratio, 2),
            "stage_breakdown": self.stage_breakdown,
            "audit_trail": self.audit_trail,
            "total_gross_exposure": round(self.total_gross_exposure, 2),
        }


def compute_ecl(
    portfolio: List[Facility],
    ckb_params: Optional[Dict[str, Any]] = None,
    scenario_weights: Optional[Dict[str, float]] = None,
    scenario_pd_multipliers: Optional[Dict[str, float]] = None,
) -> ECLResult:
    """Compute Expected Credit Loss for a portfolio using CBK/IFRS 9 methodology.

    Args:
        portfolio: List of Facility objects.
        ckb_params: Override CBK parameters.
        scenario_weights: Override scenario probability weights.
        scenario_pd_multipliers: Override scenario PD multipliers.

    Returns:
        ECLResult with stage-wise breakdown and full audit trail.
    """
    params = {**DEFAULT_CKB_PARAMS, **(ckb_params or {})}
    weights = scenario_weights or DEFAULT_SCENARIO_WEIGHTS
    pd_mults = scenario_pd_multipliers or DEFAULT_SCENARIO_PD_MULTIPLIERS

    result = ECLResult()
    stage_facilities: Dict[int, List[FacilityECL]] = {1: [], 2: [], 3: []}

    for facility in portfolio:
        # Step 1: Determine stage
        stage, stage_rules = _determine_stage(facility, params)

        # Step 2: Compute EAD (Exposure at Default)
        ead, ead_rules = _compute_ead(facility, params)

        # Step 3: Compute PD (with CBK floor)
        pd, pd_rules = _compute_pd(facility, stage, params)

        # Step 4: Compute LGD (with floor and collateral haircuts)
        # For Stage 3, also returns net_exposure after collateral haircut
        lgd, lgd_rules, net_exposure = _compute_lgd(facility, stage, ead, params)

        # Step 5: Three-scenario ECL
        # Stage 3 uses net_exposure (after collateral) instead of EAD
        exposure = net_exposure if stage == 3 else ead
        ecl = 0.0
        for scenario, weight in weights.items():
            scenario_pd = pd * pd_mults.get(scenario, 1.0)
            scenario_ecl = exposure * scenario_pd * lgd * weight
            ecl += scenario_ecl

        rules = stage_rules + ead_rules + pd_rules + lgd_rules
        rules.append(f"scenario_weighted_ecl={ecl:.2f}")

        facility_ecl = FacilityECL(
            facility_id=facility.facility_id,
            stage=stage,
            ead=ead,
            pd=pd,
            lgd=lgd,
            ecl=ecl,
            rules_applied=rules,
        )

        stage_facilities[stage].append(facility_ecl)
        result.total_gross_exposure += facility.gross_exposure

    # Aggregate by stage
    result.stage1_ecl = sum(f.ecl for f in stage_facilities[1])
    result.stage2_ecl = sum(f.ecl for f in stage_facilities[2])
    result.stage3_ecl = sum(f.ecl for f in stage_facilities[3])
    result.total_ecl = result.stage1_ecl + result.stage2_ecl + result.stage3_ecl

    # Provision coverage ratio = Total ECL / Stage 3 NPL exposure
    stage3_exposure = sum(
        f.ead for f in stage_facilities[3]
    )
    if stage3_exposure > 0:
        result.provision_coverage_ratio = result.total_ecl / stage3_exposure

    # Build stage breakdown
    for stage_num in [1, 2, 3]:
        facilities_in_stage = stage_facilities[stage_num]
        stage_ecl = sum(f.ecl for f in facilities_in_stage)
        result.stage_breakdown.append({
            "stage": stage_num,
            "facility_count": len(facilities_in_stage),
            "total_ead": round(sum(f.ead for f in facilities_in_stage), 2),
            "total_ecl": round(stage_ecl, 2),
            "facilities": [f.to_dict() for f in facilities_in_stage[:20]],  # Limit detail
        })

    # Build audit trail
    result.audit_trail = [
        f"Portfolio: {len(portfolio)} facilities",
        f"CBK params: PD floor={params['pd_floor_stage1']}, LGD floor senior={params['lgd_floor_senior']}",
        f"Scenario weights: {weights}",
        f"Stage 1: {len(stage_facilities[1])} facilities, ECL={result.stage1_ecl:.2f}",
        f"Stage 2: {len(stage_facilities[2])} facilities, ECL={result.stage2_ecl:.2f}",
        f"Stage 3: {len(stage_facilities[3])} facilities, ECL={result.stage3_ecl:.2f}",
        f"Total ECL: {result.total_ecl:.2f}",
    ]

    logger.info(
        "ECL Engine: Stage1=%.0f Stage2=%.0f Stage3=%.0f Total=%.0f",
        result.stage1_ecl, result.stage2_ecl, result.stage3_ecl, result.total_ecl,
    )

    return result


def _determine_stage(facility: Facility, params: Dict) -> tuple:
    """Determine the IFRS 9 staging for a facility."""
    rules = []

    # Stage 3: Defaulted facilities
    if facility.is_defaulted or facility.days_past_due >= 90:
        rules.append("stage3_defaulted")
        if facility.days_past_due >= 90:
            rules.append(f"stage3_due_to_{facility.days_past_due}_dpd")
        return 3, rules

    # Stage 2: Shariah non-compliance flag (takes precedence over DPD/rating)
    if facility.shariah_non_compliant:
        rules.append("stage2_shariah_non_compliant")
        return 2, rules

    # Stage 2: Significant increase in credit risk (SICR)
    # Criterion 1: 30+ DPD
    if facility.days_past_due >= params["stage2_dpd_threshold"]:
        rules.append(f"stage2_due_to_{facility.days_past_due}_dpd")
        return 2, rules

    # Criterion 2: Rating downgrade
    if facility.is_investment_grade:
        # IG: 2-notch downgrade triggers Stage 2
        notch_diff = _rating_notch_diff(facility.rating_at_origination, facility.internal_rating)
        if notch_diff >= params["stage2_rating_downgrade_ig"]:
            rules.append(f"stage2_due_to_{notch_diff}_notch_downgrade_IG")
            return 2, rules
    else:
        # Non-IG: 1-notch downgrade triggers Stage 2
        notch_diff = _rating_notch_diff(facility.rating_at_origination, facility.internal_rating)
        if notch_diff >= params["stage2_rating_downgrade_nig"]:
            rules.append(f"stage2_due_to_{notch_diff}_notch_downgrade_nonIG")
            return 2, rules

    # Stage 1: No SICR
    rules.append("stage1_no_sicr")
    return 1, rules


def _compute_ead(facility: Facility, params: Dict) -> tuple:
    """Compute Exposure at Default with Shariah-native adjustments.

    For Murabaha/Ijara/Tawarruq: subtract profit_margin from gross exposure
    before applying CCF (unearned profit is stripped from the EAD base).
    For Musharaka/Sukuk: use gross exposure directly (no profit stripping).
    Penalty amounts (Gharamah) are always excluded from EAD.
    """
    rules = []

    # Shariah-native: strip unearned profit margin for applicable contract types
    profit_strip_types = {"murabaha", "ijara", "tawarruq"}
    adjusted_gross = facility.gross_exposure
    if facility.facility_type.lower() in profit_strip_types and facility.profit_margin > 0:
        adjusted_gross = max(0, facility.gross_exposure - facility.profit_margin)
        rules.append(f"profit_margin_stripped={facility.profit_margin:.2f}_type={facility.facility_type}")

    # Exclude penalty (Gharamah) from EAD — not recognised as income
    if facility.penalty_amount > 0:
        adjusted_gross = max(0, adjusted_gross - facility.penalty_amount)
        rules.append("penalty_excluded_from_ead")

    if facility.utilized_amount > 0 or facility.unutilized_amount > 0:
        # EAD = Utilized + (Unutilized * CCF)
        utilized = facility.utilized_amount
        unutilized = facility.unutilized_amount

        ccf_util = params["ccf_utilized"]
        ccf_unutil = params.get("ccf_unutilized_cash", 0.20)

        # Scale utilized proportionally if profit was stripped
        if facility.gross_exposure > 0 and adjusted_gross != facility.gross_exposure:
            scale = adjusted_gross / facility.gross_exposure
            utilized = utilized * scale
            unutilized = unutilized * scale

        ead = (utilized * ccf_util) + (unutilized * ccf_unutil)
        rules.append(f"ead_computed_utilized_ccf={ccf_util}_unutilized_ccf={ccf_unutil}")
    else:
        # Use adjusted gross exposure directly
        ead = adjusted_gross
        rules.append("ead_equals_gross_exposure")

    return ead, rules


def _compute_pd(facility: Facility, stage: int, params: Dict) -> tuple:
    """Compute Probability of Default with CBK floor."""
    rules = []

    if stage == 3:
        # Stage 3: PD = 100% (already defaulted)
        pd = 1.0
        rules.append("pd_stage3_100_percent")
    elif stage == 2:
        # Stage 2: Lifetime PD (higher than 1-year)
        pd = facility.pd_1yr * min(facility.maturity_years, params["stage2_min_maturity_years"])
        # Apply floor
        floor = params["pd_floor_stage1"] * 2  # Stage 2 floor is higher
        if pd < floor:
            pd = floor
            rules.append(f"pd_floor_applied_stage2={floor}")
        else:
            rules.append(f"pd_lifetime={pd:.4f}")
    else:
        # Stage 1: 1-year PD with floor
        pd = facility.pd_1yr
        floor = params["pd_floor_stage1"]
        if pd < floor:
            pd = floor
            rules.append(f"pd_floor_applied_stage1={floor}")
        else:
            rules.append(f"pd_1yr={pd:.4f}")

    return pd, rules


def _compute_lgd(facility: Facility, stage: int, ead: float, params: Dict) -> tuple:
    """Compute Loss Given Default with floor and collateral haircuts.

    For Stage 3, returns net_exposure (after collateral haircut) as the
    third element of the tuple. The ECL calculation should use net_exposure
    instead of EAD for Stage 3 facilities.

    Shariah-native adjustments:
    - Ijara/Musharaka with asset_recovery_rate > 0: LGD = 1 - asset_recovery_rate
      (after applying CBK haircut to eligible collateral). Rule: "asset_based_lgd".
    - Murabaha/Tawarruq: standard LGD floors (50% senior / 75% sub).

    Returns:
        Tuple of (lgd, rules, net_exposure). net_exposure equals ead for
        non-Stage-3 facilities.
    """
    rules = []

    if stage == 3:
        # Stage 3: 100% LGD on net exposure after collateral
        net_exposure = ead
        if facility.collateral_value > 0:
            haircut = params["collateral_haircuts"].get(facility.collateral_type, 0.40)
            eligible_collateral = facility.collateral_value * (1 - haircut)
            net_exposure = max(0, ead - eligible_collateral)
            rules.append(f"stage3_lgd_collateral_haircut={haircut}_eligible={eligible_collateral:.0f}")

        if net_exposure > 0:
            lgd = params["lgd_stage3"]  # 100% on net
        else:
            lgd = 0.0
            rules.append("stage3_fully_collateralized")

        return lgd, rules, net_exposure

    # Shariah-native: asset-based LGD for Ijara/Musharaka
    asset_based_types = {"ijara", "musharakah"}
    if facility.facility_type.lower() in asset_based_types and facility.asset_recovery_rate > 0:
        # LGD based on tangible asset recovery rather than conventional LGD floors
        recovery = facility.asset_recovery_rate
        # Apply CBK collateral haircut to eligible collateral portion
        if facility.collateral_value > 0 and facility.gross_exposure > 0:
            haircut = params["collateral_haircuts"].get(facility.collateral_type, 0.40)
            eligible_collateral = facility.collateral_value * (1 - haircut)
            collateral_coverage = eligible_collateral / facility.gross_exposure
            # Blend asset recovery with collateral benefit
            effective_lgd = (1 - recovery) * (1 - min(collateral_coverage, 0.8))
        else:
            effective_lgd = 1 - recovery
        # Apply CBK floor as minimum
        if facility.seniority == "subordinated":
            lgd_floor = params["lgd_floor_subordinated"]
        else:
            lgd_floor = params["lgd_floor_senior"]
        lgd = max(effective_lgd, lgd_floor)
        rules.append(f"asset_based_lgd_recovery={recovery}_type={facility.facility_type}")
        rules.append("lgd_floor_senior" if facility.seniority != "subordinated" else "lgd_floor_subordinated")
        return lgd, rules, ead

    # Stage 1 & 2: Apply LGD floor (standard path for Murabaha/Tawarruq/Sukuk)
    if facility.seniority == "subordinated":
        lgd_floor = params["lgd_floor_subordinated"]
        rules.append("lgd_floor_subordinated")
    else:
        lgd_floor = params["lgd_floor_senior"]
        rules.append("lgd_floor_senior")

    lgd = max(facility.lgd, lgd_floor)

    # Apply collateral benefit (reduces LGD but not below floor)
    if facility.collateral_value > 0 and facility.gross_exposure > 0:
        haircut = params["collateral_haircuts"].get(facility.collateral_type, 0.40)
        eligible_collateral = facility.collateral_value * (1 - haircut)
        collateral_coverage = eligible_collateral / facility.gross_exposure
        # LGD reduced by collateral coverage (but not below floor)
        adjusted_lgd = lgd * (1 - min(collateral_coverage, 0.8))
        lgd = max(adjusted_lgd, lgd_floor)
        rules.append(f"collateral_adjustment_haircut={haircut}_coverage={collateral_coverage:.2f}")

    return lgd, rules, ead


# Rating scale for notch calculation
_RATING_SCALE = [
    "AAA", "AA+", "AA", "AA-", "A+", "A", "A-",
    "BBB+", "BBB", "BBB-", "BB+", "BB", "BB-",
    "B+", "B", "B-", "CCC", "CC", "C", "D",
]


def _rating_notch_diff(origination: str, current: str) -> int:
    """Calculate the number of notches between two ratings (positive = downgrade)."""
    try:
        orig_idx = _RATING_SCALE.index(origination.upper())
        curr_idx = _RATING_SCALE.index(current.upper())
        return max(0, curr_idx - orig_idx)
    except ValueError:
        return 0
