from __future__ import annotations

import json
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.worker.qlib_config import QlibConfigurationError, load_qlib_config  # noqa: E402
from services.worker.qlib_dataset import DatasetBundle  # noqa: E402
from services.worker.qlib_features import AUXILIARY_FEATURE_COLUMNS, PRIMARY_FEATURE_COLUMNS  # noqa: E402
from services.worker.qlib_features import FEATURE_COLUMNS, build_feature_rows  # noqa: E402
from services.worker.qlib_labels import LABEL_COLUMNS, build_label_rows  # noqa: E402
from services.worker.qlib_runner import QlibRunner  # noqa: E402


class QlibConfigTests(unittest.TestCase):
    def test_missing_explicit_config_returns_clear_status(self) -> None:
        config = load_qlib_config(env={}, require_explicit=True)

        self.assertEqual(config.status, "unconfigured")
        self.assertIn("QUANT_QLIB_RUNTIME_ROOT", config.detail)

    def test_missing_runtime_root_is_created_automatically(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime_root = Path(temp_dir) / "missing-root"
            config = load_qlib_config(
                env={"QUANT_QLIB_RUNTIME_ROOT": str(runtime_root)},
                require_explicit=True,
            )
            config.ensure_ready()
            self.assertTrue(runtime_root.exists())

    def test_backtest_assumptions_can_be_overridden_from_env(self) -> None:
        config = load_qlib_config(
            env={
                "QUANT_QLIB_RUNTIME_ROOT": "/tmp/quant-qlib-runtime",
                "QUANT_QLIB_BACKTEST_FEE_BPS": "12",
                "QUANT_QLIB_BACKTEST_SLIPPAGE_BPS": "7",
            },
            require_explicit=True,
        )

        self.assertEqual(str(config.backtest_fee_bps), "12")
        self.assertEqual(str(config.backtest_slippage_bps), "7")

    def test_runtime_controls_can_be_overridden_from_env(self) -> None:
        config = load_qlib_config(
            env={
                "QUANT_QLIB_RUNTIME_ROOT": "/tmp/quant-qlib-runtime",
                "QUANT_QLIB_SELECTED_SYMBOLS": "ETHUSDT,DOGEUSDT",
                "QUANT_QLIB_TIMEFRAMES": "4h",
                "QUANT_QLIB_SAMPLE_LIMIT": "180",
                "QUANT_QLIB_LOOKBACK_DAYS": "21",
                "QUANT_QLIB_PRIMARY_FACTORS": "ema20_gap_pct,trend_gap_pct",
                "QUANT_QLIB_AUXILIARY_FACTORS": "rsi14",
                "QUANT_QLIB_RESEARCH_TEMPLATE": "single_asset_timing_strict",
                "QUANT_QLIB_LABEL_TARGET_PCT": "1.5",
                "QUANT_QLIB_LABEL_STOP_PCT": "-0.8",
                "QUANT_QLIB_HOLDING_WINDOW_MIN_DAYS": "2",
                "QUANT_QLIB_HOLDING_WINDOW_MAX_DAYS": "4",
                "QUANT_QLIB_MODEL_KEY": "trend_bias_v2",
                "QUANT_QLIB_DRY_RUN_MIN_SCORE": "0.60",
                "QUANT_QLIB_LIVE_MIN_SCORE": "0.80",
            },
            require_explicit=True,
        )

        self.assertEqual(config.selected_symbols, ("ETHUSDT", "DOGEUSDT"))
        self.assertEqual(config.selected_timeframes, ("4h",))
        self.assertEqual(config.sample_limit, 180)
        self.assertEqual(config.lookback_days, 21)
        self.assertEqual(config.primary_feature_columns, ("ema20_gap_pct", "trend_gap_pct"))
        self.assertEqual(config.auxiliary_feature_columns, ("rsi14",))
        self.assertEqual(config.research_template, "single_asset_timing_strict")
        self.assertEqual(config.label_mode, "earliest_hit")
        self.assertEqual(str(config.label_target_pct), "1.5")
        self.assertEqual(str(config.label_stop_pct), "-0.8")
        self.assertEqual(config.holding_window_label, "2-4d")
        self.assertEqual(config.model_key, "trend_bias_v2")
        self.assertEqual(str(config.dry_run_min_score), "0.60")
        self.assertEqual(str(config.live_min_score), "0.80")

    def test_runtime_controls_include_label_mode_and_preprocessing_policies(self) -> None:
        config = load_qlib_config(
            env={
                "QUANT_QLIB_RUNTIME_ROOT": "/tmp/quant-qlib-runtime",
                "QUANT_QLIB_LABEL_MODE": "close_only",
                "QUANT_QLIB_OUTLIER_POLICY": "raw",
                "QUANT_QLIB_NORMALIZATION_POLICY": "zscore_by_symbol",
                "QUANT_QLIB_SIGNAL_CONFIDENCE_FLOOR": "0.63",
                "QUANT_QLIB_TREND_WEIGHT": "1.8",
                "QUANT_QLIB_VOLUME_WEIGHT": "1.4",
                "QUANT_QLIB_OSCILLATOR_WEIGHT": "0.5",
                "QUANT_QLIB_VOLATILITY_WEIGHT": "0.6",
                "QUANT_QLIB_STRICT_PENALTY_WEIGHT": "1.4",
            },
            require_explicit=True,
        )

        self.assertEqual(config.label_mode, "close_only")
        self.assertEqual(config.outlier_policy, "raw")
        self.assertEqual(config.normalization_policy, "zscore_by_symbol")
        self.assertEqual(str(config.signal_confidence_floor), "0.63")
        self.assertEqual(str(config.trend_weight), "1.8")
        self.assertEqual(str(config.volume_weight), "1.4")
        self.assertEqual(str(config.oscillator_weight), "0.5")
        self.assertEqual(str(config.volatility_weight), "0.6")
        self.assertEqual(str(config.strict_penalty_weight), "1.4")

    def test_runtime_controls_use_default_factors_when_not_configured(self) -> None:
        config = load_qlib_config(
            env={"QUANT_QLIB_RUNTIME_ROOT": "/tmp/quant-qlib-runtime"},
            require_explicit=True,
        )

        self.assertEqual(config.primary_feature_columns, PRIMARY_FEATURE_COLUMNS)
        self.assertEqual(config.auxiliary_feature_columns, AUXILIARY_FEATURE_COLUMNS)


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

    def test_label_builder_supports_close_only_mode(self) -> None:
        rows = build_label_rows(
            "BTCUSDT",
            _sample_window_competing_hit_candles(),
            label_mode="close_only",
        )

        self.assertTrue(rows[0]["is_trainable"])
        self.assertEqual(rows[0]["holding_window"], "1-3d")
        self.assertEqual(rows[0]["label"], "sell")

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
    def test_scoring_and_rule_gate_change_when_strict_template_is_selected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime_root = Path(temp_dir)
            runtime_root.mkdir(exist_ok=True)
            base_env = {"QUANT_QLIB_RUNTIME_ROOT": str(runtime_root)}
            relaxed_runner = QlibRunner(config=load_qlib_config(env=base_env, require_explicit=True))
            strict_runner = QlibRunner(
                config=load_qlib_config(
                    env={**base_env, "QUANT_QLIB_RESEARCH_TEMPLATE": "single_asset_timing_strict"},
                    require_explicit=True,
                )
            )
            metrics = {
                "feature_averages": {
                    "trend_gap_pct": "0.8000",
                    "ema20_gap_pct": "0.9000",
                    "ema55_gap_pct": "1.4000",
                    "atr_pct": "4.0000",
                    "volume_ratio": "1.0000",
                },
                "avg_future_return_pct": "0.6000",
                "positive_rate": "0.5200",
            }
            feature_row = {
                "trend_gap_pct": "1.1000",
                "ema20_gap_pct": "1.1000",
                "ema55_gap_pct": "1.7000",
                "atr_pct": "4.7000",
                "volume_ratio": "1.0200",
            }

            relaxed_score = relaxed_runner._score_signal(feature_row, metrics)
            strict_score = strict_runner._score_signal(feature_row, metrics)
            relaxed_gate = relaxed_runner._build_rule_gate(feature_row)
            strict_gate = strict_runner._build_rule_gate(feature_row)

        self.assertGreater(relaxed_score, strict_score)
        self.assertEqual(relaxed_gate["status"], "passed")
        self.assertEqual(strict_gate["status"], "failed")
        self.assertIn("strict_template_not_confirmed", strict_gate["reasons"])

    def test_scoring_respects_configured_category_weights(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime_root = Path(temp_dir)
            runtime_root.mkdir(exist_ok=True)
            low_weight_runner = QlibRunner(
                config=load_qlib_config(
                    env={
                        "QUANT_QLIB_RUNTIME_ROOT": str(runtime_root),
                        "QUANT_QLIB_TREND_WEIGHT": "0.5",
                    },
                    require_explicit=True,
                )
            )
            high_weight_runner = QlibRunner(
                config=load_qlib_config(
                    env={
                        "QUANT_QLIB_RUNTIME_ROOT": str(runtime_root),
                        "QUANT_QLIB_TREND_WEIGHT": "2.2",
                    },
                    require_explicit=True,
                )
            )
            metrics = {
                "feature_averages": {
                    "trend_gap_pct": "0.5000",
                    "ema20_gap_pct": "0.9000",
                    "ema55_gap_pct": "1.1000",
                },
                "avg_future_return_pct": "0.3000",
                "positive_rate": "0.5200",
            }
            feature_row = {
                "trend_gap_pct": "1.3000",
                "ema20_gap_pct": "1.5000",
                "ema55_gap_pct": "1.7000",
            }

            low_score = low_weight_runner._score_signal(feature_row, metrics)
            high_score = high_weight_runner._score_signal(feature_row, metrics)

        self.assertGreater(high_score, low_score)

    def test_training_exposes_data_states_and_backtest_snapshot_reference(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime_root = Path(temp_dir)
            runtime_root.mkdir(exist_ok=True)
            config = load_qlib_config(
                env={"QUANT_QLIB_RUNTIME_ROOT": str(runtime_root)},
                require_explicit=True,
            )
            runner = QlibRunner(config=config)

            result = runner.train(
                dataset={
                    "BTCUSDT": _sample_timing_candles(step_hours=4),
                    "ETHUSDT": _sample_timing_candles(step_hours=4),
                }
            )

        snapshot = result["dataset_snapshot"]
        self.assertEqual(snapshot["active_data_state"], "feature-ready")
        self.assertEqual(set(snapshot["data_states"].keys()), {"raw", "cleaned", "feature-ready"})
        self.assertEqual(snapshot["data_states"]["raw"]["symbol_count"], 2)
        self.assertGreater(snapshot["data_states"]["feature-ready"]["row_count"], 0)
        self.assertEqual(result["backtest"]["data_snapshot"]["snapshot_id"], snapshot["snapshot_id"])
        self.assertEqual(result["backtest"]["data_snapshot"]["cache_signature"], snapshot["cache_signature"])

    def test_training_returns_experiment_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime_root = Path(temp_dir)
            runtime_root.mkdir(exist_ok=True)
            config = load_qlib_config(
                env={"QUANT_QLIB_RUNTIME_ROOT": str(runtime_root)},
                require_explicit=True,
            )
            runner = QlibRunner(config=config)

            result = runner.train(
                dataset={
                    "BTCUSDT": _sample_timing_candles(step_hours=4),
                    "ETHUSDT": _sample_timing_candles(step_hours=4),
                }
            )

        self.assertIn("experiment_report", result)
        self.assertIn("overview", result["experiment_report"])
        self.assertEqual(result["experiment_report"]["overview"]["candidate_count"], 0)
        self.assertEqual(result["experiment_report"]["latest_training"]["model_version"], result["model_version"])
        self.assertIn("dataset_snapshot", result)
        self.assertIn("dataset_snapshot_path", result)

    def test_training_uses_dataset_bundle_for_multi_timeframe_input(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime_root = Path(temp_dir)
            runtime_root.mkdir(exist_ok=True)
            config = load_qlib_config(
                env={"QUANT_QLIB_RUNTIME_ROOT": str(runtime_root)},
                require_explicit=True,
            )
            runner = QlibRunner(config=config)
            candles_1h = _sample_timing_candles(step_hours=1, count=96)
            candles_4h = _sample_timing_candles(step_hours=4, count=80)
            bundle = DatasetBundle(
                symbol="BTCUSDT",
                timeframe="4h",
                training_rows=[_sample_training_row(1), _sample_training_row(2), _sample_training_row(3)],
                validation_rows=[_sample_training_row(4)],
                testing_rows=[_sample_training_row(5), _sample_training_row(6)],
            )

            with mock.patch("services.worker.qlib_runner.build_dataset_bundle", return_value=bundle) as mocked_bundle:
                result = runner.train(
                    dataset={
                        "BTCUSDT": {
                            "candles_1h": candles_1h,
                            "candles_4h": candles_4h,
                        }
                    }
                )

        mocked_bundle.assert_called_once_with(
            symbol="BTCUSDT",
            candles_1h=candles_1h,
            candles_4h=candles_4h,
            lookback_days=config.lookback_days,
            label_target_pct=config.label_target_pct,
            label_stop_pct=config.label_stop_pct,
            label_mode=config.label_mode,
            missing_policy=config.missing_policy,
            outlier_policy=config.outlier_policy,
            normalization_policy=config.normalization_policy,
            min_window_days=config.holding_window_min_days,
            max_window_days=config.holding_window_max_days,
            holding_window_label=config.holding_window_label,
            window_mode=config.window_mode,
            start_date=config.start_date,
            end_date=config.end_date,
            train_split_ratio=config.train_split_ratio,
            validation_split_ratio=config.validation_split_ratio,
            test_split_ratio=config.test_split_ratio,
        )
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["sample_count"], 3)

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
            self.assertTrue(Path(result["dataset_snapshot_path"]).exists())

        self.assertEqual(result["status"], "completed")
        self.assertIn("run_id", result)
        self.assertIn("model_version", result)
        self.assertGreater(result["sample_count"], 0)
        self.assertIn("validation", result)
        self.assertIn("backtest", result)
        self.assertIn("assumptions", result["backtest"])
        self.assertIn("training_context", result)
        self.assertEqual(result["training_context"]["feature_version"], "v2")
        self.assertEqual(result["training_context"]["holding_window"], "1-3d")
        self.assertIn("sample_window", result["training_context"])

    def test_training_writes_dataset_snapshot_and_experiment_index(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime_root = Path(temp_dir)
            runtime_root.mkdir(exist_ok=True)
            config = load_qlib_config(
                env={"QUANT_QLIB_RUNTIME_ROOT": str(runtime_root)},
                require_explicit=True,
            )
            runner = QlibRunner(config=config)

            result = runner.train(dataset={"BTCUSDT": _sample_timing_candles(step_hours=4), "ETHUSDT": _sample_timing_candles(step_hours=4)})

            dataset_snapshot = json.loads(config.paths.latest_dataset_snapshot_path.read_text(encoding="utf-8"))
            experiment_index = json.loads(config.paths.experiment_index_path.read_text(encoding="utf-8"))

        self.assertEqual(dataset_snapshot["snapshot_id"], result["dataset_snapshot"]["snapshot_id"])
        self.assertEqual(dataset_snapshot["summary"]["symbol_count"], 2)
        self.assertIn("cache", dataset_snapshot["summary"])
        self.assertIn("data_states", dataset_snapshot["summary"])
        self.assertEqual(dataset_snapshot["summary"]["data_states"]["current"], "feature-ready")
        self.assertEqual(dataset_snapshot["symbols"][0]["data_layers"]["feature-ready"]["state"], "ready")
        self.assertEqual(experiment_index["items"][0]["run_id"], result["run_id"])
        self.assertEqual(experiment_index["items"][0]["run_type"], "training")
        self.assertIn("dataset_snapshot", experiment_index["items"][0])
        self.assertEqual(experiment_index["items"][0]["dataset_snapshot"]["data_states"]["current"], "feature-ready")

    def test_training_reuses_dataset_cache_for_same_input(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime_root = Path(temp_dir)
            runtime_root.mkdir(exist_ok=True)
            config = load_qlib_config(
                env={"QUANT_QLIB_RUNTIME_ROOT": str(runtime_root)},
                require_explicit=True,
            )
            runner = QlibRunner(config=config)
            dataset = {"BTCUSDT": _sample_timing_candles(step_hours=4), "ETHUSDT": _sample_timing_candles(step_hours=4)}

            first = runner.train(dataset=dataset)
            second = runner.train(dataset=dataset)

        self.assertEqual(first["dataset_snapshot"]["summary"]["cache"]["miss_count"], 2)
        self.assertEqual(second["dataset_snapshot"]["summary"]["cache"]["hit_count"], 2)
        self.assertEqual(second["dataset_snapshot"]["symbols"][0]["cache"]["status"], "hit")
        self.assertTrue(second["dataset_snapshot"]["symbols"][0]["cache"]["path"])

    def test_training_invalidates_dataset_cache_when_label_parameters_change(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime_root = Path(temp_dir)
            runtime_root.mkdir(exist_ok=True)
            dataset = {"BTCUSDT": _sample_timing_candles(step_hours=4), "ETHUSDT": _sample_timing_candles(step_hours=4)}
            first_runner = QlibRunner(
                config=load_qlib_config(
                    env={
                        "QUANT_QLIB_RUNTIME_ROOT": str(runtime_root),
                        "QUANT_QLIB_LABEL_TARGET_PCT": "1.0",
                        "QUANT_QLIB_LABEL_STOP_PCT": "-1.0",
                    },
                    require_explicit=True,
                )
            )
            second_runner = QlibRunner(
                config=load_qlib_config(
                    env={
                        "QUANT_QLIB_RUNTIME_ROOT": str(runtime_root),
                        "QUANT_QLIB_LABEL_TARGET_PCT": "1.8",
                        "QUANT_QLIB_LABEL_STOP_PCT": "-0.5",
                    },
                    require_explicit=True,
                )
            )

            first = first_runner.train(dataset=dataset)
            second = second_runner.train(dataset=dataset)

        self.assertEqual(first["dataset_snapshot"]["summary"]["cache"]["miss_count"], 2)
        self.assertEqual(second["dataset_snapshot"]["summary"]["cache"]["miss_count"], 2)
        self.assertEqual(second["dataset_snapshot"]["symbols"][0]["cache"]["status"], "miss")
        self.assertNotEqual(
            first["dataset_snapshot"]["symbols"][0]["cache"]["key"],
            second["dataset_snapshot"]["symbols"][0]["cache"]["key"],
        )

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

    def test_inference_uses_research_template_to_select_strategy_template(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime_root = Path(temp_dir)
            runtime_root.mkdir(exist_ok=True)
            config = load_qlib_config(
                env={
                    "QUANT_QLIB_RUNTIME_ROOT": str(runtime_root),
                    "QUANT_QLIB_RESEARCH_TEMPLATE": "single_asset_timing_strict",
                },
                require_explicit=True,
            )
            runner = QlibRunner(config=config)
            dataset = {"BTCUSDT": _sample_timing_candles(step_hours=4), "ETHUSDT": _sample_timing_candles(step_hours=4)}
            runner.train(dataset=dataset)

            result = runner.infer(dataset=dataset)

        self.assertTrue(result["candidates"]["items"])
        self.assertTrue(all(item["strategy_template"] == "trend_pullback_timing" for item in result["candidates"]["items"]))

    def test_inference_returns_experiment_report(self) -> None:
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

        self.assertIn("experiment_report", result)
        self.assertEqual(result["experiment_report"]["overview"]["signal_count"], len(result["signals"]))
        self.assertEqual(result["experiment_report"]["overview"]["candidate_count"], len(result["candidates"]["items"]))
        self.assertIn("leaderboard", result["experiment_report"])
        self.assertIn("screening", result["experiment_report"])
        self.assertIn("recent_runs", result["experiment_report"]["experiments"])

    def test_inference_reuses_standardized_snapshot_for_same_dataset(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime_root = Path(temp_dir)
            runtime_root.mkdir(exist_ok=True)
            config = load_qlib_config(
                env={"QUANT_QLIB_RUNTIME_ROOT": str(runtime_root)},
                require_explicit=True,
            )
            runner = QlibRunner(config=config)
            dataset = {
                "BTCUSDT": _sample_timing_candles(step_hours=4),
                "ETHUSDT": _sample_timing_candles(step_hours=4),
            }

            training_result = runner.train(dataset=dataset)
            inference_result = runner.infer(dataset=dataset)

        self.assertEqual(
            training_result["dataset_snapshot"]["cache_signature"],
            inference_result["dataset_snapshot"]["cache_signature"],
        )
        self.assertEqual(training_result["dataset_snapshot_path"], inference_result["dataset_snapshot_path"])
        self.assertEqual(inference_result["dataset_snapshot"]["cache_status"], "reused")

    def test_inference_appends_recent_runs_to_experiment_report(self) -> None:
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

        recent_runs = result["experiment_report"]["experiments"]["recent_runs"]
        self.assertGreaterEqual(len(recent_runs), 2)
        self.assertEqual(recent_runs[0]["run_type"], "inference")
        self.assertEqual(recent_runs[1]["run_type"], "training")
        self.assertIn("signal_count", recent_runs[0])
        self.assertIn("backtest", recent_runs[0])

    def test_inference_exposes_input_output_context_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime_root = Path(temp_dir)
            runtime_root.mkdir(exist_ok=True)
            config = load_qlib_config(
                env={"QUANT_QLIB_RUNTIME_ROOT": str(runtime_root)},
                require_explicit=True,
            )
            runner = QlibRunner(config=config)
            dataset = {"BTCUSDT": _sample_timing_candles(step_hours=4), "ETHUSDT": _sample_timing_candles(step_hours=4)}

            runner.train(dataset=dataset)
            result = runner.infer(dataset=dataset)

        self.assertIn("inference_context", result)
        self.assertEqual(result["inference_context"]["symbol_count"], 2)
        self.assertEqual(result["inference_context"]["feature_version"], "v2")
        self.assertIn("input_summary", result["inference_context"])
        self.assertIn("output_summary", result["inference_context"])

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
                    "BTCUSDT": _sample_timing_candles(step_hours=4, count=160),
                    "DOGEUSDT": _sample_negative_timing_candles(step_hours=4, count=160),
                }
            )
            with mock.patch.object(
                runner,
                "_build_candidate_backtest",
                side_effect=[
                    {
                        "metrics": {
                            "total_return_pct": "14.20",
                            "max_drawdown_pct": "-5.10",
                            "sharpe": "1.10",
                            "win_rate": "0.58",
                            "turnover": "0.24",
                            "sample_count": "26",
                            "max_loss_streak": "1",
                        }
                    },
                    {
                        "metrics": {
                            "total_return_pct": "-4.20",
                            "max_drawdown_pct": "-18.10",
                            "sharpe": "0.10",
                            "win_rate": "0.41",
                            "turnover": "0.74",
                            "sample_count": "26",
                            "max_loss_streak": "5",
                        }
                    },
                ],
            ):
                result = runner.infer(
                    dataset={
                        "BTCUSDT": _sample_timing_candles(step_hours=4, count=160),
                        "DOGEUSDT": _sample_negative_timing_candles(step_hours=4, count=160),
                    }
                )

        candidates = {item["symbol"]: item for item in result["candidates"]["items"]}
        self.assertTrue(candidates["BTCUSDT"]["allowed_to_dry_run"])
        self.assertFalse(candidates["DOGEUSDT"]["allowed_to_dry_run"])

    def test_inference_applies_rule_gate_before_candidate_can_enter_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime_root = Path(temp_dir)
            runtime_root.mkdir(exist_ok=True)
            config = load_qlib_config(
                env={"QUANT_QLIB_RUNTIME_ROOT": str(runtime_root)},
                require_explicit=True,
            )
            runner = QlibRunner(config=config)
            candles_1h = _sample_timing_candles(step_hours=1, count=96)
            candles_4h = _sample_timing_candles(step_hours=4, count=80)
            dataset = {
                "BTCUSDT": {
                    "candles_1h": candles_1h,
                    "candles_4h": candles_4h,
                }
            }
            runner.train(dataset=dataset)

            with mock.patch(
                "services.worker.qlib_runner.evaluate_rule_gate",
                return_value={"allowed": False, "reason": "trend_broken"},
            ) as mocked_gate:
                result = runner.infer(dataset=dataset)

        mocked_gate.assert_called()
        candidate = result["candidates"]["items"][0]
        self.assertFalse(candidate["allowed_to_dry_run"])
        self.assertEqual(candidate["rule_gate"]["status"], "failed")
        self.assertEqual(candidate["rule_gate"]["reasons"], ["trend_broken"])

    def test_inference_applies_training_validation_gate_before_candidate_can_enter_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime_root = Path(temp_dir)
            runtime_root.mkdir(exist_ok=True)
            config = load_qlib_config(
                env={"QUANT_QLIB_RUNTIME_ROOT": str(runtime_root)},
                require_explicit=True,
            )
            runner = QlibRunner(config=config)
            dataset = {
                "BTCUSDT": _sample_timing_candles(step_hours=4, count=120),
                "ETHUSDT": _sample_negative_timing_candles(step_hours=4, count=120),
            }
            runner.train(dataset=dataset)
            latest_training_path = runtime_root / "latest_training.json"
            training_payload = runner._read_json(latest_training_path)
            assert training_payload is not None
            training_payload["validation"] = {
                "sample_count": 10,
                "positive_rate": "0.42",
                "avg_future_return_pct": "-0.20",
            }
            latest_training_path.write_text(__import__("json").dumps(training_payload, ensure_ascii=False, indent=2), encoding="utf-8")

            result = runner.infer(dataset=dataset)

        candidate = result["candidates"]["items"][0]
        self.assertEqual(candidate["research_validation_gate"]["status"], "failed")
        self.assertEqual(candidate["next_action"], "continue_research")
        self.assertFalse(candidate["allowed_to_dry_run"])

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


def _sample_training_row(index: int) -> dict[str, object]:
    return {
        "symbol": "BTCUSDT",
        "generated_at": index,
        "close_return_pct": f"{0.2 * index:.4f}",
        "range_pct": "1.0000",
        "body_pct": "0.5000",
        "volume_ratio": "1.2000",
        "trend_gap_pct": "1.6000",
        "ema20_gap_pct": "1.4000",
        "ema55_gap_pct": "2.2000",
        "atr_pct": "2.4000",
        "rsi14": "61.0000",
        "breakout_strength": "0.8000",
        "future_return_pct": "1.5000",
        "label": "buy",
        "holding_window": "1-3d",
        "is_trainable": True,
    }


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
