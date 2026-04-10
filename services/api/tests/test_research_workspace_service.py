from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.api.app.services.research_workspace_service import ResearchWorkspaceService  # noqa: E402


class ResearchWorkspaceServiceTests(unittest.TestCase):
    def test_workspace_returns_research_context(self) -> None:
        service = ResearchWorkspaceService(report_reader=_FakeResearchService(), controls_builder=_fake_controls)

        item = service.get_workspace()

        self.assertEqual(item["status"], "ready")
        self.assertEqual(item["overview"]["holding_window"], "1-3d")
        self.assertEqual(item["overview"]["candidate_count"], 2)
        self.assertEqual(item["model"]["model_version"], "qlib-minimal-1")
        self.assertIn("trend_breakout_timing", item["strategy_templates"])
        self.assertEqual(item["labeling"]["label_columns"][0], "symbol")
        self.assertEqual(item["labeling"]["label_mode"], "earliest_hit")
        self.assertEqual(item["sample_window"]["training"]["count"], 120)
        self.assertEqual(item["parameters"]["backtest_fee_bps"], "10")
        self.assertIn("controls", item)
        self.assertEqual(item["controls"]["train_split_ratio"], "0.6")
        self.assertEqual(item["controls"]["validation_split_ratio"], "0.2")
        self.assertEqual(item["controls"]["test_split_ratio"], "0.2")
        self.assertEqual(item["controls"]["model_catalog"][0]["key"], "heuristic_v1")
        self.assertEqual(item["controls"]["research_template_catalog"][0]["key"], "single_asset_timing")
        self.assertEqual(item["controls"]["label_mode_catalog"][0]["key"], "earliest_hit")
        self.assertEqual(item["controls"]["label_trigger_catalog"][0]["key"], "close")
        self.assertEqual(item["controls"]["holding_window_catalog"][0]["key"], "1-3d")
        self.assertEqual(item["controls"]["signal_confidence_floor"], "0.55")
        self.assertTrue(item["controls"]["force_validation_top_candidate"])
        self.assertEqual(item["controls"]["trend_weight"], "1.3")
        self.assertEqual(item["controls"]["strict_penalty_weight"], "1")
        self.assertTrue(item["readiness"]["train_ready"])
        self.assertTrue(item["readiness"]["infer_ready"])
        self.assertIn("可以进入评估", item["readiness"]["next_step"])
        self.assertIn("BTCUSDT", item["execution_preview"]["data_scope"])
        self.assertIn("主判断", item["execution_preview"]["factor_mix"])
        self.assertIn("earliest_hit", item["execution_preview"]["label_scope"])
        self.assertIn("score", item["execution_preview"]["dry_run_gate"])
        self.assertIn("score", item["execution_preview"]["live_gate"])
        self.assertIn("强制送去验证", item["execution_preview"]["validation_policy"])
        self.assertEqual(item["label_rule_summary"]["preset_key"], "balanced_window")
        self.assertIn("目标 1%", item["label_rule_summary"]["headline"])
        self.assertIn("1-3 天", item["label_rule_summary"]["detail"])
        self.assertIn("单币择时", item["selection_story"]["headline"])
        self.assertEqual(item["selection_story"]["model"]["key"], "heuristic_v1")
        self.assertEqual(item["selection_story"]["label_preset"]["key"], "balanced_window")
        self.assertEqual(item["selection_story"]["holding_window"]["key"], "1-3d")
        self.assertEqual(item["artifact_templates"]["training"]["key"], "single_asset_timing")
        self.assertEqual(item["artifact_templates"]["inference"]["key"], "single_asset_timing")
        self.assertEqual(item["artifact_templates"]["alignment_status"], "aligned")
        self.assertEqual(item["candidate_scope"]["status"], "ready")
        self.assertEqual(item["candidate_scope"]["candidate_symbols"], ["BTCUSDT", "ETHUSDT"])
        self.assertEqual(item["candidate_scope"]["live_allowed_symbols"], ["BTCUSDT", "ETHUSDT"])
        self.assertIn("范围契约", item["candidate_scope"]["detail"])

    def test_workspace_describes_window_majority_label_definition(self) -> None:
        service = ResearchWorkspaceService(
            report_reader=_FakeResearchService(),
            controls_builder=_fake_controls_window_majority,
        )

        item = service.get_workspace()

        self.assertEqual(item["labeling"]["label_mode"], "window_majority")
        self.assertIn("多数阶段", item["labeling"]["definition"])
        self.assertEqual(item["selection_story"]["label_mode"]["key"], "window_majority")
        self.assertEqual(item["selection_story"]["model"]["key"], "stability_guard_v5")
        self.assertEqual(item["selection_story"]["holding_window"]["key"], "2-5d")

    def test_workspace_handles_missing_report(self) -> None:
        service = ResearchWorkspaceService(report_reader=_UnavailableResearchService(), controls_builder=_fake_controls)

        item = service.get_workspace()

        self.assertEqual(item["status"], "unavailable")
        self.assertEqual(item["strategy_templates"], [])
        self.assertEqual(item["parameters"], {})
        self.assertEqual(item["artifact_templates"]["alignment_status"], "missing")
        self.assertTrue(item["readiness"]["train_ready"])
        self.assertFalse(item["readiness"]["infer_ready"])
        self.assertEqual(item["readiness"]["blocking_reasons"], [])
        self.assertIn("先运行研究训练", item["readiness"]["next_step"])
        self.assertEqual(item["candidate_scope"]["status"], "ready")

    def test_workspace_marks_template_drift_between_current_choice_and_latest_runs(self) -> None:
        service = ResearchWorkspaceService(
            report_reader=_DriftedArtifactResearchService(),
            controls_builder=_fake_controls,
        )

        item = service.get_workspace()

        self.assertEqual(item["artifact_templates"]["training"]["key"], "single_asset_timing_strict")
        self.assertEqual(item["artifact_templates"]["inference"]["key"], "single_asset_timing_strict")
        self.assertEqual(item["artifact_templates"]["current"]["key"], "single_asset_timing")
        self.assertEqual(item["artifact_templates"]["alignment_status"], "drifted")
        self.assertIn("最近训练和推理", item["artifact_templates"]["note"])


