"""VPN PrimaryBackupPolicy 单元测试（纯逻辑，mock 探针和注册表）。"""

from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.api.app.services.vpn_failover_policy import (  # noqa: E402
    FailoverEvent,
    PrimaryBackupPolicy,
)
from services.api.app.services.vpn_node_registry import NodeEntry, NodeRegistry  # noqa: E402
from services.api.app.services.vpn_health_probe import NodeHealthProbe, ProbeResult  # noqa: E402


class PrimaryBackupPolicyTests(unittest.TestCase):
    """PrimaryBackupPolicy 单元测试。"""

    def setUp(self) -> None:
        self.policy = PrimaryBackupPolicy(
            fail_threshold=3,
            recover_threshold=3,
            observe_seconds=300,
        )
        self.primary = "★ 日本¹"

    def test_should_failover_after_consecutive_failures(self) -> None:
        # 1 failure: no failover
        self.policy.record_probe(self.primary, ok=False)
        self.assertFalse(self.policy.should_failover(self.primary))

        # 2 failures: still no
        self.policy.record_probe(self.primary, ok=False)
        self.assertFalse(self.policy.should_failover(self.primary))

        # 3 failures: trigger failover
        self.policy.record_probe(self.primary, ok=False)
        self.assertTrue(self.policy.should_failover(self.primary))

    def test_should_failover_resets_on_success(self) -> None:
        # 2 failures, then success
        self.policy.record_probe(self.primary, ok=False)
        self.policy.record_probe(self.primary, ok=False)
        self.policy.record_probe(self.primary, ok=True)
        self.assertFalse(self.policy.should_failover(self.primary))

        # Need 3 more consecutive failures
        self.policy.record_probe(self.primary, ok=False)
        self.policy.record_probe(self.primary, ok=False)
        self.assertFalse(self.policy.should_failover(self.primary))
        self.policy.record_probe(self.primary, ok=False)
        self.assertTrue(self.policy.should_failover(self.primary))

    def test_should_failback_after_consecutive_successes(self) -> None:
        # Record successes on primary
        self.policy.record_probe(self.primary, ok=True)
        self.policy.record_probe(self.primary, ok=True)
        self.assertFalse(self.policy.should_failback(self.primary))

        self.policy.record_probe(self.primary, ok=True)
        # Not in observation, so should failback
        self.assertTrue(self.policy.should_failback(self.primary))

    def test_should_failback_resets_on_failure(self) -> None:
        # 2 successes, then failure
        self.policy.record_probe(self.primary, ok=True)
        self.policy.record_probe(self.primary, ok=True)
        self.policy.record_probe(self.primary, ok=False)
        self.assertFalse(self.policy.should_failback(self.primary))

    def test_in_observation(self) -> None:
        # Just switched
        now = time.time()
        self.assertTrue(self.policy.in_observation(now))

        # Switched 400 seconds ago
        self.assertFalse(self.policy.in_observation(now - 400))

        # Default observe is 300s, so exactly 300 is not in observation
        # (elapsed 300 >= observe_seconds 300)
        self.assertFalse(self.policy.in_observation(now - 300))

    def test_in_observation_zero_or_negative(self) -> None:
        self.assertFalse(self.policy.in_observation(0))
        self.assertFalse(self.policy.in_observation(-1))

    def test_should_failback_blocked_in_observation(self) -> None:
        # Primary recovered (3 successes) but we're in observation
        self.policy.mark_switched()  # sets _switched_at to now
        self.policy.record_probe(self.primary, ok=True)
        self.policy.record_probe(self.primary, ok=True)
        self.policy.record_probe(self.primary, ok=True)

        self.assertFalse(self.policy.should_failback(self.primary))

    def test_mark_switched(self) -> None:
        self.assertIsNone(self.policy.switched_at)
        self.policy.mark_switched()
        self.assertIsNotNone(self.policy.switched_at)
        self.assertGreater(self.policy.switched_at or 0, 0)

    def test_pick_backup_returns_first_valid_candidate(self) -> None:
        registry = NodeRegistry(
            primary=self.primary,
            backups=["★ 日本²", "★ 日本³", "★ 香港²"],
            whitelisted_ips={"154.31.113.7", "45.95.212.80"},
        )
        probe = mock.MagicMock(spec=NodeHealthProbe)
        # First candidate succeeds
        probe.check_with_interval.return_value = ProbeResult(
            ok=True, ip="45.95.212.80", node_name="★ 日本²",
        )

        result = self.policy.pick_backup(registry, probe)
        self.assertEqual(result, "★ 日本²")
        probe.check_with_interval.assert_called_once_with("★ 日本²")

    def test_pick_backup_skips_failed_candidates(self) -> None:
        registry = NodeRegistry(
            primary=self.primary,
            backups=["★ 日本²", "★ 日本³", "★ 香港²"],
            whitelisted_ips={"154.31.113.7", "45.95.212.80"},
        )
        probe = mock.MagicMock(spec=NodeHealthProbe)
        # First fails, second succeeds
        probe.check_with_interval.side_effect = [
            ProbeResult(ok=False, node_name="★ 日本²", error="timeout"),
            ProbeResult(ok=True, ip="45.95.212.81", node_name="★ 日本³"),
        ]

        result = self.policy.pick_backup(registry, probe)
        self.assertEqual(result, "★ 日本³")
        self.assertEqual(probe.check_with_interval.call_count, 2)

    def test_pick_backup_all_fail_returns_none(self) -> None:
        registry = NodeRegistry(
            primary=self.primary,
            backups=["★ 日本²"],
            whitelisted_ips={"154.31.113.7"},
        )
        probe = mock.MagicMock(spec=NodeHealthProbe)
        probe.check_with_interval.return_value = ProbeResult(
            ok=False, node_name="★ 日本²", error="timeout",
        )

        result = self.policy.pick_backup(registry, probe)
        self.assertIsNone(result)

    def test_pick_backup_empty_candidates(self) -> None:
        registry = NodeRegistry(
            primary=self.primary,
            backups=[],
            whitelisted_ips=set(),
        )
        probe = mock.MagicMock(spec=NodeHealthProbe)

        result = self.policy.pick_backup(registry, probe)
        self.assertIsNone(result)

    def test_record_event(self) -> None:
        event = self.policy.record_event(
            from_node="★ 日本¹",
            to_node="★ 日本²",
            reason="主节点连续3次探测失败",
            success=True,
        )
        self.assertEqual(event.from_node, "★ 日本¹")
        self.assertEqual(event.to_node, "★ 日本²")
        self.assertTrue(event.success)
        self.assertEqual(len(self.policy.get_events()), 1)

    def test_reset_clears_all_state(self) -> None:
        self.policy.record_probe(self.primary, ok=False)
        self.policy.mark_switched()
        self.policy.record_event("a", "b", "test", True)

        self.policy.reset()
        self.assertIsNone(self.policy.switched_at)
        self.assertFalse(self.policy.should_failover(self.primary))
        self.assertEqual(len(self.policy.get_events()), 0)

    def test_current_backup_property(self) -> None:
        self.assertIsNone(self.policy.current_backup)
        self.policy.current_backup = "★ 日本²"
        self.assertEqual(self.policy.current_backup, "★ 日本²")

    def test_record_probe_tracks_multiple_nodes(self) -> None:
        self.policy.record_probe(self.primary, ok=False)
        self.policy.record_probe("★ 日本²", ok=True)

        self.assertEqual(
            self.policy._consecutive_failures.get(self.primary, 0), 1
        )
        self.assertEqual(
            self.policy._consecutive_successes.get("★ 日本²", 0), 1
        )

    def test_failover_event_to_dict(self) -> None:
        event = FailoverEvent(
            ts=1234567890.0,
            from_node="★ 日本¹",
            to_node="★ 日本²",
            reason="auto",
            success=True,
        )
        d = event.to_dict()
        self.assertEqual(d["ts"], 1234567890.0)
        self.assertEqual(d["from"], "★ 日本¹")
        self.assertEqual(d["to"], "★ 日本²")
        self.assertEqual(d["reason"], "auto")
        self.assertTrue(d["success"])


if __name__ == "__main__":
    unittest.main()
