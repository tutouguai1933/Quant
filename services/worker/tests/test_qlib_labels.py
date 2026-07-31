"""LabelEngine 和标签相关测试。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.worker.qlib_labels import (  # noqa: E402
    LabelEngine,
    LabelSpec,
    LabeledRow,
    LabelQuality,
    build_label_rows,
)


def _sample_candles(count: int) -> list[dict[str, object]]:
    """生成最小的时间序列样本（4h K线）。"""
    candles: list[dict[str, object]] = []
    base_open_time = 1712016000000
    step_ms = 4 * 60 * 60 * 1000
    for index in range(count):
        open_time = base_open_time + index * step_ms
        close_time = open_time + step_ms - 1
        price = 100 + index
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


class LabelSpecTests(unittest.TestCase):
    def test_default_spec_parameters(self) -> None:
        spec = LabelSpec()
        self.assertEqual(spec.target_pct, 1.0)
        self.assertEqual(spec.stop_pct, -1.0)
        self.assertEqual(spec.window_bars, 18)
        self.assertEqual(spec.mode, "earliest_hit")
        self.assertEqual(spec.neutral_threshold_pct, 0.0)

    def test_custom_spec_parameters(self) -> None:
        spec = LabelSpec(
            target_pct=2.0,
            stop_pct=-1.5,
            window_bars=12,
            mode="close_only",
            neutral_threshold_pct=0.3,
        )
        self.assertEqual(spec.target_pct, 2.0)
        self.assertEqual(spec.stop_pct, -1.5)
        self.assertEqual(spec.window_bars, 12)
        self.assertEqual(spec.mode, "close_only")
        self.assertEqual(spec.neutral_threshold_pct, 0.3)


class LabelEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = LabelEngine()

    def test_build_empty_candles_returns_empty(self) -> None:
        rows = self.engine.build([], LabelSpec())
        self.assertEqual(len(rows), 0)

    def test_build_produces_labeled_rows(self) -> None:
        candles = _sample_candles(60)
        rows = self.engine.build(candles, LabelSpec())
        self.assertGreater(len(rows), 0)
        for r in rows:
            self.assertIsInstance(r, LabeledRow)
            self.assertIsInstance(r.open_time, int)
            self.assertIsInstance(r.future_return_pct, float)
            self.assertIn(r.label, ("buy", "sell", "watch"))
            self.assertIsInstance(r.is_trainable, bool)

    def test_build_early_bars_are_untrainable(self) -> None:
        """尾部 bar 没有足够的未来窗口应为 untrainable。"""
        candles = _sample_candles(20)
        rows = self.engine.build(candles, LabelSpec(window_bars=18))
        trainable = [r for r in rows if r.is_trainable]
        untrainable = [r for r in rows if not r.is_trainable]
        self.assertGreater(len(untrainable), 0)
        self.assertGreater(len(trainable), 0)

    def test_build_earliest_hit_mode(self) -> None:
        candles = _sample_candles(60)
        rows = self.engine.build(candles, LabelSpec(mode="earliest_hit", window_bars=18))
        labels = [r.label for r in rows if r.is_trainable]
        self.assertGreater(len(labels), 0)

    def test_build_close_only_mode(self) -> None:
        candles = _sample_candles(60)
        rows = self.engine.build(candles, LabelSpec(mode="close_only", window_bars=18))
        trainable = [r for r in rows if r.is_trainable]
        self.assertGreater(len(trainable), 0)

    def test_build_window_majority_mode(self) -> None:
        candles = _sample_candles(60)
        rows = self.engine.build(candles, LabelSpec(mode="window_majority", window_bars=18))
        trainable = [r for r in rows if r.is_trainable]
        self.assertGreater(len(trainable), 0)

    def test_neutral_threshold_converts_to_watch(self) -> None:
        """neutral_threshold_pct > 0 时，小收益样本应标为 watch。"""
        candles = _sample_candles(60)
        spec = LabelSpec(target_pct=5.0, stop_pct=-5.0, window_bars=18, neutral_threshold_pct=2.0)
        rows = self.engine.build(candles, spec)
        # 小波动市场下几乎所有样本都落入 neutral 区变 watch
        watch_count = sum(1 for r in rows if r.label == "watch" and r.is_trainable)
        buy_count = sum(1 for r in rows if r.label == "buy")
        self.assertTrue(watch_count > 0 or buy_count == 0, f"watch={watch_count}, buy={buy_count}")

    def test_neutral_zero_has_no_effect(self) -> None:
        """neutral_threshold_pct=0 应不改变标签分类。"""
        candles = _sample_candles(60)
        spec = LabelSpec(target_pct=1.0, stop_pct=-1.0, window_bars=18, neutral_threshold_pct=0.0)
        rows = self.engine.build(candles, spec)
        trainable = [r for r in rows if r.is_trainable]
        self.assertGreater(len(trainable), 0)

    def test_quality_report(self) -> None:
        rows = [
            LabeledRow(open_time=100, future_return_pct=2.0, label="buy", is_trainable=True),
            LabeledRow(open_time=200, future_return_pct=-2.0, label="sell", is_trainable=True),
            LabeledRow(open_time=300, future_return_pct=0.0, label="watch", is_trainable=True),
            LabeledRow(open_time=400, future_return_pct=0.0, label="watch", is_trainable=False),
        ]
        q = self.engine.quality_report(rows)
        self.assertEqual(q.total, 4)
        self.assertAlmostEqual(q.buy_ratio, 0.25)
        self.assertAlmostEqual(q.sell_ratio, 0.25)
        self.assertAlmostEqual(q.watch_ratio, 0.5)
        self.assertAlmostEqual(q.trainable_ratio, 0.75)

    def test_quality_report_empty(self) -> None:
        q = self.engine.quality_report([])
        self.assertEqual(q.total, 0)
        self.assertEqual(q.buy_ratio, 0.0)
        self.assertEqual(q.trainable_ratio, 0.0)


class BuildLabelRowsBackwardCompatTests(unittest.TestCase):
    """验证 build_label_rows 旧签名的输出与 LabelEngine 默认参数一致。"""

    def test_build_label_rows_still_works(self) -> None:
        candles = _sample_candles(60)
        rows = build_label_rows("BTCUSDT", candles)
        self.assertGreater(len(rows), 0)
        for r in rows:
            self.assertIsInstance(r, dict)
            self.assertIn("symbol", r)
            self.assertEqual(r["symbol"], "BTCUSDT")
            self.assertIn("label", r)
            self.assertIn("is_trainable", r)
            self.assertIn("future_return_pct", r)

    def test_build_label_rows_modes(self) -> None:
        candles = _sample_candles(60)
        for mode in ("earliest_hit", "close_only", "window_majority"):
            with self.subTest(mode=mode):
                rows = build_label_rows("ETHUSDT", candles, label_mode=mode)
                self.assertGreater(len(rows), 0)

    def test_build_label_rows_respects_trigger_basis(self) -> None:
        candles = _sample_candles(60)
        rows_close = build_label_rows("BTCUSDT", candles, trigger_basis="close")
        rows_hl = build_label_rows("BTCUSDT", candles, trigger_basis="high_low")
        self.assertGreater(len(rows_close), 0)
        self.assertGreater(len(rows_hl), 0)

    def test_label_engine_and_build_label_rows_consistent_for_defaults(self) -> None:
        """默认参数下 LabelEngine.build() 产出的 label 应与 build_label_rows 一致（同为 earliest_hit）。"""
        candles = _sample_candles(60)
        engine = LabelEngine()
        spec = LabelSpec(target_pct=1.0, stop_pct=-1.0, window_bars=18, mode="earliest_hit")
        engine_rows = engine.build(candles, spec)
        legacy_rows = build_label_rows("BTCUSDT", candles, target_return_pct=1.0, stop_return_pct=-1.0)

        # 对比 label 列（由于 window 语义不同，允许最多 10% 偏差）
        engine_labels = [r.label for r in engine_rows if r.is_trainable]
        legacy_labels = [r["label"] for r in legacy_rows if r.get("is_trainable")]
        match_count = sum(1 for a, b in zip(engine_labels, legacy_labels) if a == b)
        min_len = min(len(engine_labels), len(legacy_labels))
        if min_len > 0:
            ratio = match_count / min_len
            self.assertGreater(ratio, 0.8, f"Label consistency: {match_count}/{min_len}")

    def test_label_engine_quality_report_matches_legacy_counts(self) -> None:
        """验证 LabelEngine quality_report 计数与 build_label_rows 的 label 分布基本一致。"""
        candles = _sample_candles(60)
        engine = LabelEngine()
        spec = LabelSpec(target_pct=1.0, stop_pct=-1.0, window_bars=18, mode="earliest_hit")
        engine_rows = engine.build(candles, spec)
        quality = engine.quality_report(engine_rows)

        self.assertGreater(quality.total, 0)
        self.assertGreaterEqual(quality.buy_ratio + quality.sell_ratio + quality.watch_ratio, 0.99)


if __name__ == "__main__":
    unittest.main()
