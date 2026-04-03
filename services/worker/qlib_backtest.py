"""Qlib 最小回测工具。

这个文件负责根据未来收益样本输出稳定的核心回测指标。
"""

from __future__ import annotations

import math
from decimal import Decimal, InvalidOperation


def run_backtest(*, rows: list[dict[str, object]], holding_window: str) -> dict[str, object]:
    """运行一次最小回测并返回统一指标。"""

    returns = [_to_float(item.get("future_return_pct")) for item in rows]

    metrics = {
        "total_return_pct": _format_float(sum(returns)),
        "max_drawdown_pct": _format_float(_max_drawdown_pct(returns)),
        "sharpe": _format_float(_sharpe_ratio(returns)),
        "win_rate": _format_float(_win_rate(returns)),
        "turnover": _format_float(_turnover_ratio(rows)),
    }
    return {"holding_window": holding_window, "metrics": metrics}


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


def _to_float(value: object) -> float:
    """把任意值尽量转成 float。"""

    try:
        return float(Decimal(str(value)))
    except (TypeError, ValueError, InvalidOperation):
        return 0.0


def _format_float(value: float) -> str:
    """把浮点数转成统一字符串。"""

    return f"{value:.4f}"
