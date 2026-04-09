from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
WEB_APP = REPO_ROOT / "apps" / "web" / "app"
WEB_COMPONENTS = REPO_ROOT / "apps" / "web" / "components"
CONFIG_SERVICE = REPO_ROOT / "services" / "api" / "app" / "services" / "workbench_config_service.py"


class BacktestWorkspaceTests(unittest.TestCase):
    def test_backtest_workspace_page_exists(self) -> None:
        self.assertTrue((WEB_APP / "backtest" / "page.tsx").exists())

    def test_navigation_contains_backtest_workspace_entry(self) -> None:
        shell_content = (WEB_COMPONENTS / "app-shell.tsx").read_text(encoding="utf-8")
        self.assertIn('href: "/backtest"', shell_content)

    def test_backtest_workspace_page_mentions_key_sections(self) -> None:
        content = (WEB_APP / "backtest" / "page.tsx").read_text(encoding="utf-8")
        config_content = CONFIG_SERVICE.read_text(encoding="utf-8")
        self.assertIn("回测工作台", content)
        self.assertIn("成本模型", content)
        self.assertIn("净收益", content)
        self.assertIn("成本影响", content)
        self.assertIn("最大回撤", content)
        self.assertIn("动作段统计", content)
        self.assertIn("交易明细", content)
        self.assertIn("当前回测选择", content)
        self.assertIn("当前组合", content)
        self.assertIn("当前组合说明", content)
        self.assertIn("成本与过滤拆解", content)
        self.assertIn("拆解项", content)
        self.assertIn("当前口径", content)
        self.assertIn("会影响什么", content)
        self.assertIn("过滤参数目录", content)
        self.assertIn("当前作用", content)
        self.assertIn("回测参数配置", content)
        self.assertIn("回测预设", content)
        self.assertIn("realistic_standard", config_content)
        self.assertIn("cost_stress", config_content)
        self.assertIn("signal_baseline", config_content)
        self.assertIn("fee_bps", content)
        self.assertIn("成本与过滤拆解", content)
        self.assertIn("dry-run 门槛", content)
        self.assertIn("验证与 live 门槛", content)
        self.assertIn("规则门与一致性门", content)
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
