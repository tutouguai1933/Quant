"""Qlib 最小特征定义。

这个文件负责把 K 线样本转成稳定的研究特征集合。
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation


FEATURE_COLUMNS = (
    "symbol",
    "generated_at",
    "close_return_pct",
    "range_pct",
    "body_pct",
    "volume_ratio",
    "trend_gap_pct",
)


def build_feature_rows(symbol: str, candles: list[dict[str, object]]) -> list[dict[str, object]]:
    """把 K 线样本转成最小特征行。"""

    normalized = [_normalize_candle(item) for item in candles]
    valid_candles = [item for item in normalized if item is not None]
    if not valid_candles:
        return []

    rows: list[dict[str, object]] = []
    rolling_closes: list[Decimal] = []
    rolling_volumes: list[Decimal] = []
    previous_close = valid_candles[0]["close"]

    for candle in valid_candles:
        rolling_closes.append(candle["close"])
        rolling_volumes.append(candle["volume"])

        close_return_pct = _safe_pct_change(previous_close, candle["close"] - previous_close)
        range_pct = _safe_pct_change(candle["close"], candle["high"] - candle["low"])
        body_pct = _safe_pct_change(candle["open"], candle["close"] - candle["open"])
        volume_ratio = _safe_ratio(candle["volume"], _mean(rolling_volumes[-3:]))
        trend_gap_pct = _safe_pct_change(_mean(rolling_closes[-3:]), candle["close"] - _mean(rolling_closes[-3:]))

        rows.append(
            {
                "symbol": symbol.strip().upper(),
                "generated_at": int(candle["close_time"]),
                "close_return_pct": _format_decimal(close_return_pct),
                "range_pct": _format_decimal(range_pct),
                "body_pct": _format_decimal(body_pct),
                "volume_ratio": _format_decimal(volume_ratio),
                "trend_gap_pct": _format_decimal(trend_gap_pct),
            }
        )
        previous_close = candle["close"]

    return rows


def _normalize_candle(candle: dict[str, object]) -> dict[str, Decimal | int] | None:
    """把输入 K 线整理成可计算结构。"""

    try:
        return {
            "open": Decimal(str(candle["open"])),
            "high": Decimal(str(candle["high"])),
            "low": Decimal(str(candle["low"])),
            "close": Decimal(str(candle["close"])),
            "volume": Decimal(str(candle["volume"])),
            "close_time": int(candle["close_time"]),
        }
    except (KeyError, TypeError, ValueError, InvalidOperation):
        return None


def _safe_pct_change(base: Decimal, delta: Decimal) -> Decimal:
    """计算百分比变化。"""

    if base == 0:
        return Decimal("0")
    return (delta / base) * Decimal("100")


def _safe_ratio(value: Decimal, baseline: Decimal) -> Decimal:
    """计算比例。"""

    if baseline == 0:
        return Decimal("0")
    return value / baseline


def _mean(values: list[Decimal]) -> Decimal:
    """返回均值。"""

    if not values:
        return Decimal("0")
    return sum(values) / Decimal(len(values))


def _format_decimal(value: Decimal) -> str:
    """把数值统一成字符串。"""

    normalized = value.quantize(Decimal("0.0001"))
    return format(normalized, "f")
