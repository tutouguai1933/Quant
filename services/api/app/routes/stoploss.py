"""动态止损配置和调整路由。"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from services.api.app.services.auth_service import auth_service
from services.api.app.services.dynamic_stoploss_service import dynamic_stoploss_service
from services.api.app.services.volatility_service import volatility_service


try:
    from fastapi import APIRouter, Header
except ImportError:
    class APIRouter:
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

    def Header(default=""):
        return default


router = APIRouter(prefix="/api/v1/stoploss", tags=["stoploss"])


def _success(data: dict[str, Any], meta: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"data": data, "error": None, "meta": meta or {}}


def _unauthorized() -> dict[str, Any]:
    return {
        "data": None,
        "error": {"code": "unauthorized", "message": "当前页面需要先登录"},
        "meta": {"source": "auth-service"},
    }


def _error(code: str, message: str) -> dict[str, Any]:
    return {
        "data": None,
        "error": {"code": code, "message": message},
        "meta": {},
    }


@router.get("/config")
def get_stoploss_config(token: str = "", authorization: str = Header("")) -> dict[str, Any]:
    """获取止损配置。"""
    try:
        auth_service.require_control_plane_access(
            auth_service.resolve_access_token(token, authorization)
        )
    except PermissionError:
        return _unauthorized()

    config = dynamic_stoploss_service.get_config()
    return _success(
        {"config": config},
        {"source": "dynamic-stoploss-service", "timestamp": datetime.now(timezone.utc).isoformat()},
    )


@router.post("/config")
def update_stoploss_config(
    updates: dict[str, Any],
    token: str = "",
    authorization: str = Header(""),
) -> dict[str, Any]:
    """更新止损配置。"""
    try:
        auth_service.require_control_plane_access(
            auth_service.resolve_access_token(token, authorization)
        )
    except PermissionError:
        return _unauthorized()

    try:
        updated_config = dynamic_stoploss_service.update_config(updates)
        return _success(
            {"config": updated_config, "updated": True},
            {"source": "dynamic-stoploss-service", "timestamp": datetime.now(timezone.utc).isoformat()},
        )
    except Exception as exc:
        return _error("config_update_failed", str(exc))


@router.post("/adjust")
def adjust_stoploss(
    payload: dict[str, Any],
    token: str = "",
    authorization: str = Header(""),
) -> dict[str, Any]:
    """手动调整止损。

    payload:
    - trade_id: 单个交易ID（可选）
    - force: 是否强制调整，忽略节流（可选，默认false）
    - all: 是否调整所有持仓（可选，默认false）
    """
    try:
        auth_service.require_control_plane_access(
            auth_service.resolve_access_token(token, authorization)
        )
    except PermissionError:
        return _unauthorized()

    trade_id = payload.get("trade_id")
    force = payload.get("force", False)
    adjust_all = payload.get("all", False)

    if adjust_all:
        results = dynamic_stoploss_service.adjust_all_positions(force=force)
        results_dict = [r.to_dict() for r in results]
        successful = [r for r in results if r.success]
        failed = [r for r in results if not r.success]

        return _success(
            {
                "results": results_dict,
                "summary": {
                    "total": len(results),
                    "successful": len(successful),
                    "failed": len(failed),
                },
            },
            {"source": "dynamic-stoploss-service", "adjust_all": True},
        )

    if not trade_id:
        return _error("missing_trade_id", "trade_id or all=true is required")

    result = dynamic_stoploss_service.adjust_trade_stoploss(str(trade_id), force=force)
    return _success(
        {"adjustment": result.to_dict()},
        {"source": "dynamic-stoploss-service", "trade_id": trade_id},
    )


@router.get("/positions")
def get_stoploss_positions(
    token: str = "",
    authorization: str = Header(""),
) -> dict[str, Any]:
    """获取所有持仓止损状态。"""
    try:
        auth_service.require_control_plane_access(
            auth_service.resolve_access_token(token, authorization)
        )
    except PermissionError:
        return _unauthorized()

    states = dynamic_stoploss_service.get_all_position_states()
    states_dict = [s.to_dict() for s in states]

    return _success(
        {"positions": states_dict, "count": len(states)},
        {"source": "dynamic-stoploss-service"},
    )


@router.get("/positions/{position_id}")
def get_stoploss_position(
    position_id: str,
    token: str = "",
    authorization: str = Header(""),
) -> dict[str, Any]:
    """获取单个持仓止损状态。"""
    try:
        auth_service.require_control_plane_access(
            auth_service.resolve_access_token(token, authorization)
        )
    except PermissionError:
        return _unauthorized()

    state = dynamic_stoploss_service.get_position_state(position_id)
    if not state:
        return _error("position_not_found", f"Position {position_id} not tracked")

    volatility = volatility_service.get_volatility(state.symbol)

    return _success(
        {
            "position": state.to_dict(),
            "volatility": volatility.to_dict(),
        },
        {"source": "dynamic-stoploss-service", "position_id": position_id},
    )


@router.post("/sync")
def sync_positions(
    token: str = "",
    authorization: str = Header(""),
) -> dict[str, Any]:
    """从Freqtrade同步持仓状态。"""
    try:
        auth_service.require_control_plane_access(
            auth_service.resolve_access_token(token, authorization)
        )
    except PermissionError:
        return _unauthorized()

    result = dynamic_stoploss_service.sync_with_freqtrade()
    return _success(
        {"sync": result},
        {"source": "dynamic-stoploss-service", "timestamp": datetime.now(timezone.utc).isoformat()},
    )


@router.get("/volatility/{symbol}")
def get_volatility(
    symbol: str,
    token: str = "",
    authorization: str = Header(""),
) -> dict[str, Any]:
    """获取指定币种波动率数据。"""
    try:
        auth_service.require_control_plane_access(
            auth_service.resolve_access_token(token, authorization)
        )
    except PermissionError:
        return _unauthorized()

    volatility = volatility_service.get_volatility(symbol)
    calculated_stoploss = dynamic_stoploss_service.calculate_stoploss(
        symbol,
        volatility.volatility_factor,
    )

    return _success(
        {
            "volatility": volatility.to_dict(),
            "calculated_stoploss": str(calculated_stoploss),
        },
        {"source": "volatility-service", "symbol": symbol.upper()},
    )


@router.post("/register")
def register_position(
    payload: dict[str, Any],
    token: str = "",
    authorization: str = Header(""),
) -> dict[str, Any]:
    """注册新持仓到止损监控。"""
    try:
        auth_service.require_control_plane_access(
            auth_service.resolve_access_token(token, authorization)
        )
    except PermissionError:
        return _unauthorized()

    symbol = payload.get("symbol")
    position_id = payload.get("position_id")
    entry_price = payload.get("entry_price")
    current_price = payload.get("current_price", entry_price)
    initial_stoploss = payload.get("initial_stoploss")

    if not symbol or not position_id or not entry_price:
        return _error("missing_required_fields", "symbol, position_id, entry_price are required")

    try:
        state = dynamic_stoploss_service.register_position(
            symbol=str(symbol),
            position_id=str(position_id),
            entry_price=Decimal(str(entry_price)),
            current_price=Decimal(str(current_price)),
            initial_stoploss=Decimal(str(initial_stoploss)) if initial_stoploss else None,
        )
        return _success(
            {"position": state.to_dict(), "registered": True},
            {"source": "dynamic-stoploss-service"},
        )
    except Exception as exc:
        return _error("register_failed", str(exc))


@router.delete("/positions/{position_id}")
def unregister_position(
    position_id: str,
    token: str = "",
    authorization: str = Header(""),
) -> dict[str, Any]:
    """移除持仓止损监控。"""
    try:
        auth_service.require_control_plane_access(
            auth_service.resolve_access_token(token, authorization)
        )
    except PermissionError:
        return _unauthorized()

    removed = dynamic_stoploss_service.unregister_position(position_id)
    return _success(
        {"position_id": position_id, "removed": removed},
        {"source": "dynamic-stoploss-service"},
    )