"""分组训练对比实验：合并训练 vs 主流币/meme 币分开训练。

用法（服务器容器内）：
    cd /app && PYTHONPATH=/app python3 scripts/run_group_compare.py

分组：
- 主流组：BTC/ETH/BNB/SOL/XRP/DOGE/ADA/LINK/AVAX/DOT/MATIC（11 币）
- meme 组：PEPE/SHIB/WIF/ORDI/BONK（5 币）

对比：合并训练（baseline） vs 分组训练（两组各自 val_auc 按样本加权平均）。
结果写 /tmp/group_compare_result.json
"""

from __future__ import annotations

import json
import sys
import time
from typing import Any

from scripts.run_label_sweep import build_labeled_rows, split_time_ordered, SYMBOLS

MAINSTREAM_SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT", "ADAUSDT", "LINKUSDT", "AVAXUSDT", "DOTUSDT", "MATICUSDT"]
MEME_SYMBOLS = ["PEPEUSDT", "SHIBUSDT", "WIFUSDT", "ORDIUSDT", "BONKUSDT"]

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


def train_on_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """训练并返回指标。"""

    from services.worker.ml.trainer import ModelTrainer

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
        feature_columns=tuple(FEATURE_COLS),
    )
    metrics = result.metrics
    return {
        "train_samples": len(train_rows),
        "val_samples": len(val_rows),
        "train_auc": round(float(metrics.get("train_auc", 0)), 4),
        "val_auc": round(float(metrics.get("val_auc", 0)), 4),
    }


def main() -> int:
    kline_dir = sys.argv[1] if len(sys.argv) > 1 else "/app/.runtime/kline_store"
    results: dict[str, Any] = {}

    # 合并训练（baseline）
    print("\n=== 合并训练（16 币）...", flush=True)
    started = time.time()
    all_rows = build_labeled_rows(kline_dir=kline_dir, symbols=SYMBOLS, interval="4h", label_config=OPT_LABEL_CONFIG)
    merged = train_on_rows(all_rows)
    merged["seconds"] = round(time.time() - started, 1)
    results["merged"] = merged
    print(f"    val_auc={merged['val_auc']} train_auc={merged['train_auc']}", flush=True)

    # 分组训练
    print("\n=== 分组训练 ...", flush=True)
    group_results: dict[str, Any] = {}
    group_summaries = []
    for group_name, symbols in (("mainstream", MAINSTREAM_SYMBOLS), ("meme", MEME_SYMBOLS)):
        print(f"--- {group_name}（{len(symbols)} 币）...", flush=True)
        started = time.time()
        rows = build_labeled_rows(kline_dir=kline_dir, symbols=symbols, interval="4h", label_config=OPT_LABEL_CONFIG)
        r = train_on_rows(rows)
        r["seconds"] = round(time.time() - started, 1)
        r["samples"] = r["train_samples"]
        group_results[group_name] = r
        group_summaries.append(r)
        print(f"    val_auc={r['val_auc']} train_auc={r['train_auc']}（{r['train_samples']} 样本）", flush=True)

    # 按训练样本加权平均
    total_samples = sum(g["train_samples"] for g in group_summaries)
    weighted_auc = sum(g["val_auc"] * g["train_samples"] for g in group_summaries) / total_samples if total_samples else 0
    results["grouped"] = {"groups": group_results, "weighted_val_auc": round(weighted_auc, 4)}

    print("\n=== 对比结果 ===")
    print(f"合并训练      val_auc={merged['val_auc']}")
    print(f"分组训练加权  val_auc={weighted_auc}")
    for name, r in group_results.items():
        print(f"   {name:<12} val_auc={r['val_auc']}")

    with open("/tmp/group_compare_result.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
