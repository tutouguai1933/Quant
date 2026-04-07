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
from services.api.app.core.settings import Settings  # noqa: E402
from services.api.app.services.workbench_config_service import WorkbenchConfigService  # noqa: E402
import services.api.app.services.automation_service as automation_service_module  # noqa: E402
import services.api.app.services.automation_workflow_service as automation_workflow_module  # noqa: E402


class AutomationServiceTests(unittest.TestCase):
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

    def test_configure_pause_and_resume_updates_state(self) -> None:
        service = AutomationService()

        configured = service.configure_mode("auto_dry_run", actor="tester")
        paused = service.pause("manual_stop", actor="tester")
        resumed = service.resume(actor="tester")

        self.assertEqual(configured["mode"], "auto_dry_run")
        self.assertTrue(paused["paused"])
        self.assertEqual(paused["paused_reason"], "manual_stop")
        self.assertFalse(resumed["paused"])

    def test_pause_manual_takeover_kill_and_resume_sync_global_pause_and_executor(self) -> None:
        service = AutomationService()
        with mock.patch("services.api.app.services.automation_service.risk_service") as fake_risk, mock.patch(
            "services.api.app.services.automation_service.freqtrade_client"
        ) as fake_executor:
            service.pause("manual_stop", actor="tester")
            service.manual_takeover(reason="risk_guard_triggered", actor="watchdog")
            service.kill_switch(actor="tester")
            service.resume(actor="tester")

        self.assertEqual(
            fake_risk.set_global_pause.call_args_list,
            [mock.call(True), mock.call(True), mock.call(True), mock.call(False)],
        )
        self.assertEqual(
            fake_executor.control_strategy.call_args_list,
            [mock.call(1, "pause"), mock.call(1, "pause"), mock.call(1, "stop")],
        )

    def test_pause_uses_all_executor_strategy_ids_when_available(self) -> None:
        service = AutomationService()
        with mock.patch("services.api.app.services.automation_service.risk_service") as fake_risk, mock.patch(
            "services.api.app.services.automation_service.freqtrade_client"
        ) as fake_executor:
            fake_executor.get_snapshot.return_value = mock.Mock(
                strategies=[{"id": 2}, {"id": "3"}, {"id": 2}, {"id": "bad"}]
            )
            service.pause("manual_stop", actor="tester")

        fake_risk.set_global_pause.assert_called_once_with(True)
        self.assertEqual(fake_executor.control_strategy.call_args_list, [mock.call(2, "pause"), mock.call(3, "pause")])

    def test_auto_dry_run_cycle_dispatches_ready_candidate_and_arms_symbol(self) -> None:
        scheduler = _FakeScheduler()
        automation = AutomationService()
        dispatcher = _PassingDispatchService(runtime_mode="dry-run")
        workflow = AutomationWorkflowService(
            scheduler=scheduler,
            automation=automation,
            research=_ReadyResearchService(),
            dispatcher=dispatcher,
            reviewer=_FakeReviewer(),
            syncer=_FakeSyncService(runtime_mode="dry-run"),
        )

        automation.configure_mode("auto_dry_run", actor="tester")
        result = workflow.run_cycle(source="tester")

        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(result["recommended_symbol"], "ETHUSDT")
        self.assertEqual(result["recommended_strategy_id"], 2)
        self.assertEqual(result["next_action"], "continue_dry_run")
        self.assertEqual(result["message"], "候选已通过自动 dry-run，等待下一轮 live 验证。")
        self.assertEqual(automation.get_state()["armed_symbol"], "ETHUSDT")
        self.assertEqual(dispatcher.calls[0]["strategy_id"], 2)
        self.assertGreaterEqual(len(scheduler.named_calls), 4)

    def test_auto_live_cycle_waits_for_previous_dry_run(self) -> None:
        scheduler = _FakeScheduler()
        automation = AutomationService()
        workflow = AutomationWorkflowService(
            scheduler=scheduler,
            automation=automation,
            research=_ReadyResearchService(),
            dispatcher=_PassingDispatchService(runtime_mode="live"),
            reviewer=_FakeReviewer(),
            syncer=_FakeSyncService(runtime_mode="live"),
        )

        with mock.patch.object(Settings, "from_env", return_value=_FakeSettings("live")):
            automation.configure_mode("auto_live", actor="tester")
            result = workflow.run_cycle(source="tester")

        self.assertEqual(result["status"], "waiting")
        self.assertEqual(result["next_action"], "continue_dry_run")
        self.assertEqual(result["message"], "当前候选还没有完成上一轮 dry-run 验证")
        self.assertEqual(automation.get_state()["armed_symbol"], "")

    def test_auto_live_cycle_dispatches_after_symbol_is_armed(self) -> None:
        scheduler = _FakeScheduler()
        automation = AutomationService()
        dispatcher = _PassingDispatchService(runtime_mode="live")
        workflow = AutomationWorkflowService(
            scheduler=scheduler,
            automation=automation,
            research=_ReadyResearchService(),
            dispatcher=dispatcher,
            reviewer=_FakeReviewer(),
            syncer=_FakeSyncService(runtime_mode="live"),
        )

        with mock.patch.object(Settings, "from_env", return_value=_FakeSettings("live")):
            automation.configure_mode("auto_live", actor="tester")
            automation.arm_symbol("ETHUSDT")
            result = workflow.run_cycle(source="tester")

        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(result["next_action"], "retain_small_live")
        self.assertEqual(result["message"], "自动小额 live 已完成，本轮结果可进入统一复盘。")
        self.assertEqual(automation.get_state()["armed_symbol"], "")
        self.assertEqual(dispatcher.calls[0]["strategy_id"], 2)

    def test_manual_mode_cycle_reports_manual_review_message(self) -> None:
        scheduler = _FakeScheduler()
        automation = AutomationService()
        workflow = AutomationWorkflowService(
            scheduler=scheduler,
            automation=automation,
            research=_ReadyResearchService(),
            dispatcher=_PassingDispatchService(runtime_mode="dry-run"),
            reviewer=_FakeReviewer(),
            syncer=_FakeSyncService(runtime_mode="dry-run"),
        )

        automation.configure_mode("manual", actor="tester")
        result = workflow.run_cycle(source="tester")

        self.assertEqual(result["status"], "waiting")
        self.assertEqual(result["next_action"], "manual_review")
        self.assertEqual(result["message"], "当前处于手动模式，请先人工确认再继续。")

    def test_state_is_restored_from_local_state_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, mock.patch.dict(
            os.environ,
            {"QUANT_AUTOMATION_STATE_PATH": str(Path(temp_dir) / "automation.json")},
            clear=False,
        ):
            first = AutomationService()
            first.configure_mode("auto_dry_run", actor="tester")
            first.arm_symbol("ETHUSDT")
            first.pause("manual_stop", actor="tester")

            second = AutomationService()

        state = second.get_state()
        self.assertEqual(state["mode"], "auto_dry_run")
        self.assertEqual(state["armed_symbol"], "ETHUSDT")
        self.assertTrue(state["paused"])

    def test_dry_run_only_and_kill_switch_update_state(self) -> None:
        service = AutomationService()

        dry_run_only = service.enable_dry_run_only(actor="tester")
        kill_switch = service.kill_switch(actor="tester")

        self.assertEqual(dry_run_only["mode"], "auto_dry_run")
        self.assertFalse(dry_run_only["paused"])
        self.assertTrue(kill_switch["paused"])
        self.assertEqual(kill_switch["paused_reason"], "kill_switch")
        self.assertTrue(kill_switch["manual_takeover"])

    def test_daily_summary_accumulates_cycle_and_alert_counts(self) -> None:
        service = AutomationService()

        service.record_cycle({"status": "succeeded", "next_action": "continue_dry_run"})
        service.record_cycle({"status": "attention_required", "next_action": "stop"})
        service.record_alert(level="error", code="train_failed", message="自动训练失败", source="tester")

        status = service.get_status(task_health={})

        self.assertIn("daily_summary", status)
        self.assertEqual(status["daily_summary"]["cycle_count"], 2)
        self.assertEqual(status["daily_summary"]["status_counts"]["succeeded"], 1)
        self.assertEqual(status["daily_summary"]["status_counts"]["attention_required"], 1)
        self.assertEqual(status["daily_summary"]["alert_count"], 1)

    def test_status_exposes_scheduler_plan_and_failure_policy(self) -> None:
        scheduler = _FakeScheduler()
        automation = AutomationService()
        workflow = AutomationWorkflowService(
            scheduler=scheduler,
            automation=automation,
            research=_ReadyResearchService(),
            dispatcher=_PassingDispatchService(runtime_mode="dry-run"),
            reviewer=_FakeReviewer(),
            syncer=_FakeSyncService(runtime_mode="dry-run"),
        )

        status = workflow.get_status()

        self.assertIn("scheduler_plan", status)
        self.assertEqual(status["scheduler_plan"][0]["task_type"], "research_train")
        self.assertIn("failure_policy", status)
        self.assertEqual(status["failure_policy"]["research_train"], "manual_takeover")
        self.assertIn("active_blockers", status["health"])
        self.assertIn("operator_actions", status["health"])
        self.assertIn("takeover_summary", status["health"])
        self.assertIn("alert_summary", status["health"])
        self.assertIn("active_blockers", status)
        self.assertIn("operator_actions", status)
        self.assertIn("takeover_summary", status)
        self.assertIn("alert_summary", status)
        self.assertIn("operations", status)
        self.assertEqual(status["operations"]["pause_after_consecutive_failures"], 2)
        self.assertEqual(status["operations"]["review_limit"], 10)

    def test_health_summary_exposes_blockers_actions_and_alert_summary(self) -> None:
        service = AutomationService()
        service.configure_mode("auto_live", actor="tester")
        service.arm_symbol("ETHUSDT")
        service.pause("manual_stop", actor="tester")
        service.record_alert(level="warning", code="sync_delayed", message="同步延迟", source="watchdog")
        service.record_alert(level="error", code="executor_offline", message="执行器离线", source="watchdog")

        health = service.build_health_summary(
            task_health={
                "latest_status_by_type": {
                    "research_train": "succeeded",
                    "research_infer": "succeeded",
                    "sync": "failed",
                    "review": "waiting",
                }
            }
        )

        self.assertEqual(health["takeover_summary"]["state_label"], "人工接管中")
        self.assertEqual(health["alert_summary"]["latest_code"], "executor_offline")
        self.assertEqual(health["alert_summary"]["error_count"], 1)
        self.assertEqual(health["alert_summary"]["warning_count"], 2)
        self.assertEqual(health["active_blockers"][0]["code"], "paused")
        self.assertIn("恢复自动化", [item["label"] for item in health["operator_actions"]])
        self.assertIn("查看执行器", [item["label"] for item in health["operator_actions"]])

    def test_health_summary_tracks_failure_streak_and_escalation_level(self) -> None:
        service = AutomationService()
        service.record_cycle({"status": "attention_required", "next_action": "manual_takeover"})
        service.record_cycle({"status": "attention_required", "next_action": "manual_takeover"})
        service.record_alert(level="error", code="sync_failed", message="同步失败", source="watchdog")

        health = service.build_health_summary(
            task_health={"latest_status_by_type": {"sync": "failed", "review": "waiting"}}
        )

        self.assertEqual(health["run_health"]["consecutive_failure_count"], 2)
        self.assertEqual(health["run_health"]["stale_sync_state"], "stale")
        self.assertEqual(health["run_health"]["escalation_level"], "critical")

    def test_manual_takeover_entry_switches_to_manual_with_reason(self) -> None:
        service = AutomationService()
        service.configure_mode("auto_live", actor="tester")
        with mock.patch("services.api.app.services.automation_service.risk_service") as fake_risk, mock.patch(
            "services.api.app.services.automation_service.freqtrade_client"
        ) as fake_executor:
            result = service.manual_takeover(reason="risk_guard_triggered", actor="watchdog")

        self.assertEqual(result["mode"], "manual")
        self.assertTrue(result["paused"])
        self.assertTrue(result["manual_takeover"])
        self.assertEqual(result["paused_reason"], "risk_guard_triggered")
        self.assertEqual(result["actor"], "watchdog")
        fake_risk.set_global_pause.assert_called_once_with(True)
        fake_executor.control_strategy.assert_called_once_with(1, "pause")

    def test_failure_policy_stop_marks_attention_required(self) -> None:
        scheduler = _TrainFailedScheduler()
        automation = AutomationService()
        workflow = AutomationWorkflowService(
            scheduler=scheduler,
            automation=automation,
            research=_ReadyResearchService(),
            dispatcher=_PassingDispatchService(runtime_mode="dry-run"),
            reviewer=_FakeReviewer(),
            syncer=_FakeSyncService(runtime_mode="dry-run"),
        )

        automation.configure_mode("auto_dry_run", actor="tester")
        result = workflow.run_cycle(source="watchdog")
        state = automation.get_state()

        self.assertEqual(result["status"], "attention_required")
        self.assertEqual(result["next_action"], "stop")
        self.assertEqual(result["failure_policy_action"], "manual_takeover")
        self.assertTrue(state["manual_takeover"])
        self.assertTrue(state["paused"])
        self.assertEqual(state["paused_reason"], "workflow_train_failed")

    def test_failure_policy_review_and_decide_marks_attention_required(self) -> None:
        scheduler = _FakeScheduler()
        automation = AutomationService()
        workflow = AutomationWorkflowService(
            scheduler=scheduler,
            automation=automation,
            research=_ReadyResearchService(),
            dispatcher=_DispatchFailedService(error_code="execution_failed"),
            reviewer=_FakeReviewer(),
            syncer=_FakeSyncService(runtime_mode="dry-run"),
        )

        automation.configure_mode("auto_dry_run", actor="tester")
        result = workflow.run_cycle(source="watchdog")
        state = automation.get_state()

        self.assertEqual(result["status"], "attention_required")
        self.assertEqual(result["next_action"], "review_and_decide")
        self.assertEqual(result["failure_reason"], "execution_failed")
        self.assertEqual(result["failure_policy_action"], "review_and_decide")
        self.assertTrue(state["manual_takeover"])
        self.assertTrue(state["paused"])
        self.assertEqual(state["paused_reason"], "dispatch_execution_failed")


