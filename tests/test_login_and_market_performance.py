from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
WEB_APP = REPO_ROOT / "apps" / "web" / "app"
WEB_COMPONENTS = REPO_ROOT / "apps" / "web" / "components"


class LoginAndMarketPerformanceTests(unittest.TestCase):
    def test_login_submit_sets_long_lived_cookie(self) -> None:
        content = (WEB_APP / "login" / "submit" / "route.ts").read_text(encoding="utf-8")
        self.assertIn("maxAge", content)
        self.assertIn("60 * 60 * 24 * 7", content)
        self.assertIn("303", content)

    def test_market_page_switches_to_client_loading_shell(self) -> None:
        content = (WEB_APP / "market" / "page.tsx").read_text(encoding="utf-8")
        self.assertIn("MarketSnapshotWorkspace", content)
        self.assertIn("Suspense", content)
        self.assertNotIn("listMarketSnapshots()", content)

    def test_market_snapshot_workspace_contains_cache_and_loading_shell(self) -> None:
        content = (WEB_COMPONENTS / "market-snapshot-workspace.tsx").read_text(encoding="utf-8")
        self.assertIn('"use client"', content)
        self.assertIn("memoryCache", content)
        self.assertIn("30_000", content)
        self.assertIn("loading", content)
        self.assertIn("listMarketSnapshots", content)


if __name__ == "__main__":
    unittest.main()
