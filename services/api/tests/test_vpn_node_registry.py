"""VPN NodeRegistry 单元测试。"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.api.app.services.vpn_node_registry import NodeEntry, NodeRegistry  # noqa: E402


class NodeRegistryTests(unittest.TestCase):
    """NodeRegistry 单元测试。"""

    def setUp(self) -> None:
        self.primary = "★ 日本¹"
        self.backups = ["★ 日本²", "★ 日本³", "★ 日本⁴", "★ 香港²"]
        self.whitelisted_ips = {
            "154.31.113.7",
            "45.95.212.80",
            "45.95.212.81",
            "45.95.212.82",
            "154.12.176.56",
        }
        self.registry = NodeRegistry(
            primary=self.primary,
            backups=self.backups,
            whitelisted_ips=self.whitelisted_ips,
        )

    def test_known_nodes_returns_primary_and_backups_in_order(self) -> None:
        nodes = self.registry.known_nodes()
        self.assertEqual(len(nodes), 5)
        self.assertEqual(nodes[0].name, self.primary)
        self.assertEqual(nodes[0].role, "primary")
        for i, backup in enumerate(self.backups):
            self.assertEqual(nodes[i + 1].name, backup)
            self.assertEqual(nodes[i + 1].role, "backup")

    def test_mark_probe_updates_entry(self) -> None:
        self.registry.mark_probe("★ 日本²", ok=True, ip="45.95.212.80")
        entry = self.registry.get_entry("★ 日本²")
        self.assertIsNotNone(entry)
        assert entry is not None
        self.assertTrue(entry.last_probe_ok)
        self.assertEqual(entry.ip, "45.95.212.80")
        self.assertTrue(entry.whitelisted)
        self.assertIsNotNone(entry.last_probe_at)

    def test_mark_probe_non_whitelisted_ip(self) -> None:
        self.registry.mark_probe("★ 香港²", ok=True, ip="1.2.3.4")
        entry = self.registry.get_entry("★ 香港²")
        self.assertIsNotNone(entry)
        assert entry is not None
        self.assertFalse(entry.whitelisted)

    def test_mark_probe_new_node_auto_creates_entry(self) -> None:
        self.registry.mark_probe("unknown-node", ok=False, ip=None)
        entry = self.registry.get_entry("unknown-node")
        self.assertIsNotNone(entry)
        assert entry is not None
        self.assertFalse(entry.last_probe_ok)
        self.assertEqual(entry.role, "unknown")

    def test_candidates_excludes_primary(self) -> None:
        candidates = self.registry.candidates()
        names = [c.name for c in candidates]
        self.assertNotIn(self.primary, names)
        self.assertEqual(len(candidates), len(self.backups))

    def test_candidates_whitelisted_priority(self) -> None:
        # Mark ★ 香港² as non-whitelisted
        self.registry.mark_probe("★ 香港²", ok=True, ip="1.2.3.4")
        candidates = self.registry.candidates()
        # Non-whitelisted should be last
        self.assertEqual(candidates[-1].name, "★ 香港²")

    def test_candidates_probe_ok_priority(self) -> None:
        # Two nodes both whitelisted, one probed ok, one not probed
        self.registry.mark_probe("★ 日本³", ok=True, ip="45.95.212.81")
        # ★ 日本² not probed
        candidates = self.registry.candidates()
        # Find positions of ★ 日本³ and ★ 日本²
        idx_jp3 = next(i for i, c in enumerate(candidates) if c.name == "★ 日本³")
        idx_jp2 = next(i for i, c in enumerate(candidates) if c.name == "★ 日本²")
        # ★ 日本³ (probed ok) should come before ★ 日本² (not probed)
        self.assertLess(idx_jp3, idx_jp2)

    def test_candidates_config_order_tiebreaker(self) -> None:
        # No probes at all, should be in config order
        candidates = self.registry.candidates()
        names = [c.name for c in candidates]
        self.assertEqual(names, self.backups)

    def test_candidates_failed_probe_sorts_last(self) -> None:
        # Mark all as probed, some fail
        self.registry.mark_probe("★ 日本²", ok=False, ip=None)
        self.registry.mark_probe("★ 日本³", ok=True, ip="45.95.212.81")
        candidates = self.registry.candidates()
        # Failed probe (★ 日本²) should be last
        self.assertEqual(candidates[-1].name, "★ 日本²")
        # OK probe (★ 日本³) should be first
        self.assertEqual(candidates[0].name, "★ 日本³")

    def test_save_and_load_state(self) -> None:
        self.registry.mark_probe("★ 日本²", ok=True, ip="45.95.212.80")
        self.registry.mark_probe("★ 香港²", ok=False, ip=None)

        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "vpn_nodes.json"
            self.registry.save_state(state_path)
            self.assertTrue(state_path.exists())

            # Load into a new registry
            new_registry = NodeRegistry(
                primary=self.primary,
                backups=self.backups,
                whitelisted_ips=self.whitelisted_ips,
            )
            new_registry.load_state(state_path)

            entry = new_registry.get_entry("★ 日本²")
            self.assertIsNotNone(entry)
            assert entry is not None
            self.assertTrue(entry.last_probe_ok)
            self.assertTrue(entry.whitelisted)
            self.assertEqual(entry.ip, "45.95.212.80")

    def test_load_state_missing_file_no_error(self) -> None:
        registry = NodeRegistry(
            primary=self.primary,
            backups=self.backups,
            whitelisted_ips=self.whitelisted_ips,
        )
        registry.load_state(Path("/nonexistent/path/vpn_nodes.json"))
        # Should not raise, should have default entries
        nodes = registry.known_nodes()
        self.assertEqual(len(nodes), 5)

    def test_load_state_corrupted_file_no_error(self) -> None:
        registry = NodeRegistry(
            primary=self.primary,
            backups=self.backups,
            whitelisted_ips=self.whitelisted_ips,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            bad_path = Path(tmpdir) / "corrupt.json"
            bad_path.write_text("not json {{{")
            registry.load_state(bad_path)
            # Should not raise
            nodes = registry.known_nodes()
            self.assertEqual(len(nodes), 5)

    def test_load_state_preserves_role_from_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "vpn_nodes.json"
            # Save state with a node that has wrong role
            state_data = {
                "primary": self.primary,
                "backups": self.backups,
                "whitelisted_ips": sorted(self.whitelisted_ips),
                "entries": {
                    "★ 日本¹": {
                        "name": "★ 日本¹",
                        "role": "backup",
                        "whitelisted": True,
                        "last_probe_ok": True,
                        "last_probe_at": 1234567890.0,
                    }
                },
            }
            state_path.parent.mkdir(parents=True, exist_ok=True)
            state_path.write_text(json.dumps(state_data))

            new_registry = NodeRegistry(
                primary=self.primary,
                backups=self.backups,
                whitelisted_ips=self.whitelisted_ips,
            )
            new_registry.load_state(state_path)
            entry = new_registry.get_entry("★ 日本¹")
            self.assertIsNotNone(entry)
            assert entry is not None
            # Role should be corrected to "primary" from config
            self.assertEqual(entry.role, "primary")
            self.assertTrue(entry.last_probe_ok)

    def test_empty_primary_and_backups(self) -> None:
        registry = NodeRegistry(
            primary="",
            backups=[],
            whitelisted_ips=set(),
        )
        nodes = registry.known_nodes()
        self.assertEqual(len(nodes), 0)
        candidates = registry.candidates()
        self.assertEqual(len(candidates), 0)

    def test_get_entry_nonexistent(self) -> None:
        entry = self.registry.get_entry("no-such-node")
        self.assertIsNone(entry)


if __name__ == "__main__":
    unittest.main()