class _ReadyResearchService:
    def get_research_recommendation(self) -> dict[str, object]:
        return {
            "symbol": "ETHUSDT",
            "allowed_to_dry_run": True,
            "forced_for_validation": False,
            "strategy_template": "trend_pullback_timing",
            "next_action": "enter_dry_run",
        }


class _PassingDispatchService:
    def __init__(self, *, runtime_mode: str) -> None:
        self._runtime_mode = runtime_mode
        self.calls: list[dict[str, object]] = []

    def dispatch_latest_signal(self, strategy_id: int, *, source: str = "system") -> dict[str, object]:
        self.calls.append({"strategy_id": strategy_id, "source": source})
        return {
            "status": "succeeded",
            "item": {
                "runtime": {"mode": self._runtime_mode},
                "action": {"symbol": "ETHUSDT", "side": "buy", "source_signal_id": 21},
                "order": {"id": "remote-1", "symbol": "ETHUSDT", "status": "filled"},
            },
            "risk_decision": {"status": "allow"},
            "risk_task": {"id": 11, "status": "succeeded"},
            "sync_task": {"id": 12, "status": "succeeded"},
            "meta": {"strategy_id": strategy_id, "source": source},
        }


class _DispatchFailedService:
    def __init__(self, *, error_code: str) -> None:
        self._error_code = error_code
        self.calls: list[dict[str, object]] = []

    def dispatch_latest_signal(self, strategy_id: int, *, source: str = "system") -> dict[str, object]:
        self.calls.append({"strategy_id": strategy_id, "source": source})
        return {
            "status": "failed",
            "error_code": self._error_code,
            "message": "自动派发失败，需要人工复核。",
            "risk_task": {"id": 13, "status": "failed"},
            "sync_task": None,
            "meta": {"strategy_id": strategy_id, "source": source},
        }


