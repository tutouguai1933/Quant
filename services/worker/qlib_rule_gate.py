"""Qlib 规则层门控。

这个文件负责做最小的趋势、波动和量能过滤。
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation


def evaluate_rule_gate(
    feature_row: dict[str, object],
    *,
    research_template: str = "single_asset_timing",
) -> dict[str, object]:
    """根据最小特征判断当前是否允许进入候选区。"""

    ema20_gap = _to_decimal(feature_row.get("ema20_gap_pct"))
    ema55_gap = _to_decimal(feature_row.get("ema55_gap_pct"))
    atr_pct = _to_decimal(feature_row.get("atr_pct"))
    volume_ratio = _to_decimal(feature_row.get("volume_ratio"))

    if ema20_gap <= 0 or ema55_gap <= 0:
        return {"allowed": False, "reason": "trend_broken"}
    if research_template == "single_asset_timing_strict":
        if ema20_gap < Decimal("1.2") or ema55_gap < Decimal("1.8"):
            return {"allowed": False, "reason": "strict_template_not_confirmed"}
        if atr_pct >= Decimal("4.5"):
            return {"allowed": False, "reason": "strict_template_not_confirmed"}
        if volume_ratio < Decimal("1.05"):
            return {"allowed": False, "reason": "strict_template_not_confirmed"}
        return {"allowed": True, "reason": "ready"}
    if atr_pct >= Decimal("5"):
        return {"allowed": False, "reason": "volatility_too_high"}
    if volume_ratio < Decimal("1"):
        return {"allowed": False, "reason": "volume_not_confirmed"}
    return {"allowed": True, "reason": "ready"}


def _to_decimal(value: object) -> Decimal:
    """把输入统一转成十进制数值。"""

    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0")
