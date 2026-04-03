from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.worker.qlib_config import QlibConfigurationError, load_qlib_config  # noqa: E402
from services.worker.qlib_features import FEATURE_COLUMNS, build_feature_rows  # noqa: E402
from services.worker.qlib_labels import LABEL_COLUMNS, build_label_rows  # noqa: E402
from services.worker.qlib_runner import QlibRunner  # noqa: E402


class QlibConfigTests(unittest.TestCase):
    def test_missing_explicit_config_returns_clear_status(self) -> None:
        config = load_qlib_config(env={}, require_explicit=True)

        self.assertEqual(config.status, "unconfigured")
        self.assertIn("QUANT_QLIB_RUNTIME_ROOT", config.detail)

    def test_missing_runtime_root_raises_clear_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime_root = Path(temp_dir) / "missing-root"
            config = load_qlib_config(
                env={"QUANT_QLIB_RUNTIME_ROOT": str(runtime_root)},
                require_explicit=True,
            )

            with self.assertRaises(QlibConfigurationError) as context:
                config.ensure_ready()

        self.assertIn("运行目录不存在", str(context.exception))


class QlibFeatureTests(unittest.TestCase):
    def test_feature_builder_outputs_stable_columns(self) -> None:
        rows = build_feature_rows("BTCUSDT", _sample_candles())

        self.assertEqual(len(rows), 4)
        self.assertEqual(tuple(rows[0].keys()), FEATURE_COLUMNS)
        self.assertEqual(rows[-1]["symbol"], "BTCUSDT")
        self.assertEqual(rows[0]["close_return_pct"], "0.0000")
        self.assertEqual(rows[1]["close_return_pct"], "3.9216")

    def test_feature_builder_outputs_timing_columns(self) -> None:
        rows = build_feature_rows("BTCUSDT", _sample_timing_candles(step_hours=4))

        self.assertIn("ema20_gap_pct", rows[-1])
        self.assertIn("ema55_gap_pct", rows[-1])
        self.assertIn("atr_pct", rows[-1])
        self.assertIn("rsi14", rows[-1])
        self.assertIn("breakout_strength", rows[-1])

    def test_label_builder_outputs_stable_structure(self) -> None:
        rows = build_label_rows("BTCUSDT", _sample_candles())

        self.assertEqual(len(rows), 4)
        self.assertEqual(tuple(rows[0].keys()), LABEL_COLUMNS)
        self.assertIn(rows[-1]["label"], {"buy", "sell", "watch"})

    def test_label_builder_marks_trainable_rows_with_1_to_3_day_window(self) -> None:
        rows = build_label_rows("BTCUSDT", _sample_timing_candles(step_hours=4))

        self.assertTrue(rows[10]["is_trainable"])
        self.assertEqual(rows[10]["holding_window"], "1-3d")
        self.assertEqual(rows[10]["label"], "buy")

    def test_label_builder_marks_tail_rows_without_full_future_window_untrainable(self) -> None:
        rows = build_label_rows("BTCUSDT", _sample_timing_candles(step_hours=4))

        self.assertTrue(rows[-19]["is_trainable"])
        self.assertEqual(rows[-19]["holding_window"], "1-3d")
        self.assertFalse(rows[-18]["is_trainable"])
        self.assertEqual(rows[-18]["label"], "watch")

    def test_label_builder_uses_1h_window_for_hourly_candles(self) -> None:
        rows = build_label_rows("BTCUSDT", _sample_timing_candles(step_hours=1, count=96))

        self.assertTrue(rows[23]["is_trainable"])
        self.assertEqual(rows[23]["holding_window"], "1-3d")
        self.assertFalse(rows[24]["is_trainable"])
        self.assertEqual(rows[24]["label"], "watch")

    def test_label_builder_marks_buy_when_target_is_hit_inside_1_to_3_day_window(self) -> None:
        rows = build_label_rows("BTCUSDT", _sample_window_hit_candles())

        self.assertTrue(rows[0]["is_trainable"])
        self.assertEqual(rows[0]["holding_window"], "1-3d")
        self.assertEqual(rows[0]["label"], "buy")

    def test_label_builder_marks_sell_when_stop_is_hit_inside_1_to_3_day_window(self) -> None:
        rows = build_label_rows("BTCUSDT", _sample_window_sell_hit_candles())

        self.assertTrue(rows[0]["is_trainable"])
        self.assertEqual(rows[0]["holding_window"], "1-3d")
        self.assertEqual(rows[0]["label"], "sell")

    def test_label_builder_prefers_earlier_hit_inside_1_to_3_day_window(self) -> None:
        rows = build_label_rows("BTCUSDT", _sample_window_competing_hit_candles())

        self.assertTrue(rows[0]["is_trainable"])
        self.assertEqual(rows[0]["holding_window"], "1-3d")
        self.assertEqual(rows[0]["label"], "buy")

    def test_dirty_candle_is_filtered_consistently_for_features_and_labels(self) -> None:
        candles = _sample_candles()
        candles[1] = {
            "open_time": candles[1]["open_time"],
            "high": candles[1]["high"],
            "low": candles[1]["low"],
            "close": candles[1]["close"],
            "volume": candles[1]["volume"],
            "close_time": candles[1]["close_time"],
        }

        feature_rows = build_feature_rows("BTCUSDT", candles)
        label_rows = build_label_rows("BTCUSDT", candles)

        self.assertEqual([row["generated_at"] for row in feature_rows], [row["generated_at"] for row in label_rows])


