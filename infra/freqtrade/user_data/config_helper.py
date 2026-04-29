"""Standalone configuration helper for environments without access to config_center_service.

This module provides a minimal get_config() implementation that works with:
- Environment variables (highest priority)
- Default values from CONFIG_DEFAULTS

Used by:
- Freqtrade strategy (runs in separate container, cannot import API services)
- Other standalone components

For services running in API container, use config_center_service.get_config() instead.

NOTE: CONFIG_DEFAULTS in this file is a subset of the full defaults defined in
services/api/app/services/config_center_service.py. Both files define defaults for
strategy-related configs. When adding or modifying defaults, ensure both files are
updated to maintain consistency. The config_center_service.py version is the canonical
source and includes additional defaults for network, VPN, risk, alerts, etc.
"""

from __future__ import annotations

import os
from decimal import Decimal, InvalidOperation
from typing import Any

# Default values for strategy configuration
CONFIG_DEFAULTS: dict[str, str | int | float | Decimal] = {
    # Strategy parameters
    "QUANT_STRATEGY_MIN_ENTRY_SCORE": Decimal("0.60"),
    "QUANT_STRATEGY_TRAILING_STOP_TRIGGER": Decimal("0.02"),
    "QUANT_STRATEGY_TRAILING_STOP_DISTANCE": Decimal("0.01"),
    "QUANT_STRATEGY_PROFIT_EXIT_RATIO": Decimal("0.05"),
    "QUANT_STRATEGY_MAX_HOLDING_HOURS": 48,
    "QUANT_STRATEGY_BASE_POSITION_RATIO": Decimal("0.25"),
    "QUANT_STRATEGY_MAX_POSITION_RATIO": Decimal("0.50"),
    "QUANT_STRATEGY_VOLATILITY_SCALE_FACTOR": Decimal("0.5"),
    # Technical indicators
    "QUANT_RSI_PERIOD": 14,
    "QUANT_RSI_OVERBUY_THRESHOLD": Decimal("70"),
    "QUANT_RSI_OVERSELL_THRESHOLD": Decimal("30"),
    "QUANT_MACD_FAST_PERIOD": 12,
    "QUANT_MACD_SLOW_PERIOD": 26,
    "QUANT_MACD_SIGNAL_PERIOD": 9,
    "QUANT_EMA_FAST_PERIOD": 20,
    "QUANT_EMA_SLOW_PERIOD": 55,
    "QUANT_VOLUME_TREND_PERIOD": 20,
    # Analytics
    "QUANT_ANALYTICS_HISTORY_DAYS": 30,
}


def get_config(
    key: str,
    default: str | int | float | Decimal | None = None,
    *,
    as_type: str = "str",
) -> str | int | float | Decimal | bool | None:
    """Read configuration value with type conversion.

    Priority order:
    1. Environment variable os.environ (highest priority)
    2. CONFIG_DEFAULTS
    3. Passed default parameter

    Args:
        key: Configuration key name (e.g. QUANT_STRATEGY_MIN_ENTRY_SCORE)
        default: Fallback default value
        as_type: Return type ("str", "int", "float", "decimal", "bool", "list")

    Returns:
        Configuration value with requested type, or None if not found
    """
    # Priority 1: Environment variable
    raw_value = os.environ.get(key, "")

    # Priority 2: CONFIG_DEFAULTS
    if raw_value.strip() == "":
        default_value = CONFIG_DEFAULTS.get(key)
        if default_value is not None:
            raw_value = str(default_value)

    # Priority 3: Passed default
    if raw_value.strip() == "":
        if default is not None:
            raw_value = str(default)
        else:
            return None

    # Type conversion
    try:
        if as_type == "str":
            return raw_value.strip()
        elif as_type == "int":
            return int(raw_value.strip())
        elif as_type == "float":
            return float(raw_value.strip())
        elif as_type == "decimal":
            return Decimal(raw_value.strip())
        elif as_type == "bool":
            return raw_value.strip().lower() in ("true", "1", "yes", "on")
        elif as_type == "list":
            return [item.strip() for item in raw_value.split(",") if item.strip()]
        else:
            return raw_value.strip()
    except (ValueError, InvalidOperation):
        # Type conversion failed, return default or None
        if default is not None:
            return default
        return None