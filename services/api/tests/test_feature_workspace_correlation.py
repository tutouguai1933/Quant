"""因子终端展示相关性数据。"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.api.app.services.feature_workspace_service import FeatureWorkspaceService  # noqa: E402


class CorrelationRowsTests(unittest.TestCase):
    def test_builds_correlation_rows_from_report(self):
        service = object.__new__(FeatureWorkspaceService)
        report = {
            "factor_evaluation": {
                "correlation_matrix": {
                    "factors": ["ema20_gap_pct", "ema55_gap_pct", "body_pct"],
                    "redundancy_pairs": [
                        {"factor_a": "ema20_gap_pct", "factor_b": "ema55_gap_pct", "correlation": 0.99, "redundant": True},
                    ],
                    "pairs": [],
                }
            }
        }
        rows = service._build_correlation_rows(report)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["factor_a"], "ema20_gap_pct")
        self.assertEqual(rows[0]["redundant"], True)

    def test_empty_when_no_report(self):
        service = object.__new__(FeatureWorkspaceService)
        self.assertEqual(service._build_correlation_rows({}), [])
