"""图表指标与基础标记服务。"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def build_indicator_summary(
    items: list[dict[str, object]],
    warnings: list[str] | None = None,
    now: datetime | None = None,
) -> dict[str, dict[str, object]]:
    """根据标准化 K 线生成最小指标摘要。"""

    series, row_warnings = _prepare_series(items)
    shared_warnings = _unique_messages([*(warnings or []), *row_warnings])
    reference_time = now or datetime.now(timezone.utc)
    last_candle_closed = _is_last_candle_closed(series, reference_time)

    return {
        "ema_fast": _build_metric_summary(
            values=[row["close"] for row in series],
            period=20,
            warnings=shared_warnings,
            last_candle_closed=last_candle_closed,
            calculator=lambda values: _ema(values, 20),
        ),
        "ema_slow": _build_metric_summary(
            values=[row["close"] for row in series],
            period=55,
            warnings=shared_warnings,
            last_candle_closed=last_candle_closed,
            calculator=lambda values: _ema(values, 55),
        ),
        "atr": _build_metric_summary(
            values=series,
            period=14,
            warnings=shared_warnings,
            last_candle_closed=last_candle_closed,
            calculator=lambda rows: _average(_true_ranges(rows), 14),
        ),
        "rsi": _build_metric_summary(
            values=[row["close"] for row in series],
            period=14,
            warnings=shared_warnings,
            last_candle_closed=last_candle_closed,
            calculator=lambda values: _rsi(values, 14),
        ),
        "volume_sma": _build_metric_summary(
            values=[row["volume"] for row in series],
            period=20,
            warnings=shared_warnings,
            last_candle_closed=last_candle_closed,
            calculator=lambda values: _average(values, 20),
        ),
    }


def build_empty_marker_groups() -> dict[str, list[dict[str, object]]]:
    """返回图表标记的空结构。"""

    return {"signals": [], "entries": [], "stops": []}


def _prepare_series(items: list[dict[str, object]]) -> tuple[list[dict[str, Decimal | int]], list[str]]:
    """把输入 K 线整理成可计算的数值序列。"""

    series: list[dict[str, Decimal | int]] = []
    invalid_rows = 0
    for index, item in enumerate(items):
        normalized = _prepare_row(item)
        if normalized is None:
            invalid_rows += 1
            continue
        series.append(normalized)

    warnings: list[str] = []
    if invalid_rows:
        warnings.append(f"invalid_candle_rows:{invalid_rows}")
    return series, warnings


def _prepare_row(item: dict[str, object]) -> dict[str, Decimal | int] | None:
    """把单根 K 线转成数值对象，坏数据直接跳过。"""

    try:
        return {
            "open_time": int(item["open_time"]),
            "close_time": int(item["close_time"]),
            "open": _to_decimal(item["open"]),
            "high": _to_decimal(item["high"]),
            "low": _to_decimal(item["low"]),
            "close": _to_decimal(item["close"]),
            "volume": _to_decimal(item["volume"]),
        }
    except (KeyError, TypeError, ValueError, InvalidOperation):
        return None


def _build_metric_summary(
    values: list[Decimal] | list[dict[str, Decimal | int]],
    period: int,
    warnings: list[str],
    last_candle_closed: bool,
    calculator,
) -> dict[str, object]:
    """构建单个指标的状态摘要。"""

    sample_size = len(values)
    metric_warnings = list(warnings)
    ready = sample_size >= period
    value: str | None = None

    if ready:
        computed = calculator(values)
        value = _format_decimal(computed)
    else:
        metric_warnings.append(f"insufficient_samples:{sample_size}/{period}")

    return {
        "value": value,
        "ready": ready,
        "sample_size": sample_size,
        "warnings": metric_warnings,
        "last_candle_closed": last_candle_closed,
    }


def _is_last_candle_closed(series: list[dict[str, Decimal | int]], now: datetime) -> bool:
    """用当前时间判断最后一根 K 线是否已经收盘。"""

    if not series:
        return False

    close_time = series[-1]["close_time"]
    assert isinstance(close_time, int)
    close_instant = datetime.fromtimestamp(close_time / 1000, tz=timezone.utc)
    return now >= close_instant


def _average(values: list[Decimal], period: int) -> Decimal:
    """计算最近一段数据的简单均值。"""

    if not values:
        return Decimal("0")
    window = values[-period:] if len(values) > period else values
    return sum(window) / Decimal(len(window))


def _ema(values: list[Decimal], period: int) -> Decimal:
    """计算最小可用的指数移动平均。"""

    if not values:
        return Decimal("0")
    smoothing = Decimal("2") / Decimal(period + 1)
    ema = values[0]
    for value in values[1:]:
        ema = (value - ema) * smoothing + ema
    return ema


def _true_ranges(rows: list[dict[str, Decimal | int]]) -> list[Decimal]:
    """计算真实波幅序列。"""

    if not rows:
        return []

    ranges: list[Decimal] = []
    previous_close: Decimal | None = None
    for row in rows:
        high = row["high"]
        low = row["low"]
        close = row["close"]
        assert isinstance(high, Decimal)
        assert isinstance(low, Decimal)
        assert isinstance(close, Decimal)

        current_range = high - low
        if previous_close is not None:
            current_range = max(
                current_range,
                abs(high - previous_close),
                abs(low - previous_close),
            )
        ranges.append(current_range)
        previous_close = close
    return ranges


def _rsi(closes: list[Decimal], period: int) -> Decimal:
    """计算最小可用的相对强弱指标。"""

    if len(closes) < 2:
        return Decimal("50")

    gains: list[Decimal] = []
    losses: list[Decimal] = []
    previous_close = closes[0]
    for close in closes[1:]:
        delta = close - previous_close
        gains.append(max(delta, Decimal("0")))
        losses.append(max(-delta, Decimal("0")))
        previous_close = close

    average_gain = _average(gains, period)
    average_loss = _average(losses, period)
    if average_gain == 0 and average_loss == 0:
        return Decimal("50")
    if average_loss == 0:
        return Decimal("100")

    relative_strength = average_gain / average_loss
    return Decimal("100") - (Decimal("100") / (Decimal("1") + relative_strength))


def _format_decimal(value: Decimal) -> str:
    """统一输出为固定精度的字符串。"""

    return str(value.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP))


def _to_decimal(value: object) -> Decimal:
    """把输入统一成 Decimal，坏值直接抛出以便上层跳过。"""

    return Decimal(str(value))


def _unique_messages(messages: list[str]) -> list[str]:
    """去重并保持顺序。"""

    seen: set[str] = set()
    unique: list[str] = []
    for message in messages:
        if message in seen:
            continue
        seen.add(message)
        unique.append(message)
    return unique


def calculate_rsi(closes: list[Decimal], period: int = 14) -> Decimal:
    """计算 RSI (相对强弱指标)。

    Args:
        closes: 收盘价序列
        period: RSI 周期，默认14

    Returns:
        RSI 值 (0-100)
    """
    return _rsi(closes, period)


def calculate_macd(
    closes: list[Decimal],
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
) -> dict[str, Decimal | None]:
    """计算 MACD (移动平均收敛/发散指标)。

    Args:
        closes: 收盘价序列
        fast_period: 快线周期，默认12
        slow_period: 慢线周期，默认26
        signal_period: 信号线周期，默认9

    Returns:
        dict 包含 macd_line, signal_line, histogram
    """
    if len(closes) < slow_period + signal_period:
        return {
            "macd_line": None,
            "signal_line": None,
            "histogram": None,
            "trend": "neutral",
        }

    # 计算 EMA 快线和慢线
    ema_fast = _ema(closes, fast_period)
    ema_slow = _ema(closes, slow_period)

    if ema_fast is None or ema_slow is None:
        return {
            "macd_line": None,
            "signal_line": None,
            "histogram": None,
            "trend": "neutral",
        }

    # MACD 线 = 快线 - 慢线
    macd_line = ema_fast - ema_slow

    # 计算信号线 (MACD 线的 EMA)
    # 需要计算历史 MACD 值来得到信号线
    macd_history: list[Decimal] = []
    for i in range(slow_period, len(closes) + 1):
        segment = closes[:i]
        fast = _ema(segment, fast_period)
        slow = _ema(segment, slow_period)
        if fast is not None and slow is not None:
            macd_history.append(fast - slow)

    if len(macd_history) < signal_period:
        signal_line = macd_line  # 退化为当前值
    else:
        signal_line = _ema(macd_history[-signal_period:], signal_period) or macd_line

    # 柱状图 = MACD 线 - 信号线
    histogram = macd_line - signal_line

    # 判断趋势方向
    if histogram > Decimal("0"):
        trend = "bullish"
    elif histogram < Decimal("0"):
        trend = "bearish"
    else:
        trend = "neutral"

    return {
        "macd_line": macd_line,
        "signal_line": signal_line,
        "histogram": histogram,
        "trend": trend,
    }


def calculate_volume_trend(
    volumes: list[Decimal],
    closes: list[Decimal],
    period: int = 20,
) -> dict[str, Decimal | str | None]:
    """计算成交量趋势分析。

    Args:
        volumes: 成交量序列
        closes: 收盘价序列
        period: 均量周期，默认20

    Returns:
        dict 包含 volume_ratio, price_volume_alignment, trend_strength
    """
    if len(volumes) < period or len(closes) < period:
        return {
            "volume_ratio": None,
            "price_volume_alignment": "unknown",
            "trend_strength": Decimal("0"),
        }

    # 计算均量
    avg_volume = _average(volumes[-period:], period)
    current_volume = volumes[-1]

    # 成交量比率
    if avg_volume > Decimal("0"):
        volume_ratio = current_volume / avg_volume
    else:
        volume_ratio = Decimal("1")

    # 价格变化
    current_close = closes[-1]
    prev_close = closes[-2] if len(closes) >= 2 else closes[-1]
    price_change = current_close - prev_close

    # 量价配合分析
    if volume_ratio > Decimal("1.2"):  # 成交量放大
        if price_change > Decimal("0"):
            alignment = "bullish_volume"  # 量价齐升
            trend_strength = volume_ratio
        elif price_change < Decimal("0"):
            alignment = "bearish_volume"  # 量价齐跌
            trend_strength = volume_ratio
        else:
            alignment = "high_volume_neutral"  # 放量横盘
            trend_strength = Decimal("0.5") * volume_ratio
    elif volume_ratio < Decimal("0.8"):  # 成交量萎缩
        if price_change > Decimal("0"):
            alignment = "low_volume_rise"  # 缩量上涨
            trend_strength = Decimal("0.3")
        elif price_change < Decimal("0"):
            alignment = "low_volume_fall"  # 缩量下跌
            trend_strength = Decimal("0.3")
        else:
            alignment = "low_volume_neutral"
            trend_strength = Decimal("0")
    else:
        alignment = "normal_volume"
        trend_strength = Decimal("0.5")

    return {
        "volume_ratio": volume_ratio,
        "price_volume_alignment": alignment,
        "trend_strength": trend_strength,
    }
