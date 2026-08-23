"""分数校准分析：模型分数与实际胜率的对应关系。

回答核心问题：模型的绝对分数到底能不能当买入门槛用？

方法（OOS 三段切分，防泄漏）：
- TRAIN 60% 训练 → VALID 20% / TEST 20% 滚动打分
- 收集全部分数-收益配对，按分数分桶统计实际上涨频率
- 输出：
  1. 校准表：每个分数段的"实际上涨频率"（理想情况应接近分数本身）
  2. 各阈值胜率：分数>X 才买的胜率（X 从 0.36 到 0.50）
  3. 相对排名策略：每轮买 top-1 / top-2（分数最高者）的胜率与收益

用法（服务器容器内）：
    cd /app && PYTHONPATH=/app python3 scripts/run_score_calibration.py
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
VALID_RATIO = 0.2
RETRAIN_WINDOW = 120


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


def collect_pairs(model: Any, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """滚动按时间点打分，收集 (score, future_return) 配对 + 保留时间点分组。"""
    ts_groups: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        ts_groups[int(row["generated_at"])].append(row)

    pairs: list[dict[str, Any]] = []
    timestamps = sorted(ts_groups.keys())
    for idx, ts in enumerate(timestamps):
        group = ts_groups[ts]
        if len(group) < 4:
            continue
        if idx > 0 and idx % RETRAIN_WINDOW == 0:
            history = [r for r in rows if int(r["generated_at"]) < ts]
            if len(history) > 500:
                model = _train_model(history)
        scored = _score_rows(model, group)
        pairs.extend(scored)
    return pairs


def calibration_table(pairs: list[dict[str, Any]], bucket: float = 0.02) -> list[dict[str, Any]]:
    """按分数分桶：每桶的样本数、实际上涨频率、平均未来收益。"""
    buckets: dict[float, list[float]] = defaultdict(list)
    for p in pairs:
        score = float(p["score"])
        key = round(int(score / bucket) * bucket + bucket / 2, 3)
        buckets[key].append(float(p.get("future_return_pct", 0)))
    table = []
    for key in sorted(buckets.keys()):
        rets = buckets[key]
        up = sum(1 for r in rets if r > 0)
        table.append({
            "bucket": key,
            "count": len(rets),
            "up_rate": round(up / len(rets), 4) if rets else 0,
            "avg_future_return": round(sum(rets) / len(rets), 4) if rets else 0,
        })
    return table


def threshold_analysis(pairs: list[dict[str, Any]], thresholds: list[float]) -> list[dict[str, Any]]:
    """各阈值下：买分数>=阈值的币的胜率/平均收益。"""
    out = []
    for th in thresholds:
        picked = [p for p in pairs if float(p["score"]) >= th]
        if not picked:
            continue
        rets = [float(p.get("future_return_pct", 0)) for p in picked]
        wins = sum(1 for r in rets if r > 0)
        out.append({
            "threshold": th,
            "count": len(picked),
            "win_rate": round(wins / len(picked), 4),
            "avg_return": round(sum(rets) / len(picked), 4),
        })
    return out


def relative_topk(val_pairs: list[dict[str, Any]], k: int) -> dict[str, Any]:
    """相对排名选币：每个时间点买分数最高的 k 个，统计胜率/收益。"""
    ts_groups: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for p in val_pairs:
        ts_groups[int(p["generated_at"])].append(p)
    all_rets: list[float] = []
    rounds_win = 0
    rounds = 0
    for ts in sorted(ts_groups.keys()):
        group = ts_groups[ts]
        if len(group) < k:
            continue
        picks = sorted(group, key=lambda r: -float(r["score"]))[:k]
        rets = [float(p.get("future_return_pct", 0)) for p in picks]
        avg = sum(rets) / k
        all_rets.append(avg)
        rounds += 1
        if avg > 0:
            rounds_win += 1
    return {
        "rounds": rounds,
        "avg_return_per_round": round(sum(all_rets) / rounds, 4) if rounds else 0,
        "round_positive_rate": round(rounds_win / rounds, 4) if rounds else 0,
    }


def main() -> int:
    kline_dir = sys.argv[1] if len(sys.argv) > 1 else "/app/.runtime/kline_store"
    started = time.time()

    rows = build_labeled_rows(kline_dir=kline_dir, symbols=SYMBOLS, interval="4h", label_config=OPT_LABEL_CONFIG)
    ordered = sorted(rows, key=lambda r: int(r.get("generated_at", 0)))
    total = len(ordered)
    train_end = int(total * TRAIN_RATIO)
    valid_end = int(total * (TRAIN_RATIO + VALID_RATIO))
    train_rows = ordered[:train_end]
    valid_rows = ordered[train_end:valid_end]
    test_rows = ordered[valid_end:]
    print(f"三段: TRAIN={len(train_rows)} / VALID={len(valid_rows)} / TEST={len(test_rows)}", flush=True)

    # VALID 段收集配对（用于找规律/选门槛）
    model = _train_model(train_rows)
    valid_pairs = collect_pairs(model, valid_rows)
    # TEST 段（物理隔离，最终验证用）
    test_model = _train_model(train_rows + valid_rows)
    test_pairs = collect_pairs(test_model, test_rows)

    # 校准表
    print("\n=== 分数校准表（TEST 段）===")
    print(f"{'分数桶':<10}{'样本':>8}{'实际上涨率':>12}{'平均未来收益':>14}")
    table = calibration_table(test_pairs)
    for row in table:
        print(f"{row['bucket']:<10}{row['count']:>8}{row['up_rate']:>12.4f}{row['avg_future_return']:>14.4f}")

    # 阈值分析（TEST）
    print("\n=== 绝对阈值分析（TEST 段）===")
    th_results = threshold_analysis(test_pairs, [0.38, 0.40, 0.42, 0.44, 0.46, 0.48, 0.50])
    for r in th_results:
        print(f"  分数>={r['threshold']}: 样本={r['count']} 胜率={r['win_rate']} 平均收益={r['avg_return']}%")

    # 相对排名（VALID 找 k、TEST 验证）
    print("\n=== 相对排名选币 ===")
    for k in (1, 2, 3):
        v = relative_topk(valid_pairs, k)
        t = relative_topk(test_pairs, k)
        print(f"  top-{k}: VALID 平均收益={v['avg_return_per_round']}%/轮 | TEST 平均收益={t['avg_return_per_round']}%/轮 轮胜率={t['round_positive_rate']}")

    with open("/tmp/calibration_result.json", "w", encoding="utf-8") as f:
        json.dump({
            "calibration_table": table,
            "threshold_analysis": th_results,
        }, f, ensure_ascii=False, indent=2)
    print(f"\n耗时 {time.time() - started:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
