from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.api.app.services.backtest_workspace_service import BacktestWorkspaceService  # noqa: E402


class BacktestWorkspaceServiceTests(unittest.TestCase):
    def test_workspace_returns_backtest_summary_and_candidates(self) -> None:
        service = BacktestWorkspaceService(report_reader=_FakeResearchService(), controls_builder=_fake_controls)

        item = service.get_workspace()

        self.assertEqual(item["status"], "ready")
        self.assertEqual(item["overview"]["holding_window"], "1-3d")
        self.assertEqual(item["training_backtest"]["metrics"]["net_return_pct"], "5.2000")
        self.assertEqual(item["assumptions"]["fee_bps"], "10")
        self.assertEqual(item["leaderboard"][0]["symbol"], "ETHUSDT")
        self.assertEqual(item["leaderboard"][0]["backtest"]["net_return_pct"], "2.3000")
        self.assertIn("controls", item)
        self.assertEqual(item["controls"]["cost_model_catalog"][0]["key"], "round_trip_basis_points")
        self.assertEqual(item["controls"]["dry_run_min_win_rate"], "0.50")
        self.assertEqual(item["controls"]["dry_run_max_turnover"], "0.60")
        self.assertEqual(item["controls"]["dry_run_min_sample_count"], "20")
        self.assertEqual(item["controls"]["live_min_win_rate"], "0.55")
        self.assertEqual(item["controls"]["live_max_turnover"], "0.45")
        self.assertEqual(item["controls"]["live_min_sample_count"], "24")
        self.assertEqual(item["stage_assessment"][0]["stage"], "dry-run")
        self.assertIn("净收益", item["stage_assessment"][0]["current"])
        self.assertEqual(item["stage_assessment"][1]["stage"], "validation")
        self.assertEqual(item["stage_assessment"][2]["stage"], "live")
        self.assertEqual(item["selection_story"]["backtest_preset"]["key"], "realistic_standard")
        self.assertEqual(item["selection_story"]["cost_model"]["key"], "round_trip_basis_points")
        self.assertIn("手续费 10", item["selection_story"]["detail"])
        self.assertEqual(item["cost_filter_catalog"][0]["key"], "cost_model")
        self.assertEqual(item["cost_filter_catalog"][1]["key"], "cost_inputs")
        self.assertEqual(item["cost_filter_catalog"][2]["key"], "rule_filters")
        self.assertEqual(item["cost_filter_catalog"][4]["key"], "gate_switches")
        self.assertEqual(item["selection_story"]["alignment_status"], "aligned")

    def test_workspace_handles_missing_backtest(self) -> None:
        service = BacktestWorkspaceService(report_reader=_UnavailableResearchService(), controls_builder=_fake_controls)

        item = service.get_workspace()

        self.assertEqual(item["status"], "unavailable")
        self.assertEqual(item["leaderboard"], [])
        self.assertEqual(item["training_backtest"]["metrics"], {})
        self.assertEqual(item["selection_story"]["backtest_preset"]["key"], "realistic_standard")
        self.assertTrue(item["cost_filter_catalog"])

    def test_workspace_marks_cost_story_stale_until_training_reruns(self) -> None:
        service = BacktestWorkspaceService(report_reader=_StaleCostResearchService(), controls_builder=_fake_controls)

        item = service.get_workspace()

        self.assertEqual(item["selection_story"]["alignment_status"], "stale")
        self.assertIn("已保存新回测配置", item["selection_story"]["alignment_note"])
        self.assertEqual(item["selection_story"]["cost_model"]["key"], "zero_cost_baseline")
        self.assertIn("零成本基线", item["cost_filter_catalog"][0]["current"])
        self.assertIn("手续费 0 bps / 滑点 0 bps", item["cost_filter_catalog"][1]["current"])
        self.assertIn("已保存配置：手续费 10 bps / 滑点 5 bps", item["cost_filter_catalog"][1]["detail"])


class _FakeResearchService:
    def get_factory_report(self) -> dict[str, object]:
        return {
            "status": "ready",
            "latest_training": {
                "training_context": {"holding_window": "1-3d"},
                "validation": {"avg_future_return_pct": "0.3000"},
                "backtest": {
                    "assumptions": {
                        "fee_bps": "10",
                        "slippage_bps": "5",
                        "cost_model": "round_trip_basis_points",
                    },
                    "metrics": {
                        "net_return_pct": "5.2000",
                        "cost_impact_pct": "0.6000",
                        "max_drawdown_pct": "-3.1000",
                        "sharpe": "1.4000",
                        "action_segment_count": "7",
                        "direction_switch_count": "3",
                        "win_rate": "0.6200",
                        "turnover": "0.2100",
                    },
                },
            },
            "leaderboard": [
                {
                    "symbol": "ETHUSDT",
                    "strategy_template": "trend_breakout_timing",
                    "backtest": {
                        "net_return_pct": "2.3000",
                        "cost_impact_pct": "0.2000",
                        "max_drawdown_pct": "-1.1000",
                        "sharpe": "1.1000",
                    },
                }
            ],
        }


class _UnavailableResearchService:
    def get_factory_report(self) -> dict[str, object]:
        return {"status": "unavailable"}


class _StaleCostResearchService:
    def get_factory_report(self) -> dict[str, object]:
        return {
            "status": "ready",
            "latest_training": {
                "training_context": {"holding_window": "1-3d"},
                "validation": {"avg_future_return_pct": "0.1000"},
                "backtest": {
                    "assumptions": {
                        "fee_bps": "0",
                        "slippage_bps": "0",
                        "cost_model": "zero_cost_baseline",
                    },
                    "metrics": {
                        "net_return_pct": "6.2000",
                        "cost_impact_pct": "0.0000",
                        "max_drawdown_pct": "-2.1000",
                        "sharpe": "1.7000",
                        "action_segment_count": "5",
                        "direction_switch_count": "2",
                        "win_rate": "0.6500",
                        "turnover": "0.1800",
                    },
                },
            },
            "leaderboard": [],
        }


