"""VPN 节点健康探针。

封装 Binance ping + 出口 IP 检查 + 白名单匹配逻辑，
提供探测结果缓存和节流控制。
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

import httpx

logger = logging.getLogger(__name__)


@dataclass
class ProbeResult:
    """单次探测结果。"""

    ok: bool
    ip: str | None = None
    latency_ms: float | None = None
    at: float = field(default_factory=time.time)
    error: str | None = None
    node_name: str = ""

    def to_dict(self) -> dict:
        """序列化为字典。"""
        return {
            "ok": self.ok,
            "ip": self.ip,
            "latency_ms": self.latency_ms,
            "at": self.at,
            "error": self.error,
            "node_name": self.node_name,
        }


class NodeHealthProbe:
    """VPN 节点健康探针。

    通过代理访问 Binance API 和 IP 检测服务，
    支持结果缓存和节流探测。
    """

    def __init__(
        self,
        proxy_url: str = "http://127.0.0.1:7890",
        health_check_url: str = "https://api.binance.com/api/v3/ping",
        ip_check_url: str = "https://api.ipify.org?format=json",
        whitelisted_ips: set[str] | None = None,
        cache_ttl_s: float = 120.0,
        probe_timeout: float = 10.0,
    ) -> None:
        """初始化健康探针。

        Args:
            proxy_url: mihomo 代理地址
            health_check_url: Binance 健康检查 URL
            ip_check_url: 出口 IP 检测 URL
            whitelisted_ips: 白名单 IP 集合
            cache_ttl_s: 缓存有效期（秒），默认 120
            probe_timeout: 单次探测超时（秒）
        """
        self._proxy_url = proxy_url
        self._health_check_url = health_check_url
        self._ip_check_url = ip_check_url
        self._whitelisted_ips = whitelisted_ips or set()
        self._cache_ttl_s = cache_ttl_s
        self._probe_timeout = probe_timeout
        self._cache: dict[str, ProbeResult] = {}
        self._last_probe_at: dict[str, float] = {}

    @property
    def whitelisted_ips(self) -> set[str]:
        """返回白名单 IP 集合。"""
        return self._whitelisted_ips

    def check(self, node: str, force: bool = False) -> ProbeResult:
        """探测指定节点的健康状态。

        Binance ping（走代理）+ 出口 IP（走代理）+ 白名单匹配。

        Args:
            node: 节点名称
            force: 是否强制探测（忽略缓存）

        Returns:
            探测结果
        """
        # 检查缓存
        if not force:
            cached = self._cache.get(node)
            if cached is not None:
                age = time.time() - cached.at
                if age < self._cache_ttl_s:
                    logger.debug(
                        "节点 %s 使用缓存探测结果（age=%.1fs）", node, age
                    )
                    return cached

        # 执行实际探测
        result = self._do_probe(node)
        self._cache[node] = result
        self._last_probe_at[node] = time.time()
        return result

    def check_with_interval(
        self,
        node: str,
        min_interval_s: float = 10.0,
    ) -> ProbeResult:
        """带节流的探测：距上次探测小于 min_interval_s 则返回缓存。

        Args:
            node: 节点名称
            min_interval_s: 最小探测间隔（秒），默认 10

        Returns:
            探测结果
        """
        last_at = self._last_probe_at.get(node, 0.0)
        elapsed = time.time() - last_at

        if elapsed < min_interval_s:
            # 检查缓存是否可用
            cached = self._cache.get(node)
            if cached is not None:
                logger.debug(
                    "节点 %s 节流：距上次探测 %.1fs < %.0fs，返回缓存",
                    node, elapsed, min_interval_s,
                )
                return cached
            # 缓存不可用（可能是新节点），记录警告
            logger.warning(
                "节点 %s 节流等待：距上次 %.1fs < %.0fs，无缓存可用",
                node, elapsed, min_interval_s,
            )

        # 检查缓存仍有效（优先返回缓存，减少对外请求）
        cached = self._cache.get(node)
        if cached is not None:
            age = time.time() - cached.at
            if age < self._cache_ttl_s:
                logger.debug(
                    "节点 %s 使用缓存（age=%.1fs，未过期）", node, age
                )
                return cached

        result = self._do_probe(node)
        self._cache[node] = result
        self._last_probe_at[node] = time.time()
        return result

    def _do_probe(self, node: str) -> ProbeResult:
        """执行实际探测（Binance ping + 出口 IP）。"""
        try:
            start_time = time.time()
            client = httpx.Client(
                timeout=self._probe_timeout,
                proxy=self._proxy_url,
            )
            try:
                response = client.get(self._health_check_url)
                latency_ms = (time.time() - start_time) * 1000

                if response.status_code != 200:
                    return ProbeResult(
                        ok=False,
                        node_name=node,
                        error=f"Binance ping HTTP {response.status_code}",
                    )

                # 获取出口 IP
                exit_ip = self._get_exit_ip(client)

                return ProbeResult(
                    ok=True,
                    ip=exit_ip,
                    latency_ms=round(latency_ms, 2),
                    node_name=node,
                )
            finally:
                client.close()

        except httpx.TimeoutException:
            return ProbeResult(
                ok=False,
                node_name=node,
                error="请求超时",
            )
        except httpx.RequestError as e:
            return ProbeResult(
                ok=False,
                node_name=node,
                error=str(e),
            )
        except Exception as e:
            logger.exception("探测节点 %s 异常: %s", node, e)
            return ProbeResult(
                ok=False,
                node_name=node,
                error=str(e),
            )

    def _get_exit_ip(self, client: httpx.Client) -> str | None:
        """通过代理获取出口 IP。"""
        try:
            response = client.get(self._ip_check_url)
            if response.status_code == 200:
                data = response.json()
                return data.get("ip")
            return None
        except Exception as e:
            logger.warning("获取出口 IP 失败: %s", e)
            return None

    def is_whitelisted(self, ip: str | None) -> bool:
        """检查 IP 是否在白名单中。

        Args:
            ip: IP 地址

        Returns:
            是否在白名单中
        """
        if not ip:
            return False
        return ip in self._whitelisted_ips

    def get_cached_result(self, node: str) -> ProbeResult | None:
        """获取缓存的探测结果。

        Args:
            node: 节点名称

        Returns:
            缓存的探测结果，不存在返回 None
        """
        return self._cache.get(node)

    def clear_cache(self) -> None:
        """清空缓存。"""
        self._cache.clear()
        self._last_probe_at.clear()
