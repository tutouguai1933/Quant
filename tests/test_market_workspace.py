from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
WEB_APP = REPO_ROOT / "apps" / "web" / "app"
WEB_COMPONENTS = REPO_ROOT / "apps" / "web" / "components"
WEB_LIB = REPO_ROOT / "apps" / "web" / "lib"


class MarketWorkspaceTests(unittest.TestCase):
    def test_market_pages_and_component_exist(self) -> None:
        expected_files = [
            WEB_APP / "market" / "page.tsx",
            WEB_APP / "market" / "[symbol]" / "page.tsx",
            WEB_COMPONENTS / "candle-chart.tsx",
            WEB_COMPONENTS / "timeframe-tabs.tsx",
            WEB_COMPONENTS / "trading-chart-panel.tsx",
            WEB_COMPONENTS / "research-sidecard.tsx",
            WEB_COMPONENTS / "multi-timeframe-summary.tsx",
        ]

        for file_path in expected_files:
            self.assertTrue(file_path.exists(), f"missing file: {file_path}")

    def test_market_page_wires_list_api_and_table(self) -> None:
        content = (WEB_APP / "market" / "page.tsx").read_text(encoding="utf-8")
        self.assertIn("listMarketSnapshots", content)
        self.assertIn("AppShell", content)
        self.assertIn("DataTable", content)
        self.assertIn("/market/", content)
        self.assertIn("research_brief", content)
        self.assertIn("白名单", content)
        self.assertIn("研究倾向", content)
        self.assertIn("推荐策略", content)
        self.assertIn("判断信心", content)
        self.assertIn("主判断", content)

    def test_symbol_page_uses_trading_view_components(self) -> None:
        page_content = (WEB_APP / "market" / "[symbol]" / "page.tsx").read_text(encoding="utf-8")
        global_styles = (WEB_APP / "globals.css").read_text(encoding="utf-8")

        self.assertIn("TimeframeTabs", page_content)
        self.assertIn("TradingChartPanel", page_content)
        self.assertIn("ResearchSidecard", page_content)
        self.assertIn("MultiTimeframeSummary", page_content)
        self.assertIn("active_interval", page_content)
        self.assertIn("supported_intervals", page_content)
        self.assertIn("multi_timeframe_summary", page_content)
        self.assertIn("trading-layout", page_content)
        self.assertIn(".trading-layout", global_styles)

    def test_navigation_contains_market_entry(self) -> None:
        shell_content = (WEB_COMPONENTS / "app-shell.tsx").read_text(encoding="utf-8")
        api_content = (WEB_LIB / "api.ts").read_text(encoding="utf-8")
        self.assertIn('href: "/market"', shell_content)
        self.assertIn('href: "/market"', api_content)
        self.assertIn("listMarketSnapshots", api_content)
        self.assertIn("getMarketChart", api_content)

    def test_market_chart_summary_is_timestamp_sorted(self) -> None:
        content = (WEB_COMPONENTS / "candle-chart.tsx").read_text(encoding="utf-8")
        self.assertIn("sort(", content)
        self.assertIn("open_time", content)
        self.assertIn("close_time", content)

    def test_trading_chart_panel_renders_candles_and_research_layers(self) -> None:
        content = (WEB_COMPONENTS / "trading-chart-panel.tsx").read_text(encoding="utf-8")

        self.assertIn("<svg", content)
        self.assertIn("entry", content)
        self.assertIn("stop", content)
        self.assertIn("signal", content)
        self.assertIn("当前价格", content)
        self.assertIn("当前周期", content)
        self.assertIn('style={{ width: "100%"', content)

    def test_trading_chart_panel_matches_signal_by_time_and_ignores_bad_prices(self) -> None:
        content = (WEB_COMPONENTS / "trading-chart-panel.tsx").read_text(encoding="utf-8")

        self.assertIn("item.time", content)
        self.assertIn("find(", content)
        self.assertIn("number | null", content)
        self.assertIn("return null", content)
        self.assertIn(".filter((price): price is number => price !== null)", content)

    def test_market_api_handles_non_array_items(self) -> None:
        content = (WEB_LIB / "api.ts").read_text(encoding="utf-8")
        self.assertIn("Array.isArray", content)
        self.assertIn("isPlainObject", content)
        self.assertIn("items.map", content)
        self.assertIn("recommended_strategy", content)
        self.assertIn("trend_state", content)

    def test_market_chart_api_preserves_overlays_and_markers(self) -> None:
        content = (WEB_LIB / "api.ts").read_text(encoding="utf-8")
        self.assertIn("ChartIndicatorSummary", content)
        self.assertIn("ChartMarkerGroups", content)
        self.assertIn("fetchJson<MarketChartData>", content)
        self.assertIn("ApiEnvelope<MarketChartData>", content)
        self.assertIn("overlays", content)
        self.assertIn("markers", content)
        self.assertIn("research_brief", content)
        self.assertIn("research_cockpit", content)
        self.assertIn("strategy_context", content)
        self.assertIn("freqtrade_readiness", content)
        self.assertIn("sample_size", content)
        self.assertIn("last_candle_closed", content)
        self.assertIn("warnings", content)
        self.assertIn("overlay_summary", content)


if __name__ == "__main__":
    unittest.main()
