"""选币页 terminal.metrics 指标补齐。"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.api.app.services.evaluation_workspace_service import EvaluationWorkspaceService  # noqa: E402


class TerminalMetricsTests(unittest.TestCase):
    def test_build_terminal_metrics_includes_all_keys(self):
        """terminal.metrics 应包含年化/sharpe/超额/换手。"""
        service = object.__new__(EvaluationWorkspaceService)
        leaderboard = [
            {
                "symbol": "BTCUSDT",
                "backtest": {
                    "metrics": {
                        "net_return_pct": "2.5",
                        "max_drawdown_pct": "-1.2",
                        "sharpe": "0.8",
                        "turnover": "0.3",
                    }
                },
            }
        ]
        metrics = service._build_terminal_metrics(
            leaderboard=leaderboard,
            recommended_symbol="BTCUSDT",
            candidate_count=1,
            passed_count=1,
            rejected_count=0,
        )
        values = {m["key"]: m["value"] for m in metrics}
        for key in ("best_net_return_pct", "annual_return_pct", "sharpe", "excess_return_pct", "turnover", "best_max_drawdown_pct"):
            self.assertIn(key, values)
        self.assertEqual(values["sharpe"], "0.80")
        self.assertEqual(values["turnover"], "0.30")

    def test_build_terminal_metrics_extracts_from_nested_metrics(self):
        """指标从 backtest.metrics 嵌套结构提取（兼容旧顶层结构）。"""
        service = object.__new__(EvaluationWorkspaceService)
        leaderboard = [
            {
                "symbol": "ETHUSDT",
                "backtest": {
                    "net_return_pct": "1.5",
                    "max_drawdown_pct": "-0.8",
                },
            }
        ]
        metrics = service._build_terminal_metrics(
            leaderboard=leaderboard,
            recommended_symbol="ETHUSDT",
            candidate_count=1,
            passed_count=1,
            rejected_count=0,
        )
        values = {m["key"]: m["value"] for m in metrics}
        self.assertEqual(values["best_net_return_pct"], "1.50")
        self.assertIn("annual_return_pct", values)


if __name__ == "__main__":
    unittest.main()
