"""ML 策略价格回放：只用模型信号和真实 OHLC，供 runner 与模型准入读取。"""
from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal

EVALUATION_VERSION = "ml_price_replay_v2"


def run_backtest(*, rows: list[dict[str, object]], holding_window: str,
                 fee_bps: Decimal | str | float | int = Decimal("0"),
                 slippage_bps: Decimal | str | float | int = Decimal("0"),
                 cost_model: str = "round_trip_basis_points",
                 signal_threshold: float = 0.5, stop_loss_pct: float = -8.0,
                 take_profit_pct: float = 8.0, max_holding_bars: int = 18,
                 max_positions: int | None = None) -> dict[str, object]:
    """验证输入后按价格回放，缺失必要数据时拒绝输出绩效。"""
    report = dict(holding_window=holding_window, evaluation_version=EVALUATION_VERSION,
                  evaluation_status="unavailable", metrics={}, series={"performance": []})
    try:
        fee, slippage = float(fee_bps), float(slippage_bps)
        if not all(math.isfinite(v) and 0 <= v < 10000 for v in (fee, slippage)):
            raise ValueError("手续费或滑点无效")
        if cost_model not in {"zero_cost_baseline", "single_side_basis_points", "round_trip_basis_points"}:
            raise ValueError("未知成本模型")
        # 每次成交均扣成本；单边模型把给定总成本平分到买卖两次。
        side_fee = 0 if cost_model == "zero_cost_baseline" else (fee + slippage) / 100
        if cost_model == "single_side_basis_points":
            side_fee /= 2
        normalized = _validated_rows(rows, signal_threshold)
        options = dict(stop_loss_pct=stop_loss_pct, take_profit_pct=take_profit_pct,
                       max_holding_bars=max_holding_bars, max_positions=max_positions)
        simulation = _replay(normalized, fee_pct=side_fee, **options)
        gross = _replay(normalized, fee_pct=0, **options)
    except (ValueError, TypeError, OverflowError) as exc:
        report["unavailable_reason"] = str(exc)
        return report
    trades = simulation["trades"]
    returns = simulation["bar_returns"]
    net_return = (simulation["final_nav"] - 1) * 100
    gross_return = (gross["final_nav"] - 1) * 100
    reasons = dict.fromkeys(("stop_loss", "take_profit", "signal_exit", "window_end", "end_of_series"), 0)
    for trade in trades:
        reasons[trade["exit_reason"]] += 1
    segments, switches = _signal_counts(normalized)
    report.update(evaluation_status="available", assumptions={
        "fee_bps": str(fee_bps), "slippage_bps": str(slippage_bps),
        "round_trip_cost_pct": _fmt(2 * side_fee), "cost_model": cost_model,
        "execution_rule": "next_asset_open", "switch_rule": "signal_flip_only",
        "segment_turnover_mode": "watch_to_action_segments", "position_mode": "long_only_shared_cash",
        "intrabar_rule": "stop_first_when_both_hit", "max_holding_bars": max_holding_bars,
        "max_positions": max_positions or len({r["symbol"] for r in normalized}),
        "signal_threshold": signal_threshold,
    }, metrics={
        "total_return_pct": _fmt(net_return), "gross_return_pct": _fmt(gross_return),
        "net_return_pct": _fmt(net_return), "cost_impact_pct": _fmt(gross_return - net_return),
        "max_drawdown_pct": _fmt(-simulation["max_drawdown_pct"]),
        "sharpe": _fmt(simulation["sharpe"]), "win_rate": _fmt(simulation["win_rate"]),
        "turnover": _fmt(len(trades) / len(normalized)), "sample_count": str(len(normalized)),
        "max_loss_streak": str(_max_loss_streak(returns)), "action_segment_count": str(segments),
        "direction_switch_count": str(switches), "trades_count": str(len(trades)),
        "final_nav": _fmt(simulation["final_nav"]), "exit_reasons": reasons,
    }, series={"performance": simulation["performance"]}, trades=trades)
    return report


def simulate_trades(rows: list[dict[str, object]], *, stop_loss_pct: float = -8.0,
                    take_profit_pct: float = 8.0, fee_pct: float = 0.1,
                    max_holding_bars: int = 18, signal_threshold: float = 0.5,
                    max_positions: int | None = None) -> dict[str, object]:
    """以独立币种持仓和共享现金回放；非法输入直接报错。"""
    return _replay(_validated_rows(rows, signal_threshold), stop_loss_pct=stop_loss_pct,
                   take_profit_pct=take_profit_pct, fee_pct=fee_pct,
                   max_holding_bars=max_holding_bars, max_positions=max_positions)


