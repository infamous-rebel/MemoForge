"""Abstract base classes for bank data-source connectors.

Each connector defines a typed interface that real bank integrations must implement.
Mock connectors satisfy the same interface for development and testing.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Shared data transfer objects
# ---------------------------------------------------------------------------

@dataclass
class ClientProfile:
    """Core client information from CRM."""
    client_id: str
    legal_name: str
    trade_name: str = ""
    client_type: str = "corporate"          # corporate | sme | retail
    sector: str = ""
    sub_sector: str = ""
    country: str = "KW"
    risk_rating: str = ""
    relationship_start_date: Optional[date] = None
    rm_name: str = ""
    rm_email: str = ""
    group_name: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FinancialStatement:
    """Annual / quarterly financials from core banking."""
    period_end: date
    period_type: str = "annual"             # annual | quarterly
    currency: str = "KWD"
    total_assets: float = 0.0
    total_liabilities: float = 0.0
    total_equity: float = 0.0
    net_operating_income: float = 0.0
    net_income: float = 0.0
    current_assets: float = 0.0
    current_liabilities: float = 0.0
    total_debt_service: float = 0.0
    cash_and_equivalents: float = 0.0
    revenue: float = 0.0
    cost_of_goods_sold: float = 0.0
    operating_expenses: float = 0.0
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FacilityRecord:
    """Existing facility / exposure record from core banking."""
    facility_id: str
    facility_type: str                      # murabaha | ijara | musharakah | …
    original_amount: float = 0.0
    outstanding_balance: float = 0.0
    currency: str = "KWD"
    profit_rate: float = 0.0
    maturity_date: Optional[date] = None
    origination_date: Optional[date] = None
    collateral_type: str = ""
    collateral_value: float = 0.0
    days_past_due: int = 0
    stage: int = 1                          # IFRS 9 stage
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MarketDataPoint:
    """Single market-data observation."""
    symbol: str
    value: float
    as_of: date
    currency: str = "KWD"
    extra: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Abstract connector interfaces
# ---------------------------------------------------------------------------

class CRMConnector(ABC):
    """Interface for CRM (Customer Relationship Management) data."""

    @abstractmethod
    def get_client_profile(self, client_id: str) -> ClientProfile:
        """Retrieve the client profile by ID."""

    @abstractmethod
    def search_clients(self, query: str, limit: int = 20) -> List[ClientProfile]:
        """Search for clients by name or ID."""


class CoreBankingConnector(ABC):
    """Interface for core banking / loan-management data."""

    @abstractmethod
    def get_financial_statements(
        self, client_id: str, periods: int = 3
    ) -> List[FinancialStatement]:
        """Retrieve the most recent financial statements."""

    @abstractmethod
    def get_existing_facilities(
        self, client_id: str
    ) -> List[FacilityRecord]:
        """Retrieve existing facilities / exposures for a client."""

    @abstractmethod
    def get_collateral_records(
        self, client_id: str
    ) -> List[Dict[str, Any]]:
        """Retrieve collateral records pledged by the client."""


class MarketDataConnector(ABC):
    """Interface for market / macro-economic data."""

    @abstractmethod
    def get_sector_benchmarks(
        self, sector: str
    ) -> Dict[str, MarketDataPoint]:
        """Retrieve sector-level benchmark ratios."""

    @abstractmethod
    def get_fx_rates(
        self, base: str = "KWD", symbols: Optional[List[str]] = None
    ) -> Dict[str, float]:
        """Retrieve FX rates with KWD as base."""

    @abstractmethod
    def get_policy_rate(self) -> MarketDataPoint:
        """Retrieve the current CBK discount / policy rate."""
