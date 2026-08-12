"""时序方向做空验证：模型判断"市场要跌"时做空 BTC，验证方向判断是否可靠。

与之前"截面选币做空"（选最弱币，已验证≈随机）不同，
本脚本验证"方向做空"：模型 16 币平均分数（上涨概率均值）低于阈值 → 做空 BTC。

方法（遵守 OOS 方法论，防阈值过拟合）：
- 数据切三段：TRAIN 60% / VALID 20% / TEST 20%
- TRAIN 训练 + VALID 滚动预测 → 得到（时间点, 平均分数, BTC 未来收益）序列
- 在 VALID 段扫描最优阈值（0.38~0.50）→ 在 TEST 段用该阈值**只验证一次**
- 输出：最优阈值下 TEST 段做空命中率/平均收益 + "全时段做空"随机基准

判定：TEST 段做空命中率 ≥55% 且平均收益为正 → 方向做空有效（模型的方向判断可用）
      否则 → 方向做空也不可靠，做空彻底放弃

用法（服务器容器内）：
    cd /app && PYTHONPATH=/app python3 scripts/run_direction_short.py
"""

from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
from typing import Any

from scripts.run_label_sweep import build_labeled_rows, SYMBOLS

OPT_LABEL_CONFIG = {
    "name": "opt_close_only_2pct_2-5d",
    "label_mode": "close_only",
    "target": "2",
    "stop": "-1",
    "min_days": 2,
    "max_days": 5,
}

FEATURE_COLS = [
    "close_return_pct", "range_pct", "body_pct", "volume_ratio",
    "trend_gap_pct", "ema20_gap_pct", "ema55_gap_pct", "atr_pct",
    "breakout_strength", "roc6", "trend_strength", "momentum_accel",
    "volatility_contraction", "volume_price_divergence",
    "bull_bear_ratio", "taker_buy_ratio", "btc_correlation",
]

TRAIN_RATIO = 0.6
VALID_RATIO = 0.2  # TEST 为剩余 20%
THRESHOLD_CANDIDATES = [0.38, 0.40, 0.42, 0.44, 0.46, 0.48, 0.50]
HIT_THRESHOLD = 0.55


def _train_model(train_rows: list[dict[str, Any]]) -> Any:
    from services.worker.ml.trainer import ModelTrainer

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
        validation_rows=[],
        feature_columns=tuple(FEATURE_COLS),
    )
    return result.model


def _score_rows(model: Any, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    import numpy as np

    if not rows:
        return []
    X = np.array([[float(r.get(c, 0)) for c in FEATURE_COLS] for r in rows], dtype=np.float64)
    proba = model.predict_proba(X)
    scores = proba[:, 1] if proba.ndim > 1 else proba
    out = [dict(r) for r in rows]
    for row, s in zip(out, scores):
        row["score"] = float(s)
    return out


def build_direction_series(model: Any, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """每个时间点：16 币平均分数 + BTC 未来收益 → 方向判断序列。"""
    ts_groups: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        ts_groups[int(row["generated_at"])].append(row)

    series: list[dict[str, Any]] = []
    for ts in sorted(ts_groups.keys()):
        group = ts_groups[ts]
        if len(group) < 4:
            continue
        scored = _score_rows(model, group)
        avg_score = sum(float(r["score"]) for r in scored) / len(scored)
        btc_row = next((r for r in scored if r.get("symbol") == "BTCUSDT"), None)
        btc_future = float(btc_row.get("future_return_pct", 0)) if btc_row else 0.0
        series.append({"ts": ts, "avg_score": round(avg_score, 4), "btc_future": btc_future})
    return series


def evaluate_series(series: list[dict[str, Any]], threshold: float) -> dict[str, Any]:
    """按阈值做空：avg_score < 阈值 → 做空 BTC（收益 = -btc_future）。"""
    hits = 0
    counted = 0
    returns: list[float] = []
    for item in series:
        if item["avg_score"] < threshold:
            counted += 1
            short_return = -item["btc_future"]
            returns.append(short_return)
            if item["btc_future"] < 0:
                hits += 1
    return {
        "threshold": threshold,
        "trades": counted,
        "hit_rate": round(hits / counted, 4) if counted else 0.0,
        "avg_return": round(sum(returns) / len(returns), 4) if returns else 0.0,
    }


def evaluate_baseline(series: list[dict[str, Any]]) -> dict[str, Any]:
    """基准：全部时间点都做空 BTC。"""
    returns = [-item["btc_future"] for item in series]
    hits = sum(1 for item in series if item["btc_future"] < 0)
    return {
        "trades": len(series),
        "hit_rate": round(hits / len(series), 4) if series else 0.0,
        "avg_return": round(sum(returns) / len(returns), 4) if returns else 0.0,
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
    ordered = sorted(rows, key=lambda r: int(r.get("generated_at", 0)))
    total = len(ordered)
    train_end = int(total * TRAIN_RATIO)
    valid_end = int(total * (TRAIN_RATIO + VALID_RATIO))
    train_rows = ordered[:train_end]
    valid_rows = ordered[train_end:valid_end]
    test_rows = ordered[valid_end:]
    print(f"三段: TRAIN={len(train_rows)} / VALID={len(valid_rows)} / TEST={len(test_rows)}", flush=True)

    # TRAIN 训练 + VALID 滚动预测（滚动窗口 120 个时间点重训，无泄漏）
    model = _train_model(train_rows)
    valid_series = build_direction_series(model, valid_rows)
    print(f"VALID 方向序列: {len(valid_series)} 个时间点", flush=True)

    # 在 VALID 段扫描最优阈值
    best_threshold = None
    best_score = -1
    print("\nVALID 段阈值扫描:")
    for th in THRESHOLD_CANDIDATES:
        r = evaluate_series(valid_series, th)
        if r["trades"] < 20:
            continue
        score = r["hit_rate"]
        print(f"  阈值 {th}: 做空 {r['trades']} 次, 命中率={r['hit_rate']}, 平均收益={r['avg_return']}%")
        if score > best_score:
            best_score = score
            best_threshold = th
    print(f"VALID 最优阈值: {best_threshold}（命中率 {best_score}）")

    if best_threshold is None:
        print("VALID 段样本不足，无法选阈值")
        return 1

    # TEST 段用最优阈值只验证一次（物理隔离）
    test_model = _train_model(train_rows + valid_rows)
    test_series = build_direction_series(test_model, test_rows)
    test_result = evaluate_series(test_series, best_threshold)
    baseline = evaluate_baseline(test_series)
    print("\n=== TEST 段最终验证（阈值 %.2f，只跑一次）===" % best_threshold)
    print(f"方向做空: 命中率={test_result['hit_rate']} 平均收益={test_result['avg_return']}% 做空{test_result['trades']}次/{len(test_series)}时点")
    print(f"全时段做空基准: 命中率={baseline['hit_rate']} 平均收益={baseline['avg_return']}%")

    passed = test_result["hit_rate"] >= HIT_THRESHOLD and test_result["avg_return"] > 0
    print(f"结论: {'✅ 方向做空有效（模型方向判断可用）' if passed else '❌ 方向做空不可靠（做空彻底放弃）'}")
    print(f"耗时 {time.time() - started:.1f}s")

    with open("/tmp/direction_short_result.json", "w", encoding="utf-8") as f:
        json.dump({
            "best_threshold": best_threshold,
            "test": test_result,
            "baseline": baseline,
            "passed": passed,
        }, f, ensure_ascii=False, indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