class _FakeResearchService:
    def get_factory_report(self) -> dict[str, object]:
        return {
            "status": "ready",
            "backend": "qlib-fallback",
            "config_alignment": {
                "status": "aligned",
                "note": "当前结果与配置一致",
                "stale_fields": [],
            },
            "overview": {
                "candidate_count": 2,
                "recommended_symbol": "ETHUSDT",
            },
            "latest_training": {
                "model_version": "qlib-minimal-1",
                "label_columns": ["symbol", "generated_at", "label"],
                "training_context": {
                    "holding_window": "1-3d",
                    "symbols": ["BTCUSDT", "ETHUSDT"],
                    "timeframes": ["4h"],
                    "sample_window": {
                        "training": {"count": 120},
                        "validation": {"count": 40},
                        "backtest": {"count": 30},
                    },
                    "parameters": {
                        "research_template": "single_asset_timing",
                        "backtest_fee_bps": "10",
                        "backtest_slippage_bps": "5",
                    },
                },
            },
            "latest_inference": {
                "model_version": "qlib-minimal-1",
                "inference_context": {
                    "input_summary": {
                        "research_template": "single_asset_timing",
                    }
                },
            },
            "candidates": [
                {"symbol": "ETHUSDT", "strategy_template": "trend_breakout_timing"},
                {"symbol": "BTCUSDT", "strategy_template": "trend_pullback_timing"},
            ],
        }


class _UnavailableResearchService:
    def get_factory_report(self) -> dict[str, object]:
        return {"status": "unavailable"}


def _fake_controls() -> dict[str, object]:
    return {
        "config": {
            "data": {
                "candidate_pool_preset_key": "majors_focus",
                "selected_symbols": ["BTCUSDT", "ETHUSDT"],
                "timeframes": ["4h"],
                "lookback_days": 30,
                "sample_limit": 120,
            },
            "execution": {
                "live_subset_preset_key": "strict_pairs",
                "live_allowed_symbols": ["BTCUSDT", "ETHUSDT"],
            },
            "features": {
                "primary_factors": ["ema20_gap_pct", "ema55_gap_pct"],
                "auxiliary_factors": ["volume_ratio"],
            },
            "thresholds": {
                "dry_run_min_score": "0.55",
                "dry_run_min_net_return_pct": "0.10",
                "dry_run_min_sharpe": "0.50",
                "live_min_score": "0.65",
                "live_min_net_return_pct": "0.20",
                "live_min_win_rate": "0.55",
            },
            "research": {
                "research_template": "single_asset_timing",
                "model_key": "heuristic_v1",
                "label_mode": "earliest_hit",
                "holding_window_label": "1-3d",
                "force_validation_top_candidate": True,
                "min_holding_days": 1,
                "max_holding_days": 3,
                "label_target_pct": "1",
                "label_stop_pct": "-1",
                "train_split_ratio": "0.6",
                "validation_split_ratio": "0.2",
                "test_split_ratio": "0.2",
                "signal_confidence_floor": "0.55",
                "trend_weight": "1.3",
                "volume_weight": "1.1",
                "oscillator_weight": "0.7",
                "volatility_weight": "0.9",
                "strict_penalty_weight": "1",
            }
        },
        "options": {
            "models": ["heuristic_v1", "trend_bias_v2"],
            "model_catalog": [{"key": "heuristic_v1", "label": "基础启发式", "fit": "最小闭环", "detail": "先跑通"}],
            "research_templates": ["single_asset_timing", "single_asset_timing_strict"],
            "research_template_catalog": [
                {"key": "single_asset_timing", "label": "单币择时", "fit": "默认主链", "detail": "先跑主研究链"},
                {"key": "single_asset_timing_strict", "label": "单币择时严格版", "fit": "收紧放行", "detail": "更强调一致性"},
            ],
            "label_modes": ["earliest_hit", "close_only"],
            "label_mode_catalog": [{"key": "earliest_hit", "label": "最早命中", "fit": "更接近真实退出", "detail": "先命中先记账"}],
            "label_trigger_bases": ["close", "high_low"],
            "label_trigger_catalog": [{"key": "close", "label": "按收盘价判断", "fit": "口径更稳", "detail": "只看收盘"}],
            "label_presets": ["balanced_window", "pullback_reclaim"],
            "label_preset_catalog": [{"key": "balanced_window", "label": "均衡窗口", "fit": "默认标签", "detail": "均衡判断"}],
            "holding_windows": ["1-3d", "2-4d"],
            "holding_window_catalog": [{"key": "1-3d", "label": "默认窗口", "fit": "平衡节奏", "detail": "当前默认"}],
        },
    }


