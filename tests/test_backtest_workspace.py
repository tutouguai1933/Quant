from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
WEB_APP = REPO_ROOT / "apps" / "web" / "app"
WEB_COMPONENTS = REPO_ROOT / "apps" / "web" / "components"


class BacktestWorkspaceTests(unittest.TestCase):
    def test_backtest_workspace_page_exists(self) -> None:
        self.assertTrue((WEB_APP / "backtest" / "page.tsx").exists())

    def test_navigation_contains_backtest_workspace_entry(self) -> None:
        shell_content = (WEB_COMPONENTS / "app-shell.tsx").read_text(encoding="utf-8")
        self.assertIn('href: "/backtest"', shell_content)

    def test_backtest_workspace_page_mentions_key_sections(self) -> None:
        content = (WEB_APP / "backtest" / "page.tsx").read_text(encoding="utf-8")
        self.assertIn("回测工作台", content)
        self.assertIn("成本模型", content)
        self.assertIn("净收益", content)
        self.assertIn("成本影响", content)
        self.assertIn("最大回撤", content)
        self.assertIn("动作段统计", content)
        self.assertIn("交易明细", content)


if __name__ == "__main__":
    unittest.main()
