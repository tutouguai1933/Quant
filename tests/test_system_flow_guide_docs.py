from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class SystemFlowGuideDocsTests(unittest.TestCase):
    def test_readme_links_system_flow_guide(self) -> None:
        content = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("docs/system-flow-guide.md", content)
        self.assertIn("系统导览", content)

    def test_system_flow_guide_covers_research_execution_and_automation(self) -> None:
        content = (REPO_ROOT / "docs" / "system-flow-guide.md").read_text(encoding="utf-8")

        self.assertIn("运行 Qlib 信号流水线", content)
        self.assertIn("dry-run", content)
        self.assertIn("live", content)
        self.assertIn("自动化", content)
        self.assertIn("复盘", content)
        self.assertIn("mermaid", content)


if __name__ == "__main__":
    unittest.main()
