"""最小策略评估引擎。

这个文件只实现 `trend_breakout` 和 `trend_pullback` 的最小评估逻辑，供信号路由直接调用。
支持入场评分优化，评分>=阈值才触发买入。
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any


RESEARCH_LONG_THRESHOLD = Decimal("0.60")
RESEARCH_SHORT_THRESHOLD = Decimal("0.40")
MIN_ENTRY_SCORE_THRESHOLD = 0.60


def evaluate_trend_breakout(
    symbol: str,
    candles: list[dict[str, object]],
    timeframe: str,
    lookback_bars: int,
    breakout_buffer_pct: float | int | Decimal = 0,
) -> dict[str, object]:
    """根据最小 K 线序列评估趋势突破策略。"""

    normalized_symbol = symbol.strip().upper()
    normalized_timeframe = timeframe.strip()
    normalized_lookback_bars = int(lookback_bars)
    normalized_breakout_buffer_pct = _to_decimal(breakout_buffer_pct)
    parsed_candles = [_normalize_candle(candle) for candle in candles]
    valid_candles = [candle for candle in parsed_candles if candle is not None]

    if normalized_lookback_bars <= 0:
        return {
            "strategy_id": "trend_breakout",
            "symbol": normalized_symbol,
            "timeframe": normalized_timeframe,
            "lookback_bars": normalized_lookback_bars,
            "breakout_buffer_pct": _format_decimal(normalized_breakout_buffer_pct),
            "decision": "evaluation_unavailable",
            "reason": "invalid_lookback_bars",
            "overlays": _build_overlays(valid_candles),
        }

    if len(valid_candles) < 2:
        return {
            "strategy_id": "trend_breakout",
            "symbol": normalized_symbol,
            "timeframe": normalized_timeframe,
            "lookback_bars": normalized_lookback_bars,
            "breakout_buffer_pct": _format_decimal(normalized_breakout_buffer_pct),
            "decision": "evaluation_unavailable",
            "reason": "insufficient_valid_candles",
            "overlays": _build_overlays(valid_candles),
        }

    recent_candles = valid_candles[:-1][-normalized_lookback_bars:]
    latest_candle = valid_candles[-1]
    recent_high = max(candle["high"] for candle in recent_candles)
    recent_low = min(candle["low"] for candle in recent_candles)
    latest_close = latest_candle["close"]
    breakout_threshold = recent_high * (Decimal("1") + (normalized_breakout_buffer_pct / Decimal("100")))
    breakdown_threshold = recent_low * (Decimal("1") - (normalized_breakout_buffer_pct / Decimal("100")))

    if latest_close > breakout_threshold:
        decision = "signal"
        reason = "close_breaks_recent_high"
    elif latest_close < breakdown_threshold:
        decision = "block"
        reason = "close_breaks_recent_low"
    else:
        decision = "watch"
        reason = "close_stays_inside_recent_range"

    overlays = _build_overlays(valid_candles)
    overlays.update(
        {
            "recent_high": _format_decimal(recent_high),
            "recent_low": _format_decimal(recent_low),
            "latest_close": _format_decimal(latest_close),
            "history_bars_used": len(recent_candles),
            "breakout_threshold": _format_decimal(breakout_threshold),
            "breakdown_threshold": _format_decimal(breakdown_threshold),
        }
    )
    return {
        "strategy_id": "trend_breakout",
        "symbol": normalized_symbol,
        "timeframe": normalized_timeframe,
        "lookback_bars": normalized_lookback_bars,
        "breakout_buffer_pct": _format_decimal(normalized_breakout_buffer_pct),
        "decision": decision,
        "reason": reason,
        "overlays": overlays,
    }


def evaluate_trend_pullback(
    symbol: str,
    candles: list[dict[str, object]],
    timeframe: str,
    lookback_bars: int,
    pullback_depth_pct: float | int | Decimal = 0,
) -> dict[str, object]:
    """根据最小 K 线序列评估趋势回调策略。"""

    normalized_symbol = symbol.strip().upper()
    normalized_timeframe = timeframe.strip()
    normalized_lookback_bars = int(lookback_bars)
    normalized_pullback_depth_pct = _to_decimal(pullback_depth_pct)
    parsed_candles = [_normalize_candle(candle) for candle in candles]
    valid_candles = [candle for candle in parsed_candles if candle is not None]

    if normalized_lookback_bars <= 0:
        return {
            "strategy_id": "trend_pullback",
            "symbol": normalized_symbol,
            "timeframe": normalized_timeframe,
            "lookback_bars": normalized_lookback_bars,
            "pullback_depth_pct": _format_decimal(normalized_pullback_depth_pct),
            "decision": "evaluation_unavailable",
            "reason": "invalid_lookback_bars",
            "overlays": _build_overlays(valid_candles),
        }

    if len(valid_candles) < normalized_lookback_bars + 1:
        return {
            "strategy_id": "trend_pullback",
            "symbol": normalized_symbol,
            "timeframe": normalized_timeframe,
            "lookback_bars": normalized_lookback_bars,
            "pullback_depth_pct": _format_decimal(normalized_pullback_depth_pct),
            "decision": "evaluation_unavailable",
            "reason": "insufficient_history_for_lookback",
            "overlays": _build_overlays(valid_candles),
        }

    recent_candles = valid_candles[:-1][-normalized_lookback_bars:]
    latest_candle = valid_candles[-1]
    recent_high = max(candle["high"] for candle in recent_candles)
    recent_low = min(candle["low"] for candle in recent_candles)
    latest_close = latest_candle["close"]
    latest_low = latest_candle["low"]
    pullback_level = recent_high * (Decimal("1") - (normalized_pullback_depth_pct / Decimal("100")))
    invalidation_level = recent_low

    if latest_low < invalidation_level or latest_close < invalidation_level:
        decision = "block"
        reason = "structure_low_broken"
    elif latest_low <= pullback_level and latest_close >= pullback_level:
        decision = "signal"
        reason = "close_reclaims_pullback_level"
    else:
        decision = "watch"
        reason = "pullback_pending"

    overlays = _build_overlays(valid_candles)
    overlays.update(
        {
            "recent_high": _format_decimal(recent_high),
            "recent_low": _format_decimal(recent_low),
            "latest_close": _format_decimal(latest_close),
            "latest_low": _format_decimal(latest_low),
            "history_bars_used": len(recent_candles),
            "pullback_level": _format_decimal(pullback_level),
            "invalidation_level": _format_decimal(invalidation_level),
        }
    )
    return {
        "strategy_id": "trend_pullback",
        "symbol": normalized_symbol,
        "timeframe": normalized_timeframe,
        "lookback_bars": normalized_lookback_bars,
        "pullback_depth_pct": _format_decimal(normalized_pullback_depth_pct),
        "decision": decision,
        "reason": reason,
        "overlays": overlays,
    }


def apply_research_soft_gate(
    result: dict[str, object],
    research_summary: dict[str, object] | None,
) -> dict[str, object]:
    """把研究分数作为策略判断的软门控层。

    原策略仍然是主判断源，研究层只负责确认、压低或保持观望，不单独触发新信号。
    """

    gated_result = dict(result)
    decision = str(gated_result.get("decision", "watch"))
    reason = str(gated_result.get("reason", "unknown"))
    gated_result["confidence"] = _default_confidence(decision)
    gated_result["research_gate"] = _build_research_gate_payload("unavailable")

    if not isinstance(research_summary, dict):
        return gated_result

    score = _parse_optional_decimal(research_summary.get("score"))
    research_gate = _build_research_gate_payload("available", research_summary)
    gated_result["research_gate"] = research_gate
    if score is None:
        research_gate["status"] = "invalid_score"
        return gated_result

    if decision == "signal":
        if score >= RESEARCH_LONG_THRESHOLD:
            gated_result["reason"] = f"{reason}_research_confirmed"
            gated_result["confidence"] = "high"
            research_gate["status"] = "confirmed_by_research"
        elif score <= RESEARCH_SHORT_THRESHOLD:
            gated_result["decision"] = "watch"
            gated_result["reason"] = f"{reason}_soft_blocked_by_research"
            gated_result["confidence"] = "low"
            research_gate["status"] = "suppressed_by_research"
        else:
            gated_result["decision"] = "watch"
            gated_result["reason"] = f"{reason}_soft_blocked_by_neutral_research"
            gated_result["confidence"] = "low"
            research_gate["status"] = "suppressed_by_neutral_research"
        return gated_result

    if decision == "watch":
        if score >= RESEARCH_LONG_THRESHOLD:
            gated_result["confidence"] = "medium"
            research_gate["status"] = "supportive_but_not_triggering"
        elif score <= RESEARCH_SHORT_THRESHOLD:
            gated_result["confidence"] = "medium"
            research_gate["status"] = "caution_supported_by_research"
        else:
            research_gate["status"] = "neutral_research"
        return gated_result

    if decision == "block":
        if score <= RESEARCH_SHORT_THRESHOLD:
            gated_result["confidence"] = "high"
            research_gate["status"] = "confirmed_block_by_research"
        elif score >= RESEARCH_LONG_THRESHOLD:
            gated_result["confidence"] = "medium"
            research_gate["status"] = "block_despite_supportive_research"
        else:
            research_gate["status"] = "neutral_research"
        return gated_result

    research_gate["status"] = "not_applied"
    return gated_result


def _normalize_candle(candle: dict[str, object]) -> dict[str, Decimal] | None:
    """把输入 K 线转成可比较的数值结构。"""

    try:
        return {
            "open": Decimal(str(candle["open"])),
            "high": Decimal(str(candle["high"])),
            "low": Decimal(str(candle["low"])),
            "close": Decimal(str(candle["close"])),
        }
    except (KeyError, TypeError, ValueError, InvalidOperation):
        return None


def _build_overlays(candles: list[dict[str, Decimal]]) -> dict[str, object]:
    """返回评估用的最小覆盖信息。"""

    if not candles:
        return {"sample_size": 0}

    return {
        "sample_size": len(candles),
        "last_close": _format_decimal(candles[-1]["close"]),
    }


def _format_decimal(value: Decimal) -> str:
    """把数值统一成字符串，便于直接返回给前端。"""

    normalized = value.normalize()
    if normalized == normalized.to_integral():
        return str(normalized.quantize(Decimal("1")))
    return format(normalized, "f").rstrip("0").rstrip(".")


def _to_decimal(value: float | int | Decimal) -> Decimal:
    """把输入统一成 Decimal，便于做百分比计算。"""

    return Decimal(str(value))


def _parse_optional_decimal(value: object) -> Decimal | None:
    """把可选输入转成 Decimal。"""

    try:
        parsed = Decimal(str(value))
    except (TypeError, ValueError, InvalidOperation):
        return None
    if not parsed.is_finite():
        return None
    return parsed


def _default_confidence(decision: str) -> str:
    """给不同判断一个默认信心等级。"""

    if decision == "signal":
        return "medium"
    if decision == "block":
        return "medium"
    return "low"


def _build_research_gate_payload(
    status: str,
    research_summary: dict[str, object] | None = None,
) -> dict[str, str]:
    """统一研究门控返回结构。"""

    research_summary = research_summary or {}
    return {
        "status": status,
        "score": str(research_summary.get("score", "")),
        "signal": str(research_summary.get("signal", "")),
        "model_version": str(research_summary.get("model_version", "")),
        "explanation": str(research_summary.get("explanation", "")),
    }


def apply_scoring_gate(
    result: dict[str, object],
    symbol: str,
    market_data: dict[str, Any] | None = None,
) -> dict[str, object]:
    """把评分模型作为策略判断的入场门控层。

    原策略仍然是主判断源，评分层只负责确认入场信号是否满足阈值。
    评分>=阈值才触发买入信号。

    Args:
        result: 策略评估结果
        symbol: 交易标的符号
        market_data: 市场数据（用于评分计算）

    Returns:
        dict: 添加评分门控信息后的策略结果
    """
    from services.api.app.services.scoring.scoring_service import scoring_service

    gated_result = dict(result)
    decision = str(gated_result.get("decision", "watch"))
    reason = str(gated_result.get("reason", "unknown"))

    gated_result["scoring_gate"] = {
        "status": "unavailable",
        "total_score": None,
        "threshold": scoring_service.get_min_entry_score(),
        "passed": False,
        "factors": [],
    }

    if decision != "signal":
        # 只对signal决策应用评分门控
        return gated_result

    if market_data is None:
        market_data = {}

    # 计算评分
    scoring_result = scoring_service.calculate_score(symbol, market_data)

    gated_result["scoring_gate"] = {
        "status": "evaluated",
        "total_score": scoring_result.total_score,
        "threshold": scoring_result.threshold,
        "passed": scoring_result.passed_threshold,
        "factors": [f.to_dict() for f in scoring_result.factors],
    }

    if not scoring_result.passed_threshold:
        # 评分未达阈值，将signal降级为watch
        gated_result["decision"] = "watch"
        gated_result["reason"] = f"{reason}_blocked_by_scoring_threshold"
        gated_result["confidence"] = "low"
        gated_result["scoring_gate"]["status"] = "blocked_by_threshold"
    else:
        # 评分通过，确认signal
        gated_result["reason"] = f"{reason}_confirmed_by_scoring"
        gated_result["confidence"] = "high"
        gated_result["scoring_gate"]["status"] = "confirmed_by_scoring"

    return gated_result


def prepare_market_data_for_scoring(
    candles: list[dict[str, object]],
    indicators: dict[str, object] | None = None,
) -> dict[str, Any]:
    """从K线数据和指标准备评分所需的输入数据。

    Args:
        candles: K线数据列表
        indicators: 可选的技术指标数据

    Returns:
        dict: 评分模型所需的输入数据
    """
    if not candles:
        return {}

    # 解析K线数据
    valid_candles = [_normalize_candle(c) for c in candles]
    valid_candles = [c for c in valid_candles if c is not None]

    if not valid_candles:
        return {}

    # 计算基础指标
    closes = [c["close"] for c in valid_candles]
    volumes = [c.get("volume", Decimal("0")) for c in valid_candles if "volume" in c]

    latest_close = closes[-1]
    prev_close = closes[-2] if len(closes) > 1 else latest_close

    # 计算动量
    momentum = float(latest_close - prev_close) if len(closes) > 1 else 0

    # 计算ROC（变化率）
    roc = float((latest_close - prev_close) / prev_close * 100) if len(closes) > 1 and prev_close > 0 else 0

    # 计算波动率（简化版：最近几根K线的价格范围）
    recent_highs = [c["high"] for c in valid_candles[-5:]] if len(valid_candles) >= 5 else [c["high"] for c in valid_candles]
    recent_lows = [c["low"] for c in valid_candles[-5:]] if len(valid_candles) >= 5 else [c["low"] for c in valid_candles]
    price_range = float(max(recent_highs) - min(recent_lows)) / float(latest_close)
    volatility = min(price_range, 1.0)  # 限制在1以内

    # 计算成交量比率
    if volumes and len(volumes) > 1:
        avg_volume = sum(volumes[:-1]) / len(volumes[:-1])
        current_volume = volumes[-1] if volumes else Decimal("0")
        volume_ratio = float(current_volume / avg_volume) if avg_volume > 0 else 1.0
    else:
        volume_ratio = 1.0

    # 计算趋势（简化版：使用最近几根K线的斜率）
    if len(closes) >= 3:
        recent_closes = [float(c) for c in closes[-3:]]
        slope = (recent_closes[-1] - recent_closes[0]) / 2  # 简化斜率
        price_vs_trend = float(latest_close - closes[-3]) / float(closes[-3]) if closes[-3] > 0 else 0
    else:
        slope = 0
        price_vs_trend = 0

    data = {
        "momentum": momentum,
        "roc": roc,
        "volatility": volatility,
        "volume": {
            "current": float(volumes[-1] if volumes else 0),
            "average": float(sum(volumes) / len(volumes)) if volumes else 0,
        },
        "trend": {
            "slope": slope,
            "price_vs_trend": price_vs_trend,
        },
    }

    # 合入外部指标数据（如果提供）
    if indicators:
        if "rsi" in indicators:
            data["rsi"] = indicators["rsi"]
        if "macd" in indicators:
            data["macd"] = indicators["macd"]

    return data