def _validated_rows(rows: list[dict[str, object]], threshold: float) -> list[dict]:
    """拒绝缺价格、缺预测、不合法时间或重复币种 K 线。"""
    if not rows:
        raise ValueError("缺少价格回放样本")
    if not math.isfinite(float(threshold)) or not 0 <= threshold <= 1:
        raise ValueError("预测阈值无效")
    normalized, previous = [], {}
    for raw in rows:
        try:
            row = {k: float(raw[k]) for k in ("open", "high", "low", "close")}
            row.update(symbol=str(raw["symbol"]).strip(), open_time=int(raw["open_time"]),
                       close_time=int(raw["close_time"]), generated_at=int(raw["generated_at"]))
            if not row["symbol"] or not all(math.isfinite(row[k]) and row[k] > 0 for k in ("open", "high", "low", "close")):
                raise ValueError("币种或真实价格无效")
            if row["low"] > min(row["open"], row["close"]) or row["high"] < max(row["open"], row["close"]) or row["high"] < row["low"]:
                raise ValueError("OHLC 价格范围无效")
            if row["open_time"] > row["close_time"] or row["generated_at"] != row["close_time"]:
                raise ValueError("预测必须在当前 K 线收盘生成")
            score = float(raw["prediction_score"]) if "prediction_score" in raw else 0.
            if not math.isfinite(score) or not 0 <= score <= 1:
                raise ValueError("模型概率无效")
            row["prediction_score"] = score
            if "model_signal" in raw:
                signal = str(raw["model_signal"])
                if signal not in {"buy", "sell", "watch"}:
                    raise ValueError("模型信号无效")
            else:
                if "prediction_score" not in raw:
                    raise ValueError("缺少模型预测字段：prediction_score")
                # 低概率只退出已有多仓，不能解释为做空信号。
                signal = "buy" if score >= threshold else "sell"
            row["model_signal"] = signal
            normalized.append(row)
        except KeyError as exc:
            raise ValueError(f"缺少真实价格或模型预测字段：{exc.args[0]}") from exc
    normalized.sort(key=lambda r: (r["open_time"], r["symbol"]))
    for row in normalized:
        prior = previous.get(row["symbol"])
        if prior is not None and row["open_time"] <= prior:
            raise ValueError("同币 K 线重复或时间重叠")
        previous[row["symbol"]] = row["close_time"]
    return normalized


