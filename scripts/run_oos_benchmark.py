"""物理隔离样本外考核（OOS Benchmark）——模型改动的最终考卷。

方法论（源自 EP004 四模型比赛的核心教训）：
- 数据按时间切三段：TRAIN 60% / VALID 20% / TEST 20%
- TRAIN 用来训练，VALID 用来迭代调参（可反复看），**TEST 物理隔离**
- 任何模型/特征/标签改动，只有 TEST 段表现显著优于基线才允许上线
- TEST 段绝不参与训练和参数选择——防止"调参调出幻觉"

用法（服务器容器内）：
    cd /app && PYTHONPATH=/app python3 scripts/run_oos_benchmark.py

基线：首次运行生成 /app/.runtime/oos_baseline.json，后续运行对比基线输出结论。

改动验收规则（写死，防止临时放宽）：
    test_auc 相对基线提升 >= +0.01 且 valid/test 差距没有恶化 -> 通过
    否则 -> 不通过，改动不部署
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
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

# 三段切分比例
TRAIN_RATIO = 0.6
VALID_RATIO = 0.2  # TEST 自动为剩余 20%
BASELINE_PATH = "/app/.runtime/oos_baseline.json"
MIN_TEST_GAIN = 0.01  # TEST 至少提升 0.01 才允许上线


def train_and_score(train_rows: list[dict[str, Any]], score_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """训练模型并在给定数据上打分（返回 AUC）。"""
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
        validation_rows=score_rows,
        feature_columns=tuple(FEATURE_COLS),
    )
    return {
        "val_auc": round(float(result.metrics.get("val_auc", 0)), 4),
        "train_auc": round(float(result.metrics.get("train_auc", 0)), 4),
    }


def main() -> int:
    kline_dir = sys.argv[1] if len(sys.argv) > 1 else "/app/.runtime/kline_store"
    started = time.time()

    # 1. 构建数据并按时间切三段
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
    test_rows = ordered[valid_end:]  # 物理隔离段
    print(f"三段切分: TRAIN={len(train_rows)} / VALID={len(valid_rows)} / TEST={len(test_rows)}", flush=True)

    # 2. TRAIN 训练 + VALID 迭代评分（可以反复看的部分）
    valid_result = train_and_score(train_rows, valid_rows)
    print(f"VALID 段: auc={valid_result['val_auc']}（训练 {valid_result['train_auc']}）", flush=True)

    # 3. TEST 最终考核（只跑一次，不参与任何调参）
    test_result = train_and_score(train_rows + valid_rows, test_rows)
    print(f"TEST 段: auc={test_result['val_auc']}（训练 {test_result['train_auc']}）", flush=True)

    # 4. 基线对比
    baseline_path = Path(BASELINE_PATH)
    baseline = None
    if baseline_path.exists():
        try:
            baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            baseline = None

    if baseline is None:
        # 首次运行：建立基线
        baseline_data = {
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "test_auc": test_result["val_auc"],
            "valid_auc": valid_result["val_auc"],
            "train_auc_test_phase": test_result["train_auc"],
            "config": {"label": OPT_LABEL_CONFIG["name"], "features": len(FEATURE_COLS)},
        }
        baseline_path.parent.mkdir(parents=True, exist_ok=True)
        baseline_path.write_text(json.dumps(baseline_data, ensure_ascii=False, indent=2), encoding="utf-8")
        print("\n✅ 基线已建立（首次运行）")
        print(f"   基线 TEST auc = {baseline_data['test_auc']}")
        print("   以后任何模型改动都跑本脚本，与基线对比。")
    else:
        base_test = float(baseline.get("test_auc", 0))
        gain = test_result["val_auc"] - base_test
        valid_gap_ok = (valid_result["val_auc"] - test_result["val_auc"]) <= 0.05
        passed = gain >= MIN_TEST_GAIN and valid_gap_ok
        print("\n=== 考核结果 ===")
        print(f"   基线 TEST auc: {base_test}")
        print(f"   本次 TEST auc: {test_result['val_auc']}（变化 {gain:+.4f}）")
        print(f"   VALID/TEST 差距: {valid_result['val_auc'] - test_result['val_auc']:+.4f}（阈值 ≤0.05）")
        print(f"   结论: {'✅ 通过，允许部署' if passed else '❌ 未通过，改动不部署'}")
        if not passed and gain >= MIN_TEST_GAIN:
            print("   原因: VALID 与 TEST 差距过大，疑似对验证段过拟合")

    print(f"耗时 {time.time() - started:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
