"""Business configuration loaded from config.json.

This module loads and validates the bank-specific configuration including
RBAC matrix, Shariah terminology rules, HITL rules, risk thresholds,
approval workflow stages, notification channels, and escalation rules.

Design decision: Config is loaded once from JSON and validated at startup
rather than scattered across modules. This makes the system auditable —
a compliance officer can inspect config.json to understand all rules.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config.json"
_config_cache: Optional[Dict[str, Any]] = None


def load_config(path: Optional[Path] = None) -> Dict[str, Any]:
    """Load and cache the business configuration from JSON file."""
    global _config_cache
    if _config_cache is not None and path is None:
        return _config_cache

    config_path = path or _CONFIG_PATH
    if not config_path.exists():
        raise FileNotFoundError(f"Business config not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    _validate_config(config)

    if path is None:
        _config_cache = config
    return config


def reload_config() -> Dict[str, Any]:
    """Force-reload the configuration from disk."""
    global _config_cache
    _config_cache = None
    return load_config()


def _validate_config(config: Dict[str, Any]) -> None:
    """Validate required config sections exist."""
    required_sections = [
        "rbac",
        "shariah_terminology",
        "hitl_rules",
        "risk_thresholds",
        "approval_workflow",
    ]
    missing = [s for s in required_sections if s not in config]
    if missing:
        raise ValueError(f"Config missing required sections: {missing}")

    # Validate RBAC roles
    required_roles = {"RM", "Risk", "CreditCommittee", "ShariahBoard", "Admin"}
    config_roles = set(config["rbac"].get("roles", []))
    if not required_roles.issubset(config_roles):
        missing_roles = required_roles - config_roles
        raise ValueError(f"Config missing required roles: {missing_roles}")

    # Validate approval workflow stages
    stages = config["approval_workflow"].get("stages", [])
    if "draft" not in stages:
        raise ValueError("Approval workflow must include 'draft' stage")

    logger.info("Business config validated successfully")


def get_rbac_config() -> Dict[str, Any]:
    """Return the RBAC configuration section."""
    return load_config()["rbac"]


def get_shariah_terminology(facility_type: str) -> Dict[str, List[str]]:
    """Return required and prohibited terms for a facility type.

    Args:
        facility_type: One of murabaha, ijara, musharakah, sukuk, tawarruq.

    Returns:
        Dict with 'required_terms' and 'prohibited_terms' lists.
    """
    config = load_config()
    terms = config["shariah_terminology"].get(facility_type.lower())
    if terms is None:
        raise ValueError(
            f"Unknown facility type '{facility_type}'. "
            f"Valid types: {list(config['shariah_terminology'].keys())}"
        )
    return terms


def get_hitl_rules() -> Dict[str, Any]:
    """Return the human-in-the-loop rules configuration."""
    return load_config()["hitl_rules"]


def get_risk_thresholds() -> Dict[str, float]:
    """Return the risk threshold configuration."""
    return load_config()["risk_thresholds"]


def get_approval_workflow() -> Dict[str, Any]:
    """Return the approval workflow configuration."""
    return load_config()["approval_workflow"]


def get_notification_channels() -> Dict[str, List[str]]:
    """Return the notification channel configuration."""
    return load_config()["notification_channels"]


def get_escalation_rules() -> Dict[str, Dict[str, str]]:
    """Return the escalation rules configuration."""
    return load_config()["escalation_rules"]


def get_data_validation_config() -> Dict[str, Any]:
    """Return the data validation configuration."""
    return load_config()["data_validation"]


def get_section_approval_roles(section_key: str) -> List[str]:
    """Return which roles can approve a given section type.

    Args:
        section_key: The memo section key (e.g., 'borrower_overview').

    Returns:
        List of role names authorized to approve this section.
    """
    matrix = get_rbac_config().get("section_approval_matrix", {})
    return matrix.get(section_key, ["Admin"])
