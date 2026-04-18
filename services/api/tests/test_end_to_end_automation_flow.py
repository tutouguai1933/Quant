"""端到端自动化运维流程测试。

验证完整的自动化工作流：
- 研究训练（research_train）
- 研究推理（research_infer）
- 信号输出（signal_output）
- 策略派发（dispatch）
- 执行同步（sync）
- 统一复盘（review）
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.api.app.services.automation_service import AutomationService  # noqa: E402
from services.api.app.services.automation_workflow_service import AutomationWorkflowService  # noqa: E402
from services.api.app.services.workbench_config_service import WorkbenchConfigService  # noqa: E402
import services.api.app.services.automation_service as automation_service_module  # noqa: E402
import services.api.app.services.automation_workflow_service as automation_workflow_module  # noqa: E402


class EndToEndAutomationFlowTests(unittest.TestCase):
    """端到端自动化运维流程测试。"""

    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self._original_automation_config_service = automation_service_module.workbench_config_service
        self._original_workflow_config_service = automation_workflow_module.workbench_config_service
        isolated_config = WorkbenchConfigService(
            config_path=Path(self._temp_dir.name) / "workbench_config.json"
        )
        automation_service_module.workbench_config_service = isolated_config
        automation_workflow_module.workbench_config_service = isolated_config
        self._env_patcher = mock.patch.dict(
            os.environ,
            {"QUANT_AUTOMATION_STATE_PATH": str(Path(self._temp_dir.name) / "automation.json")},
            clear=False,
        )
        self._env_patcher.start()

    def tearDown(self) -> None:
        self._env_patcher.stop()
        automation_service_module.workbench_config_service = self._original_automation_config_service
        automation_workflow_module.workbench_config_service = self._original_workflow_config_service
        self._temp_dir.cleanup()

    def test_end_to_end_automation_flow_completes_all_stages(self) -> None:
        """验证端到端自动化流程包含所有必需阶段。"""
        scheduler = _TrackingScheduler()
        automation = AutomationService()
        dispatcher = _TrackingDispatchService()
        syncer = _TrackingSyncService()
        reviewer = _TrackingReviewService()
        workflow = AutomationWorkflowService(
            scheduler=scheduler,
            automation=automation,
            research=_ReadyResearchService(),
            dispatcher=dispatcher,
            reviewer=reviewer,
            syncer=syncer,
        )

        automation.configure_mode("auto_dry_run", actor="tester")
        result = workflow.run_cycle(source="end_to_end_test")

        # 验证流程状态
        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(result["mode"], "auto_dry_run")
        self.assertEqual(result["recommended_symbol"], "ETHUSDT")

        # 验证所有任务都被执行
        task_types = [call[0] for call in scheduler.task_calls]
        self.assertIn("research_train", task_types, "缺少研究训练步骤")
        self.assertIn("research_infer", task_types, "缺少研究推理步骤")
        self.assertIn("signal_output", task_types, "缺少信号输出步骤")
        self.assertIn("review", task_types, "缺少统一复盘步骤")

        # 验证任务执行顺序
        train_index = task_types.index("research_train")
        infer_index = task_types.index("research_infer")
        signal_index = task_types.index("signal_output")
        review_index = task_types.index("review")

        self.assertLess(train_index, infer_index, "训练应该在推理之前")
        self.assertLess(infer_index, signal_index, "推理应该在信号输出之前")
        self.assertLess(signal_index, review_index, "信号输出应该在复盘之前")

        # 验证派发被调用
        self.assertEqual(len(dispatcher.dispatch_calls), 1, "派发应该被调用一次")
        self.assertEqual(dispatcher.dispatch_calls[0]["strategy_id"], 2)
        self.assertEqual(dispatcher.dispatch_calls[0]["source"], "end_to_end_test")

        # 验证复盘被调用
        self.assertGreaterEqual(len(reviewer.report_calls), 1, "复盘应该至少被调用一次")

        # 验证结果包含所有任务摘要
        self.assertIsNotNone(result["train_task"])
        self.assertIsNotNone(result["infer_task"])
        self.assertIsNotNone(result["signal_task"])
        self.assertIsNotNone(result["dispatch"])
        self.assertIsNotNone(result["review_task"])
        self.assertIsNotNone(result["review_overview"])

        # 验证所有任务都成功
        self.assertEqual(result["train_task"]["status"], "succeeded")
        self.assertEqual(result["infer_task"]["status"], "succeeded")
        self.assertEqual(result["signal_task"]["status"], "succeeded")
        self.assertEqual(result["dispatch"]["status"], "succeeded")
        self.assertEqual(result["review_task"]["status"], "succeeded")

    def test_end_to_end_flow_stops_on_train_failure(self) -> None:
        """验证训练失败时流程正确停止。"""
        scheduler = _TrainFailedScheduler()
        automation = AutomationService()
        workflow = AutomationWorkflowService(
            scheduler=scheduler,
            automation=automation,
            research=_ReadyResearchService(),
            dispatcher=_TrackingDispatchService(),
            reviewer=_TrackingReviewService(),
            syncer=_TrackingSyncService(),
        )

        automation.configure_mode("auto_dry_run", actor="tester")
        result = workflow.run_cycle(source="end_to_end_test")

        # 验证流程在训练失败后停止
        self.assertEqual(result["status"], "attention_required")
        self.assertEqual(result["next_action"], "stop")
        self.assertEqual(result["failure_policy_action"], "manual_takeover")

        # 验证只执行了训练和复盘
        task_types = [call[0] for call in scheduler.task_calls]
        self.assertIn("research_train", task_types)
        self.assertIn("review", task_types)
        self.assertNotIn("research_infer", task_types, "推理不应该在训练失败后执行")
        self.assertNotIn("signal_output", task_types, "信号输出不应该在训练失败后执行")

        # 验证自动化进入人工接管
        state = automation.get_state()
        self.assertTrue(state["manual_takeover"])
        self.assertEqual(state["paused_reason"], "workflow_train_failed")

    def test_end_to_end_flow_stops_on_infer_failure(self) -> None:
        """验证推理失败时流程正确停止。"""
        scheduler = _InferFailedScheduler()
        automation = AutomationService()
        workflow = AutomationWorkflowService(
            scheduler=scheduler,
            automation=automation,
            research=_ReadyResearchService(),
            dispatcher=_TrackingDispatchService(),
            reviewer=_TrackingReviewService(),
            syncer=_TrackingSyncService(),
        )

        automation.configure_mode("auto_dry_run", actor="tester")
        result = workflow.run_cycle(source="end_to_end_test")

        # 验证流程在推理失败后停止
        self.assertEqual(result["status"], "attention_required")
        self.assertEqual(result["next_action"], "stop")

        # 验证执行了训练、推理和复盘
        task_types = [call[0] for call in scheduler.task_calls]
        self.assertIn("research_train", task_types)
        self.assertIn("research_infer", task_types)
        self.assertIn("review", task_types)
        self.assertNotIn("signal_output", task_types, "信号输出不应该在推理失败后执行")

    def test_end_to_end_flow_stops_on_signal_output_failure(self) -> None:
        """验证信号输出失败时流程正确停止。"""
        scheduler = _SignalFailedScheduler()
        automation = AutomationService()
        workflow = AutomationWorkflowService(
            scheduler=scheduler,
            automation=automation,
            research=_ReadyResearchService(),
            dispatcher=_TrackingDispatchService(),
            reviewer=_TrackingReviewService(),
            syncer=_TrackingSyncService(),
        )

        automation.configure_mode("auto_dry_run", actor="tester")
        result = workflow.run_cycle(source="end_to_end_test")

        # 验证流程在信号输出失败后停止
        self.assertEqual(result["status"], "attention_required")
        self.assertEqual(result["next_action"], "stop")

        # 验证执行了训练、推理、信号输出和复盘
        task_types = [call[0] for call in scheduler.task_calls]
        self.assertIn("research_train", task_types)
        self.assertIn("research_infer", task_types)
        self.assertIn("signal_output", task_types)
        self.assertIn("review", task_types)

    def test_end_to_end_flow_handles_dispatch_failure(self) -> None:
        """验证派发失败时流程正确处理。"""
        scheduler = _TrackingScheduler()
        automation = AutomationService()
        dispatcher = _DispatchFailedService()
        workflow = AutomationWorkflowService(
            scheduler=scheduler,
            automation=automation,
            research=_ReadyResearchService(),
            dispatcher=dispatcher,
            reviewer=_TrackingReviewService(),
            syncer=_TrackingSyncService(),
        )

        automation.configure_mode("auto_dry_run", actor="tester")
        result = workflow.run_cycle(source="end_to_end_test")

        # 验证流程标记为需要关注
        self.assertEqual(result["status"], "attention_required")
        self.assertEqual(result["next_action"], "review_and_decide")
        self.assertEqual(result["failure_reason"], "execution_failed")

        # 验证所有任务都被执行（包括复盘）
        task_types = [call[0] for call in scheduler.task_calls]
        self.assertIn("research_train", task_types)
        self.assertIn("research_infer", task_types)
        self.assertIn("signal_output", task_types)
        self.assertIn("review", task_types)

    def test_end_to_end_flow_scheduler_plan_matches_execution(self) -> None:
        """验证调度计划与实际执行一致。"""
        scheduler = _TrackingScheduler()
        automation = AutomationService()
        workflow = AutomationWorkflowService(
            scheduler=scheduler,
            automation=automation,
            research=_ReadyResearchService(),
            dispatcher=_TrackingDispatchService(),
            reviewer=_TrackingReviewService(),
            syncer=_TrackingSyncService(),
        )

        automation.configure_mode("auto_dry_run", actor="tester")

        # 获取调度计划
        status = workflow.get_status()
        scheduler_plan = status["scheduler_plan"]

        # 执行周期
        result = workflow.run_cycle(source="end_to_end_test")

        # 验证调度计划包含所有必需步骤
        plan_task_types = [step["task_type"] for step in scheduler_plan]
        self.assertEqual(plan_task_types[0], "research_train")
        self.assertEqual(plan_task_types[1], "research_infer")
        self.assertEqual(plan_task_types[2], "signal_output")
        self.assertEqual(plan_task_types[3], "dispatch")
        self.assertEqual(plan_task_types[4], "review")

        # 验证实际执行与计划一致（除了 dispatch 是通过服务调用而非任务）
        executed_task_types = [call[0] for call in scheduler.task_calls]
        self.assertIn("research_train", executed_task_types)
        self.assertIn("research_infer", executed_task_types)
        self.assertIn("signal_output", executed_task_types)
        self.assertIn("review", executed_task_types)

    def test_end_to_end_flow_records_cycle_summary(self) -> None:
        """验证端到端流程记录周期摘要。"""
        scheduler = _TrackingScheduler()
        automation = AutomationService()
        workflow = AutomationWorkflowService(
            scheduler=scheduler,
            automation=automation,
            research=_ReadyResearchService(),
            dispatcher=_TrackingDispatchService(),
            reviewer=_TrackingReviewService(),
            syncer=_TrackingSyncService(),
        )

        automation.configure_mode("auto_dry_run", actor="tester")
        result = workflow.run_cycle(source="end_to_end_test")

        # 验证周期被记录
        state = automation.get_state()
        self.assertIn("last_cycle", state)
        self.assertIn("daily_summary", state)

        # 验证日统计
        daily_summary = state["daily_summary"]
        self.assertEqual(daily_summary["cycle_count"], 1)
        self.assertEqual(daily_summary["status_counts"]["succeeded"], 1)


# 测试辅助类

class _TrackingScheduler:
    """跟踪任务调用的调度器。"""

    def __init__(self) -> None:
        self.task_calls: list[tuple[str, dict[str, object]]] = []

    def run_named_task(
        self,
        task_type: str,
        source: str,
        target_type: str,
        payload: dict[str, object] | None = None,
        target_id=None,
    ) -> dict[str, object]:
        self.task_calls.append((task_type, dict(payload or {})))
        return {
            "id": len(self.task_calls),
            "task_type": task_type,
            "status": "succeeded",
            "result": {"status": "completed"},
        }

    def get_health_summary(self) -> dict[str, object]:
        return {
            "latest_status_by_type": {},
            "latest_success_by_type": {},
            "latest_failure_by_type": {},
            "consecutive_failure_count_by_type": {},
        }


class _TrainFailedScheduler(_TrackingScheduler):
    """训练失败的调度器。"""

    def run_named_task(
        self,
        task_type: str,
        source: str,
        target_type: str,
        payload: dict[str, object] | None = None,
        target_id=None,
    ) -> dict[str, object]:
        self.task_calls.append((task_type, dict(payload or {})))
        if task_type == "research_train":
            return {
                "id": len(self.task_calls),
                "task_type": task_type,
                "status": "failed",
                "error_message": "训练阶段失败",
            }
        return super().run_named_task(task_type, source, target_type, payload, target_id)


class _InferFailedScheduler(_TrackingScheduler):
    """推理失败的调度器。"""

    def run_named_task(
        self,
        task_type: str,
        source: str,
        target_type: str,
        payload: dict[str, object] | None = None,
        target_id=None,
    ) -> dict[str, object]:
        self.task_calls.append((task_type, dict(payload or {})))
        if task_type == "research_infer":
            return {
                "id": len(self.task_calls),
                "task_type": task_type,
                "status": "failed",
                "error_message": "推理阶段失败",
            }
        return super().run_named_task(task_type, source, target_type, payload, target_id)


class _SignalFailedScheduler(_TrackingScheduler):
    """信号输出失败的调度器。"""

    def run_named_task(
        self,
        task_type: str,
        source: str,
        target_type: str,
        payload: dict[str, object] | None = None,
        target_id=None,
    ) -> dict[str, object]:
        self.task_calls.append((task_type, dict(payload or {})))
        if task_type == "signal_output":
            return {
                "id": len(self.task_calls),
                "task_type": task_type,
                "status": "failed",
                "error_message": "信号输出失败",
            }
        return super().run_named_task(task_type, source, target_type, payload, target_id)


class _TrackingDispatchService:
    """跟踪派发调用的服务。"""

    def __init__(self) -> None:
        self.dispatch_calls: list[dict[str, object]] = []

    def dispatch_latest_signal(self, strategy_id: int, *, source: str = "system") -> dict[str, object]:
        self.dispatch_calls.append({"strategy_id": strategy_id, "source": source})
        return {
            "status": "succeeded",
            "item": {
                "runtime": {"mode": "dry-run"},
                "action": {"symbol": "ETHUSDT", "side": "buy", "source_signal_id": 21},
                "order": {"id": "remote-1", "symbol": "ETHUSDT", "status": "filled"},
            },
            "risk_decision": {"status": "allow"},
            "risk_task": {"id": 11, "status": "succeeded"},
            "sync_task": {"id": 12, "status": "succeeded"},
            "meta": {"strategy_id": strategy_id, "source": source},
        }


class _DispatchFailedService:
    """派发失败的服务。"""

    def dispatch_latest_signal(self, strategy_id: int, *, source: str = "system") -> dict[str, object]:
        return {
            "status": "failed",
            "error_code": "execution_failed",
            "message": "自动派发失败，需要人工复核。",
            "risk_task": {"id": 13, "status": "failed"},
            "sync_task": None,
            "meta": {"strategy_id": strategy_id, "source": source},
        }


class _TrackingSyncService:
    """跟踪同步调用的服务。"""

    def __init__(self) -> None:
        self.sync_calls: list[dict[str, object]] = []

    def get_execution_health_summary(
        self,
        *,
        task_health: dict[str, object] | None = None,
        automation_state: dict[str, object] | None = None,
    ) -> dict[str, object]:
        self.sync_calls.append({"task_health": task_health, "automation_state": automation_state})
        return {
            "runtime_mode": "dry-run",
            "backend": "rest",
            "connection_status": "connected",
            "latest_sync_status": "succeeded",
            "latest_review_status": "succeeded",
            "status": "healthy",
        }


class _TrackingReviewService:
    """跟踪复盘调用的服务。"""

    def __init__(self) -> None:
        self.report_calls: list[dict[str, object]] = []

    def build_report(self, limit: int = 10) -> dict[str, object]:
        self.report_calls.append({"limit": limit})
        return {
            "overview": {
                "workflow_status": "ready",
                "recommended_symbol": "ETHUSDT",
                "recommended_action": "enter_dry_run",
                "candidate_count": 1,
                "ready_count": 1,
                "detail": "当前有 1 个候选可以进入 dry-run。",
            }
        }


class _ReadyResearchService:
    """准备就绪的研究服务。"""

    def get_research_recommendation(self) -> dict[str, object]:
        return {
            "symbol": "ETHUSDT",
            "allowed_to_dry_run": True,
            "allowed_to_live": True,
            "forced_for_validation": False,
            "strategy_template": "trend_pullback_timing",
            "next_action": "go_live",
        }

    def get_research_priority_queue(self) -> dict[str, object]:
        return {
            "items": [
                {
                    "priority_rank": 1,
                    "symbol": "ETHUSDT",
                    "strategy_template": "trend_pullback_timing",
                    "queue_status": "ready",
                    "recommended_stage": "dry_run",
                    "allowed_to_dry_run": True,
                    "allowed_to_live": True,
                    "next_action": "enter_dry_run",
                }
            ],
            "summary": {
                "active_symbol": "ETHUSDT",
                "next_symbol": "",
                "ready_count": 1,
                "blocked_count": 0,
            },
        }


if __name__ == "__main__":
    unittest.main()
