"""Mock market-data connector with realistic CBK / Kuwait market data.

Used when INTEGRATION_MODE=mock. Returns deterministic market
benchmarks aligned with CBK published rates.
"""

from __future__ import annotations

from datetime import date
from typing import Dict, List, Optional

from app.integrations.base import MarketDataConnector, MarketDataPoint


class MockMarketDataConnector(MarketDataConnector):
    """Mock market-data connector with realistic Kuwait macro data."""

    def get_sector_benchmarks(
        self, sector: str
    ) -> Dict[str, MarketDataPoint]:
        """Return sector-average financial ratios for benchmarking."""
        today = date(2025, 6, 30)
        benchmarks = {
            "Real Estate": {
                "avg_dscr": MarketDataPoint("avg_dscr", 1.35, today),
                "avg_leverage": MarketDataPoint("avg_leverage", 2.50, today),
                "avg_current_ratio": MarketDataPoint("avg_current_ratio", 1.60, today),
                "avg_roe": MarketDataPoint("avg_roe", 0.12, today),
                "avg_roa": MarketDataPoint("avg_roa", 0.04, today),
                "avg_net_margin": MarketDataPoint("avg_net_margin", 0.14, today),
            },
            "Industrial": {
                "avg_dscr": MarketDataPoint("avg_dscr", 1.80, today),
                "avg_leverage": MarketDataPoint("avg_leverage", 1.60, today),
                "avg_current_ratio": MarketDataPoint("avg_current_ratio", 2.00, today),
                "avg_roe": MarketDataPoint("avg_roe", 0.15, today),
                "avg_roa": MarketDataPoint("avg_roa", 0.07, today),
                "avg_net_margin": MarketDataPoint("avg_net_margin", 0.12, today),
            },
            "Construction": {
                "avg_dscr": MarketDataPoint("avg_dscr", 1.25, today),
                "avg_leverage": MarketDataPoint("avg_leverage", 3.00, today),
                "avg_current_ratio": MarketDataPoint("avg_current_ratio", 1.30, today),
                "avg_roe": MarketDataPoint("avg_roe", 0.10, today),
                "avg_roa": MarketDataPoint("avg_roa", 0.03, today),
                "avg_net_margin": MarketDataPoint("avg_net_margin", 0.08, today),
            },
            "Retail": {
                "avg_dscr": MarketDataPoint("avg_dscr", 1.50, today),
                "avg_leverage": MarketDataPoint("avg_leverage", 2.00, today),
                "avg_current_ratio": MarketDataPoint("avg_current_ratio", 1.80, today),
                "avg_roe": MarketDataPoint("avg_roe", 0.11, today),
                "avg_roa": MarketDataPoint("avg_roa", 0.05, today),
                "avg_net_margin": MarketDataPoint("avg_net_margin", 0.06, today),
            },
        }
        return benchmarks.get(sector, benchmarks["Real Estate"])

    def get_fx_rates(
        self, base: str = "KWD", symbols: Optional[List[str]] = None
    ) -> Dict[str, float]:
        """Return FX rates with KWD as base (approximate mid-market)."""
        rates = {
            "USD": 3.256,
            "EUR": 3.542,
            "GBP": 4.120,
            "SAR": 0.868,
            "AED": 0.886,
            "BHD": 8.640,
        }
        if symbols:
            return {s: rates.get(s, 1.0) for s in symbols}
        return rates

    def get_policy_rate(self) -> MarketDataPoint:
        """Return the CBK discount rate (as of mid-2025)."""
        return MarketDataPoint(
            symbol="CBK_DISCOUNT_RATE",
            value=0.04,
            as_of=date(2025, 1, 1),
            currency="KWD",
            extra={"source": "Central Bank of Kuwait"},
        )
