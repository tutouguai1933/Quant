from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.api.app.services.feature_workspace_service import FeatureWorkspaceService  # noqa: E402


class FeatureWorkspaceServiceTests(unittest.TestCase):
    def test_workspace_returns_factor_protocol_summary(self) -> None:
        service = FeatureWorkspaceService(research_reader=_FakeResearchService(), controls_builder=_fake_controls)

        item = service.get_workspace()

        self.assertEqual(item["status"], "ready")
        self.assertEqual(item["overview"]["feature_version"], "v2")
        self.assertEqual(item["overview"]["factor_count"], 4)
        self.assertIn("trend", item["categories"])
        self.assertIn("ema20_gap_pct", item["roles"]["primary"])
        self.assertIn("rsi14", item["roles"]["auxiliary"])
        self.assertEqual(item["preprocessing"]["missing_policy"], "坏行直接丢弃")
        self.assertEqual(item["controls"]["missing_policy"], "strict_drop")
        self.assertEqual(item["controls"]["outlier_policy"], "clip")
        self.assertEqual(item["controls"]["normalization_policy"], "fixed_4dp")
        self.assertIn("neutral_fill", item["controls"]["available_missing_policies"])
        self.assertIn("raw", item["controls"]["available_outlier_policies"])
        self.assertIn("zscore_by_symbol", item["controls"]["available_normalization_policies"])
        self.assertIn("4h", item["timeframe_profiles"])
        self.assertEqual(item["factors"][0]["name"], "ema20_gap_pct")
        self.assertEqual(item["selection_matrix"][0]["name"], "ema20_gap_pct")
        self.assertEqual(item["selection_matrix"][0]["current_role"], "主判断")
        self.assertEqual(item["selection_matrix"][2]["current_role"], "辅助确认")
        self.assertIn("controls", item)
        self.assertEqual(item["selection_story"]["feature_preset"]["key"], "balanced_default")
        self.assertIn("strict_drop", item["selection_story"]["detail"])
        self.assertEqual(item["category_catalog"][0]["key"], "trend")
        self.assertEqual(item["category_catalog"][0]["primary_count"], 2)
        self.assertEqual(item["category_catalog"][1]["auxiliary_count"], 1)

    def test_workspace_handles_missing_factor_protocol(self) -> None:
        service = FeatureWorkspaceService(research_reader=_UnavailableResearchService(), controls_builder=_fake_controls)

        item = service.get_workspace()

        self.assertEqual(item["status"], "unavailable")
        self.assertGreater(item["overview"]["factor_count"], 0)
        self.assertTrue(item["factors"])
        self.assertIn("trend", item["categories"])
        self.assertIn("ema20_gap_pct", item["roles"]["primary"])
        self.assertEqual(item["selection_story"]["feature_preset"]["key"], "balanced_default")

    def test_workspace_uses_factor_protocol_as_ready_signal(self) -> None:
        service = FeatureWorkspaceService(research_reader=_ProtocolOnlyResearchService(), controls_builder=_fake_controls)

        item = service.get_workspace()

        self.assertEqual(item["status"], "ready")
        self.assertEqual(item["overview"]["factor_count"], 1)
        self.assertEqual(item["factors"][0]["name"], "ema20_gap_pct")

    def test_workspace_provides_summary_fields(self) -> None:
        service = FeatureWorkspaceService(research_reader=_FakeResearchService(), controls_builder=_fake_controls)

        item = service.get_workspace()
        effectiveness = item.get("effectiveness_summary") or {}
        redundancy = item.get("redundancy_summary") or {}
        score_story = item.get("score_story") or {}

        self.assertTrue(effectiveness.get("headline"))
        self.assertTrue(effectiveness.get("top_category"))
        self.assertTrue(effectiveness.get("ic_story"))
        self.assertIn("category_rows", effectiveness)

        self.assertTrue(redundancy.get("headline"))
        overlap_groups = redundancy.get("overlap_groups") or []
        self.assertGreaterEqual(len(overlap_groups), 3)
        self.assertIn("量能", overlap_groups[-1].get("label", ""))

        contributors = score_story.get("contributors") or []
        self.assertEqual(len(contributors), 5)
        self.assertTrue(contributors[0].get("weight"))
        self.assertTrue(score_story.get("candidate_explanation"))


class _FakeResearchService:
    def get_factory_report(self) -> dict[str, object]:
        return {
            "status": "ready",
            "factor_protocol": {
                "version": "v2",
                "categories": {
                    "trend": ["ema20_gap_pct", "ema55_gap_pct"],
                    "oscillator": ["rsi14"],
                },
                "roles": {
                    "primary": ["ema20_gap_pct", "ema55_gap_pct"],
                    "auxiliary": ["rsi14"],
                },
                "preprocessing": {
                    "missing_policy": "坏行直接丢弃",
                    "outlier_policy": "裁剪极值",
                    "normalization_policy": "统一输出四位小数字符串",
                },
                "timeframe_profiles": {
                    "1h": {"ema_fast": 20, "ema_slow": 55},
                    "4h": {"ema_fast": 12, "ema_slow": 34},
                },
                "factors": [
                    {"name": "ema20_gap_pct", "category": "trend", "role": "primary", "description": "价格相对 EMA20 的偏离"},
                    {"name": "ema55_gap_pct", "category": "trend", "role": "primary", "description": "价格相对 EMA55 的偏离"},
                    {"name": "rsi14", "category": "oscillator", "role": "auxiliary", "description": "14 周期 RSI"},
                    {"name": "atr_pct", "category": "volatility", "role": "auxiliary", "description": "ATR 波动率"},
                ],
            },
        }


