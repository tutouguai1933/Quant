"""Strategy management service for multi-strategy template framework.

Handles strategy registration, switching, configuration persistence,
and notification to Freqtrade.
"""

from __future__ import annotations

import json
import logging
import os
from copy import deepcopy
from datetime import datetime
from typing import Any

from services.api.app.services.strategy.base import StrategyBase
from services.api.app.services.strategy.trend import TrendStrategy
from services.api.app.services.strategy.grid import GridStrategy


logger = logging.getLogger(__name__)

DEFAULT_STRATEGY_CONFIG_PATH = ".runtime/strategy_config.json"


class StrategyService:
    """Service for managing trading strategies.

    Features:
    - Register and list available strategies
    - Switch active strategy
    - Load/save configuration to file
    - Notify Freqtrade on strategy change
    """

    def __init__(self, config_path: str | None = None) -> None:
        self._config_path = config_path or os.getenv(
            "QUANT_STRATEGY_CONFIG_PATH",
            DEFAULT_STRATEGY_CONFIG_PATH,
        )
        self._strategies: dict[str, StrategyBase] = {}
        self._current_strategy_name: str = "trend"
        self._strategy_order: list[str] = ["trend", "grid"]

        # Register default strategies
        self._register_default_strategies()

        # Load persisted configuration
        self._load_config()

    def _register_default_strategies(self) -> None:
        """Register built-in strategies."""
        self._strategies["trend"] = TrendStrategy()
        self._strategies["grid"] = GridStrategy()

    def _load_config(self) -> None:
        """Load strategy configuration from file."""
        try:
            if os.path.exists(self._config_path):
                with open(self._config_path, "r", encoding="utf-8") as f:
                    config_data = json.load(f)

                # Load current strategy
                current = config_data.get("current_strategy", "trend")
                if current in self._strategies:
                    self._current_strategy_name = current

                # Load individual strategy configs
                strategy_configs = config_data.get("strategy_configs", {})
                for strategy_name, strategy_config in strategy_configs.items():
                    if strategy_name in self._strategies:
                        self._strategies[strategy_name].update_config(strategy_config)

                logger.info("Loaded strategy config from %s", self._config_path)

        except Exception as exc:
            logger.warning("Failed to load strategy config: %s", exc)

    def _save_config(self) -> bool:
        """Save strategy configuration to file."""
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self._config_path) or ".", exist_ok=True)

            config_data = {
                "current_strategy": self._current_strategy_name,
                "strategy_configs": {
                    name: strategy.config
                    for name, strategy in self._strategies.items()
                },
                "updated_at": datetime.utcnow().isoformat(),
            }

            with open(self._config_path, "w", encoding="utf-8") as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)

            logger.info("Saved strategy config to %s", self._config_path)
            return True

        except Exception as exc:
            logger.error("Failed to save strategy config: %s", exc)
            return False

    def _notify_freqtrade(self, strategy_name: str) -> dict[str, Any]:
        """Notify Freqtrade of strategy change.

        In production, this would send a reload signal to Freqtrade
        to apply the new strategy configuration.
        """
        try:
            from services.api.app.adapters.freqtrade.client import freqtrade_client

            # Try to get Freqtrade runtime snapshot to check availability
            strategy = self._strategies.get(strategy_name)
            if strategy:
                logger.info("Notifying Freqtrade of strategy change: %s", strategy_name)

                # Check Freqtrade availability via runtime snapshot
                snapshot = freqtrade_client.get_runtime_snapshot()
                backend = snapshot.get("backend", "memory")

                if backend == "rest":
                    # Real Freqtrade backend - log strategy config change
                    # In production, this would trigger Freqtrade config reload
                    logger.info(
                        "Freqtrade REST backend available - strategy %s config change recorded",
                        strategy_name,
                    )
                    return {
                        "notified": True,
                        "freqtrade_backend": backend,
                        "strategy_config": strategy.config,
                    }

                return {"notified": False, "reason": "freqtrade_memory_backend", "backend": backend}

            return {"notified": False, "reason": "strategy_not_found"}

        except Exception as exc:
            logger.warning("Failed to notify Freqtrade: %s", exc)
            return {"notified": False, "reason": str(exc)}

    def list_strategies(self) -> list[dict[str, Any]]:
        """Return list of available strategies with their info."""
        result = []
        for name in self._strategy_order:
            if name in self._strategies:
                strategy = self._strategies[name]
                info = strategy.to_dict()
                info["is_current"] = name == self._current_strategy_name
                result.append(info)

        return result

    def get_current_strategy(self) -> dict[str, Any]:
        """Return current active strategy info."""
        strategy = self._strategies.get(self._current_strategy_name)
        if strategy:
            info = strategy.to_dict()
            info["is_current"] = True
            return info

        return {
            "name": self._current_strategy_name,
            "error": "strategy_not_found",
        }

    def switch_strategy(self, strategy_name: str) -> dict[str, Any]:
        """Switch to a different strategy.

        Args:
            strategy_name: Name of strategy to activate

        Returns:
            Result dict with success status and notification info
        """
        if strategy_name not in self._strategies:
            return {
                "success": False,
                "error": "strategy_not_found",
                "message": f"Strategy '{strategy_name}' not registered",
                "available_strategies": list(self._strategies.keys()),
            }

        old_strategy = self._current_strategy_name
        self._current_strategy_name = strategy_name

        # Save configuration
        saved = self._save_config()

        # Notify Freqtrade
        notification = self._notify_freqtrade(strategy_name)

        logger.info("Switched strategy from %s to %s", old_strategy, strategy_name)

        return {
            "success": True,
            "previous_strategy": old_strategy,
            "current_strategy": strategy_name,
            "config_saved": saved,
            "freqtrade_notification": notification,
            "timestamp": datetime.utcnow().isoformat(),
        }

    def get_strategy_config(self, strategy_name: str | None = None) -> dict[str, Any]:
        """Get configuration for a specific strategy.

        Args:
            strategy_name: Strategy name, or None for current strategy

        Returns:
            Strategy configuration with schema
        """
        name = strategy_name or self._current_strategy_name
        strategy = self._strategies.get(name)

        if not strategy:
            return {
                "strategy_name": name,
                "error": "strategy_not_found",
                "config": {},
                "schema": {},
            }

        return {
            "strategy_name": name,
            "config": deepcopy(strategy.config),
            "schema": strategy.get_config_schema(),
            "is_current": name == self._current_strategy_name,
        }

    def update_strategy_config(
        self,
        strategy_name: str | None,
        config: dict[str, Any],
    ) -> dict[str, Any]:
        """Update configuration for a strategy.

        Args:
            strategy_name: Strategy name, or None for current strategy
            config: New configuration values

        Returns:
            Result dict with success status
        """
        name = strategy_name or self._current_strategy_name
        strategy = self._strategies.get(name)

        if not strategy:
            return {
                "success": False,
                "error": "strategy_not_found",
                "message": f"Strategy '{name}' not registered",
            }

        # Validate and update config
        is_valid, error_message = strategy.validate_config(config)
        if not is_valid:
            return {
                "success": False,
                "error": "invalid_config",
                "message": error_message,
                "validation_errors": [error_message],
            }

        updated = strategy.update_config(config)
        if not updated:
            return {
                "success": False,
                "error": "update_failed",
                "message": "Configuration update failed",
            }

        # Save to file
        saved = self._save_config()

        # Notify Freqtrade if this is current strategy
        notification = {}
        if name == self._current_strategy_name:
            notification = self._notify_freqtrade(name)

        return {
            "success": True,
            "strategy_name": name,
            "config": deepcopy(strategy.config),
            "config_saved": saved,
            "freqtrade_notification": notification,
        }

    def analyze_with_current_strategy(self, data: dict[str, Any]) -> dict[str, Any]:
        """Run analysis with current strategy.

        Args:
            data: Market data for analysis

        Returns:
            Analysis result from current strategy
        """
        strategy = self._strategies.get(self._current_strategy_name)
        if not strategy:
            return {
                "error": "no_current_strategy",
                "strategy_name": self._current_strategy_name,
            }

        result = strategy.analyze(data)
        return result.to_dict()

    def analyze_with_strategy(
        self,
        strategy_name: str,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """Run analysis with a specific strategy.

        Args:
            strategy_name: Strategy to use for analysis
            data: Market data for analysis

        Returns:
            Analysis result from specified strategy
        """
        strategy = self._strategies.get(strategy_name)
        if not strategy:
            return {
                "error": "strategy_not_found",
                "strategy_name": strategy_name,
            }

        result = strategy.analyze(data)
        return result.to_dict()

    def register_strategy(self, strategy: StrategyBase) -> bool:
        """Register a new strategy.

        Args:
            strategy: Strategy instance to register

        Returns:
            True if registration successful
        """
        name = strategy.name
        if name in self._strategies:
            logger.warning("Strategy %s already registered, replacing", name)

        self._strategies[name] = strategy
        if name not in self._strategy_order:
            self._strategy_order.append(name)

        logger.info("Registered strategy: %s", name)
        return True

    def get_available_strategy_names(self) -> list[str]:
        """Return list of registered strategy names."""
        return list(self._strategies.keys())


# Global singleton instance
strategy_service = StrategyService()