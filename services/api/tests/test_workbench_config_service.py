from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.api.app.services.workbench_config_service import WorkbenchConfigService  # noqa: E402


class WorkbenchConfigServiceTests(unittest.TestCase):
    def test_returns_normalized_defaults_when_file_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = WorkbenchConfigService(config_path=Path(temp_dir) / "workbench.json")

            config = service.get_config()

        self.assertEqual(config["data"]["selected_symbols"][0], "BTCUSDT")
        self.assertEqual(config["data"]["timeframes"], ["4h", "1h"])
        self.assertEqual(config["data"]["lookback_days"], 30)
        self.assertEqual(config["data"]["window_mode"], "rolling")
        self.assertEqual(config["data"]["start_date"], "")
        self.assertEqual(config["data"]["end_date"], "")
        self.assertEqual(config["research"]["model_key"], "heuristic_v1")
        self.assertEqual(config["research"]["label_mode"], "earliest_hit")
        self.assertFalse(config["research"]["force_validation_top_candidate"])
        self.assertEqual(config["research"]["train_split_ratio"], "0.6")
        self.assertEqual(config["research"]["validation_split_ratio"], "0.2")
        self.assertEqual(config["research"]["test_split_ratio"], "0.2")
        self.assertEqual(config["research"]["signal_confidence_floor"], "0.55")
        self.assertEqual(config["research"]["trend_weight"], "1.3")
        self.assertEqual(config["research"]["volume_weight"], "1.1")
        self.assertEqual(config["research"]["oscillator_weight"], "0.7")
        self.assertEqual(config["research"]["volatility_weight"], "0.9")
        self.assertEqual(config["research"]["strict_penalty_weight"], "1")
        self.assertEqual(config["backtest"]["fee_bps"], "10")
        self.assertEqual(config["execution"]["live_allowed_symbols"], ["BTCUSDT", "ETHUSDT", "SOLUSDT", "DOGEUSDT"])
        self.assertEqual(config["execution"]["live_max_stake_usdt"], "6")
        self.assertEqual(config["execution"]["live_max_open_trades"], "1")
        self.assertEqual(config["features"]["outlier_policy"], "clip")
        self.assertEqual(config["features"]["normalization_policy"], "fixed_4dp")
        self.assertEqual(config["features"]["missing_policy"], "neutral_fill")
        self.assertEqual(config["thresholds"]["live_min_score"], "0.65")
        self.assertEqual(config["thresholds"]["dry_run_min_win_rate"], "0.5")
        self.assertEqual(config["thresholds"]["dry_run_max_turnover"], "0.6")
        self.assertEqual(config["thresholds"]["dry_run_min_sample_count"], "20")
        self.assertEqual(config["thresholds"]["validation_min_sample_count"], "12")
        self.assertEqual(config["thresholds"]["live_min_win_rate"], "0.55")
        self.assertEqual(config["thresholds"]["live_max_turnover"], "0.45")
        self.assertEqual(config["thresholds"]["live_min_sample_count"], "24")
        self.assertEqual(config["operations"]["pause_after_consecutive_failures"], "2")
        self.assertEqual(config["operations"]["stale_sync_failure_threshold"], "1")
        self.assertTrue(config["operations"]["auto_pause_on_error"])
        self.assertEqual(config["operations"]["review_limit"], "10")
        self.assertEqual(config["operations"]["cycle_cooldown_minutes"], "15")
        self.assertEqual(config["operations"]["max_daily_cycle_count"], "8")
        self.assertEqual(config["automation"]["long_run_seconds"], "300")
        self.assertEqual(config["automation"]["alert_cleanup_minutes"], "15")

    def test_update_section_persists_and_normalizes_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "workbench.json"
            service = WorkbenchConfigService(config_path=config_path)

            config = service.update_section(
                "data",
                {
                    "selected_symbols": ["ethusdt", "DOGEUSDT", "invalid-1"],
                    "primary_symbol": "DOGEUSDT",
                    "timeframes": ["1h"],
                    "sample_limit": "20",
                    "lookback_days": "7",
                    "window_mode": "fixed",
                    "start_date": "2026-01-01",
                    "end_date": "2026-02-01",
                },
            )

            persisted = json.loads(config_path.read_text(encoding="utf-8"))

        self.assertEqual(config["data"]["selected_symbols"], ["ETHUSDT", "DOGEUSDT"])
        self.assertEqual(config["data"]["primary_symbol"], "DOGEUSDT")
        self.assertEqual(config["data"]["timeframes"], ["1h"])
        self.assertEqual(config["data"]["sample_limit"], 60)
        self.assertEqual(config["data"]["lookback_days"], 7)
        self.assertEqual(config["data"]["window_mode"], "fixed")
        self.assertEqual(config["data"]["start_date"], "2026-01-01")
        self.assertEqual(config["data"]["end_date"], "2026-02-01")
        self.assertEqual(persisted["data"]["primary_symbol"], "DOGEUSDT")

    def test_runtime_overrides_include_all_research_controls(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = WorkbenchConfigService(config_path=Path(temp_dir) / "workbench.json")
            service.update_section(
                "research",
                {
                    "research_template": "single_asset_timing_strict",
                    "model_key": "trend_bias_v2",
                    "label_mode": "close_only",
                    "force_validation_top_candidate": True,
                    "min_holding_days": "2",
                    "max_holding_days": "4",
                    "label_target_pct": "1.5",
                    "label_stop_pct": "-0.8",
                    "train_split_ratio": "0.5",
                    "validation_split_ratio": "0.3",
                    "test_split_ratio": "0.2",
                    "signal_confidence_floor": "0.62",
                    "trend_weight": "1.8",
                    "volume_weight": "1.4",
                    "oscillator_weight": "0.5",
                    "volatility_weight": "0.6",
                    "strict_penalty_weight": "1.4",
                },
            )
            service.update_section(
                "features",
                {
                    "outlier_policy": "raw",
                    "normalization_policy": "zscore_by_symbol",
                    "missing_policy": "strict_drop",
                },
            )
            service.update_section(
                "backtest",
                {
                    "fee_bps": "12",
                    "slippage_bps": "7",
                },
            )
            service.update_section(
                "thresholds",
                {
                    "dry_run_min_score": "0.6",
                    "live_min_score": "0.8",
                    "dry_run_min_win_rate": "0.57",
                    "dry_run_max_turnover": "0.5",
                    "dry_run_min_sample_count": "26",
                    "validation_min_sample_count": "18",
                    "live_min_win_rate": "0.61",
                    "live_max_turnover": "0.42",
                    "live_min_sample_count": "30",
                },
            )

            overrides = service.get_research_runtime_overrides()

        self.assertEqual(overrides["QUANT_QLIB_MODEL_KEY"], "trend_bias_v2")
        self.assertEqual(overrides["QUANT_QLIB_RESEARCH_TEMPLATE"], "single_asset_timing_strict")
        self.assertEqual(overrides["QUANT_QLIB_LABEL_MODE"], "close_only")
        self.assertEqual(overrides["QUANT_QLIB_FORCE_TOP_CANDIDATE"], "true")
        self.assertEqual(overrides["QUANT_QLIB_HOLDING_WINDOW_MIN_DAYS"], "2")
        self.assertEqual(overrides["QUANT_QLIB_HOLDING_WINDOW_MAX_DAYS"], "4")
        self.assertEqual(overrides["QUANT_QLIB_LABEL_TARGET_PCT"], "1.5")
        self.assertEqual(overrides["QUANT_QLIB_LABEL_STOP_PCT"], "-0.8")
        self.assertEqual(overrides["QUANT_QLIB_TRAIN_SPLIT_RATIO"], "0.5")
        self.assertEqual(overrides["QUANT_QLIB_VALIDATION_SPLIT_RATIO"], "0.3")
        self.assertEqual(overrides["QUANT_QLIB_TEST_SPLIT_RATIO"], "0.2")
        self.assertEqual(overrides["QUANT_QLIB_SIGNAL_CONFIDENCE_FLOOR"], "0.62")
        self.assertEqual(overrides["QUANT_QLIB_TREND_WEIGHT"], "1.8")
        self.assertEqual(overrides["QUANT_QLIB_VOLUME_WEIGHT"], "1.4")
        self.assertEqual(overrides["QUANT_QLIB_OSCILLATOR_WEIGHT"], "0.5")
        self.assertEqual(overrides["QUANT_QLIB_VOLATILITY_WEIGHT"], "0.6")
        self.assertEqual(overrides["QUANT_QLIB_STRICT_PENALTY_WEIGHT"], "1.4")
        self.assertEqual(overrides["QUANT_QLIB_OUTLIER_POLICY"], "raw")
        self.assertEqual(overrides["QUANT_QLIB_NORMALIZATION_POLICY"], "zscore_by_symbol")
        self.assertEqual(overrides["QUANT_QLIB_MISSING_POLICY"], "strict_drop")
        self.assertEqual(overrides["QUANT_QLIB_BACKTEST_FEE_BPS"], "12")
        self.assertEqual(overrides["QUANT_QLIB_DRY_RUN_MIN_SCORE"], "0.6")
        self.assertEqual(overrides["QUANT_QLIB_LIVE_MIN_SCORE"], "0.8")
        self.assertEqual(overrides["QUANT_QLIB_DRY_RUN_MIN_WIN_RATE"], "0.57")
        self.assertEqual(overrides["QUANT_QLIB_DRY_RUN_MAX_TURNOVER"], "0.5")
        self.assertEqual(overrides["QUANT_QLIB_DRY_RUN_MIN_SAMPLE_COUNT"], "26")
        self.assertEqual(overrides["QUANT_QLIB_VALIDATION_MIN_SAMPLE_COUNT"], "18")
        self.assertEqual(overrides["QUANT_QLIB_LIVE_MIN_WIN_RATE"], "0.61")
        self.assertEqual(overrides["QUANT_QLIB_LIVE_MAX_TURNOVER"], "0.42")
        self.assertEqual(overrides["QUANT_QLIB_LIVE_MIN_SAMPLE_COUNT"], "30")

    def test_runtime_overrides_include_data_range_window(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = WorkbenchConfigService(config_path=Path(temp_dir) / "workbench.json")
            service.update_section(
                "data",
                {
                    "selected_symbols": ["BTCUSDT"],
                    "timeframes": ["4h"],
                    "sample_limit": "180",
                    "lookback_days": "21",
                    "window_mode": "fixed",
                    "start_date": "2026-01-05",
                    "end_date": "2026-02-07",
                },
            )

            overrides = service.get_research_runtime_overrides()

        self.assertEqual(overrides["QUANT_QLIB_SAMPLE_LIMIT"], "180")
        self.assertEqual(overrides["QUANT_QLIB_LOOKBACK_DAYS"], "21")
        self.assertEqual(overrides["QUANT_QLIB_WINDOW_MODE"], "fixed")
        self.assertEqual(overrides["QUANT_QLIB_START_DATE"], "2026-01-05")
        self.assertEqual(overrides["QUANT_QLIB_END_DATE"], "2026-02-07")

    def test_update_section_preserves_existing_values_when_partial_payload_is_submitted(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = WorkbenchConfigService(config_path=Path(temp_dir) / "workbench.json")
            service.update_section(
                "thresholds",
                {
                    "dry_run_min_score": "0.62",
                    "live_min_score": "0.95",
                    "live_min_positive_rate": "0.77",
                },
            )

            config = service.update_section(
                "thresholds",
                {
                    "dry_run_min_score": "0.70",
                },
            )

        self.assertEqual(config["thresholds"]["dry_run_min_score"], "0.7")
        self.assertEqual(config["thresholds"]["live_min_score"], "0.95")
        self.assertEqual(config["thresholds"]["live_min_positive_rate"], "0.77")

    def test_update_automation_section_normalizes_runtime_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = WorkbenchConfigService(config_path=Path(temp_dir) / "workbench.json")

            config = service.update_section(
                "automation",
                {
                    "long_run_seconds": "900",
                    "alert_cleanup_minutes": "45",
                },
            )

        self.assertEqual(config["automation"]["long_run_seconds"], "900")
        self.assertEqual(config["automation"]["alert_cleanup_minutes"], "45")

    def test_update_execution_section_normalizes_symbols_and_limits(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = WorkbenchConfigService(config_path=Path(temp_dir) / "workbench.json")

            config = service.update_section(
                "execution",
                {
                    "live_allowed_symbols": ["ethusdt", "dogeusdt", "bad-symbol"],
                    "live_max_stake_usdt": "8.5",
                    "live_max_open_trades": "2",
                },
            )

        self.assertEqual(config["execution"]["live_allowed_symbols"], ["ETHUSDT", "DOGEUSDT"])
        self.assertEqual(config["execution"]["live_max_stake_usdt"], "8.5")
        self.assertEqual(config["execution"]["live_max_open_trades"], "2")

    def test_update_section_does_not_keep_old_factor_values_when_empty_selection_is_submitted(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = WorkbenchConfigService(config_path=Path(temp_dir) / "workbench.json")
            service.update_section(
                "features",
                {
                    "primary_factors": ["trend_gap_pct"],
                    "auxiliary_factors": ["volume_ratio"],
                },
            )

            config = service.update_section(
                "features",
                {
                    "primary_factors": [],
                    "auxiliary_factors": [],
                },
            )

        self.assertEqual(config["features"]["primary_factors"], [])
        self.assertEqual(config["features"]["auxiliary_factors"], [])

    def test_update_section_keeps_empty_symbol_and_timeframe_selection(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = WorkbenchConfigService(config_path=Path(temp_dir) / "workbench.json")

            config = service.update_section(
                "data",
                {
                    "selected_symbols": [],
                    "timeframes": [],
                },
            )

        self.assertEqual(config["data"]["selected_symbols"], [])
        self.assertEqual(config["data"]["timeframes"], [])
        self.assertEqual(config["data"]["primary_symbol"], "")

    def test_research_split_ratios_are_normalized_before_persisting(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = WorkbenchConfigService(config_path=Path(temp_dir) / "workbench.json")

            config = service.update_section(
                "research",
                {
                    "train_split_ratio": "0.9",
                    "validation_split_ratio": "0.2",
                    "test_split_ratio": "0.2",
                },
            )

        self.assertEqual(config["research"]["train_split_ratio"], "0.6924")
        self.assertEqual(config["research"]["validation_split_ratio"], "0.1538")
        self.assertEqual(config["research"]["test_split_ratio"], "0.1538")

    def test_update_operations_section_normalizes_thresholds_and_flags(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = WorkbenchConfigService(config_path=Path(temp_dir) / "workbench.json")

            config = service.update_section(
                "operations",
                {
                    "pause_after_consecutive_failures": "6",
                    "stale_sync_failure_threshold": "4",
                    "auto_pause_on_error": "false",
                    "review_limit": "25",
                    "cycle_cooldown_minutes": "30",
                    "max_daily_cycle_count": "12",
                },
            )

        self.assertEqual(config["operations"]["pause_after_consecutive_failures"], "6")
        self.assertEqual(config["operations"]["stale_sync_failure_threshold"], "4")
        self.assertFalse(config["operations"]["auto_pause_on_error"])
        self.assertEqual(config["operations"]["review_limit"], "25")
        self.assertEqual(config["operations"]["cycle_cooldown_minutes"], "30")
        self.assertEqual(config["operations"]["max_daily_cycle_count"], "12")


if __name__ == "__main__":
    unittest.main()