class QlibRunnerTests(unittest.TestCase):
    def test_training_returns_run_record(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime_root = Path(temp_dir)
            runtime_root.mkdir(exist_ok=True)
            config = load_qlib_config(
                env={"QUANT_QLIB_RUNTIME_ROOT": str(runtime_root)},
                require_explicit=True,
            )
            runner = QlibRunner(config=config)

            result = runner.train(dataset={"BTCUSDT": _sample_timing_candles(step_hours=4), "ETHUSDT": _sample_timing_candles(step_hours=4)})

        self.assertEqual(result["status"], "completed")
        self.assertIn("run_id", result)
        self.assertIn("model_version", result)
        self.assertGreater(result["sample_count"], 0)
        self.assertIn("validation", result)
        self.assertIn("backtest", result)

    def test_inference_returns_standardized_signal_result(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime_root = Path(temp_dir)
            runtime_root.mkdir(exist_ok=True)
            config = load_qlib_config(
                env={"QUANT_QLIB_RUNTIME_ROOT": str(runtime_root)},
                require_explicit=True,
            )
            runner = QlibRunner(config=config)
            runner.train(dataset={"BTCUSDT": _sample_timing_candles(step_hours=4), "ETHUSDT": _sample_timing_candles(step_hours=4)})

            result = runner.infer(dataset={"BTCUSDT": _sample_timing_candles(step_hours=4), "ETHUSDT": _sample_timing_candles(step_hours=4)})

        self.assertEqual(result["status"], "completed")
        self.assertTrue(result["signals"])
        self.assertIn("candidates", result)
        self.assertTrue(result["candidates"]["items"])
        self.assertEqual(len(result["candidates"]["items"]), 2)
        self.assertEqual(result["candidates"]["summary"]["candidate_count"], 2)
        self.assertEqual(
            set(result["signals"][0].keys()),
            {
                "symbol",
                "signal",
                "side",
                "score",
                "confidence",
                "target_weight",
                "explanation",
                "model_version",
                "source",
                "generated_at",
            },
        )

    def test_inference_builds_candidate_level_dry_run_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime_root = Path(temp_dir)
            runtime_root.mkdir(exist_ok=True)
            config = load_qlib_config(
                env={"QUANT_QLIB_RUNTIME_ROOT": str(runtime_root)},
                require_explicit=True,
            )
            runner = QlibRunner(config=config)
            runner.train(
                dataset={
                    "BTCUSDT": _sample_timing_candles(step_hours=4),
                    "DOGEUSDT": _sample_negative_timing_candles(step_hours=4),
                }
            )

            result = runner.infer(
                dataset={
                    "BTCUSDT": _sample_timing_candles(step_hours=4),
                    "DOGEUSDT": _sample_negative_timing_candles(step_hours=4),
                }
            )

        candidates = {item["symbol"]: item for item in result["candidates"]["items"]}
        self.assertTrue(candidates["BTCUSDT"]["allowed_to_dry_run"])
        self.assertFalse(candidates["DOGEUSDT"]["allowed_to_dry_run"])

    def test_training_skips_dirty_candles_without_label_misalignment(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime_root = Path(temp_dir)
            runtime_root.mkdir(exist_ok=True)
            config = load_qlib_config(
                env={"QUANT_QLIB_RUNTIME_ROOT": str(runtime_root)},
                require_explicit=True,
            )
            runner = QlibRunner(config=config)
            candles = _sample_timing_candles(step_hours=4)
            candles[1] = {
                "open_time": candles[1]["open_time"],
                "high": candles[1]["high"],
                "low": candles[1]["low"],
                "close": candles[1]["close"],
                "volume": candles[1]["volume"],
                "close_time": candles[1]["close_time"],
            }

            result = runner.train(dataset={"BTCUSDT": candles})

        self.assertEqual(result["status"], "completed")
        self.assertGreater(result["sample_count"], 0)

    def test_training_rejects_dataset_without_validation_and_backtest_split(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime_root = Path(temp_dir)
            runtime_root.mkdir(exist_ok=True)
            config = load_qlib_config(
                env={"QUANT_QLIB_RUNTIME_ROOT": str(runtime_root)},
                require_explicit=True,
            )
            runner = QlibRunner(config=config)

            with self.assertRaises(RuntimeError) as ctx:
                runner.train(
                    dataset={
                        "BTCUSDT": _sample_timing_candles(step_hours=4)[:20],
                    }
                )

        self.assertIn("完整验证和回测结果", str(ctx.exception))


def _sample_candles() -> list[dict[str, object]]:
    return [
        {
            "open_time": 1712016000000,
            "open": "100",
            "high": "104",
            "low": "99",
            "close": "102",
            "volume": "1200",
            "close_time": 1712019599999,
        },
        {
            "open_time": 1712019600000,
            "open": "102",
            "high": "107",
            "low": "101",
            "close": "106",
            "volume": "1350",
            "close_time": 1712023199999,
        },
        {
            "open_time": 1712023200000,
            "open": "106",
            "high": "109",
            "low": "103",
            "close": "108",
            "volume": "1420",
            "close_time": 1712026799999,
        },
        {
            "open_time": 1712026800000,
            "open": "108",
            "high": "112",
            "low": "107",
            "close": "111",
            "volume": "1500",
            "close_time": 1712030399999,
        },
    ]



def _sample_timing_candles(*, step_hours: int, count: int = 80) -> list[dict[str, object]]:
    candles: list[dict[str, object]] = []
    base_open_time = 1712016000000
    base_close_time = 1712019599999
    step_ms = step_hours * 60 * 60 * 1000
    price = 100.0
    for index in range(count):
        open_price = price
        close_price = price + 0.8 + (index % 5) * 0.35
        high_price = max(open_price, close_price) + 1.5
        low_price = min(open_price, close_price) - 1.2
        volume = 1200 + index * 12
        candles.append(
            {
                "open_time": base_open_time + index * step_ms,
                "open": f"{open_price:.2f}",
                "high": f"{high_price:.2f}",
                "low": f"{low_price:.2f}",
                "close": f"{close_price:.2f}",
                "volume": f"{volume:.2f}",
                "close_time": base_close_time + index * step_ms,
            }
        )
        price = close_price
    return candles


def _sample_negative_timing_candles(*, step_hours: int, count: int = 80) -> list[dict[str, object]]:
    candles: list[dict[str, object]] = []
    base_open_time = 1712016000000
    base_close_time = 1712019599999
    step_ms = step_hours * 60 * 60 * 1000
    price = 100.0
    for index in range(count):
        open_price = price
        close_price = price - (0.7 + (index % 4) * 0.25)
        high_price = max(open_price, close_price) + 1.2
        low_price = min(open_price, close_price) - 1.4
        volume = 900 + index * 6
        candles.append(
            {
                "open_time": base_open_time + index * step_ms,
                "open": f"{open_price:.2f}",
                "high": f"{high_price:.2f}",
                "low": f"{low_price:.2f}",
                "close": f"{close_price:.2f}",
                "volume": f"{volume:.2f}",
                "close_time": base_close_time + index * step_ms,
            }
        )
        price = close_price
    return candles


def _sample_window_hit_candles() -> list[dict[str, object]]:
    candles: list[dict[str, object]] = []
    base_open_time = 1712016000000
    base_close_time = 1712019599999
    step_ms = 4 * 60 * 60 * 1000
    closes = [
        100.0,
        100.2,
        100.1,
        100.0,
        100.3,
        100.1,
        101.5,
        102.2,
        101.8,
        101.4,
        101.1,
        100.8,
        100.7,
        100.6,
        100.5,
        100.4,
        100.3,
        100.2,
        100.1,
        100.0,
        99.9,
        99.8,
        99.7,
        99.6,
        99.5,
    ]
    previous_close = closes[0]
    for index, close_price in enumerate(closes):
        open_price = previous_close
        high_price = max(open_price, close_price) + 0.6
        low_price = min(open_price, close_price) - 0.6
        candles.append(
            {
                "open_time": base_open_time + index * step_ms,
                "open": f"{open_price:.2f}",
                "high": f"{high_price:.2f}",
                "low": f"{low_price:.2f}",
                "close": f"{close_price:.2f}",
                "volume": f"{1200 + index * 10:.2f}",
                "close_time": base_close_time + index * step_ms,
            }
        )
        previous_close = close_price
    return candles


def _sample_window_sell_hit_candles() -> list[dict[str, object]]:
    closes = [
        100.0,
        99.8,
        99.9,
        100.1,
        100.0,
        99.7,
        98.8,
        98.5,
        98.9,
        99.1,
        99.0,
        98.7,
        98.6,
        98.4,
        98.2,
        98.1,
        98.0,
        97.9,
        97.8,
        97.9,
        98.0,
        98.1,
        98.0,
        97.9,
        97.8,
    ]
    return _build_window_candles(closes)


def _sample_window_competing_hit_candles() -> list[dict[str, object]]:
    closes = [
        100.0,
        100.1,
        100.0,
        100.2,
        100.1,
        100.0,
        101.4,
        101.8,
        100.5,
        99.2,
        98.7,
        98.5,
        98.9,
        99.1,
        99.0,
        99.2,
        99.1,
        99.0,
        98.9,
        98.8,
        98.7,
        98.6,
        98.5,
        98.4,
        98.3,
    ]
    return _build_window_candles(closes)


def _build_window_candles(closes: list[float]) -> list[dict[str, object]]:
    candles: list[dict[str, object]] = []
    base_open_time = 1712016000000
    base_close_time = 1712019599999
    step_ms = 4 * 60 * 60 * 1000
    previous_close = closes[0]
    for index, close_price in enumerate(closes):
        open_price = previous_close
        high_price = max(open_price, close_price) + 0.6
        low_price = min(open_price, close_price) - 0.6
        candles.append(
            {
                "open_time": base_open_time + index * step_ms,
                "open": f"{open_price:.2f}",
                "high": f"{high_price:.2f}",
                "low": f"{low_price:.2f}",
                "close": f"{close_price:.2f}",
                "volume": f"{1200 + index * 10:.2f}",
                "close_time": base_close_time + index * step_ms,
            }
        )
        previous_close = close_price
    return candles


if __name__ == "__main__":
    unittest.main()
