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
    """运行一次最小回测并返回统一指标（基于逐 K 线真实交易模拟）。"""

    gross_returns = [_to_float(item.get("future_return_pct")) for item in rows]
    fee_bps_decimal = _to_decimal(fee_bps)
    slippage_bps_decimal = _to_decimal(slippage_bps)
    round_trip_cost_pct = _resolve_cost_pct(
        fee_bps=fee_bps_decimal,
        slippage_bps=slippage_bps_decimal,
        cost_model=cost_model,
    )
    net_returns = [item - round_trip_cost_pct for item in gross_returns]

    # 单边手续费合计（simulate 内部开仓、平仓各扣一次 → 等价双边成本）
    sim_fee_pct = (
        0.0
        if cost_model == "zero_cost_baseline"
        else float(fee_bps_decimal + slippage_bps_decimal) / 100.0
    )
    # 逐 K 线真实交易模拟：信号开仓，止损/止盈/窗口结束平仓
    simulation = simulate_trades(
        rows,
        stop_loss_pct=-8.0,
        take_profit_pct=8.0,
        fee_pct=sim_fee_pct,
        max_holding_bars=18,
    )
    trades = simulation["trades"]
    net_trade_return = sum(float(t["return_pct"]) for t in trades)
    # 毛收益 = 净收益 + 每笔双边手续费；成本影响 = 手续费总额
    cost_impact = len(trades) * 2 * sim_fee_pct
    gross_trade_return = net_trade_return + cost_impact

    # 计算净值序列（strategy_nav 用模拟后的净值序列）
    performance_series = _build_performance_series(
        rows, net_returns, nav_series=simulation["nav_series"]
    )

    # 统计各平仓原因数量（四种原因都保留 0 计数）
    exit_reasons = {
        "stop_loss": 0,
        "take_profit": 0,
        "window_end": 0,
        "end_of_series": 0,
    }
    for trade in trades:
        reason = str(trade["exit_reason"])
        if reason in exit_reasons:
            exit_reasons[reason] += 1

    metrics = {
        "total_return_pct": _format_float(net_trade_return),
        "gross_return_pct": _format_float(gross_trade_return),
        "net_return_pct": _format_float(net_trade_return),
        "cost_impact_pct": _format_float(cost_impact),
        "max_drawdown_pct": _format_float(simulation["max_drawdown_pct"]),
        "sharpe": _format_float(simulation["sharpe"]),
        "win_rate": _format_float(simulation["win_rate"]),
        "turnover": _format_float(_turnover_ratio(rows)),
        "sample_count": str(len(rows)),
        "max_loss_streak": str(_max_loss_streak(net_returns)),
        "action_segment_count": str(_action_segment_count(rows)),
        "direction_switch_count": str(_direction_switch_count(rows)),
        "trades_count": str(simulation["trades_count"]),
        "final_nav": _format_float(simulation["final_nav"]),
        "exit_reasons": exit_reasons,
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
        "series": {
            "performance": performance_series,
        },
    }


