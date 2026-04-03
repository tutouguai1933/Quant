"""Qlib 实验对比摘要测试。

这个文件只验证统一实验对比出口的结构和计数口径。
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.worker.qlib_experiment_report import build_experiment_report  # noqa: E402


class QlibExperimentReportTests(unittest.TestCase):
    def test_build_experiment_report_returns_latest_training_and_candidate_summary(self) -> None:
        report = build_experiment_report(
            latest_training={"model_version": "m1", "backtest": {"metrics": {"sharpe": "1.10"}}},
            latest_inference={"signals": [{"symbol": "BTCUSDT"}]},
            candidates={"items": [{"symbol": "BTCUSDT", "allowed_to_dry_run": True}]},
        )

        self.assertEqual(report["overview"]["candidate_count"], 1)
        self.assertEqual(report["overview"]["ready_count"], 1)
        self.assertEqual(report["overview"]["signal_count"], 1)
        self.assertEqual(report["latest_training"]["model_version"], "m1")
        self.assertEqual(report["latest_inference"]["signals"][0]["symbol"], "BTCUSDT")
        self.assertEqual(report["candidates"][0]["symbol"], "BTCUSDT")

    def test_build_experiment_report_includes_screening_summary_and_backtest_snapshot(self) -> None:
        report = build_experiment_report(
            latest_training={
                "model_version": "m2",
                "backtest": {
                    "metrics": {
                        "total_return_pct": "12.40",
                        "max_drawdown_pct": "-4.80",
                        "sharpe": "1.22",
                        "win_rate": "0.58",
                        "turnover": "0.24",
                        "max_loss_streak": "2",
                    }
                },
            },
            latest_inference={"signals": [{"symbol": "BTCUSDT"}]},
            candidates={
                "items": [
                    {
                        "symbol": "BTCUSDT",
                        "score": "0.8123",
                        "allowed_to_dry_run": True,
                        "dry_run_gate": {"status": "passed", "reasons": []},
                        "backtest": {"metrics": {"sharpe": "1.22"}},
                    },
                    {
                        "symbol": "ETHUSDT",
                        "score": "0.6010",
                        "allowed_to_dry_run": False,
                        "dry_run_gate": {"status": "failed", "reasons": ["drawdown_too_large"]},
                        "backtest": {"metrics": {"sharpe": "0.41"}},
                    },
                ]
            },
        )

        self.assertEqual(report["overview"]["blocked_count"], 1)
        self.assertEqual(report["overview"]["pass_rate_pct"], "50.00")
        self.assertEqual(report["overview"]["top_candidate_symbol"], "BTCUSDT")
        self.assertEqual(report["overview"]["top_candidate_score"], "0.8123")
        self.assertEqual(report["experiments"]["training"]["backtest"]["sharpe"], "1.22")


if __name__ == "__main__":
    unittest.main()
