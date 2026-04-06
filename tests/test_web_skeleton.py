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
            WEB_APP / "tasks" / "page.tsx": "getAutomationStatus",
            WEB_APP / "login" / "page.tsx": "getLoginPageModel",
        }

        for file_path, symbol in page_imports.items():
            content = file_path.read_text(encoding="utf-8")
            self.assertIn(symbol, content)
            self.assertIn("export default", content)

    def test_api_client_targets_control_plane(self) -> None:
        content = (WEB_LIB / "api.ts").read_text(encoding="utf-8")
        self.assertIn("http://127.0.0.1:9011/api/v1", content)
        self.assertIn('import("next/headers")', content)
        self.assertIn("resolveControlPlaneBaseUrl", content)
        self.assertIn("deriveLocalApiBaseUrl", content)
        self.assertIn("x-forwarded-host", content)
        self.assertIn("host", content)
        self.assertIn("currentUrl.port", content)
        self.assertIn("webPort - 1", content)
        self.assertIn("resolveControlPlaneUrl", content)
        self.assertIn("fetchJson<T>(path: string, token?: string)", content)
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
        self.assertIn("config_alignment: isPlainObject(row.config_alignment) ? row.config_alignment : {}", content)

    def test_login_page_mentions_protected_pages(self) -> None:
        content = (WEB_APP / "login" / "page.tsx").read_text(encoding="utf-8")
        self.assertIn("受保护页面", content)
        self.assertIn("model.protectedPages", content)
        self.assertIn("model.sessionMode", content)

    def test_session_known_paths_include_workbenches(self) -> None:
        content = (WEB_LIB / "session.ts").read_text(encoding="utf-8")
        self.assertIn('"/data"', content)
        self.assertIn('"/features"', content)
        self.assertIn('"/research"', content)
        self.assertIn('"/backtest"', content)
        self.assertIn('"/evaluation"', content)

    def test_unavailable_workbench_pages_disable_config_submission(self) -> None:
        features = (WEB_APP / "features" / "page.tsx").read_text(encoding="utf-8")
        research = (WEB_APP / "research" / "page.tsx").read_text(encoding="utf-8")
        evaluation = (WEB_APP / "evaluation" / "page.tsx").read_text(encoding="utf-8")

        self.assertIn("configEditable", features)
        self.assertIn("disabled={!configEditable}", features)
        self.assertIn("configEditable", research)
        self.assertIn("disabled={!configEditable}", research)
        self.assertIn("configEditable", evaluation)
        self.assertIn("disabled={!configEditable}", evaluation)


if __name__ == "__main__":
    unittest.main()
