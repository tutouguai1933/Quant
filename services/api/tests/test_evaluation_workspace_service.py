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
        service = EvaluationWorkspaceService(
            report_reader=_FakeResearchService(),
            controls_builder=_fake_controls,
            review_reader=_FakeValidationReviewService(),
        )

        item = service.get_workspace()

        self.assertEqual(item["status"], "ready")
        self.assertEqual(item["overview"]["recommended_symbol"], "ETHUSDT")
        self.assertEqual(item["evaluation"]["candidate_status"]["ready_count"], 1)
        self.assertIn("net_return_pct", item["evaluation"]["metrics_catalog"])
        self.assertEqual(item["reviews"]["research"]["result"], "candidate_ready")
        self.assertEqual(item["leaderboard"][0]["symbol"], "ETHUSDT")
        self.assertEqual(item["execution_alignment"]["status"], "matched")
        self.assertEqual(item["experiment_comparison"][0]["run_type"], "training")
        self.assertIn("controls", item)

    def test_workspace_handles_missing_evaluation(self) -> None:
        service = EvaluationWorkspaceService(
            report_reader=_UnavailableResearchService(),
            controls_builder=_fake_controls,
            review_reader=_FakeValidationReviewService(),
        )

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


class _FakeValidationReviewService:
    def build_report(self, limit: int = 10) -> dict[str, object]:
        return {
            "execution_comparison": {
                "status": "matched",
                "symbol": "ETHUSDT",
                "recommended_action": "enter_dry_run",
                "note": "研究结果和执行结果已经对上",
                "execution": {
                    "matched_order_count": 1,
                    "matched_position_count": 1,
                },
            },
            "reviews": {
                "research": {
                    "result": "candidate_ready",
                    "next_action": "enter_dry_run",
                },
                "dry_run": {
                    "result": "succeeded",
                    "next_action": "review_dry_run",
                },
                "live": {
                    "result": "waiting",
                    "next_action": "wait_live",
                },
            },
        }


class _UnavailableResearchService:
    def get_factory_report(self) -> dict[str, object]:
        return {"status": "unavailable"}


def _fake_controls() -> dict[str, object]:
    return {
        "config": {
            "thresholds": {
                "dry_run_min_score": "0.55",
                "dry_run_min_positive_rate": "0.45",
                "dry_run_min_net_return_pct": "0",
                "dry_run_min_sharpe": "0.5",
                "dry_run_max_drawdown_pct": "15",
                "dry_run_max_loss_streak": "3",
                "live_min_score": "0.65",
                "live_min_positive_rate": "0.50",
                "live_min_net_return_pct": "0.20",
            }
        }
    }


if __name__ == "__main__":
    unittest.main()
