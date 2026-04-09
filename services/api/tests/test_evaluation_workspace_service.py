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
        self.assertEqual(item["candidate_scope"]["candidate_symbols"][:3], ["BTCUSDT", "ETHUSDT", "BNBUSDT"])
        self.assertEqual(item["candidate_scope"]["live_allowed_symbols"], ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT"])
        self.assertEqual(item["candidate_scope"]["candidate_pool_preset_key"], "top10_liquid")
        self.assertEqual(item["candidate_scope"]["live_subset_preset_key"], "core_live")
        self.assertIn("候选池", item["candidate_scope"]["candidate_pool_preset_detail"])
        self.assertIn("live", item["candidate_scope"]["live_subset_preset_detail"].lower())
        self.assertEqual(item["evaluation"]["candidate_status"]["ready_count"], 1)
        self.assertIn("net_return_pct", item["evaluation"]["metrics_catalog"])
        self.assertEqual(item["reviews"]["research"]["result"], "candidate_ready")
        self.assertEqual(item["leaderboard"][0]["symbol"], "ETHUSDT")
        self.assertEqual(item["leaderboard"][0]["recommendation_reason"], "trend 行情下优先参考 trend+momentum")
        self.assertEqual(item["leaderboard"][1]["elimination_reason"], "sample_count_too_low")
        self.assertEqual(item["execution_alignment"]["status"], "matched")
        self.assertEqual(item["gate_matrix"][0]["blocking_gate"], "passed")
        self.assertEqual(item["gate_matrix"][0]["live_gate"], "通过")
        self.assertEqual(item["gate_matrix"][1]["blocking_gate"], "validation_gate")
        self.assertEqual(item["comparison_summary"]["config_alignment_status"], "aligned")
        self.assertTrue(item["comparison_summary"]["model_aligned"])
        self.assertTrue(item["comparison_summary"]["dataset_aligned"])
        self.assertEqual(item["alignment_details"]["research_symbol"], "ETHUSDT")
        self.assertEqual(item["alignment_details"]["last_order_symbol"], "ETHUSDT")
        self.assertEqual(item["alignment_details"]["last_position_symbol"], "ETHUSDT")
        self.assertEqual(item["alignment_details"]["alignment_state"], "研究和执行已对齐")
        self.assertEqual(item["run_deltas"][0]["run_type"], "training")
        self.assertEqual(item["run_deltas"][0]["previous_run_id"], "train-previous")
        self.assertEqual(item["run_deltas"][0]["model_changed"], "是")
        self.assertEqual(item["run_deltas"][0]["dataset_changed"], "是")
        self.assertIn("model_key", item["run_deltas"][0]["changed_fields"])
        self.assertIn("window_mode", item["run_deltas"][0]["changed_fields"])
        self.assertIn("backtest_cost_model", item["run_deltas"][0]["changed_fields"])
        self.assertIn("enable_rule_gate", item["run_deltas"][0]["changed_fields"])
        self.assertEqual(item["run_deltas"][0]["changed_fields_status"], "ready")
        self.assertEqual(item["run_deltas"][0]["comparison_readiness"], "limited")
        self.assertIn("模型版本", item["run_deltas"][0]["change_summary"])
        self.assertIn("数据快照", item["run_deltas"][0]["comparison_reason"])
        self.assertIn("强制验证当前最优候选", item["run_deltas"][0]["comparison_reason"])
        self.assertIn("成本模型", item["run_deltas"][0]["comparison_reason"])
        self.assertIn("规则门开关", item["run_deltas"][0]["comparison_reason"])
        self.assertEqual(item["delta_overview"]["status"], "limited")
        self.assertIn("当前先看", item["delta_overview"]["headline"])
        self.assertEqual(item["experiment_comparison"][0]["run_type"], "training")
        self.assertEqual(item["alignment_details"]["difference_summary"], "研究标的、最近订单和最近持仓已经对上")
        self.assertEqual(item["alignment_details"]["difference_severity"], "low")
        self.assertEqual(item["alignment_details"]["difference_reasons"], ["当前没有明显差异"])
        self.assertEqual(item["alignment_gaps"], [])
        self.assertEqual(item["alignment_actions"][0]["label"], "继续保持研究和执行同一轮")
        self.assertEqual(item["best_experiment"]["symbol"], "ETHUSDT")
        self.assertEqual(item["best_experiment"]["recommended_stage"], "dry_run")
        self.assertIn("更适合", item["best_experiment"]["reason"])
        self.assertEqual(item["best_stage_candidates"]["dry_run"]["symbol"], "ETHUSDT")
        self.assertEqual(item["best_stage_candidates"]["live"]["symbol"], "ETHUSDT")
        self.assertEqual(item["best_stage_candidates"]["live"]["stage"], "live")
        self.assertEqual(item["alignment_metric_rows"][0]["metric"], "研究结论")
        self.assertIn("ETHUSDT", item["alignment_metric_rows"][0]["research"])
        self.assertIn("dry-run", item["alignment_metric_rows"][1]["execution"])
        self.assertEqual(item["workflow_alignment_timeline"][0]["task_type"], "research_train")
        self.assertEqual(item["workflow_alignment_timeline"][0]["status"], "succeeded")
        self.assertIn("controls", item)
        self.assertIn("operations", item)
        self.assertEqual(item["controls"]["dry_run_min_win_rate"], "0.50")
        self.assertEqual(item["controls"]["dry_run_max_turnover"], "0.60")
        self.assertEqual(item["controls"]["dry_run_min_sample_count"], "20")
        self.assertEqual(item["controls"]["validation_min_sample_count"], "12")
        self.assertEqual(item["controls"]["validation_min_avg_future_return_pct"], "-0.1")
        self.assertEqual(item["controls"]["consistency_max_validation_backtest_return_gap_pct"], "1.5")
        self.assertEqual(item["controls"]["consistency_max_training_validation_positive_rate_gap"], "0.2")
        self.assertEqual(item["controls"]["consistency_max_training_validation_return_gap_pct"], "1.5")
        self.assertEqual(item["controls"]["rule_min_ema20_gap_pct"], "0")
        self.assertEqual(item["controls"]["rule_min_ema55_gap_pct"], "0")
        self.assertEqual(item["controls"]["rule_max_atr_pct"], "5")
        self.assertEqual(item["controls"]["rule_min_volume_ratio"], "1")
        self.assertEqual(item["controls"]["live_min_win_rate"], "0.55")
        self.assertEqual(item["controls"]["live_max_turnover"], "0.45")
        self.assertEqual(item["controls"]["live_min_sample_count"], "24")
        self.assertEqual(item["selection_story"]["threshold_preset"]["key"], "standard_gate")
        self.assertEqual(item["selection_story"]["alignment_status"], "aligned")
        self.assertIn("dry-run", item["selection_story"]["detail"])
        self.assertEqual(item["threshold_catalog"][0]["key"], "threshold_preset")
        self.assertEqual(item["threshold_catalog"][1]["key"], "dry_run_gate")
        self.assertEqual(item["threshold_catalog"][2]["key"], "validation_gate")
        self.assertEqual(item["threshold_catalog"][5]["key"], "live_gate")
        self.assertEqual(item["threshold_catalog"][6]["key"], "gate_switches")
        self.assertIn("更值得进入 dry-run", item["recommendation_explanation"]["headline"])
        self.assertIn("主要卡在", item["elimination_explanation"]["headline"])
        self.assertIsInstance(item["recommendation_explanation"]["evidence"], list)
        self.assertEqual(len(item["recommendation_explanation"]["evidence"]), 3)
        self.assertIn("分数", item["recommendation_explanation"]["evidence"][0])
        self.assertIsInstance(item["elimination_explanation"]["evidence"], list)
        self.assertIn("主要原因", item["elimination_explanation"]["evidence"][1])
        self.assertIn("研究和执行", item["alignment_story"]["headline"])
        self.assertEqual(item["alignment_story"]["evidence"], ["当前没有明显差异"])
        self.assertEqual(item["operations"]["review_limit"], "10")
        self.assertEqual(item["comparison_summary"]["training_model_version"], "model-a")
        self.assertEqual(item["comparison_summary"]["inference_model_version"], "model-a")
        self.assertEqual(item["comparison_summary"]["training_dataset_snapshot"], "snapshot-1")
        self.assertEqual(item["comparison_summary"]["inference_dataset_snapshot"], "snapshot-1")
        self.assertIn("模型一致", item["comparison_summary"]["experiment_alignment_note"])
        self.assertEqual(item["recent_training_runs"][0]["run_id"], "train-1")
        self.assertEqual(item["recent_training_runs"][0]["force_validation_top_candidate"], "否")
        self.assertEqual(item["recent_inference_runs"][0]["run_id"], "infer-1")
        self.assertEqual(item["recent_review_tasks"][0]["task_type"], "research_train")
        self.assertEqual(item["recent_review_tasks"][-1]["result_summary"], "复盘完成")
        self.assertIn("ETHUSDT", item["stage_decision_summary"]["headline"])
        self.assertIn("dry-run", item["stage_decision_summary"]["headline"])
        self.assertIn("trend 行情下优先参考", item["stage_decision_summary"]["why_recommended"])
        self.assertIn("研究标的、最近订单和最近持仓已经对上", item["stage_decision_summary"]["execution_gap"])

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
        self.assertEqual(item["selection_story"]["threshold_preset"]["key"], "standard_gate")
        self.assertTrue(item["threshold_catalog"])
        self.assertEqual(
            item["comparison_summary"]["experiment_alignment_note"],
            "当前还没有训练或推理记录，先跑实验再来看对比。",
        )

    def test_gate_matrix_accepts_status_based_gate_payloads(self) -> None:
        rows = EvaluationWorkspaceService._build_gate_matrix(
            {
                "candidates": [
                    {
                        "symbol": "ETHUSDT",
                        "allowed_to_dry_run": True,
                        "allowed_to_live": False,
                        "rule_gate": {"status": "passed", "reasons": []},
                        "research_validation_gate": {"status": "passed", "reasons": []},
                        "backtest_gate": {"status": "passed", "reasons": []},
                        "consistency_gate": {"status": "passed", "reasons": []},
                        "dry_run_gate": {"status": "passed", "reasons": []},
                        "live_gate": {"status": "failed", "reasons": ["score_below_live_floor"]},
                    },
                    {
                        "symbol": "BTCUSDT",
                        "allowed_to_dry_run": False,
                        "allowed_to_live": False,
                        "rule_gate": {"status": "passed", "reasons": []},
                        "research_validation_gate": {"status": "failed", "reasons": ["sample_count_too_low"]},
                        "backtest_gate": {"status": "passed", "reasons": []},
                        "consistency_gate": {"status": "passed", "reasons": []},
                        "dry_run_gate": {"status": "failed", "reasons": ["sample_count_too_low"]},
                        "live_gate": {"status": "failed", "reasons": ["live_threshold_not_met"]},
                    },
                ]
            }
        )

        self.assertEqual(rows[0]["blocking_gate"], "live_gate")
        self.assertEqual(rows[0]["rule_gate"], "通过")
        self.assertEqual(rows[0]["live_gate"], "拦下")
        self.assertEqual(rows[0]["primary_reason"], "score_below_live_floor")
        self.assertEqual(rows[1]["blocking_gate"], "validation_gate")
        self.assertEqual(rows[1]["primary_reason"], "sample_count_too_low")

    def test_gate_matrix_keeps_legacy_candidates_neutral_when_live_gate_is_missing(self) -> None:
        rows = EvaluationWorkspaceService._build_gate_matrix(
            {
                "candidates": [
                    {
                        "symbol": "BTCUSDT",
                        "allowed_to_dry_run": True,
                        "allowed_to_live": False,
                        "rule_gate": {"status": "passed", "reasons": []},
                        "research_validation_gate": {"status": "passed", "reasons": []},
                        "backtest_gate": {"status": "passed", "reasons": []},
                        "consistency_gate": {"status": "passed", "reasons": []},
                        "dry_run_gate": {"status": "passed", "reasons": []},
                    },
                ]
            }
        )

        self.assertEqual(rows[0]["blocking_gate"], "passed")
        self.assertEqual(rows[0]["primary_reason"], "已通过")
        self.assertEqual(rows[0]["live_gate"], "n/a")

    def test_workspace_marks_run_delta_as_unavailable_when_context_is_missing(self) -> None:
        service = EvaluationWorkspaceService(
            report_reader=_MissingContextResearchService(),
            controls_builder=_fake_controls,
            review_reader=_FakeValidationReviewService(),
        )

        item = service.get_workspace()

        self.assertEqual(item["run_deltas"][0]["changed_fields"], [])
        self.assertEqual(item["run_deltas"][0]["changed_fields_status"], "unavailable")
        self.assertIn("暂时无法比较", item["run_deltas"][0]["changed_fields_note"])
        self.assertEqual(item["run_deltas"][0]["comparison_readiness"], "unavailable")
        self.assertIn("配置快照", item["run_deltas"][0]["comparison_reason"])

    def test_workspace_preserves_research_and_label_configuration_in_recent_runs(self) -> None:
        service = EvaluationWorkspaceService(
            report_reader=_FakeResearchService(),
            controls_builder=_fake_controls,
            review_reader=_FakeValidationReviewService(),
        )

        item = service.get_workspace()

        self.assertEqual(item["recent_training_runs"][0]["research_preset_key"], "baseline_balanced")
        self.assertEqual(item["recent_training_runs"][0]["label_preset_key"], "balanced_window")
        self.assertEqual(item["recent_training_runs"][0]["label_trigger_basis"], "close")
        self.assertEqual(item["recent_inference_runs"][0]["research_preset_key"], "baseline_balanced")
        self.assertEqual(item["recent_inference_runs"][0]["label_preset_key"], "balanced_window")
        self.assertEqual(item["recent_inference_runs"][0]["label_trigger_basis"], "close")

    def test_workspace_uses_configured_review_limit(self) -> None:
        review_reader = _CapturingValidationReviewService()
        service = EvaluationWorkspaceService(
            report_reader=_FakeResearchService(),
            controls_builder=lambda: _fake_controls(review_limit="3"),
            review_reader=review_reader,
        )

        service.get_workspace()

        self.assertEqual(review_reader.last_limit, 3)

    def test_workspace_limits_comparison_views_by_configured_window(self) -> None:
        service = EvaluationWorkspaceService(
            report_reader=_FakeResearchService(),
            controls_builder=lambda: _fake_controls(review_limit="10", comparison_run_limit="1"),
            review_reader=_FakeValidationReviewService(),
        )

        item = service.get_workspace()

        self.assertEqual(item["operations"]["comparison_run_limit"], "1")
        self.assertEqual(len(item["recent_training_runs"]), 1)
        self.assertEqual(len(item["recent_inference_runs"]), 1)
        self.assertEqual(len(item["run_deltas"]), 1)
        self.assertEqual(item["run_deltas"][0]["run_type"], "training")

    def test_workspace_builds_execution_gap_summary_when_research_and_execution_diverge(self) -> None:
        service = EvaluationWorkspaceService(
            report_reader=_FakeResearchService(),
            controls_builder=_fake_controls,
            review_reader=_DivergedValidationReviewService(),
        )

        item = service.get_workspace()

        self.assertEqual(item["alignment_details"]["difference_severity"], "high")
        self.assertIn("研究建议 ETHUSDT", item["alignment_details"]["difference_summary"])
        self.assertIn("最近订单仍是 BTCUSDT", item["alignment_details"]["difference_reasons"])
        self.assertIn("同步失败", item["alignment_details"]["difference_reasons"])
        self.assertEqual(item["alignment_details"]["next_step"], "先恢复同步，再确认是否真的把研究候选派发到执行侧。")
        self.assertEqual(item["alignment_gaps"][0]["severity"], "high")
        self.assertEqual(item["alignment_actions"][0]["label"], "先恢复同步")

    def test_workspace_does_not_mark_alignment_as_matched_when_research_candidate_is_missing(self) -> None:
        service = EvaluationWorkspaceService(
            report_reader=_NoRecommendationResearchService(),
            controls_builder=_fake_controls,
            review_reader=_UnavailableAlignmentReviewService(),
        )

        item = service.get_workspace()

        self.assertEqual(item["alignment_details"]["difference_severity"], "unknown")
        self.assertEqual(item["alignment_details"]["difference_summary"], "当前还没有足够结果可对齐")
        self.assertEqual(item["alignment_details"]["difference_reasons"], ["当前还没有研究候选，先补研究结果。"])
        self.assertEqual(item["alignment_details"]["next_step"], "先补研究结果、执行同步或 dry-run，再回来复核。")
        self.assertEqual(item["alignment_gaps"][0]["severity"], "unknown")
        self.assertEqual(item["alignment_actions"][0]["label"], "继续研究")


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
                    "allowed_to_live": True,
                    "rule_gate": {"passed": True, "reasons": []},
                    "research_validation_gate": {"passed": True, "reasons": []},
                    "backtest_gate": {"passed": True, "reasons": []},
                    "consistency_gate": {"passed": True, "reasons": []},
                    "dry_run_gate": {"passed": True, "reasons": []},
                    "live_gate": {"passed": True, "reasons": []},
                },
                {
                    "symbol": "BTCUSDT",
                    "allowed_to_dry_run": False,
                    "allowed_to_live": False,
                    "rule_gate": {"passed": True, "reasons": []},
                    "research_validation_gate": {"passed": False, "reasons": ["sample_count_too_low"]},
                    "backtest_gate": {"passed": True, "reasons": []},
                    "consistency_gate": {"passed": True, "reasons": []},
                    "dry_run_gate": {"passed": False, "reasons": ["sample_count_too_low"]},
                    "live_gate": {"passed": False, "reasons": ["sample_count_too_low"]},
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
                        "training_context": {
                            "parameters": {
                                "research_preset_key": "baseline_balanced",
                                "model_key": "heuristic_v1",
                                "label_preset_key": "balanced_window",
                                "label_trigger_basis": "close",
                                "window_mode": "fixed",
                                "start_date": "2026-01-01",
                                "end_date": "2026-02-01",
                                "force_validation_top_candidate": False,
                                "backtest_cost_model": "zero_cost_baseline",
                                "enable_rule_gate": False,
                            }
                        },
                    },
                    {
                        "run_type": "training",
                        "run_id": "train-previous",
                        "model_version": "model-prev",
                        "signal_count": "0",
                        "backtest": {"net_return_pct": "5.20", "sharpe": "0.90", "win_rate": "0.51"},
                        "dataset_snapshot": {"snapshot_id": "snapshot-prev"},
                        "training_context": {
                            "parameters": {
                                "research_preset_key": "momentum_breakout",
                                "model_key": "trend_bias_v2",
                                "label_preset_key": "volatility_breakout",
                                "label_trigger_basis": "high_low",
                                "window_mode": "rolling",
                                "start_date": "",
                                "end_date": "",
                                "backtest_cost_model": "round_trip_basis_points",
                                "enable_rule_gate": True,
                            }
                        },
                    },
                    {
                        "run_type": "inference",
                        "run_id": "infer-1",
                        "model_version": "model-a",
                        "signal_count": "2",
                        "dataset_snapshot": {"snapshot_id": "snapshot-1"},
                        "inference_context": {
                            "input_summary": {
                                "research_preset_key": "baseline_balanced",
                                "model_key": "heuristic_v1",
                                "label_preset_key": "balanced_window",
                                "label_trigger_basis": "close",
                                "window_mode": "fixed",
                                "force_validation_top_candidate": False,
                            }
                        },
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
                    "runtime_mode": "dry-run",
                    "latest_sync_status": "succeeded",
                    "matched_order_count": 1,
                    "matched_position_count": 1,
                    "orders": [{"symbol": "ETHUSDT", "status": "filled"}],
                    "positions": [{"symbol": "ETHUSDT", "side": "long"}],
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
            "recent_tasks": [
                {
                    "task_type": "research_train",
                    "status": "succeeded",
                    "finished_at": "2026-04-07T12:00:00+00:00",
                    "result_summary": "训练完成",
                },
                {
                    "task_type": "research_infer",
                    "status": "succeeded",
                    "finished_at": "2026-04-07T12:03:00+00:00",
                    "result_summary": "推理完成",
                },
                {
                    "task_type": "signal_output",
                    "status": "succeeded",
                    "finished_at": "2026-04-07T12:04:00+00:00",
                    "result_summary": "信号已输出",
                },
                {
                    "task_type": "sync",
                    "status": "succeeded",
                    "finished_at": "2026-04-07T12:05:00+00:00",
                    "result_summary": "同步完成",
                },
                {
                    "task_type": "review",
                    "status": "succeeded",
                    "finished_at": "2026-04-07T12:06:00+00:00",
                    "result_summary": "复盘完成",
                },
            ],
        }