def _fake_controls_window_majority() -> dict[str, object]:
    controls = _fake_controls()
    research = dict((controls.get("config") or {}).get("research") or {})
    research.update(
        {
            "research_template": "single_asset_timing_strict",
            "model_key": "stability_guard_v5",
            "label_preset_key": "pullback_reclaim",
            "label_mode": "window_majority",
            "label_trigger_basis": "high_low",
            "holding_window_label": "2-5d",
            "min_holding_days": 2,
            "max_holding_days": 5,
            "label_target_pct": "1.4",
            "label_stop_pct": "-0.8",
        }
    )
    options = dict(controls.get("options") or {})
    options.update(
        {
            "models": ["heuristic_v1", "trend_bias_v2", "stability_guard_v5"],
            "model_catalog": [
                {"key": "heuristic_v1", "label": "基础启发式", "fit": "最小闭环", "detail": "先跑通"},
                {"key": "stability_guard_v5", "label": "稳定守门", "fit": "先看稳定性", "detail": "更稳一点"},
            ],
            "research_template_catalog": [
                {"key": "single_asset_timing", "label": "单币择时", "fit": "默认主链", "detail": "先跑主研究链"},
                {"key": "single_asset_timing_strict", "label": "单币择时严格版", "fit": "收紧放行", "detail": "更强调一致性"},
            ],
            "label_modes": ["earliest_hit", "close_only", "window_majority"],
            "label_mode_catalog": [
                {"key": "earliest_hit", "label": "最早命中", "fit": "更接近真实退出", "detail": "先命中先记账"},
                {"key": "window_majority", "label": "多数表决", "fit": "更保守", "detail": "按多数阶段结果记账"},
            ],
            "label_trigger_bases": ["close", "high_low"],
            "label_trigger_catalog": [
                {"key": "close", "label": "按收盘价判断", "fit": "口径更稳", "detail": "只看收盘"},
                {"key": "high_low", "label": "按高低点命中", "fit": "更接近盘中", "detail": "看窗口高低点"},
            ],
            "label_presets": ["balanced_window", "pullback_reclaim"],
            "label_preset_catalog": [
                {"key": "balanced_window", "label": "均衡窗口", "fit": "默认标签", "detail": "均衡判断"},
                {"key": "pullback_reclaim", "label": "回踩收复", "fit": "慢一点更稳", "detail": "更看重收盘修复"},
            ],
            "holding_windows": ["1-3d", "2-4d", "2-5d"],
            "holding_window_catalog": [
                {"key": "1-3d", "label": "默认窗口", "fit": "平衡节奏", "detail": "当前默认"},
                {"key": "2-5d", "label": "稳定复核窗口", "fit": "多给走势修复时间", "detail": "更偏稳定复核"},
            ],
        }
    )
    return {
        "config": {
            **dict(controls.get("config") or {}),
            "research": research,
        },
        "options": options,
    }


class _DriftedArtifactResearchService(_FakeResearchService):
    def get_factory_report(self) -> dict[str, object]:
        payload = super().get_factory_report()
        latest_training = dict(payload.get("latest_training") or {})
        training_context = dict(latest_training.get("training_context") or {})
        parameters = dict(training_context.get("parameters") or {})
        parameters["research_template"] = "single_asset_timing_strict"
        training_context["parameters"] = parameters
        latest_training["training_context"] = training_context
        payload["latest_training"] = latest_training

        latest_inference = dict(payload.get("latest_inference") or {})
        inference_context = dict(latest_inference.get("inference_context") or {})
        input_summary = dict(inference_context.get("input_summary") or {})
        input_summary["research_template"] = "single_asset_timing_strict"
        inference_context["input_summary"] = input_summary
        latest_inference["inference_context"] = inference_context
        payload["latest_inference"] = latest_inference
        return payload


if __name__ == "__main__":
    unittest.main()
