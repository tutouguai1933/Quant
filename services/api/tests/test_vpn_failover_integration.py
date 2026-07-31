"""VPN 故障切换集成测试（mock mihomo API 与探测结果）。

测试完整的 failover/failback 流程。
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.api.app.services.vpn_failover_policy import PrimaryBackupPolicy  # noqa: E402
from services.api.app.services.vpn_health_probe import NodeHealthProbe, ProbeResult  # noqa: E402
from services.api.app.services.vpn_node_registry import NodeRegistry  # noqa: E402
from services.api.app.services.vpn_failover_controller import (  # noqa: E402
    VPNFailoverController,
)


class VPNFailoverControllerTests(unittest.TestCase):
    """控制器单元测试（mock 探针）。"""

    def setUp(self) -> None:
        self.primary = "★ 日本¹"
        self.backups = ["★ 日本²", "★ 日本³"]
        self.whitelisted_ips = {
            "154.31.113.7",
            "45.95.212.80",
            "45.95.212.81",
        }
        self._tmpdir = tempfile.TemporaryDirectory()
        tmp_path = Path(self._tmpdir.name)
        self.controller = VPNFailoverController(
            primary=self.primary,
            backups=self.backups,
            whitelisted_ips=self.whitelisted_ips,
            proxy_url="http://127.0.0.1:7890",
            state_path=tmp_path / "vpn_nodes.json",
            events_path=tmp_path / "vpn_failover_events.jsonl",
        )

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_controller_initialization(self) -> None:
        self.assertTrue(self.controller.enabled)
        self.assertEqual(self.controller.primary_name, self.primary)
        self.assertIsNotNone(self.controller.registry)
        self.assertIsNotNone(self.controller.probe)
        self.assertIsNotNone(self.controller.policy)

    def test_controller_disabled_when_no_nodes(self) -> None:
        ctrl = VPNFailoverController(
            primary="",
            backups=[],
            whitelisted_ips=set(),
        )
        self.assertFalse(ctrl.enabled)

    def test_check_primary_healthy(self) -> None:
        """主节点健康时返回 healthy。"""
        with mock.patch.object(
            self.controller.probe, "check_with_interval"
        ) as mock_check:
            mock_check.return_value = ProbeResult(
                ok=True, ip="154.31.113.7", node_name=self.primary,
            )
            result = self.controller.check_primary()

        self.assertEqual(result["action"], "healthy")
        self.assertTrue(result["ok"])

    def test_check_primary_probing(self) -> None:
        """主节点探测失败但未达到 fail_threshold 时返回 probing。"""
        # One failure
        with mock.patch.object(
            self.controller.probe, "check_with_interval"
        ) as mock_check:
            mock_check.return_value = ProbeResult(
                ok=False, node_name=self.primary, error="timeout",
            )
            result = self.controller.check_primary()

        self.assertEqual(result["action"], "probing")

        # Two failures
        with mock.patch.object(
            self.controller.probe, "check_with_interval"
        ) as mock_check:
            mock_check.return_value = ProbeResult(
                ok=False, node_name=self.primary, error="timeout",
            )
            result = self.controller.check_primary()

        self.assertEqual(result["action"], "probing")

    def test_check_primary_failover(self) -> None:
        """主节点连续失败达到阈值触发故障切换。"""
        # Force 2 existing failures
        self.controller.policy.record_probe(self.primary, ok=False)
        self.controller.policy.record_probe(self.primary, ok=False)

        # 3rd failure triggers failover
        with mock.patch.object(
            self.controller.probe, "check_with_interval"
        ) as mock_check_interval:
            # Return different results per node: primary fails, backup OK
            def side_effect(node, **kwargs):
                if node == self.primary:
                    return ProbeResult(ok=False, node_name=node, error="timeout")
                return ProbeResult(ok=True, ip="45.95.212.80", node_name=node)

            mock_check_interval.side_effect = side_effect
            result = self.controller.check_primary()

        self.assertEqual(result["action"], "failover")
        self.assertEqual(result["to"], "★ 日本²")
        self.assertTrue(result["success"])

        # Verify event was written
        events_path = self.controller._events_path
        self.assertTrue(events_path.exists())
        with open(events_path, "r") as f:
            lines = f.readlines()
        self.assertEqual(len(lines), 1)
        event = json.loads(lines[0])
        self.assertEqual(event["from"], self.primary)
        self.assertEqual(event["to"], "★ 日本²")
        self.assertTrue(event["success"])

    def test_check_primary_failover_all_backups_fail(self) -> None:
        """所有备选节点预验证失败。"""
        self.controller.policy.record_probe(self.primary, ok=False)
        self.controller.policy.record_probe(self.primary, ok=False)

        with mock.patch.object(
            self.controller.probe, "check_with_interval"
        ) as mock_check_interval:
            # All probes fail
            mock_check_interval.return_value = ProbeResult(
                ok=False, node_name="probe", error="timeout",
            )
            result = self.controller.check_primary()

        self.assertEqual(result["action"], "failover_failed")
        self.assertFalse(result["success"])

    def test_failback_after_recovery(self) -> None:
        """主节点恢复后触发回切。"""
        # Simulate: already failed over to backup
        self.controller.policy.current_backup = "★ 日本²"
        self.controller.policy.mark_switched()
        # Manually advance switched_at to outside observation
        self.controller.policy._switched_at = (
            self.controller.policy._switched_at or 0
        ) - 400

        # Record 3 successes on primary
        self.controller.policy.record_probe(self.primary, ok=True)
        self.controller.policy.record_probe(self.primary, ok=True)
        self.controller.policy.record_probe(self.primary, ok=True)

        with mock.patch.object(
            self.controller.probe, "check_with_interval"
        ) as mock_check:
            mock_check.return_value = ProbeResult(
                ok=True, ip="154.31.113.7", node_name=self.primary,
            )
            result = self.controller.check_primary()

        self.assertEqual(result["action"], "failback")
        self.assertTrue(result["success"])
        self.assertIsNone(self.controller.policy.current_backup)

    def test_failback_blocked_during_observation(self) -> None:
        """观察期内不回切。"""
        self.controller.policy.current_backup = "★ 日本²"
        self.controller.policy.mark_switched()  # just now

        # Record 3 successes
        self.controller.policy.record_probe(self.primary, ok=True)
        self.controller.policy.record_probe(self.primary, ok=True)
        self.controller.policy.record_probe(self.primary, ok=True)

        with mock.patch.object(
            self.controller.probe, "check_with_interval"
        ) as mock_check:
            mock_check.return_value = ProbeResult(
                ok=True, ip="154.31.113.7", node_name=self.primary,
            )
            result = self.controller.check_primary()

        # Should be observing, not failback
        self.assertEqual(result["action"], "observing")

    def test_state_persistence(self) -> None:
        """注册表状态持久化测试。"""
        self.controller.registry.mark_probe("★ 日本²", ok=True, ip="45.95.212.80")
        self.controller.registry.save_state(self.controller._state_path)

        # Create a new controller with same state path
        new_ctrl = VPNFailoverController(
            primary=self.primary,
            backups=self.backups,
            whitelisted_ips=self.whitelisted_ips,
            state_path=self.controller._state_path,
        )
        entry = new_ctrl.registry.get_entry("★ 日本²")
        self.assertIsNotNone(entry)
        assert entry is not None
        self.assertTrue(entry.last_probe_ok)

    def test_get_status(self) -> None:
        status = self.controller.get_status()
        self.assertTrue(status["enabled"])
        self.assertEqual(status["primary"], self.primary)
        self.assertIsNone(status["current_backup"])
        self.assertFalse(status["in_observation"])

    def test_events_written_to_jsonl(self) -> None:
        self.controller._write_event(
            self.controller.policy.record_event(
                from_node="★ 日本¹",
                to_node="★ 日本²",
                reason="test",
                success=True,
            )
        )
        events_path = self.controller._events_path
        self.assertTrue(events_path.exists())
        with open(events_path, "r") as f:
            line = f.readline()
        event = json.loads(line)
        self.assertEqual(event["from"], "★ 日本¹")
        self.assertEqual(event["to"], "★ 日本²")


class VPNPatrolIntegrationTests(unittest.TestCase):
    """巡检集成测试（mock vpn_switch_service 的切换方法）。"""

    def setUp(self) -> None:
        from services.api.app.services.vpn_switch_service import (
            NodeHealthResult,
            NodeHealthStatus,
            VPNSwitchService,
        )

        # Mock vpn_switch_service with healthy node
        self._mock_switch = mock.patch.object(
            VPNSwitchService, "check_node_health_sync"
        )
        self._mock_check = self._mock_switch.start()

        self._mock_switch_node = mock.patch.object(
            VPNSwitchService, "switch_node_sync"
        )
        self._mock_sw = self._mock_switch_node.start()

        self._healthy_result = NodeHealthResult(
            node_name="★ 日本¹",
            status=NodeHealthStatus.HEALTHY,
            exit_ip="154.31.113.7",
            is_whitelisted=True,
        )

    def tearDown(self) -> None:
        self._mock_switch.stop()
        self._mock_switch_node.stop()

    def test_patrol_uses_legacy_when_no_failover_config(self) -> None:
        """未配置主备策略时，巡检使用原有逻辑。"""
        self._mock_check.return_value = self._healthy_result

        from services.api.app.services.openclaw_patrol_service import (
            OpenclawPatrolService,
        )

        patrol = OpenclawPatrolService(
            snapshot_service=mock.Mock(),
            action_service=mock.Mock(),
            health_service=mock.Mock(),
        )
        # Make failover controller return None
        with mock.patch.object(
            OpenclawPatrolService, "_get_failover_controller", return_value=None
        ):
            result = patrol._check_vpn_health()

        self.assertFalse(result.get("action_taken"))
        self.assertEqual(result.get("patrol_status"), "normal")

    def test_patrol_with_failover_controller_healthy(self) -> None:
        """主备策略启用时，主节点健康返回正常。"""
        from services.api.app.services.openclaw_patrol_service import (
            OpenclawPatrolService,
        )

        mock_ctrl = mock.MagicMock()
        mock_ctrl.enabled = True
        mock_ctrl.check_primary.return_value = {
            "action": "healthy",
            "ok": True,
            "ip": "154.31.113.7",
            "message": "主节点健康",
        }

        patrol = OpenclawPatrolService(
            snapshot_service=mock.Mock(),
            action_service=mock.Mock(),
            health_service=mock.Mock(),
        )
        with mock.patch.object(
            OpenclawPatrolService, "_get_failover_controller", return_value=mock_ctrl
        ):
            result = patrol._check_vpn_health()

        self.assertFalse(result.get("action_taken"))
        self.assertEqual(result.get("patrol_status"), "normal")

    def test_patrol_with_failover_triggers_switch(self) -> None:
        """主备策略触发故障切换。"""
        from services.api.app.services.openclaw_patrol_service import (
            OpenclawPatrolService,
        )
        from services.api.app.services.vpn_switch_service import SwitchResult

        mock_ctrl = mock.MagicMock()
        mock_ctrl.enabled = True
        mock_ctrl.primary_name = "★ 日本¹"
        mock_ctrl.check_primary.return_value = {
            "action": "failover",
            "to": "★ 日本²",
            "success": True,
            "message": "故障切换到备选节点",
        }

        self._mock_sw.return_value = SwitchResult(
            success=True,
            previous_node="★ 日本¹",
            current_node="★ 日本²",
            exit_ip="45.95.212.80",
            is_whitelisted=True,
        )

        patrol = OpenclawPatrolService(
            snapshot_service=mock.Mock(),
            action_service=mock.Mock(),
            health_service=mock.Mock(),
        )
        with mock.patch.object(
            OpenclawPatrolService, "_get_failover_controller", return_value=mock_ctrl
        ):
            result = patrol._check_vpn_health()

        self.assertTrue(result.get("action_taken"))
        self.assertEqual(result.get("action"), "vpn_failover")
        self.assertTrue(result.get("success"))

    def test_patrol_with_failback_triggers_switch(self) -> None:
        """主备策略触发回切。"""
        from services.api.app.services.openclaw_patrol_service import (
            OpenclawPatrolService,
        )
        from services.api.app.services.vpn_switch_service import SwitchResult

        mock_ctrl = mock.MagicMock()
        mock_ctrl.enabled = True
        mock_ctrl.primary_name = "★ 日本¹"
        mock_ctrl.check_primary.return_value = {
            "action": "failback",
            "to": "★ 日本¹",
            "success": True,
            "message": "回切到主节点",
        }

        self._mock_sw.return_value = SwitchResult(
            success=True,
            previous_node="★ 日本²",
            current_node="★ 日本¹",
            exit_ip="154.31.113.7",
            is_whitelisted=True,
        )

        patrol = OpenclawPatrolService(
            snapshot_service=mock.Mock(),
            action_service=mock.Mock(),
            health_service=mock.Mock(),
        )
        with mock.patch.object(
            OpenclawPatrolService, "_get_failover_controller", return_value=mock_ctrl
        ):
            result = patrol._check_vpn_health()

        self.assertTrue(result.get("action_taken"))
        self.assertEqual(result.get("action"), "vpn_failback")
        self.assertTrue(result.get("success"))


if __name__ == "__main__":
    unittest.main()
