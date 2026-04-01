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

    def test_label_builder_outputs_stable_structure(self) -> None:
        rows = build_label_rows("BTCUSDT", _sample_candles())

        self.assertEqual(len(rows), 4)
        self.assertEqual(tuple(rows[0].keys()), LABEL_COLUMNS)
        self.assertIn(rows[-1]["direction"], {"up", "down", "flat", "unknown"})

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

            result = runner.train(dataset={"BTCUSDT": _sample_candles(), "ETHUSDT": _sample_candles()})

        self.assertEqual(result["status"], "completed")
        self.assertIn("run_id", result)
        self.assertIn("model_version", result)
        self.assertGreater(result["sample_count"], 0)

    def test_inference_returns_standardized_signal_result(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime_root = Path(temp_dir)
            runtime_root.mkdir(exist_ok=True)
            config = load_qlib_config(
                env={"QUANT_QLIB_RUNTIME_ROOT": str(runtime_root)},
                require_explicit=True,
            )
            runner = QlibRunner(config=config)
            runner.train(dataset={"BTCUSDT": _sample_candles(), "ETHUSDT": _sample_candles()})

            result = runner.infer(dataset={"BTCUSDT": _sample_candles(), "ETHUSDT": _sample_candles()})

        self.assertEqual(result["status"], "completed")
        self.assertTrue(result["signals"])
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

    def test_training_skips_dirty_candles_without_label_misalignment(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime_root = Path(temp_dir)
            runtime_root.mkdir(exist_ok=True)
            config = load_qlib_config(
                env={"QUANT_QLIB_RUNTIME_ROOT": str(runtime_root)},
                require_explicit=True,
            )
            runner = QlibRunner(config=config)
            candles = _sample_candles()
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
        self.assertEqual(result["sample_count"], 2)


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


if __name__ == "__main__":
    unittest.main()
