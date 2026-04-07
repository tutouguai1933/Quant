"""Qlib 因子层测试。

这个文件负责验证因子分类、预处理协议和训练/推理共享的因子出口。
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from services.worker.qlib_config import load_qlib_config
from services.worker.qlib_features import (
    AUXILIARY_FEATURE_COLUMNS,
    FEATURE_COLUMNS,
    FEATURE_PROTOCOL,
    PRIMARY_FEATURE_COLUMNS,
    build_feature_rows,
)
from services.worker.qlib_runner import QlibRunner


class QlibFactorLayerTests(unittest.TestCase):
    def test_feature_protocol_groups_primary_and_auxiliary_factors(self) -> None:
        self.assertIn("trend", FEATURE_PROTOCOL["categories"])
        self.assertIn("momentum", FEATURE_PROTOCOL["categories"])
        self.assertIn("oscillator", FEATURE_PROTOCOL["categories"])
        self.assertIn("volume", FEATURE_PROTOCOL["categories"])
        self.assertIn("volatility", FEATURE_PROTOCOL["categories"])
        self.assertIn("roc6", PRIMARY_FEATURE_COLUMNS)
        self.assertIn("cci20", AUXILIARY_FEATURE_COLUMNS)
        self.assertIn("stoch_k14", AUXILIARY_FEATURE_COLUMNS)
        self.assertTrue(FEATURE_PROTOCOL["roles"]["primary"])
        self.assertTrue(FEATURE_PROTOCOL["roles"]["auxiliary"])

    def test_feature_protocol_exposes_preprocessing_and_timeframe_profiles(self) -> None:
        preprocessing = FEATURE_PROTOCOL["preprocessing"]
        self.assertEqual(preprocessing["missing_policy"], "窗口不足时用中性值补齐")
        self.assertEqual(preprocessing["outlier_policy"], "按因子预设范围裁剪极值")
        self.assertEqual(preprocessing["normalization_policy"], "统一输出四位小数字符串")
        profile_1h = FEATURE_PROTOCOL["timeframe_profiles"]["1h"]
        profile_4h = FEATURE_PROTOCOL["timeframe_profiles"]["4h"]
        self.assertNotEqual(profile_1h["rsi_period"], profile_4h["rsi_period"])
        self.assertNotEqual(profile_1h["roc_period"], profile_4h["roc_period"])

    def test_feature_builder_outputs_extended_factor_columns(self) -> None:
        rows = build_feature_rows("ETHUSDT", _sample_timing_candles(step_hours=4))

        self.assertEqual(tuple(rows[-1].keys()), FEATURE_COLUMNS)
        self.assertIn("roc6", rows[-1])
        self.assertIn("cci20", rows[-1])
        self.assertIn("stoch_k14", rows[-1])

    def test_feature_builder_supports_configurable_preprocessing_policies(self) -> None:
        candles = _sample_timing_candles(step_hours=4)
        clipped_rows = build_feature_rows(
            "ETHUSDT",
            candles,
            outlier_policy="clip",
            normalization_policy="fixed_4dp",
        )
        normalized_rows = build_feature_rows(
            "ETHUSDT",
            candles,
            outlier_policy="raw",
            normalization_policy="zscore_by_symbol",
        )

        self.assertNotEqual(clipped_rows[-1]["ema20_gap_pct"], normalized_rows[-1]["ema20_gap_pct"])
        self.assertNotEqual(clipped_rows[-1]["volume_ratio"], normalized_rows[-1]["volume_ratio"])

    def test_feature_builder_drops_warmup_rows_in_strict_drop_mode(self) -> None:
        candles = _sample_timing_candles(step_hours=4)

        neutral_rows = build_feature_rows("ETHUSDT", candles, missing_policy="neutral_fill")
        strict_rows = build_feature_rows("ETHUSDT", candles, missing_policy="strict_drop")

        self.assertLess(len(strict_rows), len(neutral_rows))

    def test_training_and_inference_share_same_factor_protocol(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config = load_qlib_config(
                env={"QUANT_QLIB_RUNTIME_ROOT": str(Path(temp_dir))},
                require_explicit=True,
            )
            runner = QlibRunner(config=config)
            dataset = {
                "BTCUSDT": _sample_timing_candles(step_hours=4, count=120),
                "ETHUSDT": _sample_timing_candles(step_hours=4, count=120),
            }

            training_result = runner.train(dataset)
            inference_result = runner.infer(dataset)

        self.assertEqual(
            training_result["factor_protocol"]["primary_feature_columns"],
            FEATURE_PROTOCOL["primary_feature_columns"],
        )
        self.assertEqual(
            inference_result["factor_protocol"]["auxiliary_feature_columns"],
            FEATURE_PROTOCOL["auxiliary_feature_columns"],
        )
        self.assertEqual(
            training_result["factor_protocol"]["roles"],
            inference_result["factor_protocol"]["roles"],
        )

    def test_training_and_inference_expose_selected_preprocessing_rules(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config = load_qlib_config(
                env={
                    "QUANT_QLIB_RUNTIME_ROOT": str(Path(temp_dir)),
                    "QUANT_QLIB_WINDOW_MODE": "rolling",
                    "QUANT_QLIB_MISSING_POLICY": "strict_drop",
                    "QUANT_QLIB_OUTLIER_POLICY": "raw",
                    "QUANT_QLIB_NORMALIZATION_POLICY": "zscore_by_symbol",
                },
                require_explicit=True,
            )
            runner = QlibRunner(config=config)
            dataset = {
                "BTCUSDT": _sample_timing_candles(step_hours=4, count=240),
                "ETHUSDT": _sample_timing_candles(step_hours=4, count=240),
            }

            training_result = runner.train(dataset)
            inference_result = runner.infer(dataset)

        self.assertEqual(training_result["factor_protocol"]["preprocessing"]["missing_policy"], "窗口不足时直接丢弃")
        self.assertEqual(training_result["factor_protocol"]["preprocessing"]["outlier_policy"], "保留原始极值")
        self.assertEqual(training_result["factor_protocol"]["preprocessing"]["normalization_policy"], "按单币样本做 z-score 标准化")
        self.assertEqual(
            inference_result["factor_protocol"]["preprocessing"],
            training_result["factor_protocol"]["preprocessing"],
        )


def _sample_timing_candles(*, step_hours: int, count: int = 72) -> list[dict[str, object]]:
    candles: list[dict[str, object]] = []
    base_open_time = 1712016000000
    step_ms = step_hours * 60 * 60 * 1000
    previous_close = 100.0
    for index in range(count):
        close_price = previous_close + 0.8
        candles.append(
            {
                "open_time": base_open_time + index * step_ms,
                "open": f"{previous_close:.2f}",
                "high": f"{close_price + 0.6:.2f}",
                "low": f"{previous_close - 0.4:.2f}",
                "close": f"{close_price:.2f}",
                "volume": f"{1200 + index * 12:.2f}",
                "close_time": base_open_time + (index + 1) * step_ms - 1,
            }
        )
        previous_close = close_price
    return candles


if __name__ == "__main__":
    unittest.main()
