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
            latest_training={
                "model_version": "m1",
                "backtest": {"metrics": {"sharpe": "1.10"}},
                "dataset_snapshot": {
                    "snapshot_id": "dataset-training",
                    "data_states": {"current": "feature-ready"},
                    "cache": {"hit_count": 1, "miss_count": 0},
                },
            },
            latest_inference={"signals": [{"symbol": "BTCUSDT"}]},
            candidates={"items": [{"symbol": "BTCUSDT", "allowed_to_dry_run": True}]},
        )

        self.assertEqual(report["overview"]["candidate_count"], 1)
        self.assertEqual(report["overview"]["ready_count"], 1)
        self.assertEqual(report["overview"]["signal_count"], 1)
        self.assertEqual(report["latest_training"]["model_version"], "m1")
        self.assertEqual(report["latest_inference"]["signals"][0]["symbol"], "BTCUSDT")
        self.assertEqual(report["candidates"][0]["symbol"], "BTCUSDT")
        self.assertEqual(report["experiments"]["training"]["dataset_snapshot"]["data_states"]["current"], "feature-ready")
        self.assertEqual(report["experiments"]["training"]["dataset_snapshot"]["cache"]["hit_count"], 1)

    def test_build_experiment_report_includes_screening_summary_and_backtest_snapshot(self) -> None:
        report = build_experiment_report(
            latest_training={
                "model_version": "m2",
                "backtest": {
                    "metrics": {
                        "total_return_pct": "12.10",
                        "gross_return_pct": "12.40",
                        "net_return_pct": "12.10",
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
                        "rule_gate": {"status": "failed", "reasons": ["trend_broken"]},
                        "research_validation_gate": {"status": "failed", "reasons": ["validation_positive_rate_too_low"]},
                        "backtest_gate": {"status": "failed", "reasons": ["drawdown_too_large"]},
                        "consistency_gate": {"status": "failed", "reasons": ["validation_backtest_drift_too_large"]},
                        "backtest": {"metrics": {"sharpe": "0.41"}},
                    },
                ]
            },
            recent_runs=[
                {
                    "run_id": "infer-1",
                    "run_type": "inference",
                    "status": "completed",
                    "generated_at": "2026-04-04T09:00:00+00:00",
                    "model_version": "m2",
                    "dataset_snapshot_path": "/tmp/dataset.json",
                    "dataset_snapshot": {
                        "snapshot_id": "dataset-inference",
                        "data_states": {"current": "feature-ready"},
                        "cache": {"hit_count": 1, "miss_count": 0},
                    },
                    "artifact_path": "/tmp/artifact.json",
                }
            ],
        )

        self.assertEqual(report["overview"]["blocked_count"], 1)
        self.assertEqual(report["overview"]["pass_rate_pct"], "50.00")
        self.assertEqual(report["overview"]["top_candidate_symbol"], "BTCUSDT")
        self.assertEqual(report["overview"]["top_candidate_score"], "0.8123")
        self.assertEqual(report["experiments"]["training"]["backtest"]["sharpe"], "1.22")
        self.assertEqual(report["overview"]["recommended_symbol"], "BTCUSDT")
        self.assertEqual(report["overview"]["recommended_action"], "enter_dry_run")
        self.assertEqual(report["leaderboard"][0]["symbol"], "BTCUSDT")
        self.assertEqual(report["leaderboard"][1]["next_action"], "continue_research")
        self.assertEqual(report["screening"]["blocked_reason_counts"]["drawdown_too_large"], 1)
        self.assertEqual(report["screening"]["gate_reason_counts"]["rule_gate"]["trend_broken"], 1)
        self.assertEqual(report["screening"]["gate_reason_counts"]["validation_gate"]["validation_positive_rate_too_low"], 1)
        self.assertEqual(report["screening"]["gate_reason_counts"]["consistency_gate"]["validation_backtest_drift_too_large"], 1)
        self.assertEqual(report["experiments"]["training"]["backtest"]["net_return_pct"], "12.10")
        self.assertEqual(report["experiments"]["recent_runs"][0]["run_id"], "infer-1")
        self.assertEqual(report["experiments"]["recent_runs"][0]["dataset_snapshot"]["cache"]["hit_count"], 1)

    def test_build_experiment_report_marks_forced_validation_recommendation(self) -> None:
        report = build_experiment_report(
            latest_training={"model_version": "m3"},
            latest_inference={"signals": [{"symbol": "ETHUSDT"}]},
            candidates={
                "items": [
                    {
                        "symbol": "ETHUSDT",
                        "score": "0.8200",
                        "allowed_to_dry_run": True,
                        "forced_for_validation": True,
                        "forced_reason": "force_top_candidate_for_validation",
                        "review_status": "forced_validation",
                        "next_action": "enter_dry_run",
                        "dry_run_gate": {"status": "failed", "reasons": ["drawdown_too_large"]},
                    }
                ]
            },
        )

        self.assertTrue(report["overview"]["forced_validation"])
        self.assertEqual(report["overview"]["forced_symbol"], "ETHUSDT")
        self.assertEqual(report["overview"]["recommended_symbol"], "ETHUSDT")
        self.assertEqual(report["overview"]["recommended_action"], "enter_dry_run")
        self.assertEqual(report["leaderboard"][0]["review_status"], "forced_validation")

    def test_build_experiment_report_exposes_snapshot_and_data_state_references(self) -> None:
        report = build_experiment_report(
            latest_training={
                "run_id": "train-1",
                "status": "completed",
                "generated_at": "2026-04-06T09:00:00+00:00",
                "model_version": "m4",
                "dataset_snapshot_path": "/tmp/qlib-dataset-cache-abc123.json",
                "dataset_snapshot": {
                    "snapshot_id": "dataset-abc123",
                    "cache_signature": "abc123",
                    "cache_status": "created",
                    "active_data_state": "feature-ready",
                    "data_states": {
                        "raw": {"symbol_count": 2, "row_count": 160},
                        "cleaned": {"symbol_count": 2, "row_count": 160},
                        "feature-ready": {"symbol_count": 2, "row_count": 120},
                    },
                },
            },
            latest_inference={
                "run_id": "infer-1",
                "status": "completed",
                "generated_at": "2026-04-06T10:00:00+00:00",
                "model_version": "m4",
                "dataset_snapshot_path": "/tmp/qlib-dataset-cache-abc123.json",
                "dataset_snapshot": {
                    "snapshot_id": "dataset-abc123",
                    "cache_signature": "abc123",
                    "cache_status": "reused",
                    "active_data_state": "feature-ready",
                    "data_states": {
                        "raw": {"symbol_count": 2, "row_count": 160},
                        "cleaned": {"symbol_count": 2, "row_count": 160},
                        "feature-ready": {"symbol_count": 2, "row_count": 120},
                    },
                },
                "signals": [{"symbol": "BTCUSDT"}],
            },
            candidates={"items": [{"symbol": "BTCUSDT", "allowed_to_dry_run": True}]},
        )

        self.assertEqual(report["snapshots"]["training"]["snapshot_id"], "dataset-abc123")
        self.assertEqual(report["snapshots"]["inference"]["cache_status"], "reused")
        self.assertEqual(report["experiments"]["training"]["dataset_snapshot_id"], "dataset-abc123")
        self.assertEqual(report["experiments"]["inference"]["active_data_state"], "feature-ready")

    def test_build_experiment_report_includes_evaluation_and_review_summary(self) -> None:
        report = build_experiment_report(
            latest_training={
                "run_id": "train-2",
                "status": "completed",
                "model_version": "m5",
                "backtest": {
                    "metrics": {
                        "gross_return_pct": "12.4000",
                        "net_return_pct": "11.1000",
                        "cost_impact_pct": "1.3000",
                        "max_drawdown_pct": "-4.2000",
                        "sharpe": "1.2800",
                        "win_rate": "0.6100",
                        "turnover": "0.1400",
                        "max_loss_streak": "2",
                    }
                },
            },
            latest_inference={"signals": [{"symbol": "ETHUSDT"}]},
            candidates={
                "items": [
                    {
                        "symbol": "ETHUSDT",
                        "score": "0.8300",
                        "allowed_to_dry_run": True,
                        "review_status": "ready_for_dry_run",
                        "next_action": "enter_dry_run",
                        "dry_run_gate": {"status": "passed", "reasons": []},
                        "backtest": {"metrics": {"net_return_pct": "11.1000", "max_drawdown_pct": "-4.2000"}},
                    },
                    {
                        "symbol": "BTCUSDT",
                        "score": "0.5200",
                        "allowed_to_dry_run": False,
                        "review_status": "needs_research_iteration",
                        "next_action": "continue_research",
                        "dry_run_gate": {"status": "failed", "reasons": ["drawdown_too_large"]},
                        "backtest": {"metrics": {"net_return_pct": "-2.3000", "max_drawdown_pct": "-12.0000"}},
                    },
                ]
            },
        )

        self.assertIn("evaluation", report)
        self.assertEqual(report["evaluation"]["metrics_catalog"][0], "gross_return_pct")
        self.assertEqual(report["evaluation"]["candidate_status"]["ready_count"], 1)
        self.assertIn("drawdown_too_large", report["evaluation"]["elimination_rules"]["blocked_reason_counts"])
        self.assertIn("reviews", report)
        self.assertEqual(report["reviews"]["research"]["next_action"], "enter_dry_run")
        self.assertEqual(report["reviews"]["research"]["result"], "candidate_ready")


if __name__ == "__main__":
    unittest.main()
