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


if __name__ == "__main__":
    unittest.main()
