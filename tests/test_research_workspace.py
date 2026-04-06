from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
WEB_APP = REPO_ROOT / "apps" / "web" / "app"
WEB_COMPONENTS = REPO_ROOT / "apps" / "web" / "components"


class ResearchWorkspaceTests(unittest.TestCase):
    def test_research_workspace_page_exists(self) -> None:
        self.assertTrue((WEB_APP / "research" / "page.tsx").exists())

    def test_navigation_contains_research_workspace_entry(self) -> None:
        shell_content = (WEB_COMPONENTS / "app-shell.tsx").read_text(encoding="utf-8")
        self.assertIn('href: "/research"', shell_content)

    def test_research_workspace_page_mentions_key_sections(self) -> None:
        content = (WEB_APP / "research" / "page.tsx").read_text(encoding="utf-8")
        runtime_content = (WEB_COMPONENTS / "research-runtime-panel.tsx").read_text(encoding="utf-8")
        self.assertIn("策略研究工作台", content)
        self.assertIn("研究模板", content)
        self.assertIn("标签定义", content)
        self.assertIn("训练窗口", content)
        self.assertIn("当前模型", content)
        self.assertIn("实验参数", content)
        self.assertIn("研究训练", content)
        self.assertIn("研究推理", content)
        self.assertIn("研究参数配置", content)
        self.assertIn("label_mode", content)
        self.assertIn("label_target_pct", content)
        self.assertIn("当前结果与配置对齐", content)
        self.assertIn("工作台暂时不可用", content)
        self.assertIn("ResearchRuntimePanel", content)
        self.assertIn("研究运行状态", runtime_content)
        self.assertIn("预计时长", runtime_content)
        self.assertIn("完成后去哪里看", runtime_content)


if __name__ == "__main__":
    unittest.main()