def _replay(rows: list[dict], *, stop_loss_pct: float, take_profit_pct: float,
            fee_pct: float, max_holding_bars: int, max_positions: int | None) -> dict:
    """在开盘/收盘事件回放成交、逐币风险和账户净值。"""
    if not all(math.isfinite(float(v)) for v in (stop_loss_pct, take_profit_pct, fee_pct)) or not -100 < stop_loss_pct < 0 or take_profit_pct <= 0 or not 0 <= fee_pct < 100:
        raise ValueError("风险或成本参数无效")
    if max_holding_bars < 1 or (max_positions is not None and max_positions < 1):
        raise ValueError("持仓窗口或数量无效")
    capacity = max_positions or len({r["symbol"] for r in rows})
    events, last = defaultdict(lambda: {"open": [], "close": []}), {}
    for row in rows:
        events[row["open_time"]]["open"].append(row)
        events[row["close_time"]]["close"].append(row)
        last[row["symbol"]] = row["close_time"]
    cash, peak, previous_nav, max_dd = 1., 1., 1., 0.
    positions, pending, marks = {}, {}, {}
    trades, performance, returns = [], [], []
    cost = fee_pct / 100

    def equity():
        """按各币最新已知价格计价，未成交现金不会获得收益。"""
        return cash + sum(p["quantity"] * marks[s] for s, p in positions.items())

    def close_position(symbol, price, ts, reason):
        """按卖出价扣成本结算一笔独立持仓。"""
        nonlocal cash
        position = positions.pop(symbol)
        proceeds = position["quantity"] * price * (1 - cost)
        cash += proceeds
        trades.append(dict(symbol=symbol, entry_bar=position["entry_bar"], exit_bar=ts,
                           bars_held=position["bars_held"],
                           return_pct=(proceeds / position["budget"] - 1) * 100,
                           exit_reason=reason))

    for ts, event in sorted(events.items()):
        # 同时点先结算退出再分配预算，结果不依赖输入币种顺序。
        for row in event["open"]:
            symbol = row["symbol"]
            marks[symbol] = row["open"]
            if symbol in positions and pending.get(symbol) == "sell":
                close_position(symbol, row["open"], ts, "signal_exit")
        target_budget = equity() / capacity
        # 当前开盘只能读取上一根已收盘的分数，不能用本根收盘才生成的预测排名。
        for row in sorted(event["open"], key=lambda r: (-pending.get((r["symbol"], "score"), 0), r["symbol"])):
            symbol = row["symbol"]
            if pending.get(symbol) == "buy" and symbol not in positions and len(positions) < capacity and cash > 1e-12:
                budget = min(cash, target_budget)
                positions[symbol] = dict(quantity=budget / (row["open"] * (1 + cost)),
                                         entry_price=row["open"], budget=budget,
                                         entry_bar=ts, bars_held=0)
                cash -= budget
        # 收盘时采用本根已完成 OHLC；双触发保守按止损先成交，跳空按较差开盘价。
        for row in event["close"]:
            symbol = row["symbol"]
            marks[symbol] = row["close"]
            if symbol in positions:
                pos = positions[symbol]
                pos["bars_held"] += 1
                stop = pos["entry_price"] * (1 + stop_loss_pct / 100)
                take = pos["entry_price"] * (1 + take_profit_pct / 100)
                if row["low"] <= stop:
                    close_position(symbol, min(row["open"], stop), ts, "stop_loss")
                elif row["high"] >= take:
                    close_position(symbol, take, ts, "take_profit")
                elif pos["bars_held"] >= max_holding_bars:
                    close_position(symbol, row["close"], ts, "window_end")
                elif ts == last[symbol]:
                    close_position(symbol, row["close"], ts, "end_of_series")
            pending[symbol] = row["model_signal"]
            pending[(symbol, "score")] = row["prediction_score"]
        nav = equity()
        peak = max(peak, nav)
        drawdown = (nav / peak - 1) * 100
        max_dd = max(max_dd, -drawdown)
        if event["close"]:
            ret = (nav / previous_nav - 1) * 100
            returns.append(ret)
            performance.append(dict(date=datetime.fromtimestamp(ts / 1000, timezone.utc).strftime("%Y-%m-%d"),
                                    generated_at=ts, strategy_nav=round(nav, 8), benchmark_nav=1.,
                                    drawdown_pct=round(drawdown, 4), daily_return_pct=round(ret, 4), turnover=0.))
            previous_nav = nav
    final_nav = equity()
    return dict(trades=trades, trades_count=len(trades), final_nav=final_nav,
                max_drawdown_pct=max_dd, win_rate=sum(t["return_pct"] > 0 for t in trades) / len(trades) if trades else 0.,
                sharpe=_sharpe_ratio(returns), nav_series=[p["strategy_nav"] for p in performance],
                performance=performance, bar_returns=returns)


def _signal_counts(rows):
    """独立统计每币模型信号的动作段与买卖切换。"""
    previous, segments, switches = {}, 0, 0
    for row in rows:
        old, new = previous.get(row["symbol"], "watch"), row["model_signal"]
        segments += int(new != "watch" and new != old)
        switches += int(old in {"buy", "sell"} and new in {"buy", "sell"} and new != old)
        previous[row["symbol"]] = new
    return segments, switches


def _sharpe_ratio(returns):
    """计算逐时间段非年化 Sharpe，不把多日标签当逐根收益。"""
    if len(returns) < 2:
        return 0.
    mean = sum(returns) / len(returns)
    variance = sum((v - mean) ** 2 for v in returns) / len(returns)
    return mean / math.sqrt(variance) if variance > 0 else 0.


def _max_loss_streak(returns):
    """统计账户净值的最长连续亏损段。"""
    longest = current = 0
    for value in returns:
        current = current + 1 if value < 0 else 0
        longest = max(longest, current)
    return longest


def _fmt(value):
    """保留下游使用的指标字符串格式。"""
    return f"{value:.4f}"