class _UnavailableResearchService:
    def get_factory_report(self) -> dict[str, object]:
        return {"status": "unavailable"}


class _NoRecommendationResearchService(_FakeResearchService):
    def get_factory_report(self) -> dict[str, object]:
        payload = super().get_factory_report()
        payload["overview"] = {
            "recommended_symbol": "",
            "recommended_action": "run_inference",
        }
        return payload


class _MissingContextResearchService(_FakeResearchService):
    def get_factory_report(self) -> dict[str, object]:
        payload = super().get_factory_report()
        payload["latest_training"] = {
            "run_id": "train-1",
            "model_version": "model-a",
            "dataset_snapshot_id": "snapshot-1",
        }
        payload["experiments"]["recent_runs"] = [
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
        ]
        return payload


class _CapturingValidationReviewService(_FakeValidationReviewService):
    def __init__(self) -> None:
        self.last_limit = 0

    def build_report(self, limit: int = 10) -> dict[str, object]:
        self.last_limit = limit
        return super().build_report(limit=limit)


class _DivergedValidationReviewService(_FakeValidationReviewService):
    def build_report(self, limit: int = 10) -> dict[str, object]:
        payload = super().build_report(limit=limit)
        payload["execution_comparison"] = {
            "status": "attention_required",
            "symbol": "ETHUSDT",
            "recommended_action": "enter_dry_run",
            "note": "研究允许执行，但最近同步失败，执行结果也还没跟上。",
            "execution": {
                "runtime_mode": "manual",
                "latest_sync_status": "failed",
                "matched_order_count": 0,
                "matched_position_count": 0,
                "orders": [{"symbol": "BTCUSDT", "status": "filled"}],
                "positions": [{"symbol": "BTCUSDT", "side": "long"}],
            },
        }
        return payload


