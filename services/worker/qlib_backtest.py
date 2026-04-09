"""Qlib 最小回测工具。

这个文件负责根据未来收益样本输出稳定的核心回测指标。
"""

from __future__ import annotations

import math
from decimal import Decimal, InvalidOperation


def run_backtest(
    *,
    rows: list[dict[str, object]],
    holding_window: str,
    fee_bps: Decimal | str | float | int = Decimal("0"),
    slippage_bps: Decimal | str | float | int = Decimal("0"),
    cost_model: str = "round_trip_basis_points",
) -> dict[str, object]:
    """运行一次最小回测并返回统一指标。"""

    gross_returns = [_to_float(item.get("future_return_pct")) for item in rows]
    fee_bps_decimal = _to_decimal(fee_bps)
    slippage_bps_decimal = _to_decimal(slippage_bps)
    round_trip_cost_pct = _resolve_cost_pct(
        fee_bps=fee_bps_decimal,
        slippage_bps=slippage_bps_decimal,
        cost_model=cost_model,
    )
    net_returns = [item - round_trip_cost_pct for item in gross_returns]

    metrics = {
        "total_return_pct": _format_float(sum(net_returns)),
        "gross_return_pct": _format_float(sum(gross_returns)),
        "net_return_pct": _format_float(sum(net_returns)),
        "cost_impact_pct": _format_float(sum(gross_returns) - sum(net_returns)),
        "max_drawdown_pct": _format_float(_max_drawdown_pct(net_returns)),
        "sharpe": _format_float(_sharpe_ratio(net_returns)),
        "win_rate": _format_float(_win_rate(net_returns)),
        "turnover": _format_float(_turnover_ratio(rows)),
        "sample_count": str(len(rows)),
        "max_loss_streak": str(_max_loss_streak(net_returns)),
        "action_segment_count": str(_action_segment_count(rows)),
        "direction_switch_count": str(_direction_switch_count(rows)),
    }
    return {
        "holding_window": holding_window,
        "assumptions": {
            "fee_bps": str(fee_bps_decimal),
            "slippage_bps": str(slippage_bps_decimal),
            "round_trip_cost_pct": _format_float(round_trip_cost_pct),
            "cost_model": str(cost_model),
            "switch_rule": "signal_flip_only",
            "segment_turnover_mode": "watch_to_action_segments",
        },
        "metrics": metrics,
    }


def _resolve_cost_pct(*, fee_bps: Decimal, slippage_bps: Decimal, cost_model: str) -> float:
    """按成本模型计算净收益扣减比例。"""

    if cost_model == "zero_cost_baseline":
        return 0.0
    if cost_model == "single_side_basis_points":
        return float((fee_bps + slippage_bps) / Decimal("100"))
    return float((fee_bps + slippage_bps) * Decimal("2") / Decimal("100"))


def _max_drawdown_pct(returns: list[float]) -> float:
    """根据累计收益计算最大回撤。"""

    equity = 1.0
    peak = 1.0
    max_drawdown = 0.0
    for item in returns:
        equity *= 1 + (item / 100.0)
        peak = max(peak, equity)
        if peak == 0:
            continue
        drawdown = ((equity / peak) - 1.0) * 100.0
        max_drawdown = min(max_drawdown, drawdown)
    return max_drawdown


def _sharpe_ratio(returns: list[float]) -> float:
    """计算最小 Sharpe。"""

    if len(returns) < 2:
        return 0.0
    average = sum(returns) / len(returns)
    variance = sum((item - average) ** 2 for item in returns) / len(returns)
    if variance <= 0:
        return 0.0
    return average / math.sqrt(variance)


def _win_rate(returns: list[float]) -> float:
    """计算正收益占比。"""

    if not returns:
        return 0.0
    return sum(1 for item in returns if item > 0) / len(returns)


def _turnover_ratio(rows: list[dict[str, object]]) -> float:
    """按动作段数量计算最小换手。"""

    if not rows:
        return 0.0

    turnover_count = 0
    previous_direction = "watch"
    for row in rows:
        raw_direction = str(row.get("label", "")).strip() or "watch"
        current_direction = raw_direction if raw_direction in {"buy", "sell"} else "watch"
        if current_direction != "watch" and previous_direction == "watch":
            turnover_count += 1
        previous_direction = current_direction
    return turnover_count / len(rows)


def _action_segment_count(rows: list[dict[str, object]]) -> int:
    """统计从空档进入动作段的次数。"""

    if not rows:
        return 0
    count = 0
    previous_direction = "watch"
    for row in rows:
        current_direction = _normalize_direction(row.get("label"))
        if current_direction != "watch" and current_direction != previous_direction:
            count += 1
        previous_direction = current_direction
    return count


def _direction_switch_count(rows: list[dict[str, object]]) -> int:
    """统计动作段内部从买切到卖或从卖切到买的次数。"""

    switch_count = 0
    previous_direction = "watch"
    for row in rows:
        current_direction = _normalize_direction(row.get("label"))
        if previous_direction in {"buy", "sell"} and current_direction in {"buy", "sell"} and current_direction != previous_direction:
            switch_count += 1
        previous_direction = current_direction
    return switch_count


def _max_loss_streak(returns: list[float]) -> int:
    """计算最长连续亏损段。"""

    longest = 0
    current = 0
    for item in returns:
        if item < 0:
            current += 1
            longest = max(longest, current)
            continue
        current = 0
    return longest


def _normalize_direction(value: object) -> str:
    """把标签统一成动作方向。"""

    raw = str(value or "").strip()
    return raw if raw in {"buy", "sell"} else "watch"


def _to_float(value: object) -> float:
    """把任意值尽量转成 float。"""

    try:
        return float(Decimal(str(value)))
    except (TypeError, ValueError, InvalidOperation):
        return 0.0


def _to_decimal(value: object) -> Decimal:
    """把任意值尽量转成 Decimal。"""

    try:
        return Decimal(str(value))
    except (TypeError, ValueError, InvalidOperation):
        return Decimal("0")


def _format_float(value: float) -> str:
    """把浮点数转成统一字符串。"""

    return f"{value:.4f}"
