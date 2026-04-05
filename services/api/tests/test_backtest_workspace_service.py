from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.api.app.services.backtest_workspace_service import BacktestWorkspaceService  # noqa: E402


class BacktestWorkspaceServiceTests(unittest.TestCase):
    def test_workspace_returns_backtest_summary_and_candidates(self) -> None:
        service = BacktestWorkspaceService(report_reader=_FakeResearchService())

        item = service.get_workspace()

        self.assertEqual(item["status"], "ready")
        self.assertEqual(item["overview"]["holding_window"], "1-3d")
        self.assertEqual(item["training_backtest"]["metrics"]["net_return_pct"], "5.2000")
        self.assertEqual(item["assumptions"]["fee_bps"], "10")
        self.assertEqual(item["leaderboard"][0]["symbol"], "ETHUSDT")
        self.assertEqual(item["leaderboard"][0]["backtest"]["net_return_pct"], "2.3000")

    def test_workspace_handles_missing_backtest(self) -> None:
        service = BacktestWorkspaceService(report_reader=_UnavailableResearchService())

        item = service.get_workspace()

        self.assertEqual(item["status"], "unavailable")
        self.assertEqual(item["leaderboard"], [])
        self.assertEqual(item["training_backtest"]["metrics"], {})


class _FakeResearchService:
    def get_factory_report(self) -> dict[str, object]:
        return {
            "status": "ready",
            "latest_training": {
                "training_context": {"holding_window": "1-3d"},
                "backtest": {
                    "assumptions": {
                        "fee_bps": "10",
                        "slippage_bps": "5",
                        "cost_model": "round_trip_basis_points",
                    },
                    "metrics": {
                        "net_return_pct": "5.2000",
                        "cost_impact_pct": "0.6000",
                        "max_drawdown_pct": "-3.1000",
                        "sharpe": "1.4000",
                        "action_segment_count": "7",
                        "direction_switch_count": "3",
                    },
                },
            },
            "leaderboard": [
                {
                    "symbol": "ETHUSDT",
                    "strategy_template": "trend_breakout_timing",
                    "backtest": {
                        "net_return_pct": "2.3000",
                        "cost_impact_pct": "0.2000",
                        "max_drawdown_pct": "-1.1000",
                        "sharpe": "1.1000",
                    },
                }
            ],
        }


class _UnavailableResearchService:
    def get_factory_report(self) -> dict[str, object]:
        return {"status": "unavailable"}


if __name__ == "__main__":
    unittest.main()
