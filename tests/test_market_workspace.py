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
            WEB_COMPONENTS / "market-symbol-workspace.tsx",
            WEB_COMPONENTS / "market-snapshot-workspace.tsx",
            WEB_COMPONENTS / "market-filter-bar.tsx",
            WEB_COMPONENTS / "market-focus-board.tsx",
            WEB_COMPONENTS / "pro-chart-script.tsx",
            WEB_COMPONENTS / "pro-kline-chart.tsx",
            WEB_COMPONENTS / "timeframe-tabs.tsx",
            WEB_COMPONENTS / "trading-chart-panel.tsx",
            WEB_COMPONENTS / "research-sidecard.tsx",
            WEB_COMPONENTS / "multi-timeframe-summary.tsx",
        ]

        for file_path in expected_files:
            self.assertTrue(file_path.exists(), f"missing file: {file_path}")

    def test_market_page_wires_list_api_and_table(self) -> None:
        page_content = (WEB_APP / "market" / "page.tsx").read_text(encoding="utf-8")
        workspace_content = (WEB_COMPONENTS / "market-snapshot-workspace.tsx").read_text(encoding="utf-8")
        self.assertIn("MarketSnapshotWorkspace", page_content)
        self.assertIn("getMarketSnapshotsSnapshot", page_content)
        self.assertNotIn("listMarketSnapshots()", page_content)
        self.assertIn("DataTable", workspace_content)
        self.assertIn("/market/", workspace_content)
        self.assertIn("research_brief", workspace_content)
        self.assertIn("研究倾向", workspace_content)
        self.assertIn("推荐策略", workspace_content)
        self.assertIn("判断信心", workspace_content)
        self.assertIn("主判断", workspace_content)
        self.assertIn("进入策略中心", workspace_content)
        self.assertIn('/strategies?symbol=${encodeURIComponent(item.symbol)}', workspace_content)

    def test_market_page_uses_filter_bar_and_focus_board(self) -> None:
        page_content = (WEB_APP / "market" / "page.tsx").read_text(encoding="utf-8")
        workspace_content = (WEB_COMPONENTS / "market-snapshot-workspace.tsx").read_text(encoding="utf-8")
        focus_board_content = (WEB_COMPONENTS / "market-focus-board.tsx").read_text(encoding="utf-8")

        self.assertIn("MarketFilterBar", page_content)
        self.assertIn("MarketFocusBoard", workspace_content)
        self.assertIn("多周期状态", workspace_content)
        self.assertIn("优先关注", focus_board_content)
        self.assertIn("高信心", focus_board_content)

    def test_market_focus_board_uses_research_brief_strategy_source(self) -> None:
        content = (WEB_COMPONENTS / "market-focus-board.tsx").read_text(encoding="utf-8")

        self.assertIn("research_brief.recommended_strategy", content)
        self.assertNotIn("right.recommended_strategy", content)
        self.assertNotIn("item.recommended_strategy", content)

    def test_symbol_page_uses_trading_view_components(self) -> None:
        page_content = (WEB_APP / "market" / "[symbol]" / "page.tsx").read_text(encoding="utf-8")
        workspace_content = (WEB_COMPONENTS / "market-symbol-workspace.tsx").read_text(encoding="utf-8")
        global_styles = (WEB_APP / "globals.css").read_text(encoding="utf-8")

        self.assertIn("MarketSymbolWorkspace", page_content)
        self.assertIn("candidate={candidate}", page_content)
        self.assertIn("active_interval", page_content)
        self.assertIn("supported_intervals", page_content)
        self.assertIn("multi_timeframe_summary", workspace_content)
        self.assertIn("TradingChartPanel", workspace_content)
        self.assertIn("CompactDecisionCard", workspace_content)
        self.assertIn(".terminal-layout", global_styles)

    def test_symbol_page_shows_research_gate_and_next_step(self) -> None:
        page_content = (WEB_APP / "market" / "[symbol]" / "page.tsx").read_text(encoding="utf-8")
        workspace_content = (WEB_COMPONENTS / "market-symbol-workspace.tsx").read_text(encoding="utf-8")

        self.assertIn("candidate={candidate}", page_content)
        self.assertIn("执行摘要", workspace_content)
        self.assertIn("研究分数", workspace_content)
        self.assertIn("研究门", workspace_content)
        self.assertIn("下一步动作", workspace_content)
        self.assertIn("返回信号页继续研究", page_content)
        self.assertIn('<section className="space-y-6">', page_content)

    def test_symbol_page_has_timeout_fallback_for_slow_market_chart(self) -> None:
        page_content = (WEB_APP / "market" / "[symbol]" / "page.tsx").read_text(encoding="utf-8")

        self.assertIn("withTimeout(getMarketChart", page_content)
        self.assertIn("market_chart_timeout", page_content)
        self.assertIn("图表加载较慢", page_content)

    def test_symbol_page_uses_client_trading_workspace_and_not_static_svg_main_chart(self) -> None:
        page_content = (WEB_APP / "market" / "[symbol]" / "page.tsx").read_text(encoding="utf-8")
        chart_content = (WEB_COMPONENTS / "pro-kline-chart.tsx").read_text(encoding="utf-8")

        self.assertIn("MarketSymbolWorkspace", page_content)
        self.assertIn('"use client"', chart_content)
        self.assertIn("crosshair", chart_content)
        self.assertIn("priceScale", chart_content)
        self.assertIn("timeScale", chart_content)
        self.assertIn("histogram", chart_content)
        self.assertNotIn("<svg", chart_content)
        self.assertIn("EMA20", chart_content)
        self.assertIn("EMA55", chart_content)
        self.assertIn("最近图表点", chart_content)

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
        self.assertIn("最近图表点", content)
        self.assertIn("进入策略中心", content)
        self.assertIn('encodeURIComponent(symbol.toUpperCase())', content)
        self.assertIn('style={{ width: "100%"', content)
        self.assertIn("本地主图", content)
        self.assertIn("交互增强", content)
        self.assertIn("lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]", content)

    def test_trading_chart_panel_matches_signal_by_time_and_ignores_bad_prices(self) -> None:
        content = (WEB_COMPONENTS / "trading-chart-panel.tsx").read_text(encoding="utf-8")

        self.assertIn("item.time", content)
        self.assertIn("find(", content)
        self.assertIn("number | null", content)
        self.assertIn("return null", content)
        self.assertIn(".filter((price): price is number => price !== null)", content)

    def test_symbol_workspace_keeps_chart_first_and_details_below(self) -> None:
        content = (WEB_COMPONENTS / "market-symbol-workspace.tsx").read_text(encoding="utf-8")

        self.assertIn('<section className="space-y-5">', content)
        self.assertIn('lg:grid-cols-[minmax(0,1.35fr)_340px]', content)
        self.assertIn("ResearchSidecard", content)
        self.assertIn("CompactDecisionCard", content)

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
