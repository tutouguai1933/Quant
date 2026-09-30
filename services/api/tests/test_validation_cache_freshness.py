"""验证复盘缓存随任务列表和条数变化失效，避免返回过期结果。"""

import unittest
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from services.api.app.services.validation_workflow_service import ValidationWorkflowService


class ValidationCacheFreshnessTests(unittest.TestCase):
    """使用本地依赖替身验证真实缓存分支，不调用交易所。"""

    def setUp(self):
        """提供稳定报告输入，隔离网络和运行状态文件。"""
        self.tasks = [{"id": 1, "status": "succeeded", "finished_at": "one"}]
        self.reader = Mock()
        self.reader.get_factory_report.return_value = {}
        scheduler = SimpleNamespace(
            list_tasks=lambda limit: self.tasks[:limit],
            get_health_summary=lambda: {},
        )
        self.service = ValidationWorkflowService(
            research_reader=self.reader, sync_reader=Mock(), scheduler=scheduler,
        )
        for method, value in {
            "_build_account_snapshot": {}, "_build_execution_comparison": {},
            "_build_steps": [], "_serialize_recent_tasks": [],
            "_resolve_workflow_status": "ready", "_resolve_next_action": "wait",
            "_build_reviews": [],
        }.items():
            patcher = patch.object(self.service, method, return_value=value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_new_task_invalidates_report_without_waiting_for_ttl(self):
        """新增任务后立即刷新报告，稳定任务列表仍复用缓存。"""
        self.service.build_report(limit=3)
        self.service.build_report(limit=3)
        self.assertEqual(self.reader.get_factory_report.call_count, 1)
        self.tasks.append({"id": 2, "status": "running", "finished_at": None})
        self.service.build_report(limit=3)
        self.assertEqual(self.reader.get_factory_report.call_count, 2)

    def test_limit_and_status_change_invalidate_report(self):
        """条数变化和任务完成也要刷新，不能只比较最新任务编号。"""
        self.service.build_report(limit=1)
        self.service.build_report(limit=3)
        self.assertEqual(self.reader.get_factory_report.call_count, 2)
        self.tasks[0]["status"] = "failed"
        self.service.build_report(limit=3)
        self.assertEqual(self.reader.get_factory_report.call_count, 3)


class ConfigCacheFreshnessTests(unittest.TestCase):
    """保存配置后下一次读取应立即使用新值。"""

    def test_saved_config_replaces_warm_cache(self):
        """连续保存不同配置段时不得把旧缓存写回覆盖刚保存的值。"""
        from services.api.app.services.workbench_config_service import WorkbenchConfigService
        with tempfile.TemporaryDirectory() as directory:
            service = WorkbenchConfigService(config_path=Path(directory) / "config.json")
            service.get_config()
            service.update_section("operations", {"review_limit": "3"})
            self.assertEqual(service.get_config()["operations"]["review_limit"], "3")
            service.update_section("automation", {"long_run_seconds": "600"})
            self.assertEqual(service.get_config()["operations"]["review_limit"], "3")
