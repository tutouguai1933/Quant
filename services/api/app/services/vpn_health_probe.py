"""VPN 节点健康探针。

封装 Binance ping + 签名接口实测 + 出口 IP 检查 + 白名单匹配逻辑，
提供探测结果缓存和节流控制。
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import time
from dataclasses import dataclass, field
from urllib.parse import quote

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
        mihomo_api_url: str = "http://127.0.0.1:9090",
        signed_check_url: str = "https://api.binance.com/api/v3/account",
        binance_api_key: str | None = None,
        binance_api_secret: str | None = None,
    ) -> None:
        """初始化健康探针。

        Args:
            proxy_url: mihomo 代理地址（签名实测和 IP 检查走它）
            health_check_url: Binance 健康检查 URL（delay 测试目标）
            ip_check_url: 出口 IP 检测 URL（预留）
            whitelisted_ips: 白名单 IP 集合
            cache_ttl_s: 缓存有效期（秒），默认 120
            probe_timeout: 单次探测超时（秒）
            mihomo_api_url: mihomo controller 地址，用于逐节点 delay 测试
            signed_check_url: 签名实测接口（检测出口 IP 是否在白名单）
            binance_api_key: Binance API key（签名实测用）
            binance_api_secret: Binance API secret（签名实测用）
        """
        self._proxy_url = proxy_url
        self._health_check_url = health_check_url
        self._ip_check_url = ip_check_url
        self._whitelisted_ips = whitelisted_ips or set()
        self._cache_ttl_s = cache_ttl_s
        self._probe_timeout = probe_timeout
        self._mihomo_api_url = mihomo_api_url
        self._signed_check_url = signed_check_url
        self._binance_api_key = binance_api_key
        self._binance_api_secret = binance_api_secret
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
        """执行实际探测（mihomo 逐节点 delay 测试）。

        通过 mihomo controller 的 delay 接口让指定节点测 Binance ping，
        不改变当前代理出口（走 7890 只会测到 BestSSR 当前选中的节点，
        无法发现指定节点宕机）。
        """
        try:
            start_time = time.time()
            client = httpx.Client(timeout=self._probe_timeout)
            try:
                response = client.get(
                    f"{self._mihomo_api_url}/proxies/{quote(node)}/delay",
                    params={
                        "timeout": int(self._probe_timeout * 1000),
                        "url": self._health_check_url,
                    },
                )
                latency_ms = (time.time() - start_time) * 1000

                if response.status_code != 200:
                    return ProbeResult(
                        ok=False,
                        node_name=node,
                        error=f"mihomo delay HTTP {response.status_code}",
                    )

                body = response.json()
                delay = body.get("delay")
                if delay is None:
                    return ProbeResult(
                        ok=False,
                        node_name=node,
                        error="mihomo delay FAIL",
                    )

                return ProbeResult(
                    ok=True,
                    latency_ms=round(float(delay), 2),
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

    def check_signed_exit(
        self,
        min_interval_s: float = 60.0,
        force: bool = False,
    ) -> ProbeResult:
        """签名接口实测：验证当前出口能否正常签名调用 Binance。

        这是发现“出口 IP 不在白名单”（-2015）和签名接口超时的手段，
        mihomo delay API 测公共接口发现不了这两类故障。

        Args:
            min_interval_s: 最小探测间隔（秒），签名请求有 Binance 限流，默认 60
            force: 强制实测（忽略节流与缓存），failover 后复验时使用

        Returns:
            探测结果（走代理实测签名接口）
        """
        if not self._binance_api_key or not self._binance_api_secret:
            return ProbeResult(
                ok=True,
                node_name="signed",
                error="未配置 Binance key，跳过签名实测",
            )

        if not force:
            node_key = "signed_exit"
            last_at = self._last_probe_at.get(node_key, 0.0)
            if time.time() - last_at < min_interval_s:
                cached = self._cache.get(node_key)
                if cached is not None:
                    logger.debug("签名实测节流：返回缓存")
                    return cached

            cached = self._cache.get(node_key)
            if cached is not None and (time.time() - cached.at) < self._cache_ttl_s:
                return cached

        result = self._do_signed_probe()
        self._cache["signed_exit"] = result
        self._last_probe_at["signed_exit"] = time.time()
        return result

    def _do_signed_probe(self) -> ProbeResult:
        """执行一次真实签名请求（走 7890 当前出口）。

        Returns:
            探测结果，ok=False 表示签名接口不可用（IP 不在白名单或超时）
        """
        timestamp_ms = int(time.time() * 1000)
        query = f"timestamp={timestamp_ms}&recvWindow=10000"
        signature = hmac.new(
            self._binance_api_secret.encode("utf-8"),
            query.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        url = f"{self._signed_check_url}?{query}&signature={signature}"
        headers = {"X-MBX-APIKEY": self._binance_api_key}

        try:
            start_time = time.time()
            with httpx.Client(
                proxy=self._proxy_url,
                timeout=self._probe_timeout,
            ) as client:
                response = client.get(url, headers=headers)
            latency_ms = (time.time() - start_time) * 1000

            if response.status_code == 200:
                return ProbeResult(
                    ok=True,
                    latency_ms=round(latency_ms, 2),
                    node_name="signed",
                )

            body = response.text[:300]
            if "-2015" in body or response.status_code == 401:
                return ProbeResult(
                    ok=False,
                    node_name="signed",
                    error=f"出口 IP 不在白名单 (-2015), HTTP {response.status_code}: {body}",
                )
            return ProbeResult(
                ok=False,
                node_name="signed",
                error=f"签名接口 HTTP {response.status_code}: {body}",
            )
        except httpx.TimeoutException:
            return ProbeResult(
                ok=False,
                node_name="signed",
                error="签名接口请求超时",
            )
        except httpx.RequestError as e:
            return ProbeResult(
                ok=False,
                node_name="signed",
                error=f"签名接口请求错误: {e}",
            )
        except Exception as e:
            logger.exception("签名实测异常: %s", e)
            return ProbeResult(
                ok=False,
                node_name="signed",
                error=str(e),
            )

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