class _UnavailableResearchService:
    def get_factory_report(self) -> dict[str, object]:
        return {"status": "unavailable"}


class _ProtocolOnlyResearchService:
    def get_factory_report(self) -> dict[str, object]:
        return {
            "status": "unavailable",
            "factor_protocol": {
                "version": "v2",
                "categories": {"trend": ["ema20_gap_pct"]},
                "roles": {"primary": ["ema20_gap_pct"], "auxiliary": []},
                "preprocessing": {
                    "missing_policy": "坏行直接丢弃",
                    "outlier_policy": "裁剪极值",
                    "normalization_policy": "统一输出四位小数字符串",
                },
                "timeframe_profiles": {"4h": {"ema_fast": 12}},
                "factors": [
                    {"name": "ema20_gap_pct", "category": "trend", "role": "primary", "description": "价格相对 EMA20 的偏离"},
                ],
            },
        }


def _fake_controls() -> dict[str, object]:
    return {
        "config": {
            "features": {
                "primary_factors": ["ema20_gap_pct", "ema55_gap_pct"],
                "auxiliary_factors": ["rsi14"],
                "missing_policy": "strict_drop",
                "outlier_policy": "clip",
                "normalization_policy": "fixed_4dp",
            }
        },
        "options": {
            "feature_presets": ["balanced_default", "trend_focus"],
            "feature_preset_catalog": [
                {"key": "balanced_default", "label": "balanced_default / 均衡默认", "fit": "默认第一轮", "detail": "先平衡观察"},
                {"key": "trend_focus", "label": "trend_focus / 趋势优先", "fit": "更重趋势", "detail": "更看趋势推进"},
            ],
            "primary_factors": ["ema20_gap_pct", "ema55_gap_pct"],
            "auxiliary_factors": ["rsi14", "atr_pct"],
            "missing_policies": ["neutral_fill", "strict_drop"],
            "outlier_policies": ["clip", "raw"],
            "normalization_policies": ["fixed_4dp", "zscore_by_symbol"],
        },
    }


    def test_workspace_includes_terminal_view(self) -> None:
        """测试 workspace 包含 terminal 视图字段。"""
        service = FeatureWorkspaceService(research_reader=_FakeResearchService(), controls_builder=_fake_controls)

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
        service = FeatureWorkspaceService(research_reader=_FakeResearchService(), controls_builder=_fake_controls)

        item = service.get_workspace()

        terminal = item.get("terminal", {})
        page = terminal.get("page", {})
        self.assertIn("route", page)
        self.assertIn("title", page)
        self.assertIn("breadcrumb", page)
        self.assertIn("updated_at", page)

    def test_terminal_view_states_structure(self) -> None:
        """测试 terminal 视图 states 结构。"""
        service = FeatureWorkspaceService(research_reader=_FakeResearchService(), controls_builder=_fake_controls)

        item = service.get_workspace()

        terminal = item.get("terminal", {})
        states = terminal.get("states", {})
        self.assertIn("status", states)
        self.assertIn("data_quality", states)
        self.assertIn("warnings", states)
        self.assertIn("updated_at", states)

    def test_terminal_view_metrics_format(self) -> None:
        """测试 terminal 视图 metrics 格式。"""
        service = FeatureWorkspaceService(research_reader=_FakeResearchService(), controls_builder=_fake_controls)

        item = service.get_workspace()

        terminal = item.get("terminal", {})
        metrics = terminal.get("metrics", [])
        self.assertIsInstance(metrics, list)
        for metric in metrics:
            self.assertIn("key", metric)
            self.assertIn("label", metric)
            self.assertIn("value", metric)
            self.assertIn("format", metric)

    def test_terminal_view_charts_structure(self) -> None:
        """测试 terminal 视图 charts 结构。"""
        service = FeatureWorkspaceService(research_reader=_FakeResearchService(), controls_builder=_fake_controls)

        item = service.get_workspace()

        terminal = item.get("terminal", {})
        charts = terminal.get("charts", {})
        # 图表可能包含 feature_importance、factor_ic 等
        self.assertIsInstance(charts, dict)
        for chart_name, chart_data in charts.items():
            self.assertIn("series", chart_data)
            self.assertIn("meta", chart_data)

    def test_terminal_view_empty_state(self) -> None:
        """测试 terminal 视图空状态。"""
        service = FeatureWorkspaceService(research_reader=_UnavailableResearchService(), controls_builder=_fake_controls)

        item = service.get_workspace()

        terminal = item.get("terminal", {})
        states = terminal.get("states", {})
        self.assertEqual(states.get("status"), "unavailable")

    def test_terminal_view_tables_structure(self) -> None:
        """测试 terminal 视图 tables 结构。"""
        service = FeatureWorkspaceService(research_reader=_FakeResearchService(), controls_builder=_fake_controls)

        item = service.get_workspace()

        terminal = item.get("terminal", {})
        tables = terminal.get("tables", {})
        self.assertIn("selection_matrix", tables)
        self.assertIsInstance(tables["selection_matrix"], list)


if __name__ == "__main__":
    unittest.main()
