"""Qlib 最小回测测试。

这个文件只验证回测报告会稳定输出核心指标。
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.worker.qlib_backtest import run_backtest  # noqa: E402


class QlibBacktestTests(unittest.TestCase):
    def test_backtest_report_contains_core_metrics(self) -> None:
        report = run_backtest(
            rows=_sample_ranked_rows(),
            holding_window="1-3d",
        )

        self.assertEqual(report["holding_window"], "1-3d")
        self.assertEqual(
            set(report["metrics"].keys()),
            {
                "total_return_pct",
                "max_drawdown_pct",
                "sharpe",
                "win_rate",
                "turnover",
                "sample_count",
                "max_loss_streak",
            },
        )

    def test_backtest_turnover_stays_low_when_direction_is_stable(self) -> None:
        report = run_backtest(
            rows=[
                {"future_return_pct": "1.8000", "label": "buy"},
                {"future_return_pct": "1.2000", "label": "buy"},
                {"future_return_pct": "0.9000", "label": "buy"},
                {"future_return_pct": "1.1000", "label": "buy"},
            ],
            holding_window="1-3d",
        )

        self.assertEqual(report["metrics"]["turnover"], "0.2500")
        self.assertEqual(report["metrics"]["sample_count"], "4")
        self.assertEqual(report["metrics"]["max_loss_streak"], "0")

    def test_backtest_reports_max_loss_streak(self) -> None:
        report = run_backtest(
            rows=[
                {"future_return_pct": "-0.8000", "label": "sell"},
                {"future_return_pct": "-0.6000", "label": "sell"},
                {"future_return_pct": "1.1000", "label": "buy"},
                {"future_return_pct": "-0.3000", "label": "sell"},
            ],
            holding_window="1-3d",
        )

        self.assertEqual(report["metrics"]["sample_count"], "4")
        self.assertEqual(report["metrics"]["max_loss_streak"], "2")


def _sample_ranked_rows() -> list[dict[str, object]]:
    return [
        {"future_return_pct": "2.0000", "label": "buy"},
        {"future_return_pct": "-1.2000", "label": "sell"},
        {"future_return_pct": "0.4000", "label": "watch"},
        {"future_return_pct": "1.1000", "label": "buy"},
    ]


if __name__ == "__main__":
    unittest.main()
