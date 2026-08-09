"""标签配置对比实验：同一 K 线数据上用不同标签配置训练，对比验证 AUC。

用法（服务器容器内）：
    cd /app && python3 scripts/run_label_sweep.py

流程：读 16 币 4h K 线 → 构建特征 → 按每组标签配置打标 → 时间序切分(75/25)
      → lightgbm 二分类训练 → 对比验证 AUC / 正样本率。
输出：控制台对比表 + /tmp/label_sweep_result.json
"""

from __future__ import annotations

import json
import logging
import sys
import time
from decimal import Decimal
from typing import Any

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")

# 实验标签配置组：基准(当前线上) + 5 组候选
LABEL_SWEEP_CONFIGS: list[dict[str, Any]] = [
    {"name": "baseline_1pct_1-3d", "label_mode": "earliest_hit", "target": "1", "stop": "-1", "min_days": 1, "max_days": 3},
    {"name": "target_2pct_1-3d", "label_mode": "earliest_hit", "target": "2", "stop": "-1", "min_days": 1, "max_days": 3},
    {"name": "target_3pct_1-3d", "label_mode": "earliest_hit", "target": "3", "stop": "-1", "min_days": 1, "max_days": 3},
    {"name": "target_2pct_2-5d", "label_mode": "earliest_hit", "target": "2", "stop": "-1", "min_days": 2, "max_days": 5},
    {"name": "target_2pct_stop2_1-3d", "label_mode": "earliest_hit", "target": "2", "stop": "-2", "min_days": 1, "max_days": 3},
    {"name": "close_only_2pct_2-5d", "label_mode": "close_only", "target": "2", "stop": "-1", "min_days": 2, "max_days": 5},
]

SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT",
    "ADAUSDT", "LINKUSDT", "AVAXUSDT", "DOTUSDT", "MATICUSDT", "PEPEUSDT",
    "SHIBUSDT", "WIFUSDT", "ORDIUSDT", "BONKUSDT",
]

INTERVAL = "4h"
TRAIN_RATIO = 0.75


def load_dataset_rows(kline_dir: str) -> list[dict[str, Any]]:
    """从 dataset cache 目录加载全部特征行（供退化对比/参考用）。"""
    import glob

    rows: list[dict[str, Any]] = []
    for path in sorted(glob.glob(f"{kline_dir}/*.json")):
        try:
            with open(path, encoding="utf-8") as f:
                bundle = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        for key in ("training_rows", "validation_rows", "testing_rows"):
            rows.extend(bundle.get(key) or [])
    return rows


def load_klines(kline_dir: str, symbol: str, interval: str) -> list[dict[str, Any]]:
    """读单币单周期 K 线（jsonl，升序）。"""

    from pathlib import Path

    path = Path(kline_dir) / f"{symbol}_{interval}.jsonl"
    bars: list[dict[str, Any]] = []
    if not path.exists():
        return bars
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                bars.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    bars.sort(key=lambda b: int(b.get("open_time", 0)))
    return bars


def build_labeled_rows(
    *,
    kline_dir: str,
    symbols: list[str],
    interval: str,
    label_config: dict[str, Any],
) -> list[dict[str, Any]]:
    """为全部币构建"特征+标签"合并行。

    每个币：K 线 → 特征行（build_feature_rows，generated_at=close_time）
           → 标签行（build_label_rows，generated_at=close_time）→ 按时间合并。
    """

    from services.worker.qlib_features import build_feature_rows
    from services.worker.qlib_labels import build_label_rows

    merged: list[dict[str, Any]] = []
    for symbol in symbols:
        candles = load_klines(kline_dir, symbol, interval)
        if len(candles) < 200:
            continue
        feature_rows = build_feature_rows(symbol, candles)
        label_rows = build_label_rows(
            symbol,
            candles,
            label_mode=label_config["label_mode"],
            target_return_pct=Decimal(label_config["target"]),
            stop_return_pct=Decimal(label_config["stop"]),
            min_window_days=int(label_config["min_days"]),
            max_window_days=int(label_config["max_days"]),
            holding_window_label=f"{label_config['min_days']}-{label_config['max_days']}d",
        )
        feature_by_ts = {int(r["generated_at"]): r for r in feature_rows}
        for label_row in label_rows:
            ts = int(label_row["generated_at"])
            feature_row = feature_by_ts.get(ts)
            if feature_row is None or not label_row.get("is_trainable", False):
                continue
            combined = dict(feature_row)
            combined["future_return_pct"] = label_row["future_return_pct"]
            combined["label"] = label_row["label"]
            merged.append(combined)
    return merged


