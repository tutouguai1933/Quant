"""多周期特征对比实验：4h 基础特征 vs 4h + 1h 附加特征。

用法（服务器容器内）：
    cd /app && PYTHONPATH=/app python3 scripts/run_multi_tf_compare.py

1h 附加特征（与 4h 行按 close_time 对齐，只用已收盘数据避免泄漏）：
- close_return_6h_pct：该 4h 收盘时刻前 6 根 1h 的涨跌幅（6 小时动量）
- volume_ratio_1h：近 4 根 1h 均量 / 前 20 根 1h 均量
- rsi_14_1h：1h RSI(14)

结果写 /tmp/multi_tf_compare_result.json
"""

from __future__ import annotations

import json
import sys
import time
from typing import Any

from scripts.run_label_sweep import build_labeled_rows, split_time_ordered, SYMBOLS
from scripts.run_label_sweep import LABEL_SWEEP_CONFIGS

# 用最优标签配置
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

# 新增 1h 附加特征列名
AUX_1H_COLS = ["close_return_6h_pct", "volume_ratio_1h", "rsi_14_1h"]


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


def _rsi(values: list[float], period: int = 14) -> float:
    """简单 RSI。"""
    if len(values) < period + 1:
        return 50.0
    gains, losses = 0.0, 0.0
    for i in range(-period, 0):
        diff = values[i] - values[i - 1]
        if diff >= 0:
            gains += diff
        else:
            losses -= diff
    if losses == 0:
        return 100.0
    rs = (gains / period) / (losses / period)
    return 100.0 - 100.0 / (1.0 + rs)


def build_aux_1h_features(candles_1h: list[dict[str, Any]]) -> dict[int, dict[str, float]]:
    """计算每根 1h K 线收盘时刻的附加特征（key=close_time）。"""

    closes = [float(c["close"]) for c in candles_1h]
    volumes = [float(c["volume"]) for c in candles_1h]
    result: dict[int, dict[str, float]] = {}
    for idx, candle in enumerate(candles_1h):
        close_time = int(candle["close_time"])
        # 近 6 根 1h 涨跌幅（含当前）
        if idx >= 6:
            ret_6h = (closes[idx] - closes[idx - 6]) / closes[idx - 6] * 100.0
        elif idx >= 1:
            ret_6h = (closes[idx] - closes[0]) / closes[0] * 100.0
        else:
            ret_6h = 0.0
        # 近 4 根 1h 均量 / 前 20 根 1h 均量
        if idx >= 24:
            vol_recent = sum(volumes[idx - 3 : idx + 1]) / 4.0
            vol_prev = sum(volumes[idx - 23 : idx - 3]) / 20.0
            vol_ratio = vol_recent / vol_prev if vol_prev > 0 else 1.0
        else:
            vol_ratio = 1.0
        result[close_time] = {
            "close_return_6h_pct": round(ret_6h, 6),
            "volume_ratio_1h": round(vol_ratio, 6),
            "rsi_14_1h": round(_rsi(closes[: idx + 1]), 6),
        }
    return result


def merge_aux_features(
    rows: list[dict[str, Any]],
    aux_by_ts: dict[int, dict[str, float]],
) -> list[dict[str, Any]]:
    """把 1h 附加特征合并到 4h 特征行（按 4h close_time 对齐，取 <= 该时刻的最近 1h 特征）。"""

    aux_times = sorted(aux_by_ts.keys())
    import bisect

    merged: list[dict[str, Any]] = []
    for row in rows:
        ts = int(row["generated_at"])
        pos = bisect.bisect_right(aux_times, ts) - 1
        if pos < 0:
            continue
        aux = aux_by_ts[aux_times[pos]]
        combined = dict(row)
        for col in AUX_1H_COLS:
            combined[col] = aux.get(col, 0.0)
        merged.append(combined)
    return merged


def run_experiment(kline_dir: str, with_aux: bool) -> dict[str, Any]:
    """训练并返回指标。"""

    from services.worker.ml.trainer import ModelTrainer

    # 4h 特征 + 标签
    rows = build_labeled_rows(
        kline_dir=kline_dir,
        symbols=SYMBOLS,
        interval="4h",
        label_config=OPT_LABEL_CONFIG,
    )
    feature_cols = list(BASE_FEATURE_COLS)

    if with_aux:
        # 附加 1h 特征：逐币读取 1h K 线并合并
        all_aux: dict[str, dict[int, dict[str, float]]] = {}
        for symbol in SYMBOLS:
            candles_1h = load_klines(kline_dir, symbol, "1h")
            if candles_1h:
                all_aux[symbol] = build_aux_1h_features(candles_1h)
        merged_rows: list[dict[str, Any]] = []
        for row in rows:
            symbol = str(row.get("symbol", ""))
            aux_map = all_aux.get(symbol)
            if aux_map is None:
                continue
            merged_rows.append(merge_aux_features([row], aux_map)[0])
        rows = merged_rows
        feature_cols = list(BASE_FEATURE_COLS) + AUX_1H_COLS

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
    return {
        "with_aux": with_aux,
        "feature_count": len(feature_cols),
        "train_samples": len(train_rows),
        "val_samples": len(val_rows),
        "train_auc": round(float(metrics.get("train_auc", 0)), 4),
        "val_auc": round(float(metrics.get("val_auc", 0)), 4),
    }


def main() -> int:
    kline_dir = sys.argv[1] if len(sys.argv) > 1 else "/app/.runtime/kline_store"
    results = []
    for with_aux in (False, True):
        label = "基础4h" if not with_aux else "4h+1h附加"
        print(f"\n=== 特征组: {label} ...", flush=True)
        started = time.time()
        r = run_experiment(kline_dir, with_aux)
        r["seconds"] = round(time.time() - started, 1)
        results.append(r)
        print(
            f"    特征数={r['feature_count']} val_auc={r['val_auc']} "
            f"train_auc={r['train_auc']}（耗时 {r['seconds']}s）",
            flush=True,
        )

    print("\n=== 对比结果 ===")
    for r in results:
        print(
            f"{'基础4h' if not r['with_aux'] else '4h+1h附加':<12} "
            f"val_auc={r['val_auc']} train_auc={r['train_auc']}"
        )
    with open("/tmp/multi_tf_compare_result.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
