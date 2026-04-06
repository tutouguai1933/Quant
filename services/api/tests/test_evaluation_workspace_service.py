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
        self.assertEqual(item["leaderboard"][0]["recommendation_reason"], "trend 行情下优先参考 trend+momentum")
        self.assertEqual(item["leaderboard"][1]["elimination_reason"], "sample_count_too_low")
        self.assertEqual(item["execution_alignment"]["status"], "matched")
        self.assertEqual(item["gate_matrix"][0]["blocking_gate"], "passed")
        self.assertEqual(item["gate_matrix"][1]["blocking_gate"], "validation_gate")
        self.assertEqual(item["comparison_summary"]["config_alignment_status"], "aligned")
        self.assertTrue(item["comparison_summary"]["model_aligned"])
        self.assertTrue(item["comparison_summary"]["dataset_aligned"])
        self.assertEqual(item["run_deltas"][0]["run_type"], "training")
        self.assertEqual(item["run_deltas"][0]["previous_run_id"], "train-previous")
        self.assertEqual(item["run_deltas"][0]["model_changed"], "是")
        self.assertEqual(item["run_deltas"][0]["dataset_changed"], "是")
        self.assertEqual(item["experiment_comparison"][0]["run_type"], "training")
        self.assertIn("controls", item)
        self.assertEqual(item["controls"]["dry_run_min_win_rate"], "0.50")
        self.assertEqual(item["controls"]["dry_run_max_turnover"], "0.60")
        self.assertEqual(item["controls"]["dry_run_min_sample_count"], "20")
        self.assertEqual(item["controls"]["validation_min_sample_count"], "12")
        self.assertEqual(item["controls"]["live_min_win_rate"], "0.55")
        self.assertEqual(item["controls"]["live_max_turnover"], "0.45")
        self.assertEqual(item["controls"]["live_min_sample_count"], "24")

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
            "config_alignment": {
                "status": "aligned",
                "stale_fields": [],
                "note": "当前结果与配置一致",
            },
            "overview": {
                "recommended_symbol": "ETHUSDT",
                "recommended_action": "enter_dry_run",
            },
            "latest_training": {
                "run_id": "train-1",
                "model_version": "model-a",
                "dataset_snapshot_id": "snapshot-1",
            },
            "latest_inference": {
                "run_id": "infer-1",
                "model_version": "model-a",
                "dataset_snapshot_id": "snapshot-1",
            },
            "candidates": [
                {
                    "symbol": "ETHUSDT",
                    "allowed_to_dry_run": True,
                    "rule_gate": {"passed": True, "reasons": []},
                    "research_validation_gate": {"passed": True, "reasons": []},
                    "backtest_gate": {"passed": True, "reasons": []},
                    "consistency_gate": {"passed": True, "reasons": []},
                },
                {
                    "symbol": "BTCUSDT",
                    "allowed_to_dry_run": False,
                    "rule_gate": {"passed": True, "reasons": []},
                    "research_validation_gate": {"passed": False, "reasons": ["sample_count_too_low"]},
                    "backtest_gate": {"passed": True, "reasons": []},
                    "consistency_gate": {"passed": True, "reasons": []},
                },
            ],
            "leaderboard": [
                {
                    "symbol": "ETHUSDT",
                    "score": "0.8300",
                    "next_action": "enter_dry_run",
                    "failure_reasons": [],
                    "recommendation_reason": "trend 行情下优先参考 trend+momentum",
                },
                {
                    "symbol": "BTCUSDT",
                    "score": "0.6200",
                    "next_action": "continue_research",
                    "failure_reasons": ["sample_count_too_low"],
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
                    {
                        "run_type": "training",
                        "run_id": "train-1",
                        "model_version": "model-a",
                        "signal_count": "0",
                        "backtest": {"net_return_pct": "8.10", "sharpe": "1.10", "win_rate": "0.58"},
                        "dataset_snapshot": {"snapshot_id": "snapshot-1"},
                    },
                    {
                        "run_type": "training",
                        "run_id": "train-previous",
                        "model_version": "model-prev",
                        "signal_count": "0",
                        "backtest": {"net_return_pct": "5.20", "sharpe": "0.90", "win_rate": "0.51"},
                        "dataset_snapshot": {"snapshot_id": "snapshot-prev"},
                    },
                    {
                        "run_type": "inference",
                        "run_id": "infer-1",
                        "model_version": "model-a",
                        "signal_count": "2",
                        "dataset_snapshot": {"snapshot_id": "snapshot-1"},
                    },
                    {
                        "run_type": "inference",
                        "run_id": "infer-previous",
                        "model_version": "model-prev",
                        "signal_count": "1",
                        "dataset_snapshot": {"snapshot_id": "snapshot-prev"},
                    },
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
                "dry_run_min_win_rate": "0.50",
                "dry_run_max_turnover": "0.60",
                "dry_run_min_sample_count": "20",
                "validation_min_sample_count": "12",
                "live_min_score": "0.65",
                "live_min_positive_rate": "0.50",
                "live_min_net_return_pct": "0.20",
                "live_min_win_rate": "0.55",
                "live_max_turnover": "0.45",
                "live_min_sample_count": "24",
            }
        }
    }


if __name__ == "__main__":
    unittest.main()
