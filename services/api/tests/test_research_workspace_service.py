from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.api.app.services.research_workspace_service import ResearchWorkspaceService  # noqa: E402


class ResearchWorkspaceServiceTests(unittest.TestCase):
    def test_workspace_returns_research_context(self) -> None:
        service = ResearchWorkspaceService(report_reader=_FakeResearchService(), controls_builder=_fake_controls)

        item = service.get_workspace()

        self.assertEqual(item["status"], "ready")
        self.assertEqual(item["overview"]["holding_window"], "1-3d")
        self.assertEqual(item["overview"]["candidate_count"], 2)
        self.assertEqual(item["model"]["model_version"], "qlib-minimal-1")
        self.assertIn("trend_breakout_timing", item["strategy_templates"])
        self.assertEqual(item["labeling"]["label_columns"][0], "symbol")
        self.assertEqual(item["labeling"]["label_mode"], "earliest_hit")
        self.assertEqual(item["sample_window"]["training"]["count"], 120)
        self.assertEqual(item["parameters"]["backtest_fee_bps"], "10")
        self.assertIn("controls", item)
        self.assertEqual(item["controls"]["train_split_ratio"], "0.6")
        self.assertEqual(item["controls"]["validation_split_ratio"], "0.2")
        self.assertEqual(item["controls"]["test_split_ratio"], "0.2")
        self.assertEqual(item["controls"]["signal_confidence_floor"], "0.55")
        self.assertEqual(item["controls"]["trend_weight"], "1.3")
        self.assertEqual(item["controls"]["strict_penalty_weight"], "1")

    def test_workspace_handles_missing_report(self) -> None:
        service = ResearchWorkspaceService(report_reader=_UnavailableResearchService(), controls_builder=_fake_controls)

        item = service.get_workspace()

        self.assertEqual(item["status"], "unavailable")
        self.assertEqual(item["strategy_templates"], [])
        self.assertEqual(item["parameters"], {})


class _FakeResearchService:
    def get_factory_report(self) -> dict[str, object]:
        return {
            "status": "ready",
            "backend": "qlib-fallback",
            "overview": {
                "candidate_count": 2,
                "recommended_symbol": "ETHUSDT",
            },
            "latest_training": {
                "model_version": "qlib-minimal-1",
                "label_columns": ["symbol", "generated_at", "label"],
                "training_context": {
                    "holding_window": "1-3d",
                    "symbols": ["BTCUSDT", "ETHUSDT"],
                    "timeframes": ["4h"],
                    "sample_window": {
                        "training": {"count": 120},
                        "validation": {"count": 40},
                        "backtest": {"count": 30},
                    },
                    "parameters": {
                        "backtest_fee_bps": "10",
                        "backtest_slippage_bps": "5",
                    },
                },
            },
            "latest_inference": {
                "model_version": "qlib-minimal-1",
            },
            "candidates": [
                {"symbol": "ETHUSDT", "strategy_template": "trend_breakout_timing"},
                {"symbol": "BTCUSDT", "strategy_template": "trend_pullback_timing"},
            ],
        }


class _UnavailableResearchService:
    def get_factory_report(self) -> dict[str, object]:
        return {"status": "unavailable"}


def _fake_controls() -> dict[str, object]:
    return {
        "config": {
            "research": {
                "research_template": "single_asset_timing",
                "model_key": "heuristic_v1",
                "label_mode": "earliest_hit",
                "holding_window_label": "1-3d",
                "min_holding_days": 1,
                "max_holding_days": 3,
                "label_target_pct": "1",
                "label_stop_pct": "-1",
                "train_split_ratio": "0.6",
                "validation_split_ratio": "0.2",
                "test_split_ratio": "0.2",
                "signal_confidence_floor": "0.55",
                "trend_weight": "1.3",
                "volume_weight": "1.1",
                "oscillator_weight": "0.7",
                "volatility_weight": "0.9",
                "strict_penalty_weight": "1",
            }
        },
        "options": {
            "models": ["heuristic_v1", "trend_bias_v2"],
            "research_templates": ["single_asset_timing", "single_asset_timing_strict"],
            "label_modes": ["earliest_hit", "close_only"],
        },
    }


if __name__ == "__main__":
    unittest.main()
