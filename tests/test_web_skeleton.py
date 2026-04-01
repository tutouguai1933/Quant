from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
WEB_APP = REPO_ROOT / "apps" / "web" / "app"
WEB_LIB = REPO_ROOT / "apps" / "web" / "lib"


class WebSkeletonTests(unittest.TestCase):
    def test_task4_files_exist(self) -> None:
        expected_files = [
            WEB_APP / "page.tsx",
            WEB_APP / "signals" / "page.tsx",
            WEB_APP / "strategies" / "page.tsx",
            WEB_APP / "balances" / "page.tsx",
            WEB_APP / "positions" / "page.tsx",
            WEB_APP / "orders" / "page.tsx",
            WEB_APP / "risk" / "page.tsx",
            WEB_APP / "tasks" / "page.tsx",
            WEB_APP / "login" / "page.tsx",
            WEB_LIB / "api.ts",
        ]

        for file_path in expected_files:
            self.assertTrue(file_path.exists(), f"missing file: {file_path}")

    def test_dashboard_page_stays_overview_only(self) -> None:
        content = (WEB_APP / "page.tsx").read_text(encoding="utf-8")
        self.assertIn("系统总览", content)
        self.assertIn("crypto", content)
        self.assertIn("Freqtrade", content)

    def test_subpages_import_api_models(self) -> None:
        page_imports = {
            WEB_APP / "signals" / "page.tsx": "listSignals",
            WEB_APP / "strategies" / "page.tsx": "getStrategyWorkspace",
            WEB_APP / "balances" / "page.tsx": "listBalances",
            WEB_APP / "positions" / "page.tsx": "listPositions",
            WEB_APP / "orders" / "page.tsx": "listOrders",
            WEB_APP / "risk" / "page.tsx": "listRiskEvents",
            WEB_APP / "tasks" / "page.tsx": "listTasks",
            WEB_APP / "login" / "page.tsx": "getLoginPageModel",
        }

        for file_path, symbol in page_imports.items():
            content = file_path.read_text(encoding="utf-8")
            self.assertIn(symbol, content)
            self.assertIn("export default", content)

    def test_api_client_targets_control_plane(self) -> None:
        content = (WEB_LIB / "api.ts").read_text(encoding="utf-8")
        self.assertIn("http://127.0.0.1:8000/api/v1", content)
        self.assertIn("fetch(buildApiUrl(path)", content)
        self.assertIn("ApiEnvelope", content)
        self.assertIn("cache: \"no-store\"", content)
        self.assertIn("export async function listSignals()", content)
        self.assertIn("Authorization", content)
        self.assertIn("/auth/login", content)
        self.assertIn('"/strategies"', content)
        self.assertIn('"/balances"', content)
        self.assertIn('"/tasks"', content)
        self.assertIn('"/risk"', content)
        self.assertIn("executor_runtime", content)
        self.assertIn("truthSource", content)

    def test_login_page_mentions_protected_pages(self) -> None:
        content = (WEB_APP / "login" / "page.tsx").read_text(encoding="utf-8")
        self.assertIn("受保护页面", content)
        self.assertIn("model.protectedPages", content)
        self.assertIn("model.sessionMode", content)


if __name__ == "__main__":
    unittest.main()
