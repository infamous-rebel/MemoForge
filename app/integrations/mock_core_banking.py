"""Mock core-banking connector with realistic financial and facility data.

Used when INTEGRATION_MODE=mock. Returns deterministic financials
matching typical Kuwaiti corporate profiles.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List

from app.integrations.base import CoreBankingConnector, FacilityRecord, FinancialStatement

# ---- Financial statements by client ----
_FINANCIALS: Dict[str, List[FinancialStatement]] = {
    "CORP-001": [
        FinancialStatement(
            period_end=date(2024, 12, 31), period_type="annual", currency="KWD",
            total_assets=45_000_000, total_liabilities=22_500_000, total_equity=22_500_000,
            net_operating_income=5_800_000, net_income=3_200_000,
            current_assets=18_000_000, current_liabilities=9_000_000,
            total_debt_service=3_800_000, cash_and_equivalents=4_500_000,
            revenue=28_000_000, cost_of_goods_sold=18_200_000, operating_expenses=4_000_000,
        ),
        FinancialStatement(
            period_end=date(2023, 12, 31), period_type="annual", currency="KWD",
            total_assets=42_000_000, total_liabilities=21_000_000, total_equity=21_000_000,
            net_operating_income=5_400_000, net_income=2_900_000,
            current_assets=16_800_000, current_liabilities=8_400_000,
            total_debt_service=3_600_000, cash_and_equivalents=4_000_000,
            revenue=25_500_000, cost_of_goods_sold=16_600_000, operating_expenses=3_500_000,
        ),
        FinancialStatement(
            period_end=date(2022, 12, 31), period_type="annual", currency="KWD",
            total_assets=38_000_000, total_liabilities=19_000_000, total_equity=19_000_000,
            net_operating_income=4_800_000, net_income=2_500_000,
            current_assets=15_200_000, current_liabilities=7_600_000,
            total_debt_service=3_200_000, cash_and_equivalents=3_500_000,
            revenue=23_000_000, cost_of_goods_sold=15_000_000, operating_expenses=3_200_000,
        ),
    ],
    "CORP-002": [
        FinancialStatement(
            period_end=date(2024, 12, 31), period_type="annual", currency="KWD",
            total_assets=85_000_000, total_liabilities=34_000_000, total_equity=51_000_000,
            net_operating_income=12_000_000, net_income=7_500_000,
            current_assets=34_000_000, current_liabilities=17_000_000,
            total_debt_service=6_000_000, cash_and_equivalents=8_500_000,
            revenue=62_000_000, cost_of_goods_sold=38_000_000, operating_expenses=12_000_000,
        ),
    ],
}

# ---- Existing facilities by client ----
_FACILITIES: Dict[str, List[FacilityRecord]] = {
    "CORP-001": [
        FacilityRecord(
            facility_id="FAC-1001", facility_type="murabaha",
            original_amount=5_000_000, outstanding_balance=3_200_000,
            profit_rate=0.045, maturity_date=date(2026, 6, 30),
            origination_date=date(2023, 7, 1),
            collateral_type="Real Estate", collateral_value=7_500_000,
            days_past_due=0, stage=1,
        ),
        FacilityRecord(
            facility_id="FAC-1002", facility_type="ijara",
            original_amount=8_000_000, outstanding_balance=6_800_000,
            profit_rate=0.05, maturity_date=date(2028, 12, 31),
            origination_date=date(2022, 1, 1),
            collateral_type="Real Estate", collateral_value=12_000_000,
            days_past_due=0, stage=1,
        ),
    ],
    "CORP-002": [
        FacilityRecord(
            facility_id="FAC-2001", facility_type="musharakah",
            original_amount=15_000_000, outstanding_balance=10_000_000,
            profit_rate=0.055, maturity_date=date(2027, 3, 31),
            origination_date=date(2021, 4, 1),
            collateral_type="Industrial Equipment", collateral_value=20_000_000,
            days_past_due=0, stage=1,
        ),
    ],
}

# ---- Collateral records ----
_COLLATERAL: Dict[str, List[Dict[str, Any]]] = {
    "CORP-001": [
        {
            "collateral_id": "COL-5001",
            "type": "Real Estate",
            "description": "Commercial building, Sharq district, Kuwait City",
            "valued_amount": 7_500_000,
            "valuation_date": "2024-06-30",
            "valuator": "Kuwait International Appraisal Co.",
        },
        {
            "collateral_id": "COL-5002",
            "type": "Real Estate",
            "description": "Warehouse complex, Amghara industrial area",
            "valued_amount": 12_000_000,
            "valuation_date": "2024-03-15",
            "valuator": "Gulf Valuation Services",
        },
    ],
    "CORP-002": [
        {
            "collateral_id": "COL-6001",
            "type": "Industrial Equipment",
            "description": "Manufacturing plant and machinery",
            "valued_amount": 20_000_000,
            "valuation_date": "2024-09-01",
            "valuator": "Industrial Appraisal Bureau",
        },
    ],
}


def _default_financials(client_id: str) -> List[FinancialStatement]:
    """Generate default financials for unknown clients."""
    return [
        FinancialStatement(
            period_end=date(2024, 12, 31), period_type="annual", currency="KWD",
            total_assets=10_000_000, total_liabilities=5_000_000, total_equity=5_000_000,
            net_operating_income=2_500_000, net_income=1_200_000,
            current_assets=4_000_000, current_liabilities=2_000_000,
            total_debt_service=1_500_000, cash_and_equivalents=1_000_000,
            revenue=12_000_000, cost_of_goods_sold=7_800_000, operating_expenses=1_700_000,
        ),
    ]


class MockCoreBankingConnector(CoreBankingConnector):
    """Mock core-banking connector returning deterministic data."""

    def get_financial_statements(
        self, client_id: str, periods: int = 3
    ) -> List[FinancialStatement]:
        stmts = _FINANCIALS.get(client_id, _default_financials(client_id))
        return stmts[:periods]

    def get_existing_facilities(self, client_id: str) -> List[FacilityRecord]:
        return _FACILITIES.get(client_id, [])

    def get_collateral_records(self, client_id: str) -> List[Dict[str, Any]]:
        return _COLLATERAL.get(client_id, [])
