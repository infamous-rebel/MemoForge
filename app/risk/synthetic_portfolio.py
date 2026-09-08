"""Synthetic Portfolio Generator — matches Warba Bank's disclosed profile.

Generates a deterministic portfolio for ECL demonstration and validation:
- Total gross financing ~KD 4.0–4.3B
- NPL ratio ~1.4–1.5%
- Provision coverage ratio ~153–156%
- Facility types: Murabaha, Ijara, Musharakah, Sukuk, Tawarruq
- Collateral: cash, real estate, guarantees, receivables (with CBK haircuts)
"""

from __future__ import annotations

import logging
from typing import List

from app.risk.ecl_engine import Facility

logger = logging.getLogger(__name__)


def generate_synthetic_portfolio(
    total_gross_financing: float = 4_150_000_000,
    npl_ratio: float = 0.0145,
    num_facilities: int = 200,
) -> List[Facility]:
    """Generate a deterministic synthetic portfolio matching Warba's profile.

    Args:
        total_gross_financing: Total gross financing in KD (default ~4.15B).
        npl_ratio: Non-performing loan ratio (default 1.45%).
        num_facilities: Number of facilities to generate.

    Returns:
        List of Facility objects representing the portfolio.
    """
    import hashlib

    facilities: List[Facility] = []
    avg_exposure = total_gross_financing / num_facilities

    # Facility type distribution (matching Warba's typical mix)
    type_distribution = [
        ("murabaha", 0.35),
        ("ijara", 0.25),
        ("musharakah", 0.15),
        ("sukuk", 0.10),
        ("tawarruq", 0.15),
    ]

    # Segment distribution
    segments = [
        ("corporate", 0.50),
        ("sme", 0.25),
        ("consumer", 0.15),
        ("real_estate", 0.10),
    ]

    # Collateral types
    collateral_types = ["cash", "real_estate", "guarantees", "receivables", "securities"]

    facility_idx = 0
    for ftype, ftype_pct in type_distribution:
        count = max(1, int(num_facilities * ftype_pct))
        for i in range(count):
            if facility_idx >= num_facilities:
                break

            # Deterministic seed for reproducibility
            seed = int(hashlib.md5(f"{ftype}_{i}".encode()).hexdigest()[:8], 16)
            rng_val = (seed % 1000) / 1000.0

            # Exposure: vary around average
            exposure = avg_exposure * (0.3 + rng_val * 1.4)

            # Determine if defaulted (NPL)
            is_defaulted = rng_val < npl_ratio

            # DPD
            if is_defaulted:
                dpd = 90 + (seed % 270)  # 90-360 DPD
            elif rng_val < 0.05:
                dpd = 30 + (seed % 60)  # 30-90 DPD (Stage 2 trigger)
            else:
                dpd = seed % 30  # 0-29 DPD (Stage 1)

            # Rating
            if is_defaulted:
                rating = "CCC" if rng_val < 0.5 else "CC"
                is_ig = False
            elif dpd >= 30:
                rating = "BB" if rng_val < 0.5 else "BB+"
                is_ig = False
            else:
                ratings_ig = ["AAA", "AA+", "AA", "AA-", "A+", "A", "A-", "BBB+", "BBB", "BBB-"]
                rating = ratings_ig[seed % len(ratings_ig)]
                is_ig = True

            # Collateral
            coll_type = collateral_types[seed % len(collateral_types)]
            coll_value = exposure * (0.3 + (seed % 70) / 100.0)

            # PD
            if is_defaulted:
                pd = 1.0
            elif is_ig:
                pd = 0.005 + (seed % 20) / 1000.0  # 0.5%-2.5%
            else:
                pd = 0.03 + (seed % 50) / 1000.0  # 3%-8%

            # LGD
            if is_defaulted:
                lgd = 1.0
            else:
                lgd = 0.40 + (seed % 30) / 100.0  # 40%-70%

            # Maturity
            maturity = 1.0 + (seed % 10)  # 1-10 years

            # Utilized vs unutilized
            util_ratio = 0.6 + (seed % 40) / 100.0  # 60%-100%
            utilized = exposure * util_ratio
            unutilized = exposure * (1 - util_ratio)

            # Shariah-native fields
            profit_margin = 0.0
            asset_recovery_rate = 0.0
            penalty_amount = 0.0
            shariah_non_compliant = False

            if ftype == "murabaha":
                profit_margin = exposure * 0.10  # ~10% of gross exposure
            elif ftype == "tawarruq":
                profit_margin = exposure * 0.08
            elif ftype == "ijara":
                asset_recovery_rate = 0.70  # 70% tangible asset recovery

            # A few facilities flagged for Shariah non-compliance (Stage 2 trigger)
            if not is_defaulted and facility_idx % 25 == 7:
                shariah_non_compliant = True

            # A few facilities with penalty amounts (Gharamah excluded from EAD)
            if not is_defaulted and facility_idx % 30 == 3:
                penalty_amount = exposure * 0.02  # 2% penalty

            facility = Facility(
                facility_id=f"SYN-{ftype[:3].upper()}-{facility_idx:04d}",
                client_id=f"CLIENT-{(seed % 50) + 1:03d}",
                facility_type=ftype,
                gross_exposure=exposure,
                utilized_amount=utilized,
                unutilized_amount=unutilized,
                pd_1yr=pd,
                lgd=lgd,
                days_past_due=dpd,
                internal_rating=rating,
                is_investment_grade=is_ig,
                rating_at_origination=rating if not is_defaulted else "BBB",
                collateral_type=coll_type,
                collateral_value=coll_value,
                seniority="senior" if rng_val > 0.2 else "subordinated",
                maturity_years=maturity,
                is_defaulted=is_defaulted,
                profit_margin=profit_margin,
                asset_recovery_rate=asset_recovery_rate,
                penalty_amount=penalty_amount,
                shariah_non_compliant=shariah_non_compliant,
            )
            facilities.append(facility)
            facility_idx += 1

    logger.info(
        "Synthetic portfolio: %d facilities, total gross=%.0f KD, NPL=%d (%.2f%%)",
        len(facilities),
        sum(f.gross_exposure for f in facilities),
        sum(1 for f in facilities if f.is_defaulted),
        sum(1 for f in facilities if f.is_defaulted) / max(len(facilities), 1) * 100,
    )

    return facilities
