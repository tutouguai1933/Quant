"""Qlib 因子层定义。

这个文件负责统一管理因子分类、预处理规则和特征输出协议。
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from statistics import mean, pstdev


DEFAULT_OUTLIER_POLICY = "clip"
DEFAULT_NORMALIZATION_POLICY = "fixed_4dp"
DEFAULT_MISSING_POLICY = "neutral_fill"
OUTLIER_POLICY_LABELS = {
    "clip": "按因子预设范围裁剪极值",
    "raw": "保留原始极值",
}
NORMALIZATION_POLICY_LABELS = {
    "fixed_4dp": "统一输出四位小数字符串",
    "zscore_by_symbol": "按单币样本做 z-score 标准化",
}
MISSING_POLICY_LABELS = {
    "neutral_fill": "窗口不足时用中性值补齐",
    "strict_drop": "窗口不足时直接丢弃",
}


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
    # 新增因子 - 趋势强度
    {
        "name": "trend_strength",
        "category": "trend",
        "role": "primary",
        "kind": "composite",
        "description": "趋势强度指标，基于 EMA 斜率和方向一致性计算。",
        "neutral": "0",
        "clip": ("-100", "100"),
    },
    # 新增因子 - 动量加速度
    {
        "name": "momentum_accel",
        "category": "momentum",
        "role": "primary",
        "kind": "composite",
        "description": "动量加速度，判断趋势是否在加速或减速。",
        "neutral": "0",
        "clip": ("-100", "100"),
    },
    # 新增因子 - 波动收缩
    {
        "name": "volatility_contraction",
        "category": "volatility",
        "role": "primary",
        "kind": "composite",
        "description": "波动收缩因子，识别突破前的能量积累。",
        "neutral": "0",
        "clip": ("0", "100"),
    },
    # 新增因子 - 量价背离
    {
        "name": "volume_price_divergence",
        "category": "volume",
        "role": "primary",
        "kind": "composite",
        "description": "量价背离因子，识别趋势衰竭信号。",
        "neutral": "0",
        "clip": ("-100", "100"),
    },
    # 新增因子 - 多空力量对比
    {
        "name": "bull_bear_ratio",
        "category": "momentum",
        "role": "primary",
        "kind": "composite",
        "description": "多空力量对比，基于上涨下跌 K 线数量和强度。",
        "neutral": "1",
        "clip": ("0", "10"),
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
        "missing_policy": MISSING_POLICY_LABELS[DEFAULT_MISSING_POLICY],
        "outlier_policy": OUTLIER_POLICY_LABELS[DEFAULT_OUTLIER_POLICY],
        "normalization_policy": NORMALIZATION_POLICY_LABELS[DEFAULT_NORMALIZATION_POLICY],
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


def build_feature_rows(
    symbol: str,
    candles: list[dict[str, object]],
    *,
    missing_policy: str = DEFAULT_MISSING_POLICY,
    outlier_policy: str = DEFAULT_OUTLIER_POLICY,
    normalization_policy: str = DEFAULT_NORMALIZATION_POLICY,
    timeframe_profiles: dict[str, dict[str, int | str]] | None = None,
) -> list[dict[str, object]]:
    """把 K 线样本转成统一因子行。"""

    normalized = [_normalize_candle(item) for item in candles]
    valid_candles = [item for item in normalized if item is not None]
    if not valid_candles:
        return []

    timeframe = _infer_timeframe(valid_candles)
    profile = _resolve_timeframe_profile(timeframe, timeframe_profiles=timeframe_profiles)
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

        # 新增因子计算
        trend_strength = _trend_strength(rolling_closes, 20)
        momentum_accel = _momentum_accel(rolling_closes, 6)
        volatility_contraction = _volatility_contraction(valid_candles[: index + 1], 14)
        volume_price_divergence = _volume_price_divergence(rolling_closes, rolling_volumes, 10)
        bull_bear_ratio = _bull_bear_ratio(valid_candles[: index + 1], 10)

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
            "trend_strength": trend_strength,
            "momentum_accel": momentum_accel,
            "volatility_contraction": volatility_contraction,
            "volume_price_divergence": volume_price_divergence,
            "bull_bear_ratio": bull_bear_ratio,
            "rsi14": rsi14,
            "cci20": cci20,
            "stoch_k14": stoch_k14,
        }
        rows.append(raw_row)
        previous_close = candle["close"]

    if missing_policy == "strict_drop":
        warmup_bars = _resolve_warmup_bars(profile)
        rows = rows[warmup_bars - 1 :] if len(rows) >= warmup_bars else []

    return _apply_feature_protocol(
        rows,
        outlier_policy=outlier_policy,
        normalization_policy=normalization_policy,
    )


def _apply_feature_protocol(
    rows: list[dict[str, object]],
    *,
    outlier_policy: str,
    normalization_policy: str,
) -> list[dict[str, object]]:
    """按统一协议格式化整批因子输出。"""

    normalized_outlier_policy = outlier_policy if outlier_policy in OUTLIER_POLICY_LABELS else DEFAULT_OUTLIER_POLICY
    normalized_normalization_policy = (
        normalization_policy if normalization_policy in NORMALIZATION_POLICY_LABELS else DEFAULT_NORMALIZATION_POLICY
    )
    factor_values = {
        column: [
            _normalize_feature_decimal(column, row.get(column), outlier_policy=normalized_outlier_policy)
            for row in rows
        ]
        for column in PRIMARY_FEATURE_COLUMNS + AUXILIARY_FEATURE_COLUMNS
    }
    if normalized_normalization_policy == "zscore_by_symbol":
        factor_values = {
            column: _zscore_series(values)
            for column, values in factor_values.items()
        }

    normalized_rows: list[dict[str, object]] = []
    for index, row in enumerate(rows):
        normalized: dict[str, object] = {
            "symbol": row["symbol"],
            "generated_at": row["generated_at"],
        }
        for column in PRIMARY_FEATURE_COLUMNS + AUXILIARY_FEATURE_COLUMNS:
            normalized[column] = _format_decimal(factor_values[column][index])
        normalized_rows.append(normalized)
    return normalized_rows


def _normalize_feature_decimal(name: str, value: object, *, outlier_policy: str) -> Decimal:
    """按因子协议补齐缺失值，并按策略处理极值。"""

    metadata = FACTOR_METADATA[name]
    parsed = _to_decimal(value, default=Decimal(str(metadata["neutral"])))
    if outlier_policy == "raw":
        return parsed
    lower = Decimal(str(metadata["clip"][0]))
    upper = Decimal(str(metadata["clip"][1]))
    return min(max(parsed, lower), upper)


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


def _resolve_timeframe_profile(
    timeframe: str,
    *,
    timeframe_profiles: dict[str, dict[str, int | str]] | None = None,
) -> dict[str, int | str]:
    """返回当前周期应该使用的因子参数。"""

    defaults = dict(TIMEFRAME_PROFILES.get(timeframe, TIMEFRAME_PROFILES["4h"]))
    incoming = dict((timeframe_profiles or {}).get(timeframe) or {})
    merged = dict(defaults)
    for key, default in defaults.items():
        if key not in incoming:
            continue
        candidate = incoming.get(key, default)
        if isinstance(default, int):
            try:
                merged[key] = max(1, int(candidate))
            except (TypeError, ValueError):
                merged[key] = default
        else:
            text = str(candidate or default).strip()
            merged[key] = text or default
    return merged


def _resolve_warmup_bars(profile: dict[str, int | str]) -> int:
    """返回严格缺失处理需要预留的最小预热长度。"""

    numeric_values = [int(value) for value in profile.values() if isinstance(value, int)]
    return max([55, *numeric_values])


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


def _zscore_series(values: list[Decimal]) -> list[Decimal]:
    """按单币样本把一列值转成 z-score。"""

    if not values:
        return []
    float_values = [float(item) for item in values]
    if len(float_values) < 2:
        return [Decimal("0") for _ in values]
    std = pstdev(float_values)
    if std == 0:
        return [Decimal("0") for _ in values]
    avg = mean(float_values)
    return [Decimal(str((item - avg) / std)) for item in float_values]


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


def _trend_strength(closes: list[Decimal], period: int) -> Decimal:
    """计算趋势强度指标。

    基于 EMA 斜率和方向一致性，值域 [-100, 100]。
    正值表示上涨趋势强度，负值表示下跌趋势强度。
    """
    if len(closes) < period:
        return Decimal("0")

    # 计算 EMA
    ema_values: list[Decimal] = []
    multiplier = Decimal("2") / Decimal(str(period + 1))
    ema_values.append(closes[0])

    for close in closes[1:]:
        ema = (close - ema_values[-1]) * multiplier + ema_values[-1]
        ema_values.append(ema)

    if len(ema_values) < 2:
        return Decimal("0")

    # 计算 EMA 斜率（变化方向）
    recent_emas = ema_values[-period:]
    up_count = sum(1 for i in range(1, len(recent_emas)) if recent_emas[i] > recent_emas[i - 1])
    down_count = sum(1 for i in range(1, len(recent_emas)) if recent_emas[i] < recent_emas[i - 1])

    # 方向一致性得分
    direction_score = Decimal(str(up_count - down_count)) / Decimal(str(period - 1)) * Decimal("100")

    return direction_score


def _momentum_accel(closes: list[Decimal], period: int) -> Decimal:
    """计算动量加速度。

    判断趋势是否在加速或减速。正值表示加速上涨，负值表示加速下跌。
    """
    if len(closes) < period * 2:
        return Decimal("0")

    # 计算两段时期的 ROC
    recent_closes = closes[-period:]
    previous_closes = closes[-period * 2:-period]

    if not recent_closes or not previous_closes:
        return Decimal("0")

    recent_roc = (recent_closes[-1] - recent_closes[0]) / recent_closes[0] * Decimal("100") if recent_closes[0] != 0 else Decimal("0")
    previous_roc = (previous_closes[-1] - previous_closes[0]) / previous_closes[0] * Decimal("100") if previous_closes[0] != 0 else Decimal("0")

    # 加速度 = 当前 ROC - 之前 ROC
    return recent_roc - previous_roc


def _volatility_contraction(candles: list[dict[str, Decimal | int]], period: int) -> Decimal:
    """计算波动收缩因子。

    识别突破前的能量积累。值越小表示波动越收缩，可能即将突破。
    返回当前 ATR 相对于历史平均 ATR 的比例。
    """
    if len(candles) < period * 2:
        return Decimal("50")

    # 计算当前 ATR
    current_atr = _atr(candles, period)

    # 计算历史 ATR 均值
    atr_values: list[Decimal] = []
    for i in range(period, len(candles)):
        atr = _atr(candles[:i + 1], period)
        atr_values.append(atr)

    if not atr_values:
        return Decimal("50")

    avg_atr = sum(atr_values) / len(atr_values)

    if avg_atr == 0:
        return Decimal("50")

    # 返回当前 ATR 相对于历史的比例（归一化到 0-100）
    ratio = current_atr / avg_atr
    return min(ratio * Decimal("50"), Decimal("100"))


def _volume_price_divergence(closes: list[Decimal], volumes: list[Decimal], period: int) -> Decimal:
    """计算量价背离因子。

    识别趋势衰竭信号。
    正值表示量价同向（健康趋势），负值表示量价背离（趋势可能衰竭）。
    """
    if len(closes) < period or len(volumes) < period:
        return Decimal("0")

    recent_closes = closes[-period:]
    recent_volumes = volumes[-period:]

    # 计算价格变化方向
    price_change = recent_closes[-1] - recent_closes[0]

    # 计算成交量变化
    avg_volume = sum(recent_volumes[:-1]) / len(recent_volumes[:-1]) if len(recent_volumes) > 1 else recent_volumes[0]
    current_volume = recent_volumes[-1]
    volume_change = current_volume - avg_volume

    if avg_volume == 0:
        return Decimal("0")

    # 量价同向得正分，反向得负分
    price_direction = 1 if price_change > 0 else -1 if price_change < 0 else 0
    volume_direction = 1 if volume_change > 0 else -1 if volume_change < 0 else 0

    divergence = Decimal(str(price_direction * volume_direction)) * Decimal("50")

    return divergence


def _bull_bear_ratio(candles: list[dict[str, Decimal | int]], period: int) -> Decimal:
    """计算多空力量对比。

    基于上涨下跌 K 线数量和强度。
    值 > 1 表示多头占优，值 < 1 表示空头占优。
    """
    if len(candles) < period:
        return Decimal("1")

    window = candles[-period:]

    bull_strength = Decimal("0")
    bear_strength = Decimal("0")

    for candle in window:
        body = candle["close"] - candle["open"]
        if body > 0:
            bull_strength += body
        else:
            bear_strength += abs(body)

    if bear_strength == 0:
        return Decimal("10")  # 全阳线

    return bull_strength / bear_strength


def evaluate_factor_ic_series(
    rows: list[dict[str, object]],
    factor_names: list[str] | None = None,
) -> list[dict[str, object]]:
    """计算因子 IC 时间序列。

    Args:
        rows: 带因子值和未来收益的样本行
        factor_names: 要计算的因子名称列表，默认为主因子

    Returns:
        IC 时间序列列表，每条记录包含 date, factor, ic, rank_ic, cumulative_ic
    """
    if not rows:
        return []

    # 默认使用所有主因子
    if factor_names is None:
        factor_names = list(PRIMARY_FEATURE_COLUMNS)

    if len(rows) < 10:
        return []

    ic_series: list[dict[str, object]] = []

    # 按时间分组计算 IC
    # 首先按日期分组
    rows_by_date: dict[str, list[dict[str, object]]] = {}
    for row in rows:
        generated_at = row.get("generated_at")
        if generated_at is None:
            continue
        try:
            from datetime import datetime, timezone
            ts = int(generated_at) / 1000
            date_str = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
        except (TypeError, ValueError, OSError):
            continue

        if date_str not in rows_by_date:
            rows_by_date[date_str] = []
        rows_by_date[date_str].append(row)

    # 对每个日期的每个因子计算 IC
    cumulative_ic: dict[str, float] = {factor: 0.0 for factor in factor_names}

    for date_str in sorted(rows_by_date.keys()):
        date_rows = rows_by_date[date_str]
        if len(date_rows) < 5:  # 样本太少跳过
            continue

        for factor in factor_names:
            factor_values = [_to_float_local(row.get(factor)) for row in date_rows]
            future_returns = [_to_float_local(row.get("future_return_pct")) for row in date_rows]

            # 计算 IC（皮尔逊相关系数）
            ic = _compute_ic(factor_values, future_returns)

            # 计算 Rank IC（秩相关系数）
            rank_ic = _compute_rank_ic(factor_values, future_returns)

            # 累积 IC
            cumulative_ic[factor] += ic

            ic_series.append({
                "date": date_str,
                "factor": factor,
                "ic": round(ic, 4),
                "rank_ic": round(rank_ic, 4),
                "cumulative_ic": round(cumulative_ic[factor], 4),
            })

    return ic_series


def evaluate_factor_quantile_nav(
    rows: list[dict[str, object]],
    factor_name: str = "ema20_gap_pct",
    num_quantiles: int = 5,
) -> list[dict[str, object]]:
    """计算因子分组收益序列。

    Args:
        rows: 带因子值和未来收益的样本行
        factor_name: 要分析的因子名称
        num_quantiles: 分组数量，默认 5

    Returns:
        分组收益序列列表，每条记录包含 date, q1-q5 净值, long_short 收益差
    """
    if not rows or len(rows) < 20:
        return []

    quantile_nav: list[dict[str, object]] = []

    # 按日期分组
    rows_by_date: dict[str, list[dict[str, object]]] = {}
    for row in rows:
        generated_at = row.get("generated_at")
        if generated_at is None:
            continue
        try:
            from datetime import datetime, timezone
            ts = int(generated_at) / 1000
            date_str = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
        except (TypeError, ValueError, OSError):
            continue

        if date_str not in rows_by_date:
            rows_by_date[date_str] = []
        rows_by_date[date_str].append(row)

    # 初始化各分组的净值
    quantile_navs = {f"q{i}": 1.0 for i in range(1, num_quantiles + 1)}

    # 对每个日期计算分组收益
    for date_str in sorted(rows_by_date.keys()):
        date_rows = rows_by_date[date_str]
        if len(date_rows) < num_quantiles:
            continue

        # 按因子值排序并分组
        sorted_rows = sorted(date_rows, key=lambda r: _to_float_local(r.get(factor_name)))
        group_size = len(sorted_rows) // num_quantiles

        if group_size < 1:
            continue

        # 计算各分组的平均收益
        group_returns: list[float] = []
        for i in range(num_quantiles):
            start_idx = i * group_size
            end_idx = start_idx + group_size if i < num_quantiles - 1 else len(sorted_rows)
            group_rows = sorted_rows[start_idx:end_idx]
            if not group_rows:
                group_returns.append(0.0)
                continue
            avg_return = sum(_to_float_local(r.get("future_return_pct")) for r in group_rows) / len(group_rows)
            group_returns.append(avg_return)

        # 更新净值
        for i, ret in enumerate(group_returns):
            key = f"q{i + 1}"
            quantile_navs[key] *= 1 + (ret / 100.0)

        # 计算多空收益（最高分组 - 最低分组）
        long_short = group_returns[-1] - group_returns[0] if group_returns else 0.0

        quantile_nav.append({
            "date": date_str,
            "q1": round(quantile_navs["q1"], 4),
            "q2": round(quantile_navs["q2"], 4),
            "q3": round(quantile_navs["q3"], 4),
            "q4": round(quantile_navs["q4"], 4),
            "q5": round(quantile_navs["q5"], 4),
            "long_short": round(long_short, 4),
        })

    return quantile_nav


def _to_float_local(value: object) -> float:
    """把任意值尽量转成 float。"""
    try:
        return float(Decimal(str(value)))
    except (TypeError, ValueError, InvalidOperation):
        return 0.0


def _compute_ic(x: list[float], y: list[float]) -> float:
    """计算皮尔逊相关系数（IC）。"""
    if not x or not y or len(x) != len(y):
        return 0.0

    n = len(x)
    if n < 2:
        return 0.0

    mean_x = sum(x) / n
    mean_y = sum(y) / n

    covariance = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n))
    variance_x = sum((x[i] - mean_x) ** 2 for i in range(n))
    variance_y = sum((y[i] - mean_y) ** 2 for i in range(n))

    if variance_x == 0 or variance_y == 0:
        return 0.0

    return covariance / ((variance_x ** 0.5) * (variance_y ** 0.5))


def _compute_rank_ic(x: list[float], y: list[float]) -> float:
    """计算秩相关系数（Rank IC）。"""
    if not x or not y or len(x) != len(y):
        return 0.0

    n = len(x)
    if n < 2:
        return 0.0

    # 计算秩
    def compute_ranks(values: list[float]) -> list[int]:
        sorted_pairs = sorted(enumerate(values), key=lambda p: p[1])
        ranks = [0] * n
        for rank, (idx, _) in enumerate(sorted_pairs):
            ranks[idx] = rank + 1
        return ranks

    ranks_x = compute_ranks(x)
    ranks_y = compute_ranks(y)

    # 计算秩相关系数
    mean_rx = sum(ranks_x) / n
    mean_ry = sum(ranks_y) / n

    covariance = sum((ranks_x[i] - mean_rx) * (ranks_y[i] - mean_ry) for i in range(n))
    variance_x = sum((ranks_x[i] - mean_rx) ** 2 for i in range(n))
    variance_y = sum((ranks_y[i] - mean_ry) ** 2 for i in range(n))

    if variance_x == 0 or variance_y == 0:
        return 0.0

    return covariance / ((variance_x ** 0.5) * (variance_y ** 0.5))
