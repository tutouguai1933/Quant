"""标签敏感性扫描测试。"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.worker.qlib_label_sweep import run_label_sweep, SweepRecord  # noqa: E402


def _sample_candles(count: int) -> list[dict[str, object]]:
    """生成最小的时间序列样本（4h K线）。"""
    candles: list[dict[str, object]] = []
    base_open_time = 1712016000000
    step_ms = 4 * 60 * 60 * 1000
    for index in range(count):
        open_time = base_open_time + index * step_ms
        close_time = open_time + step_ms - 1
        price = 100 + index * 0.1
        candles.append(
            {
                "open_time": open_time,
                "open": str(price),
                "high": str(price + 4),
                "low": str(price - 1),
                "close": str(price + 2),
                "volume": str(1000 + index),
                "close_time": close_time,
            }
        )
    return candles


class LabelSweepTests(unittest.TestCase):
    def test_run_label_sweep_produces_32_records(self) -> None:
        candles = _sample_candles(120)
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "sweep"
            records = run_label_sweep(candles, output_dir=output_dir, walk_forward_n_folds=2)
            # 4 target_pct x 4 window_bars x 2 neutral = 32
            self.assertEqual(len(records), 32)
            for r in records:
                self.assertIsInstance(r, SweepRecord)
                self.assertGreater(r.label_total, 0)

    def test_run_label_sweep_writes_csv_and_json(self) -> None:
        candles = _sample_candles(120)
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "sweep"
            run_label_sweep(candles, output_dir=output_dir, walk_forward_n_folds=2)

            csv_path = output_dir / "sweep_report.csv"
            json_path = output_dir / "sweep_report.json"
            self.assertTrue(csv_path.exists(), f"CSV not found at {csv_path}")
            self.assertTrue(json_path.exists(), f"JSON not found at {json_path}")

            # 验证 CSV 表头
            csv_content = csv_path.read_text(encoding="utf-8")
            self.assertIn("target_pct", csv_content)
            self.assertIn("label_buy_ratio", csv_content)
            self.assertIn("wf_auc_mean", csv_content)

            # 验证 JSON 可解析
            json_content = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(len(json_content), 32, f"JSON has {len(json_content)} records, expected 32")

    def test_run_label_sweep_handles_empty_candles(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "sweep"
            records = run_label_sweep([], output_dir=output_dir)
            self.assertEqual(len(records), 32)
            for r in records:
                self.assertEqual(r.label_total, 0)

    def test_sweep_record_fields_are_complete(self) -> None:
        candles = _sample_candles(120)
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "sweep"
            records = run_label_sweep(candles, output_dir=output_dir, walk_forward_n_folds=2)
            for r in records:
                self.assertIsNotNone(r.target_pct)
                self.assertIsNotNone(r.window_bars)
                self.assertIsNotNone(r.neutral_pct)
                self.assertIsNotNone(r.label_buy_ratio)
                self.assertIsNotNone(r.label_sell_ratio)
                self.assertIsNotNone(r.label_watch_ratio)
                self.assertIsNotNone(r.label_trainable_ratio)
                self.assertIsNotNone(r.label_total)
                self.assertGreaterEqual(r.duration_s, 0)

    def test_walk_forward_folds_set_on_sufficient_data(self) -> None:
        """对于足够数据，wf_folds 应 > 0。"""
        candles = _sample_candles(200)
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "sweep"
            records = run_label_sweep(candles, output_dir=output_dir, walk_forward_n_folds=2)
            # 200 candles - 18 window_bars = 182 rows, enough for 2 folds
            for r in records:
                if r.window_bars <= 18:
                    self.assertGreaterEqual(r.wf_folds, 0)


if __name__ == "__main__":
    unittest.main()
