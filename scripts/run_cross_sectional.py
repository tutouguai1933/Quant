"""横截面相对强弱特征实验：基础特征 vs 基础+横截面特征。

用法（服务器容器内）：
    cd /app && PYTHONPATH=/app python3 scripts/run_cross_sectional.py

横截面特征（比赛四家策略的核心思路——不比"绝对涨跌"，比"谁相对更强"）：
- rel_strength_20：该币近 20 根 4h 收益率 - 16 币中位数（截面超额收益）
- vs_btc_20：该币近 20 根收益 - BTC 近 20 根收益（相对大盘强弱）
- cross_rank：该币收益在 16 币中的分位排名（0-1，纯截面位置）
- market_regime：16 币平均近 20 根收益率（市场整体状态，全币共享）

验证两件事：
1. 模型 AUC：基础 vs 基础+横截面（看特征是否提升预测）
2. 选币效果：模拟"买横截面最强的 top-3" 的收益，对比"绝对分数>0.45 才买"（现系统）

结果写 /tmp/cross_sectional_result.json
"""

from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
from typing import Any

from scripts.run_label_sweep import build_labeled_rows, SYMBOLS, load_klines

OPT_LABEL_CONFIG = {
    "name": "opt_close_only_2pct_2-5d",
    "label_mode": "close_only",
    "target": "2",
    "stop": "-1",
    "min_days": 2,
    "max_days": 5,
}

BASE_FEATURE_COLS = [
    "close_return_pct", "range_pct", "body_pct", "volume_ratio",
    "trend_gap_pct", "ema20_gap_pct", "ema55_gap_pct", "atr_pct",
    "breakout_strength", "roc6", "trend_strength", "momentum_accel",
    "volatility_contraction", "volume_price_divergence",
    "bull_bear_ratio", "taker_buy_ratio", "btc_correlation",
]

CROSS_COLS = ["rel_strength_20", "vs_btc_20", "cross_rank", "market_regime"]

LOOKBACK_BARS = 20


def add_cross_features(rows: list[dict[str, Any]], kline_dir: str) -> list[dict[str, Any]]:
    """给每行追加横截面特征（用真实 K 线价格计算）。

    1. 加载每币 4h K 线，建立 close_time -> 近 20 根累计收益 的映射
    2. 按时间点分组：计算该时点 16 币的截面统计（中位数/均值/分位）
    3. 写回每行：rel_strength_20 / vs_btc_20 / cross_rank / market_regime
    """
    # 每币 K 线：close_time -> 近 20 根累计收益率（含该根）
    symbol_momentum: dict[str, dict[int, float]] = {}
    for symbol in SYMBOLS:
        candles = load_klines(kline_dir, symbol, "4h")
        if len(candles) < LOOKBACK_BARS:
            continue
        closes = [float(c["close"]) for c in candles]
        symbol_momentum[symbol] = {}
        for idx, candle in enumerate(candles):
            if idx >= LOOKBACK_BARS - 1:
                ret_20 = (closes[idx] - closes[idx - LOOKBACK_BARS + 1]) / closes[idx - LOOKBACK_BARS + 1] * 100.0
            elif idx >= 1:
                ret_20 = (closes[idx] - closes[0]) / closes[0] * 100.0
            else:
                ret_20 = 0.0
            symbol_momentum[symbol][int(candle["close_time"])] = ret_20

    # 按时间点分组计算截面统计
    ts_groups: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        symbol = str(row.get("symbol", ""))
        ts = int(row.get("generated_at", 0))
        mom_map = symbol_momentum.get(symbol)
        if mom_map is None:
            continue
        row["_mom20"] = mom_map.get(ts)
        ts_groups[ts].append(row)

    enriched: list[dict[str, Any]] = []
    for ts in sorted(ts_groups.keys()):
        group = ts_groups[ts]
        valid = [r for r in group if r.get("_mom20") is not None]
        if len(valid) < 3:
            for r in group:
                r.pop("_mom20", None)
            enriched.extend(group)
            continue
        import statistics

        moments = [float(r["_mom20"]) for r in valid]
        median_mom = statistics.median(moments)
        btc_mom = next((float(r["_mom20"]) for r in valid if r.get("symbol") == "BTCUSDT"), median_mom)
        market_regime = statistics.mean(moments)
        ranked = sorted(moments)

        def rank_pct(v: float) -> float:
            below = sum(1 for x in ranked if x <= v)
            return round(below / len(ranked), 4)

        for row in group:
            if row.get("_mom20") is None:
                row.pop("_mom20", None)
                enriched.append(row)
                continue
            mom = float(row["_mom20"])
            row["rel_strength_20"] = round(mom - median_mom, 6)
            row["vs_btc_20"] = round(mom - btc_mom, 6)
            row["cross_rank"] = rank_pct(mom)
            row["market_regime"] = round(market_regime, 6)
            row.pop("_mom20", None)
            enriched.append(row)
    return enriched


