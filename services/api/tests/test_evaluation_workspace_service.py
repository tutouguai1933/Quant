from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.api.app.services.evaluation_workspace_service import EvaluationWorkspaceService  # noqa: E402


class EvaluationWorkspaceServiceTests(unittest.TestCase):
    def test_workspace_returns_evaluation_summary(self) -> None:
        service = EvaluationWorkspaceService(report_reader=_FakeResearchService())

        item = service.get_workspace()

        self.assertEqual(item["status"], "ready")
        self.assertEqual(item["overview"]["recommended_symbol"], "ETHUSDT")
        self.assertEqual(item["evaluation"]["candidate_status"]["ready_count"], 1)
        self.assertIn("net_return_pct", item["evaluation"]["metrics_catalog"])
        self.assertEqual(item["reviews"]["research"]["result"], "candidate_ready")
        self.assertEqual(item["leaderboard"][0]["symbol"], "ETHUSDT")

    def test_workspace_handles_missing_evaluation(self) -> None:
        service = EvaluationWorkspaceService(report_reader=_UnavailableResearchService())

        item = service.get_workspace()

        self.assertEqual(item["status"], "unavailable")
        self.assertEqual(item["leaderboard"], [])
        self.assertEqual(item["evaluation"], {})


class _FakeResearchService:
    def get_factory_report(self) -> dict[str, object]:
        return {
            "status": "ready",
            "overview": {
                "recommended_symbol": "ETHUSDT",
                "recommended_action": "enter_dry_run",
            },
            "leaderboard": [
                {
                    "symbol": "ETHUSDT",
                    "score": "0.8300",
                    "next_action": "enter_dry_run",
                    "failure_reasons": [],
                }
            ],
            "evaluation": {
                "metrics_catalog": ["net_return_pct", "max_drawdown_pct"],
                "candidate_status": {"ready_count": 1, "blocked_count": 3},
                "recommended_candidate": {"symbol": "ETHUSDT", "score": "0.8300"},
                "elimination_rules": {
                    "blocked_reason_counts": {"validation_score_too_low": 2},
                },
            },
            "reviews": {
                "research": {"result": "candidate_ready", "next_action": "enter_dry_run"},
            },
            "experiments": {
                "recent_runs": [
                    {"run_type": "training", "run_id": "train-1"},
                    {"run_type": "inference", "run_id": "infer-1"},
                ]
            },
        }


class _UnavailableResearchService:
    def get_factory_report(self) -> dict[str, object]:
        return {"status": "unavailable"}


if __name__ == "__main__":
    unittest.main()
