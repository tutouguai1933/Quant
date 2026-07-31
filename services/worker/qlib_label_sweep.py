"""标签敏感性扫描。

在 32 组合网格（target_pct x window_bars x neutral）上评估标签质量
和 walk-forward 表现，输出 .runtime/qlib/label_sweep/sweep_report.csv + JSON。
"""

from __future__ import annotations

import json
import os
import statistics
import time
from dataclasses import asdict, dataclass
from decimal import Decimal
from pathlib import Path

from services.worker.qlib_labels import LabelEngine, LabelSpec, LabelQuality
from services.worker.qlib_walk_forward import WalkForwardConfig, WalkForwardValidator


# 32 组合网格
_TARGET_PCT_VALUES = (0.5, 1.0, 1.5, 2.0)
_WINDOW_BARS_VALUES = (6, 12, 18, 24)
_NEUTRAL_PCT_VALUES = (0.0, 0.3)

_DEFAULT_OUTPUT_DIR = Path(".runtime/qlib/label_sweep")


@dataclass
class SweepRecord:
    """单组合扫描记录。"""

    target_pct: float
    window_bars: int
    neutral_pct: float
    label_buy_ratio: float
    label_sell_ratio: float
    label_watch_ratio: float
    label_trainable_ratio: float
    label_total: int
    wf_auc_mean: float | None
    wf_auc_std: float | None
    wf_return_mean: float
    wf_return_std: float
    wf_folds: int
    duration_s: float


def run_label_sweep(
    candles: list[dict],
    *,
    output_dir: Path | None = None,
    walk_forward_n_folds: int = 4,
    walk_forward_gap_bars: int = 18,
    model_timeout_s: int = 30,
) -> list[SweepRecord]:
    """在给定 candles 上扫描 32 组合标签参数。

    Args:
        candles: 标准 K 线列表
        output_dir: 输出目录（默认 .runtime/qlib/label_sweep）
        walk_forward_n_folds: WF 折数
        walk_forward_gap_bars: WF gap（防泄漏）
        model_timeout_s: 单组合训练超时秒数（兜底）

    Returns:
        所有组合的 SweepRecord 列表。
    """
    if output_dir is None:
        output_dir = _DEFAULT_OUTPUT_DIR

    engine = LabelEngine()
    records: list[SweepRecord] = []
    combo_index = 0

    for target_pct in _TARGET_PCT_VALUES:
        for window_bars in _WINDOW_BARS_VALUES:
            for neutral_pct in _NEUTRAL_PCT_VALUES:
                combo_index += 1
                t_start = time.monotonic()

                spec = LabelSpec(
                    target_pct=target_pct,
                    stop_pct=-(target_pct),
                    window_bars=window_bars,
                    neutral_threshold_pct=neutral_pct,
                )

                # 构建标签
                label_rows = engine.build(candles, spec)
                quality = engine.quality_report(label_rows)

                # 转为 dict 格式供 walk-forward
                rows_for_wf: list[dict] = []
                for candle, lr in zip(candles, label_rows):
                    rows_for_wf.append({
                        "open_time": lr.open_time,
                        "future_return_pct": lr.future_return_pct,
                        "label": lr.label,
                        "is_trainable": lr.is_trainable,
                    })

                # walk-forward 评估
                wf_auc_mean: float | None = None
                wf_auc_std: float | None = None
                wf_return_mean: float = 0.0
                wf_return_std: float = 0.0
                wf_folds: int = 0

                if len(rows_for_wf) >= walk_forward_n_folds * 2:
                    try:
                        wf_config = WalkForwardConfig(
                            n_folds=walk_forward_n_folds,
                            gap_bars=walk_forward_gap_bars,
                        )
                        validator = WalkForwardValidator()

                        def _predict(train_rows: list[dict], test_rows: list[dict]) -> list[float]:
                            # 简单策略：基于 train 正样本率做随机基线
                            train_returns = [_to_float(r.get("future_return_pct", 0)) for r in train_rows]
                            pos_rate = sum(1 for v in train_returns if v > 0) / max(len(train_returns), 1)
                            return [pos_rate] * len(test_rows)

                        report = validator.run(_predict, rows_for_wf, wf_config)
                        summary = report.summary
                        wf_auc_mean = summary["mean"].get("auc")
                        wf_auc_std = summary["std"].get("auc")
                        wf_return_mean = summary["mean"].get("avg_future_return_pct", 0.0)
                        wf_return_std = summary["std"].get("avg_future_return_pct", 0.0)
                        wf_folds = len(report.folds)
                    except Exception:
                        pass

                duration_s = time.monotonic() - t_start

                record = SweepRecord(
                    target_pct=target_pct,
                    window_bars=window_bars,
                    neutral_pct=neutral_pct,
                    label_buy_ratio=quality.buy_ratio,
                    label_sell_ratio=quality.sell_ratio,
                    label_watch_ratio=quality.watch_ratio,
                    label_trainable_ratio=quality.trainable_ratio,
                    label_total=quality.total,
                    wf_auc_mean=wf_auc_mean,
                    wf_auc_std=wf_auc_std,
                    wf_return_mean=wf_return_mean,
                    wf_return_std=wf_return_std,
                    wf_folds=wf_folds,
                    duration_s=duration_s,
                )
                records.append(record)

    # 写报告
    _write_sweep_report(records, output_dir)
    return records


def _write_sweep_report(records: list[SweepRecord], output_dir: Path) -> None:
    """输出 CSV 和 JSON 报告。"""
    output_dir.mkdir(parents=True, exist_ok=True)

    # CSV
    csv_path = output_dir / "sweep_report.csv"
    headers = [
        "target_pct", "window_bars", "neutral_pct",
        "label_buy_ratio", "label_sell_ratio", "label_watch_ratio", "label_trainable_ratio", "label_total",
        "wf_auc_mean", "wf_auc_std", "wf_return_mean", "wf_return_std", "wf_folds", "duration_s",
    ]
    lines = [",".join(headers)]
    for r in records:
        lines.append(",".join([
            str(r.target_pct), str(r.window_bars), str(r.neutral_pct),
            _fmt(r.label_buy_ratio), _fmt(r.label_sell_ratio), _fmt(r.label_watch_ratio),
            _fmt(r.label_trainable_ratio), str(r.label_total),
            _fmt(r.wf_auc_mean) if r.wf_auc_mean is not None else "",
            _fmt(r.wf_auc_std) if r.wf_auc_std is not None else "",
            _fmt(r.wf_return_mean), _fmt(r.wf_return_std),
            str(r.wf_folds), _fmt(r.duration_s),
        ]))
    csv_path.write_text("\n".join(lines), encoding="utf-8")

    # JSON
    json_path = output_dir / "sweep_report.json"
    json_path.write_text(
        json.dumps([asdict(r) for r in records], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _fmt(value: float | None) -> str:
    """格式化浮点数。"""
    if value is None:
        return ""
    return f"{value:.6f}"


def _to_float(value: object) -> float:
    """安全转换。"""
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
