"""Qlib 候选排行测试。

这个文件只验证候选排行和 dry-run 准入门的最小行为。
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.worker.qlib_ranking import rank_candidates  # noqa: E402


class QlibRankingTests(unittest.TestCase):
    def test_rank_candidates_sorts_by_score_descending(self) -> None:
        result = rank_candidates(
            [
                {
                    "symbol": "ETHUSDT",
                    "strategy_template": "trend_pullback_timing",
                    "score": "0.6200",
                    "backtest": {"metrics": _passing_metrics()},
                },
                {
                    "symbol": "BTCUSDT",
                    "strategy_template": "trend_breakout_timing",
                    "score": "0.7800",
                    "backtest": {"metrics": _passing_metrics()},
                },
            ]
        )

        self.assertEqual(result["items"][0]["symbol"], "BTCUSDT")
        self.assertEqual(result["items"][1]["symbol"], "ETHUSDT")

    def test_rank_candidates_marks_dry_run_ready_only_when_metrics_pass(self) -> None:
        result = rank_candidates(
            [
                {
                    "symbol": "BTCUSDT",
                    "strategy_template": "trend_breakout_timing",
                    "score": "0.7800",
                    "backtest": {"metrics": _passing_metrics()},
                }
            ]
        )

        self.assertEqual(result["items"][0]["dry_run_gate"]["status"], "passed")
        self.assertTrue(result["items"][0]["allowed_to_dry_run"])
        self.assertEqual(result["summary"]["candidate_count"], 1)
        self.assertEqual(result["summary"]["ready_count"], 1)

    def test_rank_candidates_marks_failed_when_backtest_metrics_do_not_pass(self) -> None:
        result = rank_candidates(
            [
                {
                    "symbol": "DOGEUSDT",
                    "strategy_template": "trend_pullback_timing",
                    "score": "0.8100",
                    "backtest": {"metrics": _failing_metrics()},
                }
            ]
        )

        self.assertEqual(result["items"][0]["dry_run_gate"]["status"], "failed")
        self.assertFalse(result["items"][0]["allowed_to_dry_run"])


def _passing_metrics() -> dict[str, str]:
    return {
        "total_return_pct": "14.20",
        "max_drawdown_pct": "-5.10",
        "sharpe": "1.10",
        "win_rate": "0.58",
        "turnover": "0.24",
    }


def _failing_metrics() -> dict[str, str]:
    return {
        "total_return_pct": "-3.20",
        "max_drawdown_pct": "-22.40",
        "sharpe": "0.10",
        "win_rate": "0.41",
        "turnover": "0.92",
    }


if __name__ == "__main__":
    unittest.main()
