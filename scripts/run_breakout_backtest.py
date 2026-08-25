"""波动率突破策略回测（合约双向 + 振幅过滤）。

策略逻辑：
- 波动率过滤：近 20 根平均振幅 < vol_floor 时不开仓（横盘期不做 T）
- 入场：单根放量突破（量比 >1.5 且 close 创 lookback 根新高/新低）
  → 突破向上做多 / 跌破向下做空
- 出场：止损 stop_pct、止盈 take_pct、或反向信号
- 杠杆 leverage（默认 2x），手续费双边 fee_pct

用法（服务器容器内）：
    cd /app && PYTHONPATH=/app python3 scripts/run_breakout_backtest.py

输出：每币与汇总的交易数/胜率/累计收益/最大回撤；TRAIN(70%)/TEST(30%) 分段验证。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT", "BNBUSDT"]
LOOKBACK = 20          # 平台窗口（根）
VOL_FLOOR = 1.0        # 振幅过滤：近20根均振幅低于此值%不开仓
VOL_SPIKE = 1.5        # 突破确认：当根振幅 >= 均振幅的倍数
VOLUME_RATIO = 1.5     # 放量倍数
STOP_PCT = 1.5         # 止损 %
TAKE_PCT = 4.0         # 止盈 %
LEVERAGE = 2           # 杠杆
FEE_PCT = 0.1          # 双边手续费 %
TRAIN_RATIO = 0.7


def load_klines(kline_dir: str, symbol: str) -> list[dict[str, Any]]:
    path = Path(kline_dir) / f"{symbol}_4h.jsonl"
    bars: list[dict[str, Any]] = []
    if not path.exists():
        return bars
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                bars.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    bars.sort(key=lambda b: int(b["open_time"]))
    return bars


def backtest_symbol(bars: list[dict[str, Any]], split_ratio: float = TRAIN_RATIO) -> dict[str, Any]:
    """单币回测，返回交易列表。返回字段含 train/test 标记。"""
    closes = [float(b["close"]) for b in bars]
    highs = [float(b["high"]) for b in bars]
    lows = [float(b["low"]) for b in bars]
    volumes = [float(b["volume"]) for b in bars]
    n = len(bars)
    trades: list[dict[str, Any]] = []

    position = None  # {"dir": "long"/"short", "entry": float, "bar": int}
    split_idx = int(n * split_ratio)

    for i in range(LOOKBACK, n):
        close = closes[i]

        # ---- 出场检查（先于入场）----
        if position is not None:
            entry = position["entry"]
            direction = position["dir"]
            pnl_pct = (close - entry) / entry * 100 * (1 if direction == "long" else -1) * LEVERAGE
            exit_reason = None
            if pnl_pct <= -STOP_PCT:
                exit_reason = "stop"
            elif pnl_pct >= TAKE_PCT:
                exit_reason = "take"
            if exit_reason:
                trades.append({
                    "symbol": position["symbol"],
                    "dir": direction,
                    "entry_bar": position["bar"],
                    "exit_bar": i,
                    "pnl_pct": round(pnl_pct - FEE_PCT * 2 * LEVERAGE, 4),
                    "segment": "train" if position["bar"] < split_idx else "test",
                    "reason": exit_reason,
                })
                position = None

        # ---- 波动率过滤：均振幅过低不做 ----
        window = bars[i - LOOKBACK : i]
        amps = [(float(w["high"]) - float(w["low"])) / float(w["close"]) * 100 for w in window]
        avg_amp = sum(amps) / len(amps)
        if avg_amp < VOL_FLOOR:
            continue

        # ---- 突破入场（无持仓时）----
        if position is not None:
            continue
        bar_high = highs[i]
        bar_low = lows[i]
        bar_amp = (bar_high - bar_low) / close * 100
        vol_avg = sum(volumes[i - LOOKBACK : i]) / LOOKBACK
        volume_spike = volumes[i] > vol_avg * VOLUME_RATIO
        if not volume_spike or bar_amp < avg_amp * VOL_SPIKE:
            continue

        prior_high = max(highs[i - LOOKBACK : i])
        prior_low = min(lows[i - LOOKBACK : i])
        segment = "train" if i < split_idx else "test"

        if close > prior_high:
            position = {"symbol": symbol, "dir": "long", "entry": close, "bar": i}
        elif close < prior_low:
            position = {"symbol": symbol, "dir": "short", "entry": close, "bar": i}

    # 强制平掉未平仓位（按最后收盘价结算）
    if position is not None:
        entry = position["entry"]
        direction = position["dir"]
        pnl = (closes[-1] - entry) / entry * 100 * (1 if direction == "long" else -1) * LEVERAGE
        trades.append({
            "symbol": position["symbol"], "dir": direction,
            "pnl_pct": round(pnl - FEE_PCT * 2 * LEVERAGE, 4),
            "segment": "train" if position["bar"] < split_idx else "test",
            "reason": "end",
        })
    return trades


def summarize(trades: list[dict[str, Any]], label: str) -> dict[str, Any]:
    if not trades:
        return {"label": label, "trades": 0}
    pnls = [t["pnl_pct"] for t in trades]
    wins = [p for p in pnls if p > 0]
    # 累计收益（复利近似：连乘）
    equity = 1.0
    peak = 1.0
    max_dd = 0.0
    for p in pnls:
        equity *= 1 + p / 100 / LEVERAGE  # pnl 已含杠杆，还原为净值变化
    # 简化：算术和
    total = sum(pnls)
    return {
        "label": label,
        "trades": len(trades),
        "win_rate": round(len(wins) / len(trades), 4),
        "total_pnl": round(total, 2),
        "avg_pnl": round(total / len(trades), 4),
        "max_loss": min(pnls),
    }


def main() -> int:
    kline_dir = sys.argv[1] if len(sys.argv) > 1 else "/app/.runtime/kline_store"
    all_trades: list[dict[str, Any]] = []
    for sym in SYMBOLS:
        bars = load_klines(kline_dir, sym)
        if len(bars) < LOOKBACK * 3:
            continue
        all_trades.extend(backtest_symbol(bars))
        print(f"{sym}: 完成", flush=True)

    train = [t for t in all_trades if t["segment"] == "train"]
    test = [t for t in all_trades if t["segment"] == "test"]

    print("\n=== 波动率突破策略回测（杠杆 %dx，止损 %.1f%%，止盈 %.1f%%）===" % (LEVERAGE, STOP_PCT, TAKE_PCT))
    for label, seg in (("TRAIN 段(前70%)", train), ("TEST 段(后30%, 样本外)", test)):
        s = summarize(seg, label)
        if s.get("trades"):
            print(
                f"{label}: 交易{s['trades']}次 | 胜率={s['win_rate']:.1%} | "
                f"累计收益={s['total_pnl']:+.1f}% | 单笔均={s['avg_pnl']:+.2f}% | 最大单亏={s['max_loss']:.1f}%"
            )
        else:
            print(f"{label}: 无交易")

    # 按方向拆分
    for d in ("long", "short"):
        dt = [t for t in all_trades if t["dir"] == d and t["segment"] == "test"]
        if dt:
            pnls = [t["pnl_pct"] for t in dt]
            wins = sum(1 for p in pnls if p > 0)
            print(f"{d} TEST: {len(dt)}次 胜率={wins/len(dt):.1%} 累计={sum(pnls):+.1f}%")

    verdict = "✅ 有正期望" if test and sum(t['pnl_pct'] for t in test) > 0 else "❌ 无正期望"
    print(verdict)
    with open("/tmp/breakout_backtest.json", "w", encoding="utf-8") as f:
        json.dump({"all_trades_count": len(all_trades), "test_summary": summarize(test, "test")}, f, ensure_ascii=False, indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
