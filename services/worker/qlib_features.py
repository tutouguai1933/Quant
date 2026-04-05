"""Qlib 因子层定义。

这个文件负责统一管理因子分类、预处理规则和特征输出协议。
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation


FACTOR_DEFINITIONS = (
    {
        "name": "close_return_pct",
        "category": "momentum",
        "role": "primary",
        "kind": "base",
        "description": "最近一根 K 线的收盘变化，用来观察短期动量。",
        "neutral": "0",
        "clip": ("-50", "50"),
    },
    {
        "name": "range_pct",
        "category": "volatility",
        "role": "primary",
        "kind": "base",
        "description": "单根 K 线振幅，用来判断波动环境是否扩大。",
        "neutral": "0",
        "clip": ("0", "100"),
    },
    {
        "name": "body_pct",
        "category": "momentum",
        "role": "primary",
        "kind": "base",
        "description": "K 线实体强弱，用来判断单根价格推进力度。",
        "neutral": "0",
        "clip": ("-50", "50"),
    },
    {
        "name": "volume_ratio",
        "category": "volume",
        "role": "primary",
        "kind": "base",
        "description": "成交量相对均值的放大倍数，用来确认量价是否同步。",
        "neutral": "1",
        "clip": ("0", "10"),
    },
    {
        "name": "trend_gap_pct",
        "category": "trend",
        "role": "primary",
        "kind": "composite",
        "description": "价格相对短趋势均值的偏离，用来衡量趋势位置。",
        "neutral": "0",
        "clip": ("-50", "50"),
    },
    {
        "name": "ema20_gap_pct",
        "category": "trend",
        "role": "primary",
        "kind": "composite",
        "description": "价格相对 EMA20 的偏离，用来判断趋势是否站稳。",
        "neutral": "0",
        "clip": ("-50", "50"),
    },
    {
        "name": "ema55_gap_pct",
        "category": "trend",
        "role": "primary",
        "kind": "composite",
        "description": "价格相对 EMA55 的偏离，用来判断中期结构是否完整。",
        "neutral": "0",
        "clip": ("-50", "50"),
    },
    {
        "name": "atr_pct",
        "category": "volatility",
        "role": "primary",
        "kind": "composite",
        "description": "ATR 相对价格的比例，用来评估波动与止损空间。",
        "neutral": "0",
        "clip": ("0", "100"),
    },
    {
        "name": "breakout_strength",
        "category": "momentum",
        "role": "primary",
        "kind": "composite",
        "description": "价格相对近期高点的突破强度，用来观察趋势加速。",
        "neutral": "0",
        "clip": ("-50", "50"),
    },
    {
        "name": "roc6",
        "category": "momentum",
        "role": "primary",
        "kind": "composite",
        "description": "一段窗口内的价格变化率，用来判断推进速度是否持续。",
        "neutral": "0",
        "clip": ("-100", "100"),
    },
    {
        "name": "rsi14",
        "category": "oscillator",
        "role": "auxiliary",
        "kind": "base",
        "description": "RSI 超买超卖参考，只做辅助确认，不直接进主模型。",
        "neutral": "50",
        "clip": ("0", "100"),
    },
    {
        "name": "cci20",
        "category": "oscillator",
        "role": "auxiliary",
        "kind": "composite",
        "description": "CCI 均值偏离参考，只做辅助确认，不直接进主模型。",
        "neutral": "0",
        "clip": ("-300", "300"),
    },
    {
        "name": "stoch_k14",
        "category": "oscillator",
        "role": "auxiliary",
        "kind": "composite",
        "description": "随机指标 K 值，用来辅助观察区间位置和过热状态。",
        "neutral": "50",
        "clip": ("0", "100"),
    },
)

TIMEFRAME_PROFILES = {
    "4h": {
        "profile": "swing-primary",
        "trend_window": 3,
        "volume_window": 3,
        "atr_period": 14,
        "rsi_period": 14,
        "roc_period": 6,
        "cci_period": 20,
        "stoch_period": 14,
        "breakout_lookback": 20,
    },
    "1h": {
        "profile": "swing-support",
        "trend_window": 12,
        "volume_window": 12,
        "atr_period": 24,
        "rsi_period": 21,
        "roc_period": 18,
        "cci_period": 30,
        "stoch_period": 21,
        "breakout_lookback": 24,
    },
}

PRIMARY_FEATURE_COLUMNS = tuple(item["name"] for item in FACTOR_DEFINITIONS if item["role"] == "primary")
AUXILIARY_FEATURE_COLUMNS = tuple(item["name"] for item in FACTOR_DEFINITIONS if item["role"] == "auxiliary")
FEATURE_COLUMNS = ("symbol", "generated_at", *PRIMARY_FEATURE_COLUMNS, *AUXILIARY_FEATURE_COLUMNS)
FACTOR_METADATA = {item["name"]: item for item in FACTOR_DEFINITIONS}
FEATURE_PROTOCOL = {
    "version": "v2",
    "primary_feature_columns": list(PRIMARY_FEATURE_COLUMNS),
    "auxiliary_feature_columns": list(AUXILIARY_FEATURE_COLUMNS),
    "categories": {
        "trend": [item["name"] for item in FACTOR_DEFINITIONS if item["category"] == "trend"],
        "momentum": [item["name"] for item in FACTOR_DEFINITIONS if item["category"] == "momentum"],
        "oscillator": [item["name"] for item in FACTOR_DEFINITIONS if item["category"] == "oscillator"],
        "volume": [item["name"] for item in FACTOR_DEFINITIONS if item["category"] == "volume"],
        "volatility": [item["name"] for item in FACTOR_DEFINITIONS if item["category"] == "volatility"],
    },
    "roles": {
        "primary": list(PRIMARY_FEATURE_COLUMNS),
        "auxiliary": list(AUXILIARY_FEATURE_COLUMNS),
    },
    "preprocessing": {
        "missing_policy": "坏行直接丢弃，窗口不足时用中性值补齐",
        "outlier_policy": "按因子预设范围裁剪极值",
        "normalization_policy": "统一输出四位小数字符串",
    },
    "timeframe_profiles": {key: dict(value) for key, value in TIMEFRAME_PROFILES.items()},
    "factors": [
        {
            "name": item["name"],
            "category": item["category"],
            "role": item["role"],
            "kind": item["kind"],
            "description": item["description"],
        }
        for item in FACTOR_DEFINITIONS
    ],
}


def build_feature_rows(symbol: str, candles: list[dict[str, object]]) -> list[dict[str, object]]:
    """把 K 线样本转成统一因子行。"""

    normalized = [_normalize_candle(item) for item in candles]
    valid_candles = [item for item in normalized if item is not None]
    if not valid_candles:
        return []

    timeframe = _infer_timeframe(valid_candles)
    profile = _resolve_timeframe_profile(timeframe)
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
        volume_ratio = _safe_ratio(candle["volume"], _mean(rolling_volumes[-profile["volume_window"] :]))
        trend_gap_pct = _safe_pct_change(
            _mean(rolling_closes[-profile["trend_window"] :]),
            candle["close"] - _mean(rolling_closes[-profile["trend_window"] :]),
        )
        ema20_gap_pct = _safe_pct_change(candle["close"], candle["close"] - _ema(rolling_closes, 20))
        ema55_gap_pct = _safe_pct_change(candle["close"], candle["close"] - _ema(rolling_closes, 55))
        atr_pct = _safe_pct_change(candle["close"], _atr(valid_candles[: index + 1], profile["atr_period"]))
        rsi14 = _rsi(valid_candles[: index + 1], profile["rsi_period"])
        recent_high = _recent_high(rolling_highs[:-1], profile["breakout_lookback"])
        breakout_strength = _safe_pct_change(recent_high, candle["close"] - recent_high)
        roc6 = _roc(rolling_closes, profile["roc_period"])
        cci20 = _cci(valid_candles[: index + 1], profile["cci_period"])
        stoch_k14 = _stoch_k(valid_candles[: index + 1], profile["stoch_period"])

        raw_row = {
            "symbol": symbol.strip().upper(),
            "generated_at": int(candle["close_time"]),
            "close_return_pct": close_return_pct,
            "range_pct": range_pct,
            "body_pct": body_pct,
            "volume_ratio": volume_ratio,
            "trend_gap_pct": trend_gap_pct,
            "ema20_gap_pct": ema20_gap_pct,
            "ema55_gap_pct": ema55_gap_pct,
            "atr_pct": atr_pct,
            "breakout_strength": breakout_strength,
            "roc6": roc6,
            "rsi14": rsi14,
            "cci20": cci20,
            "stoch_k14": stoch_k14,
        }
        rows.append(_apply_feature_protocol(raw_row))
        previous_close = candle["close"]

    return rows


def _apply_feature_protocol(row: dict[str, object]) -> dict[str, object]:
    """按统一协议格式化因子输出。"""

    normalized: dict[str, object] = {
        "symbol": row["symbol"],
        "generated_at": row["generated_at"],
    }
    for column in PRIMARY_FEATURE_COLUMNS + AUXILIARY_FEATURE_COLUMNS:
        normalized[column] = _format_feature_value(column, row.get(column))
    return normalized


def _format_feature_value(name: str, value: object) -> str:
    """按因子协议补齐缺失值并裁剪极值。"""

    metadata = FACTOR_METADATA[name]
    parsed = _to_decimal(value, default=Decimal(str(metadata["neutral"])))
    lower = Decimal(str(metadata["clip"][0]))
    upper = Decimal(str(metadata["clip"][1]))
    bounded = min(max(parsed, lower), upper)
    return _format_decimal(bounded)


def _normalize_candle(candle: dict[str, object]) -> dict[str, Decimal | int] | None:
    """把输入 K 线整理成可计算结构。"""

    try:
        return {
            "open": Decimal(str(candle["open"])),
            "high": Decimal(str(candle["high"])),
            "low": Decimal(str(candle["low"])),
            "close": Decimal(str(candle["close"])),
            "volume": Decimal(str(candle["volume"])),
            "open_time": int(candle.get("open_time") or candle["close_time"]),
            "close_time": int(candle["close_time"]),
        }
    except (KeyError, TypeError, ValueError, InvalidOperation):
        return None


def _infer_timeframe(candles: list[dict[str, Decimal | int]]) -> str:
    """根据 K 线时间间隔推断周期。"""

    if len(candles) < 2:
        return "1h"
    first = int(candles[0]["open_time"])
    second = int(candles[1]["open_time"])
    step_ms = max(0, second - first)
    if step_ms >= 4 * 60 * 60 * 1000:
        return "4h"
    return "1h"


def _resolve_timeframe_profile(timeframe: str) -> dict[str, int | str]:
    """返回当前周期应该使用的因子参数。"""

    return dict(TIMEFRAME_PROFILES.get(timeframe, TIMEFRAME_PROFILES["4h"]))


def _safe_pct_change(base: Decimal, delta: Decimal) -> Decimal:
    """计算百分比变化。"""

    if base == 0:
        return Decimal("0")
    return (delta / base) * Decimal("100")


def _safe_ratio(value: Decimal, baseline: Decimal) -> Decimal:
    """计算比例。"""

    if baseline == 0:
        return Decimal("1")
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


def _to_decimal(value: object, *, default: Decimal) -> Decimal:
    """把输入统一转成十进制。"""

    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return default


def _ema(values: list[Decimal], period: int) -> Decimal:
    """计算简单 EMA。"""

    if not values:
        return Decimal("0")
    alpha = Decimal("2") / Decimal(period + 1)
    ema = values[0]
    for value in values[1:]:
        ema = (value * alpha) + (ema * (Decimal("1") - alpha))
    return ema


def _atr(candles: list[dict[str, Decimal | int]], period: int) -> Decimal:
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
    return _mean(true_ranges[-period:])


def _rsi(candles: list[dict[str, Decimal | int]], period: int) -> Decimal:
    """计算 RSI。"""

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
    average_gain = _mean(gains[-period:])
    average_loss = _mean(losses[-period:])
    if average_gain == 0 and average_loss == 0:
        return Decimal("50")
    if average_loss == 0:
        return Decimal("100")
    relative_strength = average_gain / average_loss
    return Decimal("100") - (Decimal("100") / (Decimal("1") + relative_strength))


def _roc(values: list[Decimal], period: int) -> Decimal:
    """计算价格变化率。"""

    if len(values) <= period:
        return Decimal("0")
    baseline = values[-period - 1]
    return _safe_pct_change(baseline, values[-1] - baseline)


def _cci(candles: list[dict[str, Decimal | int]], period: int) -> Decimal:
    """计算 CCI。"""

    if len(candles) < period:
        return Decimal("0")
    typical_prices = [
        (candle["high"] + candle["low"] + candle["close"]) / Decimal("3")
        for candle in candles[-period:]
    ]
    typical_price = typical_prices[-1]
    moving_average = _mean(typical_prices)
    mean_deviation = _mean([abs(value - moving_average) for value in typical_prices])
    if mean_deviation == 0:
        return Decimal("0")
    return (typical_price - moving_average) / (Decimal("0.015") * mean_deviation)


def _stoch_k(candles: list[dict[str, Decimal | int]], period: int) -> Decimal:
    """计算随机指标 K 值。"""

    if len(candles) < period:
        return Decimal("50")
    window = candles[-period:]
    highest_high = max(candle["high"] for candle in window)
    lowest_low = min(candle["low"] for candle in window)
    if highest_high == lowest_low:
        return Decimal("50")
    return ((window[-1]["close"] - lowest_low) / (highest_high - lowest_low)) * Decimal("100")


def _recent_high(values: list[Decimal], lookback: int) -> Decimal:
    """返回近期高点。"""

    if not values:
        return Decimal("0")
    return max(values[-lookback:])