def split_time_ordered(
    rows: list[dict[str, Any]], *, train_ratio: float = TRAIN_RATIO
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """按 generated_at 时间升序切分：前 75% 训练、后 25% 验证（无泄漏）。"""

    ordered = sorted(rows, key=lambda r: int(r.get("generated_at", 0)))
    split_idx = int(len(ordered) * train_ratio)
    return ordered[:split_idx], ordered[split_idx:]


def run_single_experiment(
    rows: list[dict[str, Any]],
    config: dict[str, Any],
) -> dict[str, Any]:
    """对一组标签配置：切分 + 训练 + 返回指标。"""

    from services.worker.ml.trainer import ModelTrainer

    feature_cols = [
        "close_return_pct", "range_pct", "body_pct", "volume_ratio",
        "trend_gap_pct", "ema20_gap_pct", "ema55_gap_pct", "atr_pct",
        "breakout_strength", "roc6", "trend_strength", "momentum_accel",
        "volatility_contraction", "volume_price_divergence",
        "bull_bear_ratio", "taker_buy_ratio", "btc_correlation",
    ]
    train_rows, val_rows = split_time_ordered(rows)

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
    metrics = result.metrics
    positive_rate = sum(1 for r in train_rows if float(r.get("future_return_pct", 0)) > 0) / max(len(train_rows), 1)
    return {
        "config": config["name"],
        "train_samples": len(train_rows),
        "val_samples": len(val_rows),
        "positive_rate": round(positive_rate, 4),
        "train_auc": round(float(metrics.get("train_auc", 0)), 4),
        "val_auc": round(float(metrics.get("val_auc", 0)), 4),
    }


def main() -> int:
    kline_dir = sys.argv[1] if len(sys.argv) > 1 else "/app/.runtime/kline_store"
    results: list[dict[str, Any]] = []
    for config in LABEL_SWEEP_CONFIGS:
        print(f"\n=== 构建标签: {config['name']} ...", flush=True)
        started = time.time()
        rows = build_labeled_rows(
            kline_dir=kline_dir,
            symbols=SYMBOLS,
            interval=INTERVAL,
            label_config=config,
        )
        print(f"    特征行数: {len(rows)}（耗时 {time.time() - started:.1f}s）", flush=True)
        if len(rows) < 5000:
            print(f"    样本不足，跳过该组", flush=True)
            continue
        started = time.time()
        result = run_single_experiment(rows, config)
        result["build_seconds"] = round(time.time() - started, 1)
        results.append(result)
        print(
            f"    train={result['train_samples']} val={result['val_samples']} "
            f"正样本率={result['positive_rate']} "
            f"train_auc={result['train_auc']} val_auc={result['val_auc']}",
            flush=True,
        )

    print("\n\n=== 结果汇总（按 val_auc 降序）===")
    header = f"{'配置':<28}{'train_auc':>10}{'val_auc':>10}{'正样本率':>10}{'样本数':>10}"
    print(header)
    print("-" * len(header))
    for r in sorted(results, key=lambda x: x["val_auc"], reverse=True):
        print(
            f"{r['config']:<28}{r['train_auc']:>10.4f}{r['val_auc']:>10.4f}"
            f"{r['positive_rate']:>10.4f}{r['train_samples']:>10d}"
        )

    with open("/tmp/label_sweep_result.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print("\n结果已写入 /tmp/label_sweep_result.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
