"""做空方向验证：模型选最低分币做空，验证命中率与收益。

用法（服务器容器内）：
    cd /app && PYTHONPATH=/app python3 scripts/run_short_validation.py

流程：
1. 读 16 币 4h K 线 → 特征 + 标签（沿用线上最优标签配置 close_only/2%/2-5d）
2. 时间序切分：前 60% 训练、后 40% 滚动验证（每 VALIDATION_WINDOW_BARS 个时间点重训，
   只用该时间点之前的数据，无泄漏）
3. 每个时间点选分数最低的 top-3 币做空，记录未来收益；随机选 3 币做随机基准
4. 统计：做空命中率（未来收益<0 比例）、平均做空收益（-未来收益）
5. 结论：命中率 ≥55% 且比随机高 3%+ → 做空方向有效，可进入阶段 1
"""

from __future__ import annotations

import json
import random
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

VALIDATION_WINDOW_BARS = 120  # 每 120 个时间点（约 20 天）重训一次
SHORT_TOP_K = 3               # 每轮做空 top-k 个最低分币
HIT_RATE_THRESHOLD = 0.55     # 命中率硬门槛
RANDOM_MARGIN = 0.03          # 必须比随机高 3%


def build_short_pairs(rows: list[dict[str, Any]], top_k: int = SHORT_TOP_K) -> list[dict[str, Any]]:
    """从同一时间点的候选里选分数最低的 top_k 个做空。

    Args:
        rows: 同一时间点的候选行（含 score 和 future_return_pct）
        top_k: 做空数量

    Returns:
        做空候选列表（按分数升序）
    """
    sorted_rows = sorted(rows, key=lambda r: float(r.get("score", 0)))
    return list(sorted_rows[:top_k])


def compute_short_hit_rate(pairs: list[dict[str, Any]]) -> dict[str, float]:
    """统计做空命中率与平均收益。

    做空收益 = -未来收益（跌了赚钱）。未来收益为 0 的样本不计入命中分母。

    Returns:
        {hit_rate, avg_return, sample_count}
    """
    hits = 0
    counted = 0
    returns: list[float] = []
    for p in pairs:
        future = float(p.get("future_return_pct", 0))
        if future == 0:
            continue
        counted += 1
        if future < 0:
            hits += 1
        returns.append(-future)  # 做空收益
    return {
        "hit_rate": round(hits / counted, 4) if counted else 0.0,
        "avg_return": round(sum(returns) / len(returns), 4) if returns else 0.0,
        "sample_count": counted,
    }


def _train_model(train_rows: list[dict[str, Any]]) -> Any:
    """训练 binary 模型并返回。"""
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


def _predict_scores(model: Any, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """给每行打分（上涨概率），写回 score 字段。"""
    if not rows:
        return []
    import numpy as np

    X = np.array(
        [[float(r.get(c, 0)) for c in FEATURE_COLS] for r in rows],
        dtype=np.float64,
    )
    proba = model.predict_proba(X)
    scores = proba[:, 1] if proba.ndim > 1 else proba
    for row, score in zip(rows, scores):
        row["score"] = float(score)
    return rows


def main() -> int:
    kline_dir = sys.argv[1] if len(sys.argv) > 1 else "/app/.runtime/kline_store"
    started = time.time()

    # 1. 构建特征+标签（全部数据）
    rows = build_labeled_rows(
        kline_dir=kline_dir,
        symbols=SYMBOLS,
        interval="4h",
        label_config=OPT_LABEL_CONFIG,
    )
    ordered = sorted(rows, key=lambda r: (int(r.get("generated_at", 0)), str(r.get("symbol", ""))))
    print(f"总样本: {len(ordered)}", flush=True)

    # 2. 时间序切分：前 60% 训练，后 40% 滚动验证
    split_idx = int(len(ordered) * 0.6)
    train_rows = ordered[:split_idx]
    valid_rows = ordered[split_idx:]
    print(f"训练 {len(train_rows)} / 验证 {len(valid_rows)}", flush=True)

    # 3. 按时间点分组验证
    ts_groups: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in valid_rows:
        ts_groups[int(row["generated_at"])].append(row)
    timestamps = sorted(ts_groups.keys())
    print(f"验证时间点: {len(timestamps)}", flush=True)

    model = _train_model(train_rows)
    all_short_pairs: list[dict[str, Any]] = []
    all_random_pairs: list[dict[str, Any]] = []
    retrain_count = 1

    for idx, ts in enumerate(timestamps):
        group = ts_groups[ts]
        if len(group) < 4:
            continue
        # 滚动重训：只用该时间点之前的数据（无泄漏）
        if idx > 0 and idx % VALIDATION_WINDOW_BARS == 0:
            history = [r for r in ordered if int(r["generated_at"]) < ts]
            if len(history) > 500:
                model = _train_model(history)
                retrain_count += 1
        scored = _predict_scores(model, [dict(r) for r in group])
        all_short_pairs.extend(build_short_pairs(scored))
        random.seed(ts)
        all_random_pairs.extend(random.sample(scored, min(SHORT_TOP_K, len(scored))))

    # 4. 统计
    short_result = compute_short_hit_rate(all_short_pairs)
    random_result = compute_short_hit_rate(all_random_pairs)
    print(f"重训次数: {retrain_count}", flush=True)
    print("\n=== 做空方向验证结果 ===")
    print(
        f"模型做空: 命中率={short_result['hit_rate']} "
        f"平均做空收益={short_result['avg_return']}% 样本={short_result['sample_count']}"
    )
    print(
        f"随机做空: 命中率={random_result['hit_rate']} "
        f"平均做空收益={random_result['avg_return']}% 样本={random_result['sample_count']}"
    )
    passed = (
        short_result["hit_rate"] >= HIT_RATE_THRESHOLD
        and short_result["hit_rate"] > random_result["hit_rate"] + RANDOM_MARGIN
    )
    print(
        f"结论: {'✅ 做空方向有效，可进入阶段 1' if passed else '❌ 做空方向不足，不建议进入阶段 1'}"
    )
    print(f"耗时 {time.time() - started:.1f}s")

    with open("/tmp/short_validation_result.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "short": short_result,
                "random": random_result,
                "passed": passed,
                "retrain_count": retrain_count,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
