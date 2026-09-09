"""Connector factory — returns the correct connector based on configuration.

When settings.integration_mode == "mock", returns mock connectors.
When settings.integration_mode == "real", returns real connectors
(requires credentials to be configured).
"""

from __future__ import annotations

import logging
from typing import Optional

from app.core.config import get_settings
from app.integrations.base import (
    CoreBankingConnector,
    CRMConnector,
    MarketDataConnector,
)

logger = logging.getLogger(__name__)

# Caches for singleton connectors
_crm: Optional[CRMConnector] = None
_core_banking: Optional[CoreBankingConnector] = None
_market_data: Optional[MarketDataConnector] = None


def get_crm_connector() -> CRMConnector:
    """Return the configured CRM connector."""
    global _crm
    if _crm is not None:
        return _crm

    settings = get_settings()
    mode = settings.integration_mode.lower()

    if mode == "mock":
        from app.integrations.mock_crm import MockCRMConnector
        _crm = MockCRMConnector()
        logger.info("Using MockCRMConnector (integration_mode=mock)")
        return _crm

    if mode == "real":
        raise NotImplementedError(
            "Real CRM connector not yet implemented. "
            "Set INTEGRATION_MODE=mock or implement a CRMConnector subclass "
            "for your bank's CRM system (e.g., Temenos T24, Finastra)."
        )

    raise ValueError(
        f"Unknown integration_mode '{mode}'. Expected 'mock' or 'real'."
    )


def get_core_banking_connector() -> CoreBankingConnector:
    """Return the configured core-banking connector."""
    global _core_banking
    if _core_banking is not None:
        return _core_banking

    settings = get_settings()
    mode = settings.integration_mode.lower()

    if mode == "mock":
        from app.integrations.mock_core_banking import MockCoreBankingConnector
        _core_banking = MockCoreBankingConnector()
        logger.info("Using MockCoreBankingConnector (integration_mode=mock)")
        return _core_banking

    if mode == "real":
        raise NotImplementedError(
            "Real core-banking connector not yet implemented. "
            "Set INTEGRATION_MODE=mock or implement a CoreBankingConnector subclass "
            "for your bank's core system (e.g., Temenos T24, Oracle FLEXCUBE)."
        )

    raise ValueError(
        f"Unknown integration_mode '{mode}'. Expected 'mock' or 'real'."
    )


def get_market_data_connector() -> MarketDataConnector:
    """Return the configured market-data connector."""
    global _market_data
    if _market_data is not None:
        return _market_data

    settings = get_settings()
    mode = settings.integration_mode.lower()

    if mode == "mock":
        from app.integrations.mock_market_data import MockMarketDataConnector
        _market_data = MockMarketDataConnector()
        logger.info("Using MockMarketDataConnector (integration_mode=mock)")
        return _market_data

    if mode == "real":
        raise NotImplementedError(
            "Real market-data connector not yet implemented. "
            "Set INTEGRATION_MODE=mock or implement a MarketDataConnector subclass "
            "for your market-data provider (e.g., Bloomberg, Refinitiv)."
        )

    raise ValueError(
        f"Unknown integration_mode '{mode}'. Expected 'mock' or 'real'."
    )


def reset_connectors() -> None:
    """Reset cached connectors (useful for testing)."""
    global _crm, _core_banking, _market_data
    _crm = None
    _core_banking = None
    _market_data = None