def simulate_trades(
    rows: list[dict[str, object]],
    *,
    stop_loss_pct: float = -8.0,
    take_profit_pct: float = 8.0,
    fee_pct: float = 0.1,
    max_holding_bars: int = 18,
) -> dict[str, object]:
    """逐 K 线模拟交易：信号开仓，止损/止盈/窗口结束平仓。

    每行样本的 future_return_pct 视为"持有一根 K 线的收益率"。
    遇到 label=buy 开仓，后续每根累计收益；触达 stop_loss 或 take_profit
    平仓，或持有 max_holding_bars 根后按窗口结束平仓。
    """

    trades: list[dict[str, object]] = []
    position: dict[str, object] | None = None
    nav = 1.0
    nav_series: list[float] = []
    peak_nav = 1.0
    max_drawdown = 0.0
    wins = 0

    for row in rows:
        ret = float(row.get("future_return_pct", 0.0) or 0.0)
        if position is None and str(row.get("label", "")) == "buy":
            position = {
                "entry_bar": row.get("generated_at"),
                "bars_held": 0,
                "cum_return": -fee_pct,  # 开仓手续费
            }
            nav_series.append(nav)  # 开仓当根净值不变，保证序列与样本行数对齐
            continue
        if position is not None:
            position["bars_held"] += 1
            position["cum_return"] += ret
            cum = float(position["cum_return"])
            exit_reason = None
            if cum <= stop_loss_pct:
                exit_reason = "stop_loss"
            elif cum >= take_profit_pct:
                exit_reason = "take_profit"
            elif position["bars_held"] >= max_holding_bars:
                exit_reason = "window_end"
            if exit_reason:
                cum -= fee_pct  # 平仓手续费
                profit = cum
                nav *= 1 + profit / 100.0
                if profit > 0:
                    wins += 1
                trades.append({
                    "entry_bar": position["entry_bar"],
                    "exit_bar": row.get("generated_at"),
                    "bars_held": position["bars_held"],
                    "return_pct": round(profit, 4),
                    "exit_reason": exit_reason,
                })
                position = None
        nav_series.append(nav)
        peak_nav = max(peak_nav, nav)
        max_drawdown = max(max_drawdown, (peak_nav - nav) / peak_nav * 100)

    if position is not None:
        # 序列结束时仍持仓：按当前累计收益平仓
        profit = float(position["cum_return"]) - fee_pct
        nav *= 1 + profit / 100.0
        if profit > 0:
            wins += 1
        trades.append({
            "entry_bar": position["entry_bar"],
            "exit_bar": "end",
            "bars_held": position["bars_held"],
            "return_pct": round(profit, 4),
            "exit_reason": "end_of_series",
        })

    total = len(trades)
    return {
        "trades": trades,
        "trades_count": total,
        "final_nav": round(nav, 4),
        "max_drawdown_pct": round(max_drawdown, 4),
        "win_rate": round(wins / total, 4) if total else 0.0,
        "sharpe": _sharpe_ratio([t["return_pct"] for t in trades]) if total else 0.0,
        "nav_series": nav_series,
    }


def _resolve_cost_pct(*, fee_bps: Decimal, slippage_bps: Decimal, cost_model: str) -> float:
    """按成本模型计算净收益扣减比例。"""

    if cost_model == "zero_cost_baseline":
        return 0.0
    if cost_model == "single_side_basis_points":
        return float((fee_bps + slippage_bps) / Decimal("100"))
    return float((fee_bps + slippage_bps) * Decimal("2") / Decimal("100"))


def _build_performance_series(
    rows: list[dict[str, object]],
    net_returns: list[float],
    nav_series: list[float] | None = None,
) -> list[dict[str, object]]:
    """构建净值序列数据。

    Args:
        rows: 原始样本行
        net_returns: 扣除成本后的净收益列表
        nav_series: 模拟交易后的净值序列（与 rows 逐行对齐），为空时退回按净收益累计

    Returns:
        净值序列列表，包含 date, strategy_nav, benchmark_nav, drawdown_pct
    """
    if not rows or not net_returns:
        return []

    series: list[dict[str, object]] = []
    strategy_nav = 1.0  # 策略净值，初始为 1
    benchmark_nav = 1.0  # 基准净值，初始为 1
    peak_nav = 1.0  # 用于计算回撤的峰值净值

    for index, (row, net_return) in enumerate(zip(rows, net_returns)):
        # 更新净值：优先使用模拟后的净值序列，否则按净收益累计
        if nav_series is not None and index < len(nav_series):
            strategy_nav = nav_series[index]
        else:
            strategy_nav *= 1 + (net_return / 100.0)
        benchmark_nav *= 1 + (0.0 / 100.0)  # 基准净值保持不变或按需调整

        # 更新峰值并计算回撤
        peak_nav = max(peak_nav, strategy_nav)
        drawdown_pct = ((strategy_nav / peak_nav) - 1.0) * 100.0

        # 解析日期
        generated_at = row.get("generated_at")
        if generated_at is not None:
            try:
                from datetime import datetime, timezone
                ts = int(generated_at) / 1000
                date_str = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
            except (TypeError, ValueError, OSError):
                date_str = ""
        else:
            date_str = ""

        series.append({
            "date": date_str,
            "strategy_nav": round(strategy_nav, 4),
            "benchmark_nav": round(benchmark_nav, 4),
            "drawdown_pct": round(drawdown_pct, 4),
            "daily_return_pct": round(net_return, 4),
            "turnover": round(_to_float(row.get("turnover", 0)), 4),
        })

    return series


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
