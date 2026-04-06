from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
WEB_APP = REPO_ROOT / "apps" / "web" / "app"
WEB_COMPONENTS = REPO_ROOT / "apps" / "web" / "components"
WEB_LIB = REPO_ROOT / "apps" / "web" / "lib"


class DataWorkspaceTests(unittest.TestCase):
    def test_data_workspace_page_and_api_exist(self) -> None:
        self.assertTrue((WEB_APP / "data" / "page.tsx").exists())
        self.assertTrue((WEB_LIB / "api.ts").exists())

    def test_navigation_contains_data_workspace_entry(self) -> None:
        shell_content = (WEB_COMPONENTS / "app-shell.tsx").read_text(encoding="utf-8")
        self.assertIn('href: "/data"', shell_content)

    def test_data_workspace_page_mentions_snapshot_and_data_states(self) -> None:
        content = (WEB_APP / "data" / "page.tsx").read_text(encoding="utf-8")
        self.assertIn("数据工作台", content)
        self.assertIn("数据快照", content)
        self.assertIn("raw / cleaned / feature-ready", content)
        self.assertIn("时间范围", content)
        self.assertIn("样本数量", content)
        self.assertIn("刷新数据认知", content)
        self.assertIn("预览状态", content)
        self.assertIn("还没有数据状态", content)
        self.assertIn("数据范围配置", content)
        self.assertIn("selected_symbols", content)


if __name__ == "__main__":
    unittest.main()
