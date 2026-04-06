from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
WEB_APP = REPO_ROOT / "apps" / "web" / "app"
WEB_COMPONENTS = REPO_ROOT / "apps" / "web" / "components"


class EvaluationWorkspaceTests(unittest.TestCase):
    def test_evaluation_workspace_page_exists(self) -> None:
        self.assertTrue((WEB_APP / "evaluation" / "page.tsx").exists())

    def test_navigation_contains_evaluation_workspace_entry(self) -> None:
        shell_content = (WEB_COMPONENTS / "app-shell.tsx").read_text(encoding="utf-8")
        self.assertIn('href: "/evaluation"', shell_content)

    def test_evaluation_workspace_page_mentions_key_sections(self) -> None:
        content = (WEB_APP / "evaluation" / "page.tsx").read_text(encoding="utf-8")
        self.assertIn("评估与实验中心", content)
        self.assertIn("实验排行榜", content)
        self.assertIn("推荐原因", content)
        self.assertIn("淘汰原因", content)
        self.assertIn("样本外稳定性", content)
        self.assertIn("进入 dry-run", content)


if __name__ == "__main__":
    unittest.main()
