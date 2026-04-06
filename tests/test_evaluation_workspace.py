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
        self.assertIn("研究与执行对齐", content)
        self.assertIn("实验对照", content)
        self.assertIn("门控分解", content)
        self.assertIn("实验一致性", content)
        self.assertIn("最近两轮对比", content)
        self.assertIn("参数与结果一起看", content)
        self.assertIn("当前结果与配置对齐", content)
        self.assertIn("工作台暂时不可用", content)
        self.assertIn("进入 dry-run", content)
        self.assertIn("准入门槛配置", content)
        self.assertIn("研究结果 vs 执行结果", content)
        self.assertIn("对齐解释", content)
        self.assertIn("最近执行摘要", content)
        self.assertIn("执行对齐明细", content)
        self.assertIn("最近订单标的", content)
        self.assertIn("最近持仓标的", content)
        self.assertIn("live_min_score", content)
        self.assertIn("dry_run_min_win_rate", content)
        self.assertIn("dry_run_max_turnover", content)
        self.assertIn("dry_run_min_sample_count", content)
        self.assertIn("live_min_win_rate", content)
        self.assertIn("live_max_turnover", content)
        self.assertIn("live_min_sample_count", content)
        self.assertIn("淘汰原因说明", content)
        self.assertIn("研究结果 vs 执行结果", content)
        self.assertIn("对齐结论", content)
        self.assertIn("执行现状", content)
        self.assertIn("差异说明", content)
        self.assertIn("建议动作", content)


if __name__ == "__main__":
    unittest.main()
