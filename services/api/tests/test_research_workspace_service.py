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
        service = ResearchWorkspaceService(report_reader=_FakeResearchService())

        item = service.get_workspace()

        self.assertEqual(item["status"], "ready")
        self.assertEqual(item["overview"]["holding_window"], "1-3d")
        self.assertEqual(item["overview"]["candidate_count"], 2)
        self.assertEqual(item["model"]["model_version"], "qlib-minimal-1")
        self.assertIn("trend_breakout_timing", item["strategy_templates"])
        self.assertEqual(item["labeling"]["label_columns"][0], "symbol")
        self.assertEqual(item["sample_window"]["training"]["count"], 120)
        self.assertEqual(item["parameters"]["backtest_fee_bps"], "10")

    def test_workspace_handles_missing_report(self) -> None:
        service = ResearchWorkspaceService(report_reader=_UnavailableResearchService())

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


if __name__ == "__main__":
    unittest.main()
