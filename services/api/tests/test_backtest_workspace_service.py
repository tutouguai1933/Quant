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
        service = BacktestWorkspaceService(report_reader=_FakeResearchService(), controls_builder=_fake_controls)

        item = service.get_workspace()

        self.assertEqual(item["status"], "ready")
        self.assertEqual(item["overview"]["holding_window"], "1-3d")
        self.assertEqual(item["training_backtest"]["metrics"]["net_return_pct"], "5.2000")
        self.assertEqual(item["assumptions"]["fee_bps"], "10")
        self.assertEqual(item["leaderboard"][0]["symbol"], "ETHUSDT")
        self.assertEqual(item["leaderboard"][0]["backtest"]["net_return_pct"], "2.3000")
        self.assertIn("controls", item)
        self.assertEqual(item["controls"]["cost_model_catalog"][0]["key"], "round_trip_basis_points")
        self.assertEqual(item["controls"]["dry_run_min_win_rate"], "0.50")
        self.assertEqual(item["controls"]["dry_run_max_turnover"], "0.60")
        self.assertEqual(item["controls"]["dry_run_min_sample_count"], "20")
        self.assertEqual(item["controls"]["live_min_win_rate"], "0.55")
        self.assertEqual(item["controls"]["live_max_turnover"], "0.45")
        self.assertEqual(item["controls"]["live_min_sample_count"], "24")
        self.assertEqual(item["stage_assessment"][0]["stage"], "dry-run")
        self.assertIn("净收益", item["stage_assessment"][0]["current"])
        self.assertEqual(item["stage_assessment"][1]["stage"], "validation")
        self.assertEqual(item["stage_assessment"][2]["stage"], "live")

    def test_workspace_handles_missing_backtest(self) -> None:
        service = BacktestWorkspaceService(report_reader=_UnavailableResearchService(), controls_builder=_fake_controls)

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
                "validation": {"avg_future_return_pct": "0.3000"},
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
                        "win_rate": "0.6200",
                        "turnover": "0.2100",
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


def _fake_controls() -> dict[str, object]:
    return {
        "config": {
            "backtest": {
                "fee_bps": "10",
                "slippage_bps": "5",
                "cost_model": "round_trip_basis_points",
            },
            "thresholds": {
                "dry_run_min_win_rate": "0.50",
                "dry_run_max_turnover": "0.60",
                "dry_run_min_sample_count": "20",
                "dry_run_min_score": "0.55",
                "dry_run_min_net_return_pct": "0.10",
                "dry_run_min_sharpe": "0.50",
                "validation_min_sample_count": "12",
                "validation_min_avg_future_return_pct": "-0.1",
                "live_min_score": "0.65",
                "live_min_net_return_pct": "0.20",
                "live_min_win_rate": "0.55",
                "live_max_turnover": "0.45",
                "live_min_sample_count": "24",
            },
        }
        ,
        "options": {
            "backtest_cost_models": ["round_trip_basis_points", "zero_cost_baseline"],
            "cost_model_catalog": [
                {"key": "round_trip_basis_points", "label": "双边成本", "fit": "更贴近真实交易", "detail": "买卖都扣成本"}
            ],
        },
    }


if __name__ == "__main__":
    unittest.main()
