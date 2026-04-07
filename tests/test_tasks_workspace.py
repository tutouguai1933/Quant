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
        self.assertIn("长期运行参数", content)
        self.assertIn("失败后自动暂停", content)


if __name__ == "__main__":
    unittest.main()
