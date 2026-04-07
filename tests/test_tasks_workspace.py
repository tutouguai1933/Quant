from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
WEB_APP = REPO_ROOT / "apps" / "web" / "app"


class TasksWorkspaceTests(unittest.TestCase):
    def test_tasks_page_mentions_long_run_configuration(self) -> None:
        content = (WEB_APP / "tasks" / "page.tsx").read_text(encoding="utf-8")
        self.assertIn("长期运行配置", content)
        self.assertIn("pause_after_consecutive_failures", content)
        self.assertIn("stale_sync_failure_threshold", content)
        self.assertIn("auto_pause_on_error", content)
        self.assertIn("review_limit", content)
        self.assertIn("comparison_run_limit", content)
        self.assertIn("长期运行参数", content)
        self.assertIn("失败后自动暂停", content)
        self.assertIn("告警强度", content)
        self.assertIn("人工接管原因", content)
        self.assertIn("恢复前先做什么", content)
        self.assertIn("focus_cards", content)
        self.assertIn("风险等级摘要", content)
        self.assertIn("恢复清单", content)
        self.assertIn("severitySummary", content)
        self.assertIn("resumeChecklist", content)
        self.assertIn("执行安全门", content)
        self.assertIn("当前放行口径", content)
        self.assertIn("live_allowed_symbols", content)
        self.assertIn("live_max_stake_usdt", content)
        self.assertIn("live_max_open_trades", content)
        self.assertIn("同步失败细节", content)
        self.assertIn("人工接管时间线", content)
        self.assertIn("最近失败时间", content)
        self.assertIn("最近同步失败", content)
        self.assertIn("已接管多久", content)
        self.assertIn("cycle_cooldown_minutes", content)
        self.assertIn("max_daily_cycle_count", content)
        self.assertIn("自动化冷却时间", content)
        self.assertIn("每日最大轮次", content)
        self.assertIn("自动化运行参数", content)
        self.assertIn("long_run_seconds", content)
        self.assertIn("alert_cleanup_minutes", content)
        self.assertIn("长时间接管阈值", content)
        self.assertIn("活跃告警窗口", content)
        self.assertIn("长期运行窗口", content)
        self.assertIn("这一轮之后还能不能继续自动跑", content)
        self.assertIn("今日轮次", content)
        self.assertIn("冷却剩余", content)
        self.assertIn("最近告警历史", content)
        self.assertIn("活跃告警", content)
        self.assertIn("最近复盘记录", content)
        self.assertIn("这里最多显示最近", content)


if __name__ == "__main__":
    unittest.main()
