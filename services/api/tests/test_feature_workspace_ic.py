"""因子页 IC 摘要指标。"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.api.app.services.feature_workspace_service import FeatureWorkspaceService  # noqa: E402


class IcMetricsTests(unittest.TestCase):
    def test_build_ic_summary_from_ic_series(self):
        """从 ic_series 计算 mean_ic/ic_std/icir/ic_win_rate。"""
        service = object.__new__(FeatureWorkspaceService)
        report = {
            "factor_evaluation": {
                "ic_series": [
                    {"factor": "ema20_gap_pct", "ic": 0.05, "rank_ic": 0.04},
                    {"factor": "ema20_gap_pct", "ic": -0.02, "rank_ic": -0.01},
                    {"factor": "ema20_gap_pct", "ic": 0.08, "rank_ic": 0.06},
                    {"factor": "body_pct", "ic": 0.03, "rank_ic": 0.02},
                ]
            }
        }
        summary = service._build_ic_summary(report)
        self.assertIn("mean_ic", summary)
        self.assertIn("ic_std", summary)
        self.assertIn("icir", summary)
        self.assertIn("ic_win_rate", summary)
        self.assertGreater(summary["mean_ic"], 0)

    def test_build_ic_summary_empty_series(self):
        """ic_series 为空时指标为 None（前端显示 -- 而非 0）。"""
        service = object.__new__(FeatureWorkspaceService)
        summary = service._build_ic_summary({"factor_evaluation": {"ic_series": []}})
        self.assertIsNone(summary["mean_ic"])
        self.assertIsNone(summary["icir"])
