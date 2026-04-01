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
            period=12,
            warnings=shared_warnings,
            last_candle_closed=last_candle_closed,
            calculator=lambda values: _ema(values, 12),
        ),
        "ema_slow": _build_metric_summary(
            values=[row["close"] for row in series],
            period=26,
            warnings=shared_warnings,
            last_candle_closed=last_candle_closed,
            calculator=lambda values: _ema(values, 26),
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
