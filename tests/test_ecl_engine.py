"""Tests for Shariah-Native ECL Enhancements.

Verifies the Warba Bank dual-prerogative ECL adjustments:
- Profit margin stripping from EAD for Murabaha/Ijara/Tawarruq
- Asset-based LGD for Ijara/Musharaka
- Shariah non-compliance Stage 2 SICR trigger
- Penalty (Gharamah) exclusion from EAD
"""

import pytest
from app.risk.ecl_engine import (
    Facility,
    _compute_ead,
    _compute_lgd,
    _determine_stage,
    compute_ecl,
    DEFAULT_CKB_PARAMS,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _base_facility(**overrides) -> Facility:
    """Create a minimal Stage-1 facility for unit tests."""
    defaults = dict(
        facility_id="TEST-001",
        client_id="CLIENT-001",
        facility_type="murabaha",
        gross_exposure=1_000_000,
        utilized_amount=800_000,
        unutilized_amount=200_000,
        pd_1yr=0.02,
        lgd=0.50,
        days_past_due=0,
        internal_rating="BBB",
        is_investment_grade=True,
        rating_at_origination="BBB",
        collateral_type="real_estate",
        collateral_value=500_000,
        seniority="senior",
        maturity_years=5.0,
        is_defaulted=False,
    )
    defaults.update(overrides)
    return Facility(**defaults)


# ---------------------------------------------------------------------------
# 1. Profit margin stripped from EAD for Murabaha
# ---------------------------------------------------------------------------

class TestProfitMarginStripping:
    """Verify profit_margin is stripped from EAD for Murabaha/Ijara/Tawarruq."""

    def test_murabaha_profit_margin_stripped(self):
        """Murabaha with profit_margin should have lower EAD than without."""
        f_no_margin = _base_facility(profit_margin=0.0)
        f_with_margin = _base_facility(profit_margin=100_000)

        ead_no, _ = _compute_ead(f_no_margin, DEFAULT_CKB_PARAMS)
        ead_yes, rules = _compute_ead(f_with_margin, DEFAULT_CKB_PARAMS)

        assert ead_yes < ead_no, "EAD should be lower when profit margin is stripped"
        assert any("profit_margin_stripped" in r for r in rules)

    def test_tawarruq_profit_margin_stripped(self):
        """Tawarruq with profit_margin should have lower EAD."""
        f = _base_facility(facility_type="tawarruq", profit_margin=80_000)
        ead, rules = _compute_ead(f, DEFAULT_CKB_PARAMS)
        # Gross = 1,000,000; adjusted = 920,000; EAD should reflect reduced base
        assert ead < 1_000_000
        assert any("profit_margin_stripped" in r for r in rules)

    def test_musharakah_no_profit_stripping(self):
        """Musharakah should NOT have profit margin stripped."""
        f = _base_facility(facility_type="musharakah", profit_margin=100_000)
        ead, rules = _compute_ead(f, DEFAULT_CKB_PARAMS)
        # Musharakah uses gross exposure directly — no stripping
        assert not any("profit_margin_stripped" in r for r in rules)

    def test_sukuk_no_profit_stripping(self):
        """Sukuk should NOT have profit margin stripped."""
        f = _base_facility(facility_type="sukuk", profit_margin=100_000)
        ead, rules = _compute_ead(f, DEFAULT_CKB_PARAMS)
        assert not any("profit_margin_stripped" in r for r in rules)


# ---------------------------------------------------------------------------
# 2. Asset-based LGD for Ijara
# ---------------------------------------------------------------------------

class TestAssetBasedLGD:
    """Verify asset-based LGD is used for Ijara/Musharaka with recovery rate."""

    def test_ijara_asset_based_lgd(self):
        """Ijara with asset_recovery_rate should use asset-based LGD."""
        f = _base_facility(
            facility_type="ijara",
            asset_recovery_rate=0.70,
            collateral_value=0,
        )
        lgd, rules, _ = _compute_lgd(f, 1, 1_000_000, DEFAULT_CKB_PARAMS)
        # Without collateral: effective_lgd = 1 - 0.70 = 0.30, but floor is 0.50
        assert lgd == 0.50  # CBK floor applies
        assert any("asset_based_lgd" in r for r in rules)

    def test_ijara_asset_based_lgd_with_collateral(self):
        """Ijara with recovery rate and collateral blends both benefits."""
        f = _base_facility(
            facility_type="ijara",
            asset_recovery_rate=0.70,
            collateral_value=500_000,
            collateral_type="real_estate",
            gross_exposure=1_000_000,
        )
        lgd, rules, _ = _compute_lgd(f, 1, 1_000_000, DEFAULT_CKB_PARAMS)
        assert any("asset_based_lgd" in r for r in rules)
        # LGD should be at least the senior floor
        assert lgd >= 0.50

    def test_musharakah_asset_based_lgd(self):
        """Musharakah with asset_recovery_rate should use asset-based LGD."""
        f = _base_facility(
            facility_type="musharakah",
            asset_recovery_rate=0.60,
            collateral_value=0,
        )
        lgd, rules, _ = _compute_lgd(f, 1, 1_000_000, DEFAULT_CKB_PARAMS)
        # Without collateral: effective_lgd = 1 - 0.60 = 0.40, floor is 0.50
        assert lgd == 0.50
        assert any("asset_based_lgd" in r for r in rules)

    def test_murabaha_no_asset_based_lgd(self):
        """Murabaha should NOT use asset-based LGD even with recovery rate."""
        f = _base_facility(
            facility_type="murabaha",
            asset_recovery_rate=0.70,
            collateral_value=0,
        )
        lgd, rules, _ = _compute_lgd(f, 1, 1_000_000, DEFAULT_CKB_PARAMS)
        assert not any("asset_based_lgd" in r for r in rules)


# ---------------------------------------------------------------------------
# 3. Shariah non-compliance triggers Stage 2
# ---------------------------------------------------------------------------

class TestShariahNonCompliantSICR:
    """Verify shariah_non_compliant triggers Stage 2 SICR."""

    def test_shariah_non_compliant_triggers_stage2(self):
        """A facility with shariah_non_compliant=True should be Stage 2."""
        f = _base_facility(shariah_non_compliant=True)
        stage, rules = _determine_stage(f, DEFAULT_CKB_PARAMS)
        assert stage == 2
        assert "stage2_shariah_non_compliant" in rules

    def test_shariah_non_compliant_precedence_over_dpd(self):
        """Shariah non-compliance should take precedence over DPD triggers."""
        f = _base_facility(shariah_non_compliant=True, days_past_due=10)
        stage, rules = _determine_stage(f, DEFAULT_CKB_PARAMS)
        assert stage == 2
        assert "stage2_shariah_non_compliant" in rules
        # Should NOT have DPD-based Stage 2 rule
        assert not any("dpd" in r for r in rules)

    def test_shariah_non_compliant_does_not_override_stage3(self):
        """Stage 3 (defaulted) should take precedence over Shariah non-compliance."""
        f = _base_facility(shariah_non_compliant=True, is_defaulted=True)
        stage, rules = _determine_stage(f, DEFAULT_CKB_PARAMS)
        assert stage == 3
        assert "stage3_defaulted" in rules

    def test_compliant_facility_stays_stage1(self):
        """A compliant facility with no SICR should remain Stage 1."""
        f = _base_facility(shariah_non_compliant=False)
        stage, rules = _determine_stage(f, DEFAULT_CKB_PARAMS)
        assert stage == 1
        assert "stage1_no_sicr" in rules


# ---------------------------------------------------------------------------
# 4. Penalty amount excluded from EAD
# ---------------------------------------------------------------------------

class TestPenaltyExclusion:
    """Verify penalty_amount (Gharamah) is excluded from EAD."""

    def test_penalty_excluded_from_ead(self):
        """Facility with penalty_amount should have lower EAD."""
        f_no_penalty = _base_facility(penalty_amount=0)
        f_with_penalty = _base_facility(penalty_amount=50_000)

        ead_no, _ = _compute_ead(f_no_penalty, DEFAULT_CKB_PARAMS)
        ead_yes, rules = _compute_ead(f_with_penalty, DEFAULT_CKB_PARAMS)

        assert ead_yes < ead_no
        assert "penalty_excluded_from_ead" in rules

    def test_penalty_combined_with_profit_margin(self):
        """Both profit margin and penalty should reduce EAD."""
        f = _base_facility(
            facility_type="murabaha",
            profit_margin=100_000,
            penalty_amount=50_000,
        )
        ead, rules = _compute_ead(f, DEFAULT_CKB_PARAMS)
        # Both adjustments should be recorded
        assert any("profit_margin_stripped" in r for r in rules)
        assert "penalty_excluded_from_ead" in rules
        # EAD should be less than gross
        assert ead < 1_000_000


# ---------------------------------------------------------------------------
# 5. Integration: full portfolio ECL with Shariah adjustments
# ---------------------------------------------------------------------------

class TestShariahECLIntegration:
    """Verify the full ECL computation works with Shariah-native fields."""

    def test_portfolio_with_shariah_facilities(self):
        """A mixed portfolio should compute ECL correctly with Shariah adjustments."""
        portfolio = [
            _base_facility(
                facility_id="MUR-001",
                facility_type="murabaha",
                profit_margin=100_000,
            ),
            _base_facility(
                facility_id="IJR-001",
                facility_type="ijara",
                asset_recovery_rate=0.70,
            ),
            _base_facility(
                facility_id="SHNC-001",
                facility_type="murabaha",
                shariah_non_compliant=True,
            ),
            _base_facility(
                facility_id="PEN-001",
                facility_type="tawarruq",
                penalty_amount=20_000,
            ),
        ]
        result = compute_ecl(portfolio)
        assert result.total_ecl > 0
        assert result.total_ecl > 0
        # Verify stages are assigned correctly
        stages = {f.facility_id: f.stage for f in
                  [fac for stage_list in [result.stage_breakdown] for fac in []]
                  }  # Use breakdown instead
        stage2_count = result.stage_breakdown[1]["facility_count"]  # Stage 2
        assert stage2_count >= 1  # At least the shariah_non_compliant one
