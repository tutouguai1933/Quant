from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.api.app.services.openclaw_action_service import OpenclawActionService  # noqa: E402
from services.api.app.services.openclaw_patrol_service import OpenclawPatrolService  # noqa: E402
from services.api.app.services.openclaw_snapshot_service import OpenclawSnapshotService  # noqa: E402


class OpenclawServiceTests(unittest.TestCase):
    """OpenClaw 相关服务测试。"""

    def test_snapshot_includes_automation_state_and_execution_health(self) -> None:
        automation = mock.Mock()
        automation.get_state.return_value = {
            "mode": "auto_dry_run",
            "paused": False,
            "manual_takeover": False,
            "execution_health": {
                "connection_status": "error",
                "status": "degraded",
            },
        }
        workflow_status = {
            "runtime_guard": {
                "ready_for_cycle": False,
                "blocked_reason": "executor_error",
            },
            "execution_health": {
                "connection_status": "error",
                "status": "degraded",
                "latest_sync_status": "failed",
            },
        }
        health_service = mock.Mock()
        health_service.get_all_health.return_value = {"services": {}}
        restart_history_service = mock.Mock()
        restart_history_service.get_all_history.return_value = {}
        audit_service = mock.Mock()
        audit_service.get_recent_records.return_value = []

        with mock.patch(
            "services.api.app.services.openclaw_snapshot_service.automation_workflow_service.get_status",
            return_value=workflow_status,
        ):
            snapshot_service = OpenclawSnapshotService(
                automation=automation,
                strategies=mock.Mock(),
                health_service=health_service,
                restart_history_service=restart_history_service,
                audit_service=audit_service,
            )
            snapshot = snapshot_service.get_snapshot()

        self.assertIn("automation_state", snapshot)
        self.assertIn("execution_health", snapshot)
        self.assertEqual(snapshot["automation_state"]["mode"], "auto_dry_run")
        self.assertEqual(snapshot["execution_health"]["connection_status"], "error")

    def test_snapshot_keeps_state_execution_health_when_workflow_status_unavailable(self) -> None:
        automation = mock.Mock()
        automation.get_state.return_value = {
            "mode": "auto_dry_run",
            "paused": False,
            "manual_takeover": False,
            "runtime_guard": {"blocked_reason": "executor_error"},
            "execution_health": {
                "connection_status": "error",
                "status": "degraded",
            },
        }
        health_service = mock.Mock()
        health_service.get_all_health.return_value = {"services": {}}
        restart_history_service = mock.Mock()
        restart_history_service.get_all_history.return_value = {}
        audit_service = mock.Mock()
        audit_service.get_recent_records.return_value = []

        with mock.patch(
            "services.api.app.services.openclaw_snapshot_service.automation_workflow_service.get_status",
            side_effect=RuntimeError("workflow unavailable"),
        ):
            snapshot_service = OpenclawSnapshotService(
                automation=automation,
                strategies=mock.Mock(),
                health_service=health_service,
                restart_history_service=restart_history_service,
                audit_service=audit_service,
            )
            snapshot = snapshot_service.get_snapshot()

        self.assertEqual(snapshot["execution_health"]["connection_status"], "error")
        self.assertEqual(snapshot["execution_health"]["status"], "degraded")

    def test_automation_dry_run_only_calls_enable_dry_run_only(self) -> None:
        automation = mock.Mock()
        snapshot_service = mock.Mock()
        snapshot_service.get_snapshot.return_value = {"snapshot_id": "snapshot-1"}
        workflow_service = mock.Mock()
        action_service = OpenclawActionService(
            automation=automation,
            snapshot_service=snapshot_service,
            workflow_service=workflow_service,
            audit_service=mock.Mock(),
            restart_history_service=mock.Mock(),
            system_executor=mock.Mock(),
            health_service=mock.Mock(),
        )

        result = action_service.execute_action("automation_dry_run_only")

        self.assertTrue(result["success"])
        automation.enable_dry_run_only.assert_called_once_with(actor="openclaw")
        automation.set_mode.assert_not_called()

    def test_cycle_check_queues_automation_run_without_waiting_for_cycle_completion(self) -> None:
        snapshot_service = mock.Mock()
        snapshot_service.get_snapshot.return_value = {
            "snapshot_id": "snapshot-1",
            "services": {"api": {"status": "healthy"}},
            "runtime_guard": {},
            "suggested_action": {"action": "run_cycle", "auto_run_allowed": True},
        }
        action_service = mock.Mock()

        def slow_action(action: str) -> dict[str, object]:
            time.sleep(0.2)
            return {"success": True, "action": action}

        action_service.execute_action.side_effect = slow_action
        health_service = mock.Mock()

        patrol_service = OpenclawPatrolService(
            snapshot_service=snapshot_service,
            action_service=action_service,
            health_service=health_service,
        )
        patrol_service._check_vpn_health = mock.Mock(return_value={"action_taken": False})  # type: ignore[method-assign]
        patrol_service._check_service_health = mock.Mock(return_value={"action_taken": False, "patrol_status": "normal"})  # type: ignore[method-assign]
        patrol_service._can_execute_action = mock.Mock(return_value=(True, ""))  # type: ignore[method-assign]

        started_at = time.monotonic()
        result = patrol_service.patrol("cycle_check")
        elapsed = time.monotonic() - started_at

        self.assertEqual(result["actions_taken"][0]["patrol_status"], "queued")
        self.assertLess(elapsed, 0.15)


if __name__ == "__main__":
    unittest.main()