def _fake_controls() -> dict[str, object]:
    return {
        "config": {
            "backtest": {
                "fee_bps": "10",
                "slippage_bps": "5",
                "cost_model": "round_trip_basis_points",
            },
            "thresholds": {
                "dry_run_min_win_rate": "0.50",
                "dry_run_max_turnover": "0.60",
                "dry_run_min_sample_count": "20",
                "dry_run_min_score": "0.55",
                "dry_run_min_net_return_pct": "0.10",
                "dry_run_min_sharpe": "0.50",
                "validation_min_sample_count": "12",
                "validation_min_avg_future_return_pct": "-0.1",
                "live_min_score": "0.65",
                "live_min_net_return_pct": "0.20",
                "live_min_win_rate": "0.55",
                "live_max_turnover": "0.45",
                "live_min_sample_count": "24",
            },
        }
        ,
        "options": {
            "backtest_presets": ["realistic_standard", "cost_stress"],
            "backtest_preset_catalog": [
                {"key": "realistic_standard", "label": "真实标准", "fit": "默认口径", "detail": "按常用双边成本估算"},
                {"key": "cost_stress", "label": "成本压力", "fit": "高成本压力", "detail": "先看高成本下还能不能站住"},
            ],
            "backtest_cost_models": ["round_trip_basis_points", "zero_cost_baseline"],
            "cost_model_catalog": [
                {"key": "round_trip_basis_points", "label": "双边成本", "fit": "更贴近真实交易", "detail": "买卖都扣成本"},
                {"key": "zero_cost_baseline", "label": "零成本基线", "fit": "只看策略裸表现", "detail": "只适合做基线对照"},
            ],
        },
    }


    def test_workspace_includes_terminal_view(self) -> None:
        """测试 workspace 包含 terminal 视图字段。"""
        service = BacktestWorkspaceService(report_reader=_FakeResearchService(), controls_builder=_fake_controls)

        item = service.get_workspace()

        self.assertIn("terminal", item)
        terminal = item["terminal"]
        self.assertIn("page", terminal)
        self.assertIn("metrics", terminal)
        self.assertIn("charts", terminal)
        self.assertIn("tables", terminal)
        self.assertIn("states", terminal)

    def test_terminal_view_page_structure(self) -> None:
        """测试 terminal 视图 page 结构。"""
        service = BacktestWorkspaceService(report_reader=_FakeResearchService(), controls_builder=_fake_controls)

        item = service.get_workspace()

        terminal = item.get("terminal", {})
        page = terminal.get("page", {})
        self.assertIn("route", page)
        self.assertEqual(page["route"], "/backtest")
        self.assertIn("title", page)
        self.assertIn("breadcrumb", page)
        self.assertIn("updated_at", page)

    def test_terminal_view_states_structure(self) -> None:
        """测试 terminal 视图 states 结构。"""
        service = BacktestWorkspaceService(report_reader=_FakeResearchService(), controls_builder=_fake_controls)

        item = service.get_workspace()

        terminal = item.get("terminal", {})
        states = terminal.get("states", {})
        self.assertIn("status", states)
        self.assertIn("data_quality", states)
        self.assertIn("warnings", states)
        self.assertIn("updated_at", states)

    def test_terminal_view_metrics_format(self) -> None:
        """测试 terminal 视图 metrics 格式。"""
        service = BacktestWorkspaceService(report_reader=_FakeResearchService(), controls_builder=_fake_controls)

        item = service.get_workspace()

        terminal = item.get("terminal", {})
        metrics = terminal.get("metrics", [])
        self.assertIsInstance(metrics, list)
        for metric in metrics:
            self.assertIn("key", metric)
            self.assertIn("label", metric)
            self.assertIn("value", metric)
            self.assertIn("format", metric)
            self.assertIn("tone", metric)

    def test_terminal_view_charts_structure(self) -> None:
        """测试 terminal 视图 charts 结构。"""
        service = BacktestWorkspaceService(report_reader=_FakeResearchService(), controls_builder=_fake_controls)

        item = service.get_workspace()

        terminal = item.get("terminal", {})
        charts = terminal.get("charts", {})
        self.assertIn("performance", charts)
        performance = charts["performance"]
        self.assertIn("series", performance)
        self.assertIn("meta", performance)
        self.assertIn("data_quality", performance["meta"])

    def test_terminal_view_empty_state(self) -> None:
        """测试 terminal 视图空状态。"""
        service = BacktestWorkspaceService(report_reader=_UnavailableResearchService(), controls_builder=_fake_controls)

        item = service.get_workspace()

        terminal = item.get("terminal", {})
        states = terminal.get("states", {})
        self.assertEqual(states.get("status"), "unavailable")
        # 空状态时 data_quality 应为 empty 或 partial
        self.assertIn(states.get("data_quality"), ["empty", "partial"])

    def test_terminal_view_tables_structure(self) -> None:
        """测试 terminal 视图 tables 结构。"""
        service = BacktestWorkspaceService(report_reader=_FakeResearchService(), controls_builder=_fake_controls)

        item = service.get_workspace()

        terminal = item.get("terminal", {})
        tables = terminal.get("tables", {})
        self.assertIn("leaderboard", tables)
        self.assertIn("stage_assessment", tables)
        self.assertIsInstance(tables["leaderboard"], list)


if __name__ == "__main__":
    unittest.main()