class _UnavailableAlignmentReviewService(_FakeValidationReviewService):
    def build_report(self, limit: int = 10) -> dict[str, object]:
        payload = super().build_report(limit=limit)
        payload["execution_comparison"] = {
            "status": "unavailable",
            "symbol": "",
            "recommended_action": "run_inference",
            "note": "当前没有可对照的研究候选",
            "execution": {
                "runtime_mode": "demo",
                "latest_sync_status": "unknown",
                "matched_order_count": 0,
                "matched_position_count": 0,
                "orders": [],
                "positions": [],
            },
        }
        return payload


def _fake_controls(*, review_limit: str = "10", comparison_run_limit: str = "5") -> dict[str, object]:
    return {
        "config": {
            "data": {
                "selected_symbols": [
                    "BTCUSDT",
                    "ETHUSDT",
                    "BNBUSDT",
                    "SOLUSDT",
                    "XRPUSDT",
                    "DOGEUSDT",
                    "ADAUSDT",
                    "LINKUSDT",
                    "AVAXUSDT",
                    "DOTUSDT",
                ],
            },
            "execution": {
                "live_allowed_symbols": ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT"],
            },
            "operations": {
                "review_limit": review_limit,
                "comparison_run_limit": comparison_run_limit,
            },
            "thresholds": {
                "threshold_preset_key": "standard_gate",
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
                "validation_min_avg_future_return_pct": "-0.1",
                "consistency_max_validation_backtest_return_gap_pct": "1.5",
                "consistency_max_training_validation_positive_rate_gap": "0.2",
                "consistency_max_training_validation_return_gap_pct": "1.5",
                "rule_min_ema20_gap_pct": "0",
                "rule_min_ema55_gap_pct": "0",
                "rule_max_atr_pct": "5",
                "rule_min_volume_ratio": "1",
                "enable_rule_gate": True,
                "enable_validation_gate": True,
                "enable_backtest_gate": True,
                "enable_consistency_gate": True,
                "enable_live_gate": True,
                "live_min_score": "0.65",
                "live_min_positive_rate": "0.50",
                "live_min_net_return_pct": "0.20",
                "live_min_win_rate": "0.55",
                "live_max_turnover": "0.45",
                "live_min_sample_count": "24",
            },
        },
        "options": {
            "threshold_presets": ["standard_gate", "strict_live_gate", "exploratory_dry_run"],
            "threshold_preset_catalog": [
                {"key": "standard_gate", "label": "standard_gate / 标准准入", "fit": "默认口径", "detail": "适合先跑统一研究链，再看哪些候选可以进 dry-run。"},
                {"key": "strict_live_gate", "label": "strict_live_gate / 严格 live", "fit": "更适合小额 live 前复核", "detail": "会更强调趋势确认、一致性和稳定性。"},
            ],
        },
    }


if __name__ == "__main__":
    unittest.main()