class _FakeScheduler:
    def __init__(self) -> None:
        self.named_calls: list[tuple[str, dict[str, object]]] = []

    def run_named_task(
        self,
        task_type: str,
        source: str,
        target_type: str,
        payload: dict[str, object] | None = None,
        target_id=None,
    ) -> dict[str, object]:
        self.named_calls.append((task_type, dict(payload or {})))
        return {
            "id": len(self.named_calls),
            "task_type": task_type,
            "status": "succeeded",
            "result": {"status": "completed"},
        }

    def get_health_summary(self) -> dict[str, object]:
        return {"latest_status_by_type": {}, "latest_success_by_type": {}, "latest_failure_by_type": {}}


class _TrainFailedScheduler(_FakeScheduler):
    def run_named_task(
        self,
        task_type: str,
        source: str,
        target_type: str,
        payload: dict[str, object] | None = None,
        target_id=None,
    ) -> dict[str, object]:
        self.named_calls.append((task_type, dict(payload or {})))
        if task_type == "research_train":
            return {
                "id": len(self.named_calls),
                "task_type": task_type,
                "status": "failed",
                "error_message": "训练阶段失败",
            }
        return {
            "id": len(self.named_calls),
            "task_type": task_type,
            "status": "succeeded",
            "result": {"status": "completed"},
        }


class _FakeReviewer:
    def build_report(self, limit: int = 10) -> dict[str, object]:
        return {
            "overview": {
                "recommended_symbol": "ETHUSDT",
                "recommended_action": "enter_dry_run",
                "candidate_count": 1,
                "ready_count": 1,
            }
        }


class _FakeSyncService:
    def __init__(self, *, runtime_mode: str) -> None:
        self._runtime_mode = runtime_mode

    def get_execution_health_summary(
        self,
        *,
        task_health: dict[str, object] | None = None,
        automation_state: dict[str, object] | None = None,
    ) -> dict[str, object]:
        return {
            "runtime_mode": self._runtime_mode,
            "backend": "rest",
            "connection_status": "connected",
            "latest_sync_status": "succeeded",
            "latest_review_status": "succeeded",
        }


class _FakeSettings:
    def __init__(self, runtime_mode: str) -> None:
        self.runtime_mode = runtime_mode
        self.allow_live_execution = runtime_mode == "live"


if __name__ == "__main__":
    unittest.main()
