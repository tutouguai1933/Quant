from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
WEB_APP = REPO_ROOT / "apps" / "web" / "app"


class ExecutionWorkspaceFinishTests(unittest.TestCase):
    def test_strategies_page_links_back_to_research_chain(self) -> None:
        content = (WEB_APP / "strategies" / "page.tsx").read_text(encoding="utf-8")
        self.assertIn("/research", content)
        self.assertIn("/backtest", content)
        self.assertIn("/evaluation", content)
        self.assertIn("研究工作台", content)
        self.assertIn("回测工作台", content)
        self.assertIn("评估与实验中心", content)

    def test_tasks_page_links_back_to_research_chain(self) -> None:
        content = (WEB_APP / "tasks" / "page.tsx").read_text(encoding="utf-8")
        self.assertIn("/research", content)
        self.assertIn("/backtest", content)
        self.assertIn("/evaluation", content)
        self.assertIn("回到研究链", content)
        self.assertIn("去评估与实验中心", content)


if __name__ == "__main__":
    unittest.main()
