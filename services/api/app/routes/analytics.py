"""数据分析 API 路由。

提供以下接口:
- GET /api/v1/analytics/daily - 每日统计
- GET /api/v1/analytics/weekly - 每周统计
- GET /api/v1/analytics/attribution - 归因分析
- GET /api/v1/analytics/performance - 策略表现
- GET /api/v1/analytics/history - 交易历史
- POST /api/v1/analytics/sync - 同步交易数据
"""

from __future__ import annotations

from services.api.app.services.analytics_service import analytics_service
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

    def Header(default: str = "") -> str:  # pragma: no cover - fallback stub
        return default


router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


def _success(data: dict, meta: dict | None = None) -> dict:
    return {"data": data, "error": None, "meta": meta or {}}


def _unauthorized() -> dict:
    return {
        "data": None,
        "error": {"code": "unauthorized", "message": "authentication required"},
        "meta": {"source": "control-plane-api"},
    }


def _build_meta(action: str, **kwargs: object) -> dict[str, object]:
    """构建统一的元数据结构。"""
    meta: dict[str, object] = {
        "source": "control-plane-api",
        "action": action,
    }
    meta.update(kwargs)
    return meta


@router.get("")
def get_analytics_status() -> dict:
    """获取数据分析服务状态。"""
    status = analytics_service.get_service_status()
    return _success(status, _build_meta("status", history_days=analytics_service.history_days))


@router.get("/daily")
def get_daily_summary(date: str | None = None) -> dict:
    """获取每日交易统计。

    Args:
        date: YYYY-MM-DD 格式的日期，默认为今天
    """
    summary = analytics_service.get_daily_summary(date=date)
    return _success(
        {"summary": summary.to_dict()},
        _build_meta(
            "daily-summary",
            date=summary.date,
            trade_count=summary.trade_count,
        ),
    )


@router.get("/weekly")
def get_weekly_summary(week_start: str | None = None) -> dict:
    """获取每周交易统计。

    Args:
        week_start: YYYY-MM-DD 格式的周一日期，默认为本周
    """
    summary = analytics_service.get_weekly_summary(week_start=week_start)
    return _success(
        {"summary": summary.to_dict()},
        _build_meta(
            "weekly-summary",
            week_start=summary.week_start,
            week_end=summary.week_end,
            trade_count=summary.trade_count,
        ),
    )


@router.get("/attribution")
def get_pnl_attribution(days: int | None = None) -> dict:
    """获取盈亏归因分析。

    Args:
        days: 分析天数，默认使用配置的历史天数
    """
    attribution = analytics_service.get_pnl_attribution(days=days)
    return _success(
        {"attribution": attribution.to_dict()},
        _build_meta(
            "pnl-attribution",
            days=days or analytics_service.history_days,
        ),
    )


@router.get("/performance")
def get_strategy_performance(strategy_id: int | None = None) -> dict:
    """获取策略表现对比。

    Args:
        strategy_id: 可选的策略ID，用于筛选单个策略
    """
    performances = analytics_service.get_strategy_performance(strategy_id=strategy_id)
    return _success(
        {"performances": [p.to_dict() for p in performances]},
        _build_meta(
            "strategy-performance",
            strategy_id=strategy_id,
            count=len(performances),
        ),
    )


@router.get("/history")
def get_trade_history(
    limit: int = 100,
    symbol: str | None = None,
    side: str | None = None,
    strategy_id: int | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict:
    """获取交易历史记录。

    Args:
        limit: 返回记录数量上限
        symbol: 标的筛选
        side: 方向筛选（buy/sell）
        strategy_id: 策略筛选
        start_date: 开始日期（YYYY-MM-DD）
        end_date: 结束日期（YYYY-MM-DD）
    """
    trades = analytics_service.get_trade_history(
        limit=limit,
        symbol=symbol,
        side=side,
        strategy_id=strategy_id,
        start_date=start_date,
        end_date=end_date,
    )
    return _success(
        {"trades": trades, "count": len(trades)},
        _build_meta(
            "trade-history",
            limit=limit,
            symbol=symbol,
            side=side,
            strategy_id=strategy_id,
            start_date=start_date,
            end_date=end_date,
        ),
    )


@router.post("/sync")
def sync_trade_data(
    token: str = "",
    authorization: str = Header(""),
) -> dict:
    """手动同步交易数据（需要认证）。

    从执行器拉取最新订单记录并更新分析缓存。
    """
    try:
        auth_service.require_control_plane_access(
            auth_service.resolve_access_token(token, authorization)
        )
    except PermissionError:
        return _unauthorized()

    result = analytics_service.refresh_trade_history()
    return _success(result, _build_meta("sync", status=result.get("status")))