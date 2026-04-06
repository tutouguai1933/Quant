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
        self.assertEqual(config["research"]["model_key"], "heuristic_v1")
        self.assertEqual(config["research"]["label_mode"], "earliest_hit")
        self.assertEqual(config["backtest"]["fee_bps"], "10")
        self.assertEqual(config["features"]["outlier_policy"], "clip")
        self.assertEqual(config["features"]["normalization_policy"], "fixed_4dp")
        self.assertEqual(config["thresholds"]["live_min_score"], "0.65")

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
                },
            )

            persisted = json.loads(config_path.read_text(encoding="utf-8"))

        self.assertEqual(config["data"]["selected_symbols"], ["ETHUSDT", "DOGEUSDT"])
        self.assertEqual(config["data"]["primary_symbol"], "DOGEUSDT")
        self.assertEqual(config["data"]["timeframes"], ["1h"])
        self.assertEqual(config["data"]["sample_limit"], 60)
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
                    "min_holding_days": "2",
                    "max_holding_days": "4",
                    "label_target_pct": "1.5",
                    "label_stop_pct": "-0.8",
                },
            )
            service.update_section(
                "features",
                {
                    "outlier_policy": "raw",
                    "normalization_policy": "zscore_by_symbol",
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
                },
            )

            overrides = service.get_research_runtime_overrides()

        self.assertEqual(overrides["QUANT_QLIB_MODEL_KEY"], "trend_bias_v2")
        self.assertEqual(overrides["QUANT_QLIB_RESEARCH_TEMPLATE"], "single_asset_timing_strict")
        self.assertEqual(overrides["QUANT_QLIB_LABEL_MODE"], "close_only")
        self.assertEqual(overrides["QUANT_QLIB_HOLDING_WINDOW_MIN_DAYS"], "2")
        self.assertEqual(overrides["QUANT_QLIB_HOLDING_WINDOW_MAX_DAYS"], "4")
        self.assertEqual(overrides["QUANT_QLIB_LABEL_TARGET_PCT"], "1.5")
        self.assertEqual(overrides["QUANT_QLIB_LABEL_STOP_PCT"], "-0.8")
        self.assertEqual(overrides["QUANT_QLIB_OUTLIER_POLICY"], "raw")
        self.assertEqual(overrides["QUANT_QLIB_NORMALIZATION_POLICY"], "zscore_by_symbol")
        self.assertEqual(overrides["QUANT_QLIB_BACKTEST_FEE_BPS"], "12")
        self.assertEqual(overrides["QUANT_QLIB_DRY_RUN_MIN_SCORE"], "0.6")
        self.assertEqual(overrides["QUANT_QLIB_LIVE_MIN_SCORE"], "0.8")

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


if __name__ == "__main__":
    unittest.main()
