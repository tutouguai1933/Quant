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
        ]

        for file_path in expected_files:
            self.assertTrue(file_path.exists(), f"missing file: {file_path}")

    def test_market_page_wires_list_api_and_table(self) -> None:
        content = (WEB_APP / "market" / "page.tsx").read_text(encoding="utf-8")
        self.assertIn("listMarketSnapshots", content)
        self.assertIn("AppShell", content)
        self.assertIn("DataTable", content)
        self.assertIn("/market/", content)
        self.assertIn("白名单", content)
        self.assertIn("推荐策略", content)
        self.assertIn("趋势状态", content)
        self.assertIn("推荐下一步", content)
        self.assertIn("更适合哪套策略", content)

    def test_symbol_page_wires_chart_api_and_component(self) -> None:
        content = (WEB_APP / "market" / "[symbol]" / "page.tsx").read_text(encoding="utf-8")
        self.assertIn("getMarketChart", content)
        self.assertIn("getLatestResearch", content)
        self.assertIn("CandleChart", content)
        self.assertIn("AppShell", content)
        self.assertIn("研究解释", content)
        self.assertIn("策略解释", content)
        self.assertIn("止损参考", content)
        self.assertIn("Freqtrade 准备情况", content)

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
        self.assertIn("strategy_context", content)
        self.assertIn("freqtrade_readiness", content)
        self.assertIn("sample_size", content)
        self.assertIn("last_candle_closed", content)
        self.assertIn("warnings", content)


if __name__ == "__main__":
    unittest.main()
