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

from decimal import Decimal
from scripts.run_label_sweep import load_klines, SYMBOLS
from services.worker.qlib_dataset import purged_time_split
from services.worker.qlib_walk_forward import WalkForwardValidator

OOS_EVALUATION_VERSION = "purged_oos_v2"

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


def evaluate_oos(train_rows: list[dict[str, Any]], valid_rows: list[dict[str, Any]],
                 test_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """只用训练/验证段拟合一次冻结模型，最终测试段仅用于预测和评分。"""
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
        label_threshold=float(OPT_LABEL_CONFIG["target"]),
    )
    result = trainer.train(
        training_rows=train_rows,
        validation_rows=valid_rows,
        feature_columns=tuple(FEATURE_COLS),
    )
    X_test, y_test = trainer._prepare_data(test_rows, tuple(FEATURE_COLS), "future_return_pct")
    if len(X_test) == 0:
        raise RuntimeError("最终测试段为空，无法考核")
    probabilities = result.model.predict_proba(X_test)
    scores = probabilities[:, 1] if probabilities.ndim == 2 else probabilities
    test_auc = WalkForwardValidator._compute_auc(list(scores), list(y_test))
    if test_auc is None:
        raise RuntimeError("最终测试段缺少正类或负类，无法考核")
    return {
        "evaluation_version": OOS_EVALUATION_VERSION,
        "valid_auc": round(float(result.metrics.get("val_auc", 0)), 4),
        "test_auc": round(test_auc, 4),
        "train_auc": round(float(result.metrics.get("train_auc", 0)), 4),
    }


def build_labeled_rows(*, kline_dir, symbols, interval, label_config):
    """构建带实际标签成熟时间的 OOS 样本，防止旧 sweep 合并丢失元数据。"""
    from services.worker.qlib_features import build_feature_rows
    from services.worker.qlib_labels import build_label_rows
    rows = []
    for symbol in symbols:
        candles = load_klines(kline_dir, symbol, interval)
        if len(candles) < 200:
            continue
        features = {int(row["generated_at"]): row for row in build_feature_rows(symbol, candles)}
        labels = build_label_rows(symbol, candles, label_mode=label_config["label_mode"],
                                  target_return_pct=Decimal(label_config["target"]),
                                  stop_return_pct=Decimal(label_config["stop"]),
                                  min_window_days=label_config["min_days"], max_window_days=label_config["max_days"])
        rows.extend({**features[int(row["generated_at"])], **row} for row in labels
                    if row["is_trainable"] and int(row["generated_at"]) in features)
    return rows


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
    train_rows, valid_rows, test_rows = purged_time_split(rows, train_ratio=TRAIN_RATIO, validation_ratio=VALID_RATIO)
    print(f"三段切分: TRAIN={len(train_rows)} / VALID={len(valid_rows)} / TEST={len(test_rows)}", flush=True)

    # 2. TRAIN 训练 + VALID 迭代评分（可以反复看的部分）
    evaluation = evaluate_oos(train_rows, valid_rows, test_rows)
    print(f"VALID 段: auc={evaluation['valid_auc']}（训练 {evaluation['train_auc']}）", flush=True)

    # 3. TEST 最终考核（只跑一次，不参与任何调参）
    print(f"TEST 段: auc={evaluation['test_auc']}（冻结模型，只预测）", flush=True)

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
            "evaluation_version": OOS_EVALUATION_VERSION,
            "test_auc": evaluation["test_auc"],
            "valid_auc": evaluation["valid_auc"],
            "train_auc_test_phase": evaluation["train_auc"],
            "config": {"label": OPT_LABEL_CONFIG["name"], "features": len(FEATURE_COLS)},
        }
        baseline_path.parent.mkdir(parents=True, exist_ok=True)
        baseline_path.write_text(json.dumps(baseline_data, ensure_ascii=False, indent=2), encoding="utf-8")
        print("\n✅ 基线已建立（首次运行）")
        print(f"   基线 TEST auc = {baseline_data['test_auc']}")
        print("   以后任何模型改动都跑本脚本，与基线对比。")
    else:
        if baseline.get("evaluation_version") != OOS_EVALUATION_VERSION:
            print("旧基线包含测试段训练泄漏，不能与新考核比较；保留旧文件，本次拒绝准入。")
            return 1
        base_test = float(baseline.get("test_auc", 0))
        gain = evaluation["test_auc"] - base_test
        gap = evaluation["valid_auc"] - evaluation["test_auc"]
        baseline_gap = float(baseline.get("valid_auc", 0)) - base_test
        valid_gap_ok = gap <= min(0.05, baseline_gap)
        passed = gain >= MIN_TEST_GAIN and valid_gap_ok
        print("\n=== 考核结果 ===")
        print(f"   基线 TEST auc: {base_test}")
        print(f"   本次 TEST auc: {evaluation['test_auc']}（变化 {gain:+.4f}）")
        print(f"   VALID/TEST 差距: {gap:+.4f}（不得超过 0.05 或基线差距）")
        print(f"   结论: {'✅ 通过，允许部署' if passed else '❌ 未通过，改动不部署'}")
        if not passed and gain >= MIN_TEST_GAIN:
            print("   原因: VALID 与 TEST 差距过大，疑似对验证段过拟合")
        if not passed:
            return 1

    print(f"耗时 {time.time() - started:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
