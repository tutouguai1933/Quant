"""Strategy template routes for multi-strategy management.

Provides API endpoints for:
- Listing available strategies
- Getting current strategy
- Switching strategy
- Getting/updating strategy configuration
"""

from __future__ import annotations

from typing import Any

from services.api.app.services.auth_service import auth_service
from services.api.app.services.strategy_service import strategy_service


try:
    from fastapi import APIRouter, Header
except ImportError:
    class APIRouter:  # pragma: no cover
        def __init__(self, *args, **kwargs) -> None:
            self.args = args
            self.kwargs = kwargs

        def get(self, *args, **kwargs):
            def decorator(func):
                return func
            return decorator

        def post(self, *args, **kwargs):
            def decorator(func):
                return func
            return decorator

    def Header(default=""):  # pragma: no cover
        return default


router = APIRouter(prefix="/api/v1/strategy", tags=["strategy"])


def _success(data: dict[str, Any], meta: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"data": data, "error": None, "meta": meta or {}}


def _unauthorized() -> dict[str, Any]:
    return {
        "data": None,
        "error": {"code": "unauthorized", "message": "需要登录才能访问"},
        "meta": {"source": "auth-service"},
    }


def _error(code: str, message: str, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "data": None,
        "error": {"code": code, "message": message},
        "meta": meta or {},
    }


@router.get("/list")
def list_strategies(token: str = "", authorization: str = Header("")) -> dict[str, Any]:
    """Get list of available strategies.

    Returns all registered strategies with their configuration schemas.
    """
    try:
        auth_service.require_control_plane_access(
            auth_service.resolve_access_token(token, authorization)
        )
    except PermissionError:
        return _unauthorized()

    strategies = strategy_service.list_strategies()

    return _success(
        {"strategies": strategies, "total": len(strategies)},
        {
            "source": "strategy-service",
            "current_strategy": strategy_service._current_strategy_name,
        },
    )


@router.get("/current")
def get_current_strategy(token: str = "", authorization: str = Header("")) -> dict[str, Any]:
    """Get current active strategy info.

    Returns the currently selected strategy with its full configuration.
    """
    try:
        auth_service.require_control_plane_access(
            auth_service.resolve_access_token(token, authorization)
        )
    except PermissionError:
        return _unauthorized()

    current = strategy_service.get_current_strategy()

    return _success(
        current,
        {
            "source": "strategy-service",
            "strategy_name": current.get("name", "unknown"),
        },
    )


@router.post("/switch")
def switch_strategy(
    strategy_name: str = "",
    token: str = "",
    authorization: str = Header(""),
) -> dict[str, Any]:
    """Switch to a different strategy.

    Args:
        strategy_name: Name of strategy to activate

    Returns switch result with Freqtrade notification status.
    """
    try:
        auth_service.require_control_plane_access(
            auth_service.resolve_access_token(token, authorization)
        )
    except PermissionError:
        return _unauthorized()

    if not strategy_name or not strategy_name.strip():
        return _error("invalid_request", "strategy_name 参数必须提供")

    result = strategy_service.switch_strategy(strategy_name.strip())

    if not result.get("success"):
        return _error(
            result.get("error", "switch_failed"),
            result.get("message", "策略切换失败"),
            {"available_strategies": result.get("available_strategies", [])},
        )

    return _success(
        result,
        {
            "source": "strategy-service",
            "action": "switch_strategy",
        },
    )


@router.get("/config")
def get_strategy_config(
    strategy_name: str = "",
    token: str = "",
    authorization: str = Header(""),
) -> dict[str, Any]:
    """Get configuration for a strategy.

    Args:
        strategy_name: Strategy name (optional, defaults to current)

    Returns configuration values and schema.
    """
    try:
        auth_service.require_control_plane_access(
            auth_service.resolve_access_token(token, authorization)
        )
    except PermissionError:
        return _unauthorized()

    name = strategy_name.strip() if strategy_name and strategy_name.strip() else None
    config = strategy_service.get_strategy_config(name)

    if config.get("error") == "strategy_not_found":
        return _error("strategy_not_found", f"策略 '{config.get('strategy_name')}' 未注册")

    return _success(
        config,
        {
            "source": "strategy-service",
            "strategy_name": config.get("strategy_name", "unknown"),
        },
    )


@router.post("/config")
def update_strategy_config(
    strategy_name: str = "",
    config: dict[str, Any] = None,
    token: str = "",
    authorization: str = Header(""),
) -> dict[str, Any]:
    """Update configuration for a strategy.

    Args:
        strategy_name: Strategy name (optional, defaults to current)
        config: New configuration values

    Returns updated configuration with validation result.
    """
    try:
        auth_service.require_control_plane_access(
            auth_service.resolve_access_token(token, authorization)
        )
    except PermissionError:
        return _unauthorized()

    if config is None:
        config = {}

    name = strategy_name.strip() if strategy_name and strategy_name.strip() else None
    result = strategy_service.update_strategy_config(name, config)

    if not result.get("success"):
        return _error(
            result.get("error", "update_failed"),
            result.get("message", "配置更新失败"),
            {"validation_errors": result.get("validation_errors", [])},
        )

    return _success(
        result,
        {
            "source": "strategy-service",
            "action": "update_config",
            "strategy_name": result.get("strategy_name", "unknown"),
        },
    )


@router.post("/analyze")
def analyze_with_strategy(
    strategy_name: str = "",
    data: dict[str, Any] = None,
    token: str = "",
    authorization: str = Header(""),
) -> dict[str, Any]:
    """Run analysis with a strategy.

    Args:
        strategy_name: Strategy name (optional, defaults to current)
        data: Market data including candles, symbol, timeframe

    Returns analysis result with signal and indicators.
    """
    try:
        auth_service.require_control_plane_access(
            auth_service.resolve_access_token(token, authorization)
        )
    except PermissionError:
        return _unauthorized()

    if data is None:
        data = {}

    name = strategy_name.strip() if strategy_name and strategy_name.strip() else None

    if name:
        result = strategy_service.analyze_with_strategy(name, data)
    else:
        result = strategy_service.analyze_with_current_strategy(data)

    if result.get("error"):
        return _error(
            result.get("error", "analysis_failed"),
            f"策略分析失败: {result.get('error')}",
            {"strategy_name": result.get("strategy_name", "unknown")},
        )

    return _success(
        result,
        {
            "source": "strategy-service",
            "strategy_name": name or strategy_service._current_strategy_name,
            "action": "analyze",
        },
    )