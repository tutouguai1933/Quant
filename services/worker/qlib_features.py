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
    "ema20_gap_pct",
    "ema55_gap_pct",
    "atr_pct",
    "rsi14",
    "breakout_strength",
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
    rolling_highs: list[Decimal] = []
    previous_close = valid_candles[0]["close"]

    for index, candle in enumerate(valid_candles):
        rolling_closes.append(candle["close"])
        rolling_volumes.append(candle["volume"])
        rolling_highs.append(candle["high"])

        close_return_pct = _safe_pct_change(previous_close, candle["close"] - previous_close)
        range_pct = _safe_pct_change(candle["close"], candle["high"] - candle["low"])
        body_pct = _safe_pct_change(candle["open"], candle["close"] - candle["open"])
        volume_ratio = _safe_ratio(candle["volume"], _mean(rolling_volumes[-3:]))
        trend_gap_pct = _safe_pct_change(_mean(rolling_closes[-3:]), candle["close"] - _mean(rolling_closes[-3:]))
        ema20_gap_pct = _safe_pct_change(candle["close"], candle["close"] - _ema(rolling_closes, 20))
        ema55_gap_pct = _safe_pct_change(candle["close"], candle["close"] - _ema(rolling_closes, 55))
        atr_pct = _safe_pct_change(candle["close"], _atr(valid_candles[: index + 1]))
        rsi14 = _rsi(valid_candles[: index + 1])
        recent_high = _recent_high(rolling_highs[:-1])
        breakout_strength = _safe_pct_change(
            recent_high,
            candle["close"] - recent_high,
        )

        rows.append(
            {
                "symbol": symbol.strip().upper(),
                "generated_at": int(candle["close_time"]),
                "close_return_pct": _format_decimal(close_return_pct),
                "range_pct": _format_decimal(range_pct),
                "body_pct": _format_decimal(body_pct),
                "volume_ratio": _format_decimal(volume_ratio),
                "trend_gap_pct": _format_decimal(trend_gap_pct),
                "ema20_gap_pct": _format_decimal(ema20_gap_pct),
                "ema55_gap_pct": _format_decimal(ema55_gap_pct),
                "atr_pct": _format_decimal(atr_pct),
                "rsi14": _format_decimal(rsi14),
                "breakout_strength": _format_decimal(breakout_strength),
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


def _ema(values: list[Decimal], period: int) -> Decimal:
    """计算简单 EMA。"""

    if not values:
        return Decimal("0")
    alpha = Decimal("2") / Decimal(period + 1)
    ema = values[0]
    for value in values[1:]:
        ema = (value * alpha) + (ema * (Decimal("1") - alpha))
    return ema


def _atr(candles: list[dict[str, Decimal | int]]) -> Decimal:
    """计算平均真实波幅。"""

    if not candles:
        return Decimal("0")
    true_ranges: list[Decimal] = []
    previous_close: Decimal | None = None
    for candle in candles:
        current_high = candle["high"]
        current_low = candle["low"]
        if previous_close is None:
            true_ranges.append(current_high - current_low)
        else:
            true_ranges.append(
                max(
                    current_high - current_low,
                    abs(current_high - previous_close),
                    abs(current_low - previous_close),
                )
            )
        previous_close = candle["close"]
    return _mean(true_ranges[-14:])


def _rsi(candles: list[dict[str, Decimal | int]]) -> Decimal:
    """计算 14 周期 RSI。"""

    if len(candles) < 2:
        return Decimal("50")
    gains: list[Decimal] = []
    losses: list[Decimal] = []
    for previous, current in zip(candles, candles[1:]):
        change = current["close"] - previous["close"]
        if change > 0:
            gains.append(change)
        elif change < 0:
            losses.append(-change)
    average_gain = _mean(gains[-14:])
    average_loss = _mean(losses[-14:])
    if average_gain == 0 and average_loss == 0:
        return Decimal("50")
    if average_loss == 0:
        return Decimal("100")
    relative_strength = average_gain / average_loss
    return Decimal("100") - (Decimal("100") / (Decimal("1") + relative_strength))


def _recent_high(values: list[Decimal]) -> Decimal:
    """返回近期高点。"""

    if not values:
        return Decimal("0")
    return max(values[-20:])
