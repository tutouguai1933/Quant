"""市场周期相关服务。"""

from __future__ import annotations

from collections.abc import Callable


SUPPORTED_MARKET_INTERVALS = ("1m", "3m", "5m", "15m", "30m", "1h", "4h", "1d", "1w")
DEFAULT_MARKET_INTERVAL = "4h"


def get_supported_market_intervals() -> tuple[str, ...]:
    """返回市场图表支持的固定周期列表。"""

    return SUPPORTED_MARKET_INTERVALS


def normalize_market_interval(value: str | None) -> str:
    """把输入周期归一化到支持范围内。"""

    normalized = str(value or "").strip().lower()
    return normalized if normalized in SUPPORTED_MARKET_INTERVALS else DEFAULT_MARKET_INTERVAL


def build_multi_timeframe_summary(
    *,
    symbol: str,
    intervals: tuple[str, ...],
    evaluate_interval: Callable[[str], dict[str, object]],
) -> list[dict[str, object]]:
    """按固定周期列表构造多周期策略摘要。"""

    normalized_symbol = symbol.strip().upper()
    summaries: list[dict[str, object]] = []
    for interval in intervals:
        summary = dict(evaluate_interval(interval) or {})
        summaries.append(
            {
                "symbol": normalized_symbol,
                "interval": interval,
                **summary,
            }
        )
    return summaries
