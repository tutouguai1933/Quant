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
        self.assertIn("回测参数配置", content)
        self.assertIn("fee_bps", content)
        self.assertIn("准入门槛预览", content)
        self.assertIn("完整准入门槛", content)
        self.assertIn("dry_run_min_score", content)
        self.assertIn("dry_run_min_positive_rate", content)
        self.assertIn("dry_run_min_net_return_pct", content)
        self.assertIn("dry_run_min_sharpe", content)
        self.assertIn("dry_run_max_drawdown_pct", content)
        self.assertIn("dry_run_max_loss_streak", content)
        self.assertIn("dry_run_min_win_rate", content)
        self.assertIn("validation_min_sample_count", content)
        self.assertIn("live_min_score", content)
        self.assertIn("live_min_positive_rate", content)
        self.assertIn("live_min_net_return_pct", content)
        self.assertIn("live_min_win_rate", content)
        self.assertIn("WorkbenchConfigStatusCard", content)


if __name__ == "__main__":
    unittest.main()