def train_evaluate(rows: list[dict[str, Any]], feature_cols: list[str]) -> dict[str, Any]:
    """训练并评估（75/25 时间切分）。"""
    from services.worker.ml.trainer import ModelTrainer

    ordered = sorted(rows, key=lambda r: int(r.get("generated_at", 0)))
    split_idx = int(len(ordered) * 0.75)
    train_rows, val_rows = ordered[:split_idx], ordered[split_idx:]

    trainer = ModelTrainer(
        model_type="lightgbm",
        model_params={
            "objective": "binary",
            "learning_rate": 0.05,
            "num_leaves": 31,
            "n_estimators": 200,
            "early_stopping_rounds": 20,
            "verbosity": -1,
        },
        label_column="future_return_pct",
    )
    result = trainer.train(
        training_rows=train_rows,
        validation_rows=val_rows,
        feature_columns=tuple(feature_cols),
    )
    return {
        "train_samples": len(train_rows),
        "val_samples": len(val_rows),
        "train_auc": round(float(result.metrics.get("train_auc", 0)), 4),
        "val_auc": round(float(result.metrics.get("val_auc", 0)), 4),
        "model": result.model,
        "val_rows": val_rows,
    }


def simulate_top_k_picking(val_rows: list[dict[str, Any]], model: Any, k: int = 3) -> dict[str, Any]:
    """模拟"买相对最强的 top-k"的收益（用模型的绝对分数排序，横截面选币）。

    每个时间点：按模型分数排序，买 top-k，按未来收益结算。
    """
    import numpy as np

    ts_groups: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in val_rows:
        ts_groups[int(row["generated_at"])].append(row)

    returns: list[float] = []
    for ts in sorted(ts_groups.keys()):
        group = ts_groups[ts]
        if len(group) < k:
            continue
        X = np.array([[float(r.get(c, 0)) for c in BASE_FEATURE_COLS] for r in group])
        proba = model.predict_proba(X)
        scores = proba[:, 1] if proba.ndim > 1 else proba
        order = np.argsort(-scores)[:k]
        pick_returns = [float(group[i].get("future_return_pct", 0)) for i in order]
        returns.append(sum(pick_returns) / k)  # 等权 top-k 平均收益

    if not returns:
        return {"avg_return": 0.0, "positive_rate": 0.0, "rounds": 0}
    return {
        "avg_return": round(sum(returns) / len(returns), 4),
        "positive_rate": round(sum(1 for r in returns if r > 0) / len(returns), 4),
        "rounds": len(returns),
    }


def main() -> int:
    kline_dir = sys.argv[1] if len(sys.argv) > 1 else "/app/.runtime/kline_store"
    started = time.time()

    rows = build_labeled_rows(
        kline_dir=kline_dir,
        symbols=SYMBOLS,
        interval="4h",
        label_config=OPT_LABEL_CONFIG,
    )
    print(f"基础样本: {len(rows)}", flush=True)

    # 实验 A：基础特征
    print("\n=== 实验 A: 基础 17 特征 ===", flush=True)
    base_result = train_evaluate([dict(r) for r in rows], BASE_FEATURE_COLS)
    print(f"  val_auc={base_result['val_auc']} train_auc={base_result['train_auc']}", flush=True)
    topk_base = simulate_top_k_picking(base_result["val_rows"], base_result["model"])
    print(f"  top-3 选币: 平均收益={topk_base['avg_return']}% 胜率={topk_base['positive_rate']} 轮数={topk_base['rounds']}", flush=True)

    # 实验 B：基础 + 横截面特征
    print("\n=== 实验 B: 基础 + 横截面 4 特征 ===", flush=True)
    enriched = add_cross_features([dict(r) for r in rows], kline_dir)
    cross_result = train_evaluate(enriched, BASE_FEATURE_COLS + CROSS_COLS)
    print(f"  val_auc={cross_result['val_auc']} train_auc={cross_result['train_auc']}", flush=True)
    topk_cross = simulate_top_k_picking(cross_result["val_rows"], cross_result["model"])
    print(f"  top-3 选币: 平均收益={topk_cross['avg_return']}% 胜率={topk_cross['positive_rate']} 轮数={topk_cross['rounds']}", flush=True)

    print("\n=== 对比结果 ===")
    print(f"基础:       val_auc={base_result['val_auc']} | top-3 平均收益={topk_base['avg_return']}%")
    print(f"+横截面:    val_auc={cross_result['val_auc']} | top-3 平均收益={topk_cross['avg_return']}%")
    print(f"耗时 {time.time() - started:.1f}s")

    with open("/tmp/cross_sectional_result.json", "w", encoding="utf-8") as f:
        json.dump({
            "base": {"val_auc": base_result["val_auc"], "topk": topk_base},
            "cross": {"val_auc": cross_result["val_auc"], "topk": topk_cross},
        }, f, ensure_ascii=False, indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
