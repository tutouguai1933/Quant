"""回测图表路由。

提供回测可视化数据的API端点。
"""

from __future__ import annotations

from services.api.app.services.backtest_chart_service import backtest_chart_service

try:
    from fastapi import APIRouter
except ImportError:
    class APIRouter:  # pragma: no cover
        def __init__(self, *args, **kwargs) -> None:
            self.args = args
            self.kwargs = kwargs

        def get(self, *args, **kwargs):
            def decorator(func):
                return func
            return decorator


router = APIRouter(prefix="/api/v1/backtest", tags=["backtest-charts"])


def _success(data: dict[str, object], meta: dict[str, object] | None = None) -> dict[str, object]:
    """统一成功包裹。"""
    return {"data": data, "error": None, "meta": meta or {}}


@router.get("/{backtest_id}/charts")
def get_all_charts(backtest_id: str) -> dict[str, object]:
    """获取所有图表数据。

    Args:
        backtest_id: 回测ID，可以是 "latest" 或 symbol (如 "BTCUSDT")

    Returns:
        包含 profit_curve、statistics、distribution 的完整图表数据
    """
    charts = backtest_chart_service.get_all_charts(backtest_id)
    return _success(charts, {"source": "backtest-charts", "backtest_id": backtest_id})


@router.get("/{backtest_id}/profit-curve")
def get_profit_curve(backtest_id: str) -> dict[str, object]:
    """获取收益曲线数据。

    Args:
        backtest_id: 回测ID

    Returns:
        时间序列数据：日期→累计收益率
    """
    curve = backtest_chart_service.generate_profit_curve(backtest_id)
    return _success(
        {"profit_curve": curve},
        {"source": "backtest-charts", "backtest_id": backtest_id, "count": len(curve)}
    )


@router.get("/{backtest_id}/statistics")
def get_statistics(backtest_id: str) -> dict[str, object]:
    """获取统计指标。

    Args:
        backtest_id: 回测ID

    Returns:
        累计收益、最大回撤、夏普比率、胜率等统计指标
    """
    statistics = backtest_chart_service.calculate_statistics(backtest_id)
    return _success(statistics, {"source": "backtest-charts", "backtest_id": backtest_id})


@router.get("/{backtest_id}/distribution")
def get_distribution(backtest_id: str) -> dict[str, object]:
    """获取交易分布数据。

    Args:
        backtest_id: 回测ID

    Returns:
        盈利/亏损交易分布数据
    """
    distribution = backtest_chart_service.generate_trade_distribution(backtest_id)
    return _success(distribution, {"source": "backtest-charts", "backtest_id": backtest_id})