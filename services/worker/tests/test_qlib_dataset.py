"""Qlib 研究数据集整理测试。

这个文件只验证数据包整理和时间切分是否稳定。
"""

from __future__ import annotations

import sys
import unittest
from unittest import mock
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.worker.qlib_dataset import DatasetBundle, build_dataset_bundle  # noqa: E402
from services.worker.qlib_config import load_qlib_config  # noqa: E402


class QlibDatasetTests(unittest.TestCase):
    def setUp(self) -> None:
        load_qlib_config(
            env={
                "QUANT_QLIB_RUNTIME_ROOT": "/tmp/quant-qlib-runtime-tests",
                "QUANT_QLIB_TRAIN_SPLIT_RATIO": "0.6",
                "QUANT_QLIB_VALIDATION_SPLIT_RATIO": "0.2",
                "QUANT_QLIB_TEST_SPLIT_RATIO": "0.2",
            },
        )

    def test_build_dataset_bundle_returns_train_valid_test_splits(self) -> None:
        bundle = build_dataset_bundle(
            symbol="BTCUSDT",
            candles_1h=_sample_candles(96),
            candles_4h=_sample_candles(72, step_hours=4),
        )

        self.assertIsInstance(bundle, DatasetBundle)
        self.assertEqual(bundle.symbol, "BTCUSDT")
        self.assertEqual(bundle.timeframe, "4h")
        self.assertEqual(len(bundle.training_rows), 32)
        self.assertEqual(len(bundle.validation_rows), 11)
        self.assertEqual(len(bundle.testing_rows), 11)
        self.assertLess(bundle.training_rows[-1]["generated_at"], bundle.validation_rows[0]["generated_at"])
        self.assertLess(bundle.validation_rows[-1]["generated_at"], bundle.testing_rows[0]["generated_at"])

    def test_build_dataset_bundle_falls_back_to_1h_when_4h_is_empty(self) -> None:
        bundle = build_dataset_bundle(
            symbol="ethusdt",
            candles_1h=_sample_candles(96),
            candles_4h=[],
        )

        self.assertEqual(bundle.timeframe, "1h")
        self.assertEqual(bundle.symbol, "ETHUSDT")
        self.assertTrue(bundle.training_rows)
        self.assertTrue(bundle.validation_rows)
        self.assertTrue(bundle.testing_rows)

    def test_build_dataset_bundle_falls_back_to_1h_when_4h_cannot_split(self) -> None:
        bundle = build_dataset_bundle(
            symbol="BTCUSDT",
            candles_1h=_sample_candles(96),
            candles_4h=_sample_candles(2, step_hours=4),
        )

        self.assertEqual(bundle.timeframe, "1h")
        self.assertEqual(len(bundle.training_rows), 14)
        self.assertEqual(len(bundle.validation_rows), 5)
        self.assertEqual(len(bundle.testing_rows), 5)

    def test_build_dataset_bundle_raises_when_train_valid_test_cannot_be_split(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "样本不足以切成训练/验证/测试三段"):
            build_dataset_bundle(
                symbol="BTCUSDT",
                candles_1h=_sample_candles(2),
                candles_4h=_sample_candles(2, step_hours=4),
            )

    def test_build_dataset_bundle_raises_when_no_candles_are_available(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "没有可用的研究 K 线样本"):
            build_dataset_bundle(
                symbol="BTCUSDT",
                candles_1h=[],
                candles_4h=[],
            )

    def test_build_dataset_bundle_standardizes_symbol_before_builders_receive_it(self) -> None:
        feature_rows = [
            {"symbol": "ETHUSDT", "generated_at": 1, "close_return_pct": "0.0000", "range_pct": "0.0000", "body_pct": "0.0000", "volume_ratio": "1.0000", "trend_gap_pct": "0.0000"},
            {"symbol": "ETHUSDT", "generated_at": 2, "close_return_pct": "0.0000", "range_pct": "0.0000", "body_pct": "0.0000", "volume_ratio": "1.0000", "trend_gap_pct": "0.0000"},
            {"symbol": "ETHUSDT", "generated_at": 3, "close_return_pct": "0.0000", "range_pct": "0.0000", "body_pct": "0.0000", "volume_ratio": "1.0000", "trend_gap_pct": "0.0000"},
            {"symbol": "ETHUSDT", "generated_at": 4, "close_return_pct": "0.0000", "range_pct": "0.0000", "body_pct": "0.0000", "volume_ratio": "1.0000", "trend_gap_pct": "0.0000"},
        ]
        label_rows = [
            {"symbol": "ETHUSDT", "generated_at": 1, "future_return_pct": "0.1000", "label": "buy", "holding_window": "1-3d", "is_trainable": True},
            {"symbol": "ETHUSDT", "generated_at": 2, "future_return_pct": "0.1000", "label": "buy", "holding_window": "1-3d", "is_trainable": True},
            {"symbol": "ETHUSDT", "generated_at": 3, "future_return_pct": "0.1000", "label": "buy", "holding_window": "1-3d", "is_trainable": True},
            {"symbol": "ETHUSDT", "generated_at": 4, "future_return_pct": "0.1000", "label": "buy", "holding_window": "1-3d", "is_trainable": True},
        ]
        with mock.patch("services.worker.qlib_dataset.build_feature_rows", return_value=feature_rows) as mocked_features:
            with mock.patch("services.worker.qlib_dataset.build_label_rows", return_value=label_rows) as mocked_labels:
                bundle = build_dataset_bundle(
                    symbol=" ethusdt ",
                    candles_1h=[],
                    candles_4h=_sample_candles(3, step_hours=4),
                )

        mocked_features.assert_called_once_with(
            "ETHUSDT",
            _sample_candles(3, step_hours=4),
            missing_policy="neutral_fill",
            outlier_policy="clip",
            normalization_policy="fixed_4dp",
            timeframe_profiles=None,
        )
        mocked_labels.assert_called_once_with(
            "ETHUSDT",
            _sample_candles(3, step_hours=4),
            label_mode="earliest_hit",
            trigger_basis="close",
            target_return_pct=None,
            stop_return_pct=None,
            min_window_days=1,
            max_window_days=3,
            holding_window_label="1-3d",
        )
        self.assertEqual(bundle.symbol, "ETHUSDT")
        self.assertEqual(bundle.timeframe, "4h")

    def test_build_dataset_bundle_respects_runtime_split_ratio_config(self) -> None:
        load_qlib_config(
            env={
                "QUANT_QLIB_RUNTIME_ROOT": "/tmp/quant-qlib-runtime-tests",
                "QUANT_QLIB_TRAIN_SPLIT_RATIO": "0.5",
                "QUANT_QLIB_VALIDATION_SPLIT_RATIO": "0.3",
                "QUANT_QLIB_TEST_SPLIT_RATIO": "0.2",
            },
        )

        bundle = build_dataset_bundle(
            symbol="BTCUSDT",
            candles_1h=_sample_candles(96),
            candles_4h=_sample_candles(72, step_hours=4),
        )

        self.assertEqual(len(bundle.training_rows), 27)
        self.assertEqual(len(bundle.validation_rows), 16)
        self.assertEqual(len(bundle.testing_rows), 11)

    def test_build_dataset_bundle_filters_rows_by_lookback_days(self) -> None:
        candles_4h = _sample_candles(120, step_hours=4)

        bundle = build_dataset_bundle(
            symbol="BTCUSDT",
            candles_1h=[],
            candles_4h=candles_4h,
            lookback_days=10,
        )

        latest_close = candles_4h[-1]["close_time"]
        earliest_allowed_open = latest_close - 10 * 24 * 60 * 60 * 1000
        merged_rows = [*bundle.training_rows, *bundle.validation_rows, *bundle.testing_rows]

        self.assertTrue(merged_rows)
        self.assertGreaterEqual(min(int(item["generated_at"]) for item in merged_rows), earliest_allowed_open)
        self.assertLess(len(merged_rows), len(candles_4h))

    def test_build_dataset_bundle_respects_fixed_date_window(self) -> None:
        candles_4h = _sample_candles(120, step_hours=4)

        bundle = build_dataset_bundle(
            symbol="BTCUSDT",
            candles_1h=[],
            candles_4h=candles_4h,
            window_mode="fixed",
            start_date="2024-04-10",
            end_date="2024-04-20",
        )

        merged_rows = [*bundle.training_rows, *bundle.validation_rows, *bundle.testing_rows]
        self.assertTrue(merged_rows)
        self.assertGreaterEqual(min(int(item["generated_at"]) for item in merged_rows), 1712707200000)
        self.assertLessEqual(max(int(item["generated_at"]) for item in merged_rows), 1713657599999)

    def test_build_dataset_bundle_rejects_empty_fixed_date_window(self) -> None:
        candles_4h = _sample_candles(120, step_hours=4)

        with self.assertRaisesRegex(RuntimeError, "固定日期范围内没有可用研究样本"):
            build_dataset_bundle(
                symbol="BTCUSDT",
                candles_1h=[],
                candles_4h=candles_4h,
                window_mode="fixed",
                start_date="2025-01-01",
                end_date="2025-01-10",
            )


def _sample_candles(count: int, *, step_hours: int = 1) -> list[dict[str, object]]:
    """生成最小的时间序列样本。"""

    candles: list[dict[str, object]] = []
    base_open_time = 1712016000000
    base_close_time = 1712019599999
    step_ms = step_hours * 60 * 60 * 1000
    for index in range(count):
        open_time = base_open_time + index * step_ms
        close_time = base_close_time + index * step_ms
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


if __name__ == "__main__":
    unittest.main()
