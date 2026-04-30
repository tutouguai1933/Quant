"""Strategy base class for multi-strategy template framework.

All concrete strategies must inherit from this base class and implement
the analyze() and get_config_schema() methods.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class StrategySignal:
    """Represents a trading signal from a strategy."""

    action: str  # "buy", "sell", "hold"
    strength: float  # 0.0 to 1.0
    reason: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "strength": self.strength,
            "reason": self.reason,
            "metadata": self.metadata,
        }


@dataclass
class StrategyResult:
    """Represents the result of a strategy analysis."""

    signal: StrategySignal
    indicators: dict[str, Any] = field(default_factory=dict)
    timestamp: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "signal": self.signal.to_dict(),
            "indicators": self.indicators,
            "timestamp": self.timestamp,
        }


class StrategyBase(ABC):
    """Abstract base class for all trading strategies.

    Subclasses must implement:
    - analyze(): Process market data and return trading signals
    - get_config_schema(): Return the configuration schema for the strategy
    """

    name: str = "base"
    display_name: str = "基础策略"
    description: str = "策略基类"

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or self.get_default_config()

    @abstractmethod
    def analyze(self, data: dict[str, Any]) -> StrategyResult:
        """Analyze market data and return a trading signal.

        Args:
            data: Market data including candles, indicators, etc.
                Expected keys:
                - "candles": List of OHLCV candles
                - "symbol": Trading symbol
                - "timeframe": Timeframe string

        Returns:
            StrategyResult with signal and computed indicators
        """
        raise NotImplementedError

    @abstractmethod
    def get_config_schema(self) -> dict[str, Any]:
        """Return the configuration schema for this strategy.

        Schema format:
        {
            "parameters": {
                "param_name": {
                    "type": "number|string|boolean|array",
                    "default": default_value,
                    "min": minimum (for numbers),
                    "max": maximum (for numbers),
                    "options": [...] (for select type),
                    "description": "Parameter description",
                }
            }
        }
        """
        raise NotImplementedError

    def get_default_config(self) -> dict[str, Any]:
        """Extract default values from config schema."""
        schema = self.get_config_schema()
        defaults: dict[str, Any] = {}
        for param_name, param_config in schema.get("parameters", {}).items():
            if "default" in param_config:
                defaults[param_name] = param_config["default"]
        return defaults

    def validate_config(self, config: dict[str, Any]) -> tuple[bool, str]:
        """Validate configuration against schema.

        Returns:
            Tuple of (is_valid, error_message)
        """
        schema = self.get_config_schema()
        parameters = schema.get("parameters", {})

        for param_name, param_config in parameters.items():
            if param_name not in config:
                if "default" in param_config:
                    continue
                return False, f"Missing required parameter: {param_name}"

            value = config[param_name]
            expected_type = param_config.get("type", "any")

            if expected_type == "number":
                if not isinstance(value, (int, float)):
                    return False, f"Parameter {param_name} must be a number"
                if "min" in param_config and value < param_config["min"]:
                    return False, f"Parameter {param_name} must be >= {param_config['min']}"
                if "max" in param_config and value > param_config["max"]:
                    return False, f"Parameter {param_name} must be <= {param_config['max']}"

            elif expected_type == "string":
                if not isinstance(value, str):
                    return False, f"Parameter {param_name} must be a string"

            elif expected_type == "boolean":
                if not isinstance(value, bool):
                    return False, f"Parameter {param_name} must be a boolean"

            elif expected_type == "array":
                if not isinstance(value, list):
                    return False, f"Parameter {param_name} must be an array"

        return True, ""

    def update_config(self, config: dict[str, Any]) -> bool:
        """Update strategy configuration.

        Returns:
            True if config was valid and updated, False otherwise
        """
        is_valid, error = self.validate_config(config)
        if not is_valid:
            return False
        self.config = config
        return True

    def to_dict(self) -> dict[str, Any]:
        """Serialize strategy info for API responses."""
        return {
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "config": self.config,
            "config_schema": self.get_config_schema(),
        }