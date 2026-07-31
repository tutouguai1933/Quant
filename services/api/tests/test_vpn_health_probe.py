"""VPN NodeHealthProbe 单元测试。"""

from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.api.app.services.vpn_health_probe import NodeHealthProbe, ProbeResult  # noqa: E402


class NodeHealthProbeTests(unittest.TestCase):
    """NodeHealthProbe 单元测试（mock HTTP）。"""

    def setUp(self) -> None:
        self.whitelisted_ips = {"154.31.113.7", "45.95.212.80"}
        self.probe = NodeHealthProbe(
            proxy_url="http://127.0.0.1:7890",
            health_check_url="https://api.binance.com/api/v3/ping",
            ip_check_url="https://api.ipify.org?format=json",
            whitelisted_ips=self.whitelisted_ips,
            cache_ttl_s=120.0,
            probe_timeout=10.0,
        )

    def _mock_client(
        self,
        ping_status: int = 200,
        exit_ip: str | None = "154.31.113.7",
    ) -> mock.MagicMock:
        """创建 mock httpx.Client。"""
        mock_client = mock.MagicMock()
        mock_client.__enter__ = mock.Mock(return_value=mock_client)
        mock_client.__exit__ = mock.Mock(return_value=False)

        # Mock Binance ping response
        ping_response = mock.MagicMock()
        ping_response.status_code = ping_status

        # For IP check, second .get() call needs different response
        ip_response = mock.MagicMock()
        ip_response.status_code = 200
        ip_response.json.return_value = {"ip": exit_ip}

        mock_client.get.side_effect = [ping_response, ip_response]

        return mock_client

    def _make_client_factory(self, call_counter: list[int], ping_statuses=None, exit_ips=None):
        """Create a client factory side_effect function that accepts **kwargs."""
        def factory(**kwargs):
            idx = call_counter[0]
            call_counter[0] += 1
            status = 200
            ip = "154.31.113.7"
            if ping_statuses and idx < len(ping_statuses):
                status = ping_statuses[idx]
            if exit_ips and idx < len(exit_ips):
                ip = exit_ips[idx]
            return self._mock_client(ping_status=status, exit_ip=ip)
        return factory

    def test_check_success(self) -> None:
        with mock.patch("httpx.Client") as mock_client_cls:
            mock_client_cls.return_value = self._mock_client(
                ping_status=200, exit_ip="154.31.113.7"
            )
            result = self.probe.check("★ 日本¹")

        self.assertTrue(result.ok)
        self.assertEqual(result.ip, "154.31.113.7")
        self.assertEqual(result.node_name, "★ 日本¹")
        self.assertIsNotNone(result.latency_ms)

    def test_check_binance_unreachable(self) -> None:
        with mock.patch("httpx.Client") as mock_client_cls:
            mock_client_cls.return_value = self._mock_client(ping_status=500)
            result = self.probe.check("★ 日本¹")

        self.assertFalse(result.ok)
        self.assertIn("500", result.error or "")

    def test_check_timeout(self) -> None:
        import httpx as httpx_module

        with mock.patch("httpx.Client") as mock_client_cls:
            mock_client = mock.MagicMock()
            mock_client.get.side_effect = httpx_module.TimeoutException(
                "timeout"
            )
            mock_client_cls.return_value = mock_client
            result = self.probe.check("★ 日本¹")

        self.assertFalse(result.ok)
        self.assertEqual(result.error, "请求超时")

    def test_cache_returns_cached_result_within_ttl(self) -> None:
        """第二次调用在 TTL 内，应返回缓存，不发起 HTTP 请求。"""
        call_counter = [0]
        factory = self._make_client_factory(call_counter)

        with mock.patch("httpx.Client") as mock_client_cls:
            mock_client_cls.side_effect = factory
            result1 = self.probe.check("★ 日本¹")
            result2 = self.probe.check("★ 日本¹")

        self.assertTrue(result1.ok)
        self.assertTrue(result2.ok)
        self.assertEqual(call_counter[0], 1)  # Second call uses cache

    def test_cache_force_refresh(self) -> None:
        """force=True 忽略缓存，强制重新探测。"""
        call_counter = [0]
        factory = self._make_client_factory(
            call_counter,
            ping_statuses=[200, 500],
        )

        with mock.patch("httpx.Client") as mock_client_cls:
            mock_client_cls.side_effect = factory
            result1 = self.probe.check("★ 日本¹")
            result2 = self.probe.check("★ 日本¹", force=True)

        self.assertTrue(result1.ok)
        self.assertFalse(result2.ok)
        self.assertEqual(call_counter[0], 2)

    def test_check_with_interval_throttles(self) -> None:
        """节流测试：第二次调用在 min_interval_s 内，返回缓存。"""
        call_counter = [0]
        factory = self._make_client_factory(call_counter)

        with mock.patch("httpx.Client") as mock_client_cls:
            mock_client_cls.side_effect = factory
            result1 = self.probe.check_with_interval("★ 日本¹", min_interval_s=10.0)
            result2 = self.probe.check_with_interval("★ 日本¹", min_interval_s=10.0)

        self.assertTrue(result1.ok)
        self.assertTrue(result2.ok)
        self.assertEqual(call_counter[0], 1)  # Throttled

    def test_check_with_interval_allows_after_interval(self) -> None:
        """间隔已过 + 缓存已过期时，重新探测。"""
        call_counter = [0]
        factory = self._make_client_factory(call_counter)

        # Simulate last probe 15s ago
        self.probe._last_probe_at["★ 日本¹"] = time.time() - 15.0
        self.probe._cache["★ 日本¹"] = ProbeResult(
            ok=True, ip="154.31.113.7", node_name="★ 日本¹",
            at=time.time() - 130.0,  # cache expired (> 120s)
        )

        with mock.patch("httpx.Client") as mock_client_cls:
            mock_client_cls.side_effect = factory
            result = self.probe.check_with_interval("★ 日本¹", min_interval_s=10.0)

        self.assertTrue(result.ok)
        self.assertEqual(call_counter[0], 1)

    def test_check_with_interval_uses_cache_when_stale(self) -> None:
        """最近探测过 + 缓存未过期，返回缓存不发起请求。"""
        self.probe._last_probe_at["★ 日本¹"] = time.time() - 1.0
        cached = ProbeResult(
            ok=True, ip="154.31.113.7", node_name="★ 日本¹",
        )
        self.probe._cache["★ 日本¹"] = cached

        call_counter = [0]
        factory = self._make_client_factory(call_counter)

        with mock.patch("httpx.Client") as mock_client_cls:
            mock_client_cls.side_effect = factory
            result = self.probe.check_with_interval("★ 日本¹", min_interval_s=10.0)

        self.assertTrue(result.ok)
        self.assertEqual(call_counter[0], 0)

    def test_is_whitelisted(self) -> None:
        self.assertTrue(self.probe.is_whitelisted("154.31.113.7"))
        self.assertFalse(self.probe.is_whitelisted("1.2.3.4"))
        self.assertFalse(self.probe.is_whitelisted(None))

    def test_clear_cache(self) -> None:
        with mock.patch("httpx.Client") as mock_client_cls:
            mock_client_cls.return_value = self._mock_client(
                ping_status=200, exit_ip="154.31.113.7"
            )
            self.probe.check("★ 日本¹")

        self.assertIsNotNone(self.probe.get_cached_result("★ 日本¹"))
        self.probe.clear_cache()
        self.assertIsNone(self.probe.get_cached_result("★ 日本¹"))
        self.assertEqual(len(self.probe._last_probe_at), 0)

    def test_get_cached_result_nonexistent(self) -> None:
        self.assertIsNone(self.probe.get_cached_result("nonexistent"))

    def test_different_nodes_independent_cache(self) -> None:
        """不同节点独立缓存，不共享。"""
        call_counter = [0]
        factory = self._make_client_factory(
            call_counter,
            exit_ips=["154.31.113.7", "45.95.212.80"],
        )

        with mock.patch("httpx.Client") as mock_client_cls:
            mock_client_cls.side_effect = factory
            result1 = self.probe.check("★ 日本¹")
            result2 = self.probe.check("★ 日本²")

        self.assertTrue(result1.ok)
        self.assertTrue(result2.ok)
        self.assertEqual(result1.ip, "154.31.113.7")
        self.assertEqual(result2.ip, "45.95.212.80")
        self.assertEqual(call_counter[0], 2)

    def test_request_error_handling(self) -> None:
        import httpx as httpx_module

        with mock.patch("httpx.Client") as mock_client_cls:
            mock_client = mock.MagicMock()
            mock_client.get.side_effect = httpx_module.RequestError("connection refused")
            mock_client_cls.return_value = mock_client
            result = self.probe.check("★ 日本¹")

        self.assertFalse(result.ok)
        self.assertIn("connection refused", result.error or "")


if __name__ == "__main__":
    unittest.main()
