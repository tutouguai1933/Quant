"""Qlib 规则层门控。

这个文件负责做最小的趋势、波动和量能过滤。
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation


def evaluate_rule_gate(
    feature_row: dict[str, object],
    *,
    research_template: str = "single_asset_timing",
    thresholds: dict[str, object] | None = None,
) -> dict[str, object]:
    """根据最小特征判断当前是否允许进入候选区。"""

    resolved_thresholds = _resolve_thresholds(thresholds)
    ema20_gap = _to_decimal(feature_row.get("ema20_gap_pct"))
    ema55_gap = _to_decimal(feature_row.get("ema55_gap_pct"))
    atr_pct = _to_decimal(feature_row.get("atr_pct"))
    volume_ratio = _to_decimal(feature_row.get("volume_ratio"))

    if ema20_gap <= resolved_thresholds["rule_min_ema20_gap_pct"] or ema55_gap <= resolved_thresholds["rule_min_ema55_gap_pct"]:
        return {"allowed": False, "reason": "trend_broken"}
    if research_template == "single_asset_timing_strict":
        if (
            ema20_gap < resolved_thresholds["strict_rule_min_ema20_gap_pct"]
            or ema55_gap < resolved_thresholds["strict_rule_min_ema55_gap_pct"]
        ):
            return {"allowed": False, "reason": "strict_template_not_confirmed"}
        if atr_pct >= resolved_thresholds["strict_rule_max_atr_pct"]:
            return {"allowed": False, "reason": "strict_template_not_confirmed"}
        if volume_ratio < resolved_thresholds["strict_rule_min_volume_ratio"]:
            return {"allowed": False, "reason": "strict_template_not_confirmed"}
        return {"allowed": True, "reason": "ready"}
    if atr_pct >= resolved_thresholds["rule_max_atr_pct"]:
        return {"allowed": False, "reason": "volatility_too_high"}
    if volume_ratio < resolved_thresholds["rule_min_volume_ratio"]:
        return {"allowed": False, "reason": "volume_not_confirmed"}
    return {"allowed": True, "reason": "ready"}


def _resolve_thresholds(value: dict[str, object] | None) -> dict[str, Decimal]:
    """整理规则门阈值。"""

    payload = dict(value or {})
    base_ema20 = _to_decimal(payload.get("rule_min_ema20_gap_pct") or "0")
    base_ema55 = _to_decimal(payload.get("rule_min_ema55_gap_pct") or "0")
    base_atr = _to_decimal(payload.get("rule_max_atr_pct") or "5")
    base_volume = _to_decimal(payload.get("rule_min_volume_ratio") or "1")
    return {
        "rule_min_ema20_gap_pct": base_ema20,
        "rule_min_ema55_gap_pct": base_ema55,
        "rule_max_atr_pct": base_atr,
        "rule_min_volume_ratio": base_volume,
        "strict_rule_min_ema20_gap_pct": _to_decimal(payload.get("strict_rule_min_ema20_gap_pct") or (base_ema20 + Decimal("1.2"))),
        "strict_rule_min_ema55_gap_pct": _to_decimal(payload.get("strict_rule_min_ema55_gap_pct") or (base_ema55 + Decimal("1.8"))),
        "strict_rule_max_atr_pct": _to_decimal(payload.get("strict_rule_max_atr_pct") or max(base_atr - Decimal("0.5"), Decimal("0.1"))),
        "strict_rule_min_volume_ratio": _to_decimal(payload.get("strict_rule_min_volume_ratio") or (base_volume + Decimal("0.05"))),
    }


def _to_decimal(value: object) -> Decimal:
    """把输入统一转成十进制数值。"""

    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0")
