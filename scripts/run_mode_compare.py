"""模型模式对比实验：binary（二分类） vs ranking（lambdarank 排序）。

用法（服务器容器内）：
    cd /app && PYTHONPATH=/app python3 scripts/run_mode_compare.py

用最优标签配置（close_only/2%/2-5d）构建特征+标签，分别用两种模式训练，
对比 val_auc / val_ndcg@5 / top5 命中率。结果写 /tmp/mode_compare_result.json
"""

from __future__ import annotations

import json
import sys
import time
from decimal import Decimal
from typing import Any

from scripts.run_label_sweep import build_labeled_rows, split_time_ordered, SYMBOLS

LABEL_CONFIG: dict[str, Any] = {
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


def run_mode(kline_dir: str, model_mode: str) -> dict[str, Any]:
    """用指定模式训练并返回指标。"""

    from services.worker.ml.trainer import ModelTrainer

    rows = build_labeled_rows(
        kline_dir=kline_dir,
        symbols=SYMBOLS,
        interval="4h",
        label_config=LABEL_CONFIG,
    )
    train_rows, val_rows = split_time_ordered(rows)

    if model_mode == "ranking":
        model_params = {
            "objective": "lambdarank",
            "metric": "ndcg",
            "label_gain": [0, 1, 2, 3],
            "ndcg_eval_at": [5],
            "learning_rate": 0.05,
            "num_leaves": 31,
            "n_estimators": 200,
            "early_stopping_rounds": 20,
            "verbosity": -1,
        }
    else:
        model_params = {
            "objective": "binary",
            "learning_rate": 0.05,
            "num_leaves": 31,
            "n_estimators": 200,
            "early_stopping_rounds": 20,
            "verbosity": -1,
        }

    trainer = ModelTrainer(
        model_type="lightgbm",
        model_params=model_params,
        label_column="future_return_pct",
    )
    result = trainer.train(
        training_rows=train_rows,
        validation_rows=val_rows,
        feature_columns=tuple(FEATURE_COLS),
    )
    metrics = result.metrics
    return {
        "mode": model_mode,
        "train_samples": len(train_rows),
        "val_samples": len(val_rows),
        "train_auc": round(float(metrics.get("train_auc", 0)), 4),
        "val_auc": round(float(metrics.get("val_auc", 0)), 4),
        "val_ndcg_at_5": round(float(metrics.get("val_ndcg_at_5", 0)), 4),
        "val_top5_hit_rate": round(float(metrics.get("val_top5_hit_rate", 0)), 4),
    }


def main() -> int:
    kline_dir = sys.argv[1] if len(sys.argv) > 1 else "/app/.runtime/kline_store"
    results = []
    for mode in ("binary", "ranking"):
        print(f"\n=== 训练模式: {mode} ...", flush=True)
        started = time.time()
        r = run_mode(kline_dir, mode)
        r["seconds"] = round(time.time() - started, 1)
        results.append(r)
        print(
            f"    val_auc={r['val_auc']} ndcg@5={r['val_ndcg_at_5']} "
            f"top5命中={r['val_top5_hit_rate']}（耗时 {r['seconds']}s）",
            flush=True,
        )

    print("\n=== 对比结果 ===")
    for r in results:
        print(
            f"{r['mode']:<10} val_auc={r['val_auc']:<8} ndcg@5={r['val_ndcg_at_5']:<8} "
            f"top5命中率={r['val_top5_hit_rate']}"
        )
    with open("/tmp/mode_compare_result.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
