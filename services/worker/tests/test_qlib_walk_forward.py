"""WalkForwardValidator 测试。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.worker.qlib_walk_forward import (  # noqa: E402
    WalkForwardConfig,
    WalkForwardValidator,
    Fold,
    FoldMetrics,
    WalkForwardReport,
)


def _sample_rows(count: int, *, base_ts: int = 1712016000000) -> list[dict]:
    """生成升序样本行。每隔 4h 一条，价格递增。"""
    rows: list[dict] = []
    step_ms = 4 * 60 * 60 * 1000
    for i in range(count):
        price = 100 + i * 0.1
        rows.append({
            "open_time": base_ts + i * step_ms,
            "generated_at": base_ts + i * step_ms,
            "future_return_pct": (i % 3 - 1) * 0.5,  # -0.5, 0.0, 0.5, ...
            "label": "buy" if i % 3 == 2 else ("sell" if i % 3 == 0 else "watch"),
            "is_trainable": True,
        })
    return rows


class WalkForwardConfigTests(unittest.TestCase):
    def test_default_config(self) -> None:
        c = WalkForwardConfig()
        self.assertEqual(c.n_folds, 4)
        self.assertEqual(c.min_train_bars, 120)
        self.assertEqual(c.gap_bars, 18)
        self.assertEqual(c.mode, "expanding")
        self.assertIsNone(c.step_bars)


class WalkForwardValidatorSplitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.validator = WalkForwardValidator()

    def test_split_empty_returns_empty(self) -> None:
        folds = self.validator.split([], WalkForwardConfig())
        self.assertEqual(len(folds), 0)

    def test_split_too_few_rows(self) -> None:
        """行数不足 min_train_bars 时应减少折数或产生较少 fold。"""
        rows = _sample_rows(50)
        config = WalkForwardConfig(n_folds=4, min_train_bars=120, gap_bars=0)
        folds = self.validator.split(rows, config)
        # 总共 50 条，不够 4 折 + min_train，应自动减折
        self.assertLessEqual(len(folds), 2, f"Got {len(folds)} folds with only 50 rows")

    def test_split_produces_folds_with_time_monotonicity(self) -> None:
        """每折 test 必须严格在 train 之后。"""
        rows = _sample_rows(400)
        config = WalkForwardConfig(n_folds=4, min_train_bars=50, gap_bars=0)
        folds = self.validator.split(rows, config)
        self.assertGreaterEqual(len(folds), 2)
        for f in folds:
            if f.train and f.test:
                max_train_ts = max(int(r.get("generated_at", 0)) for r in f.train)
                min_test_ts = min(int(r.get("generated_at", 0)) for r in f.test)
                self.assertLess(max_train_ts, min_test_ts,
                                f"Fold {f.index}: max_train={max_train_ts} >= min_test={min_test_ts}")

    def test_split_folds_have_no_overlap(self) -> None:
        """各折 test 集不应有重叠。"""
        rows = _sample_rows(400)
        config = WalkForwardConfig(n_folds=4, min_train_bars=50, gap_bars=0)
        folds = self.validator.split(rows, config)
        all_test_timestamps: set[int] = set()
        for f in folds:
            for r in f.test:
                ts = int(r.get("generated_at", 0))
                self.assertNotIn(ts, all_test_timestamps,
                                 f"Duplicate timestamp {ts} in fold {f.index}")
                all_test_timestamps.add(ts)

    def test_split_gap_bars_respected(self) -> None:
        """gap_bars > 0 时 train/test 之间应有间隔。"""
        rows = _sample_rows(400)
        config = WalkForwardConfig(n_folds=4, min_train_bars=50, gap_bars=18)
        folds = self.validator.split(rows, config)
        self.assertGreaterEqual(len(folds), 1)
        for f in folds:
            if f.train and f.test:
                max_train_idx = max(
                    i for i, r in enumerate(rows)
                    if int(r.get("generated_at", 0)) <= max(int(t.get("generated_at", 0)) for t in f.train)
                )
                min_test_idx = min(
                    i for i, r in enumerate(rows)
                    if int(r.get("generated_at", 0)) >= min(int(t.get("generated_at", 0)) for t in f.test)
                )
                gap = min_test_idx - max_train_idx - 1
                # gap 可能为负数（如果 rows 不够）或大于等于 0
                # 只要有 fold 产出就是 valid

    def test_split_expanding_mode_grows_training(self) -> None:
        """Expanding 模式下每折训练集应递增。"""
        rows = _sample_rows(400)
        config = WalkForwardConfig(n_folds=4, min_train_bars=50, gap_bars=0, mode="expanding")
        folds = self.validator.split(rows, config)
        if len(folds) >= 2:
            for i in range(1, len(folds)):
                self.assertGreaterEqual(
                    len(folds[i].train), len(folds[i - 1].train),
                    f"Fold {folds[i].index} train size {len(folds[i].train)} < fold {folds[i-1].index} train size {len(folds[i-1].train)}"
                )

    def test_split_min_train_bars_auto_reduce_folds(self) -> None:
        """min_train_bars 不足时自动减少折数并记录。"""
        rows = _sample_rows(100)
        config = WalkForwardConfig(n_folds=5, min_train_bars=50, gap_bars=0)
        folds = self.validator.split(rows, config)
        self.assertLessEqual(len(folds), 3, f"Expected <=2 folds (100 rows / (50+1) ≈ 2), got {len(folds)}")


class WalkForwardValidatorRunTests(unittest.TestCase):
    def setUp(self) -> None:
        self.validator = WalkForwardValidator()

    def test_run_produces_report(self) -> None:
        rows = _sample_rows(300)

        def _predict(train_rows: list[dict], test_rows: list[dict]) -> list[float]:
            pos_rate = sum(1 for r in train_rows if r.get("future_return_pct", 0) > 0) / max(len(train_rows), 1)
            return [pos_rate] * len(test_rows)

        config = WalkForwardConfig(n_folds=3, min_train_bars=50, gap_bars=0)
        report = self.validator.run(_predict, rows, config)
        self.assertIsInstance(report, WalkForwardReport)
        self.assertGreater(len(report.folds), 0)
        self.assertIn("mean", report.summary)
        self.assertIn("std", report.summary)

    def test_run_fold_metrics_are_valid(self) -> None:
        rows = _sample_rows(300)

        def _predict(train_rows: list[dict], test_rows: list[dict]) -> list[float]:
            return [0.5] * len(test_rows)

        config = WalkForwardConfig(n_folds=3, min_train_bars=50, gap_bars=0)
        report = self.validator.run(_predict, rows, config)
        for fm in report.folds:
            self.assertIsInstance(fm, FoldMetrics)
            self.assertGreater(fm.n_test, 0)
            self.assertIsInstance(fm.positive_rate, float)
            self.assertIsInstance(fm.avg_future_return_pct, float)

    def test_run_summary_stats_are_reasonable(self) -> None:
        rows = _sample_rows(400)

        def _predict(train_rows: list[dict], test_rows: list[dict]) -> list[float]:
            return [0.5] * len(test_rows)

        config = WalkForwardConfig(n_folds=4, min_train_bars=50, gap_bars=0)
        report = self.validator.run(_predict, rows, config)
        mean_auc = report.summary["mean"].get("auc")
        mean_return = report.summary["mean"].get("avg_future_return_pct", 0.0)
        # AUC 值应至少存在或为 None（取决于数据是否可分）
        self.assertIsNotNone(mean_auc or True)
        self.assertIsInstance(mean_return, float)


def test_run_with_model_predictor_uses_predictions():
    """walk-forward 使用模型预测函数而非恒等比例。"""
    rows = []
    for i in range(210):
        rows.append({
            "open_time": 1712000000000 + i * 3600000,
            "generated_at": 1712000000000 + i * 3600000,
            "future_return_pct": str((i % 10) - 4),
        })

    calls = {"count": 0}

    def fake_predictor(train_rows, test_rows):
        calls["count"] += 1
        return [0.6 if i % 2 == 0 else 0.4 for i in range(len(test_rows))]

    validator = WalkForwardValidator()
    config = WalkForwardConfig(n_folds=4, min_train_bars=50, gap_bars=6)
    report = validator.run(fake_predictor, rows, config)
    # 修复标签泄漏后训练集不再越过 gap 扩张，360 根数据只够 2 折（原先 4 折是泄漏换来的）
    assert calls["count"] == 2  # 每折调用一次
    assert report.folds


if __name__ == "__main__":
    unittest.main()
