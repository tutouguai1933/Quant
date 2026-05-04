"""交易日志API路由。

提供以下接口:
- POST /api/v1/trade-log - 记录交易日志
- GET /api/v1/trade-log/history - 查询历史记录
- GET /api/v1/trade-log/{trade_id} - 获取单条记录
- GET /api/v1/trade-log/statistics - 获取统计数据
- GET /api/v1/trade-log/open-positions - 获取未平仓交易
- PUT /api/v1/trade-log/{trade_id} - 更新交易日志（平仓）
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from services.api.app.services.trade_log_service import trade_log_service, StopLossReason
from services.api.app.services.auth_service import auth_service


try:
    from fastapi import APIRouter, Header
except ImportError:
    class APIRouter:  # pragma: no cover - lightweight local fallback
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

        def put(self, *args, **kwargs):
            def decorator(func):
                return func
            return decorator

    def Header(default: str = "") -> str:  # pragma: no cover - fallback stub
        return default


router = APIRouter(prefix="/api/v1/trade-log", tags=["trade-log"])


def _success(data: dict, meta: dict | None = None) -> dict:
    return {"data": data, "error": None, "meta": meta or {}}


def _error(code: str, message: str, meta: dict | None = None) -> dict:
    return {"data": None, "error": {"code": code, "message": message}, "meta": meta or {}}


def _unauthorized() -> dict:
    return _error("unauthorized", "authentication required", {"source": "control-plane-api"})


def _build_meta(action: str, **kwargs: object) -> dict[str, object]:
    """构建统一的元数据结构。"""
    meta: dict[str, object] = {
        "source": "control-plane-api",
        "action": action,
    }
    meta.update(kwargs)
    return meta


def _parse_datetime(value: str | None) -> datetime | None:
    """解析 datetime 字符串。"""
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


@router.get("")
def get_service_status() -> dict:
    """获取交易日志服务状态。"""
    status = trade_log_service.get_service_status()
    return _success(status, _build_meta("status"))


@router.post("")
def record_trade(
    payload: dict[str, Any],
    token: str = "",
    authorization: str = Header(""),
) -> dict:
    """记录交易日志。

    Args:
        payload: {
            symbol: "BTC/USDT",
            side: "buy" | "sell",
            entry_price: 100.0,
            exit_price: 105.0,  # 可选
            entry_time: "2024-01-01T00:00:00Z",  # 可选
            exit_time: "2024-01-02T00:00:00Z",  # 可选
            quantity: 1.0,
            pnl_percent: 5.0,
            stop_loss_reason: "take_profit",  # 可选
            signal_score: 0.8,  # 可选
            strategy_name: "trend_breakout",  # 可选
            notes: "备注信息"  # 可选
        }
    """
    try:
        auth_service.require_control_plane_access(
            auth_service.resolve_access_token(token, authorization)
        )
    except PermissionError:
        return _unauthorized()

    symbol = payload.get("symbol")
    side = payload.get("side")

    if not symbol or not side:
        return _error("invalid_request", "symbol and side are required")

    try:
        trade_log = trade_log_service.record_trade(
            symbol=symbol,
            side=side,
            entry_price=payload.get("entry_price", 0),
            exit_price=payload.get("exit_price"),
            entry_time=_parse_datetime(payload.get("entry_time")),
            exit_time=_parse_datetime(payload.get("exit_time")),
            quantity=payload.get("quantity", 0),
            pnl_percent=payload.get("pnl_percent", 0),
            stop_loss_reason=payload.get("stop_loss_reason"),
            signal_score=payload.get("signal_score"),
            strategy_name=payload.get("strategy_name"),
            notes=payload.get("notes"),
        )

        return _success(
            {"trade_log": trade_log.to_dict()},
            _build_meta(
                "record-trade",
                trade_id=trade_log.trade_id,
                symbol=trade_log.symbol,
                side=trade_log.side,
            ),
        )
    except ValueError as e:
        return _error("invalid_request", str(e))


@router.get("/history")
def get_trade_history(
    symbol: str | None = None,
    side: str | None = None,
    strategy_name: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> dict:
    """查询交易历史。

    Args:
        symbol: 筛选交易对（可选）
        side: 筛选方向（可选）
        strategy_name: 筛选策略名称（可选）
        start_time: 开始时间 YYYY-MM-DDTHH:MM:SS（可选）
        end_time: 结束时间 YYYY-MM-DDTHH:MM:SS（可选）
        limit: 返回数量限制
        offset: 偏移量
    """
    if limit < 1 or limit > 1000:
        limit = 100

    if offset < 0:
        offset = 0

    logs = trade_log_service.get_trade_history(
        symbol=symbol,
        side=side,
        strategy_name=strategy_name,
        start_time=_parse_datetime(start_time),
        end_time=_parse_datetime(end_time),
        limit=limit,
        offset=offset,
    )

    return _success(
        {
            "items": [log.to_dict() for log in logs],
            "total_returned": len(logs),
            "symbol_filter": symbol,
            "side_filter": side,
        },
        _build_meta(
            "trade-history",
            count=len(logs),
            symbol=symbol,
            side=side,
            limit=limit,
            offset=offset,
        ),
    )


@router.get("/{trade_id}")
def get_trade(trade_id: int) -> dict:
    """获取单条交易日志。"""
    trade_log = trade_log_service.get_trade(trade_id)

    if trade_log is None:
        return _error("not_found", f"trade log {trade_id} not found")

    return _success(
        {"trade_log": trade_log.to_dict()},
        _build_meta("get-trade", trade_id=trade_id),
    )


@router.put("/{trade_id}")
def update_trade(
    trade_id: int,
    payload: dict[str, Any],
    token: str = "",
    authorization: str = Header(""),
) -> dict:
    """更新交易日志（主要用于平仓时更新出场信息）。

    Args:
        trade_id: 交易ID
        payload: {
            exit_price: 105.0,
            exit_time: "2024-01-02T00:00:00Z",  # 可选
            pnl_percent: 5.0,
            stop_loss_reason: "take_profit",
            notes: "备注信息"
        }
    """
    try:
        auth_service.require_control_plane_access(
            auth_service.resolve_access_token(token, authorization)
        )
    except PermissionError:
        return _unauthorized()

    trade_log = trade_log_service.update_trade(
        trade_id=trade_id,
        exit_price=payload.get("exit_price"),
        exit_time=_parse_datetime(payload.get("exit_time")),
        pnl_percent=payload.get("pnl_percent"),
        stop_loss_reason=payload.get("stop_loss_reason"),
        notes=payload.get("notes"),
    )

    if trade_log is None:
        return _error("not_found", f"trade log {trade_id} not found")

    return _success(
        {"trade_log": trade_log.to_dict()},
        _build_meta(
            "update-trade",
            trade_id=trade_id,
            symbol=trade_log.symbol,
        ),
    )


@router.get("/open-positions")
def get_open_positions() -> dict:
    """获取当前未平仓的交易。"""
    logs = trade_log_service.get_open_positions()

    return _success(
        {
            "items": [log.to_dict() for log in logs],
            "total_open": len(logs),
        },
        _build_meta("open-positions", count=len(logs)),
    )


@router.get("/statistics")
def get_statistics(
    symbol: str | None = None,
    strategy_name: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
) -> dict:
    """获取交易统计数据。

    Args:
        symbol: 筛选交易对（可选）
        strategy_name: 筛选策略名称（可选）
        start_time: 开始时间 YYYY-MM-DDTHH:MM:SS（可选）
        end_time: 结束时间 YYYY-MM-DDTHH:MM:SS（可选）
    """
    stats = trade_log_service.get_statistics(
        symbol=symbol,
        strategy_name=strategy_name,
        start_time=_parse_datetime(start_time),
        end_time=_parse_datetime(end_time),
    )

    return _success(
        {"statistics": stats},
        _build_meta(
            "statistics",
            symbol=symbol,
            strategy_name=strategy_name,
        ),
    )