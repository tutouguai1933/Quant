"""VPN节点自动切换服务。

通过mihomo代理API自动检测节点健康状态并切换到健康的白名单节点。
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# 默认白名单IP列表
DEFAULT_WHITELIST_IPS = [
    "39.106.11.65",   # 服务器IP
    "202.85.76.66",   # 白名单IP
    "154.31.113.7",   # 白名单IP
    "154.3.37.169",   # 白名单IP
]

# 默认可用节点
DEFAULT_AVAILABLE_NODES = [
    # 香港节点
    "香港¹",
    "香港²",
    "香港³",
    "香港⁴",
    # 日本节点
    "日本¹",
    "日本²",
    "日本³",
    "日本⁴",
    # 美国节点
    "美国¹",
    "美国²",
]

# 节点优先级（按白名单IP对应关系排序）
NODE_PRIORITY = {
    "202.85.76.66": ["香港¹", "香港²", "香港³", "香港⁴"],
    "154.31.113.7": ["日本¹", "日本²", "日本³", "日本⁴"],
    "154.3.37.169": ["美国¹", "美国²"],
}


class NodeHealthStatus(str, Enum):
    """节点健康状态。"""

    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class VPNConfig:
    """VPN切换配置。"""

    mihomo_api_url: str = "http://mihomo:9090"
    mihomo_proxy_url: str = "http://mihomo:7890"
    health_check_url: str = "https://api.binance.com/api/v3/ping"
    health_check_timeout: float = 10.0
    health_check_interval: int = 60  # 秒
    whitelist_ips: list[str] = field(default_factory=lambda: DEFAULT_WHITELIST_IPS)
    available_nodes: list[str] = field(default_factory=lambda: DEFAULT_AVAILABLE_NODES)
    ip_check_url: str = "https://api.ipify.org?format=json"

    @classmethod
    def from_env(cls) -> "VPNConfig":
        """从环境变量读取配置。"""
        mihomo_api_url = os.getenv("QUANT_MIHOMO_API_URL", "http://mihomo:9090")
        mihomo_proxy_url = os.getenv("QUANT_MIHOMO_PROXY_URL", "http://mihomo:7890")
        health_check_url = os.getenv("QUANT_VPN_HEALTH_CHECK_URL", "https://api.binance.com/api/v3/ping")
        health_check_timeout = float(os.getenv("QUANT_VPN_HEALTH_CHECK_TIMEOUT", "10.0"))
        health_check_interval = int(os.getenv("QUANT_VPN_HEALTH_CHECK_INTERVAL", "60"))

        # 解析白名单IP列表
        whitelist_ips_str = os.getenv("QUANT_VPN_WHITELIST_IPS", "")
        if whitelist_ips_str:
            whitelist_ips = [ip.strip() for ip in whitelist_ips_str.split(",") if ip.strip()]
        else:
            whitelist_ips = DEFAULT_WHITELIST_IPS

        # 解析可用节点列表
        available_nodes_str = os.getenv("QUANT_VPN_AVAILABLE_NODES", "")
        if available_nodes_str:
            available_nodes = [node.strip() for node in available_nodes_str.split(",") if node.strip()]
        else:
            available_nodes = DEFAULT_AVAILABLE_NODES

        return cls(
            mihomo_api_url=mihomo_api_url,
            mihomo_proxy_url=mihomo_proxy_url,
            health_check_url=health_check_url,
            health_check_timeout=health_check_timeout,
            health_check_interval=health_check_interval,
            whitelist_ips=whitelist_ips,
            available_nodes=available_nodes,
        )


@dataclass
class NodeHealthResult:
    """节点健康检查结果。"""

    node_name: str
    status: NodeHealthStatus
    exit_ip: str | None = None
    is_whitelisted: bool = False
    latency_ms: float | None = None
    error_message: str | None = None
    checked_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        """转换为字典。"""
        return {
            "node_name": self.node_name,
            "status": self.status.value,
            "exit_ip": self.exit_ip,
            "is_whitelisted": self.is_whitelisted,
            "latency_ms": self.latency_ms,
            "error_message": self.error_message,
            "checked_at": self.checked_at,
        }


@dataclass
class SwitchResult:
    """节点切换结果。"""

    success: bool
    previous_node: str | None = None
    current_node: str | None = None
    exit_ip: str | None = None
    is_whitelisted: bool = False
    error_message: str | None = None
    switched_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        """转换为字典。"""
        return {
            "success": self.success,
            "previous_node": self.previous_node,
            "current_node": self.current_node,
            "exit_ip": self.exit_ip,
            "is_whitelisted": self.is_whitelisted,
            "error_message": self.error_message,
            "switched_at": self.switched_at,
        }


class VPNSwitchService:
    """VPN节点自动切换服务。"""

    def __init__(self, config: VPNConfig | None = None) -> None:
        """初始化VPN切换服务。

        Args:
            config: VPN配置，默认从环境变量读取
        """
        self._config = config or VPNConfig.from_env()
        self._http_client: httpx.AsyncClient | None = None
        self._sync_client: httpx.Client | None = None
        self._last_health_check: dict[str, NodeHealthResult] = {}
        self._current_node: str | None = None

    @property
    def config(self) -> VPNConfig:
        """返回当前配置。"""
        return self._config

    @property
    def current_node(self) -> str | None:
        """返回当前节点名称。"""
        return self._current_node

    def _get_sync_client(self, use_proxy: bool = True) -> httpx.Client:
        """获取同步HTTP客户端。

        Args:
            use_proxy: 是否使用代理
        """
        proxies = self._config.mihomo_proxy_url if use_proxy else None
        return httpx.Client(
            timeout=self._config.health_check_timeout,
            proxies=proxies,
        )

    async def _get_async_client(self, use_proxy: bool = True) -> httpx.AsyncClient:
        """获取异步HTTP客户端。

        Args:
            use_proxy: 是否使用代理
        """
        proxies = self._config.mihomo_proxy_url if use_proxy else None
        return httpx.AsyncClient(
            timeout=self._config.health_check_timeout,
            proxies=proxies,
        )

    def check_node_health_sync(self) -> NodeHealthResult:
        """同步检查当前节点健康状态。

        通过代理访问Binance API来检测节点是否可用。
        """
        import time

        try:
            start_time = time.time()
            client = self._get_sync_client(use_proxy=True)
            response = client.get(self._config.health_check_url)
            latency_ms = (time.time() - start_time) * 1000

            if response.status_code == 200:
                # 获取出口IP
                exit_ip = self.get_current_exit_ip_sync()
                is_whitelisted = self.is_ip_in_whitelist(exit_ip) if exit_ip else False

                # 获取当前节点名称
                current_node = self._get_current_node_name_sync()

                result = NodeHealthResult(
                    node_name=current_node or "unknown",
                    status=NodeHealthStatus.HEALTHY,
                    exit_ip=exit_ip,
                    is_whitelisted=is_whitelisted,
                    latency_ms=round(latency_ms, 2),
                )
                self._last_health_check[current_node or "unknown"] = result
                return result
            else:
                current_node = self._get_current_node_name_sync()
                return NodeHealthResult(
                    node_name=current_node or "unknown",
                    status=NodeHealthStatus.UNHEALTHY,
                    error_message=f"HTTP {response.status_code}",
                )

        except httpx.TimeoutException:
            current_node = self._get_current_node_name_sync()
            logger.warning("节点健康检查超时")
            return NodeHealthResult(
                node_name=current_node or "unknown",
                status=NodeHealthStatus.UNHEALTHY,
                error_message="请求超时",
            )
        except httpx.RequestError as e:
            current_node = self._get_current_node_name_sync()
            logger.error("节点健康检查网络错误: %s", e)
            return NodeHealthResult(
                node_name=current_node or "unknown",
                status=NodeHealthStatus.UNHEALTHY,
                error_message=str(e),
            )
        except Exception as e:
            logger.exception("节点健康检查异常: %s", e)
            return NodeHealthResult(
                node_name="unknown",
                status=NodeHealthStatus.UNKNOWN,
                error_message=str(e),
            )

    async def check_node_health(self) -> NodeHealthResult:
        """异步检查当前节点健康状态。

        通过代理访问Binance API来检测节点是否可用。
        """
        import time

        try:
            start_time = time.time()
            client = await self._get_async_client(use_proxy=True)
            response = await client.get(self._config.health_check_url)
            latency_ms = (time.time() - start_time) * 1000

            if response.status_code == 200:
                # 获取出口IP
                exit_ip = await self.get_current_exit_ip()
                is_whitelisted = self.is_ip_in_whitelist(exit_ip) if exit_ip else False

                # 获取当前节点名称
                current_node = await self._get_current_node_name()

                result = NodeHealthResult(
                    node_name=current_node or "unknown",
                    status=NodeHealthStatus.HEALTHY,
                    exit_ip=exit_ip,
                    is_whitelisted=is_whitelisted,
                    latency_ms=round(latency_ms, 2),
                )
                self._last_health_check[current_node or "unknown"] = result
                return result
            else:
                current_node = await self._get_current_node_name()
                return NodeHealthResult(
                    node_name=current_node or "unknown",
                    status=NodeHealthStatus.UNHEALTHY,
                    error_message=f"HTTP {response.status_code}",
                )

        except httpx.TimeoutException:
            current_node = await self._get_current_node_name()
            logger.warning("节点健康检查超时")
            return NodeHealthResult(
                node_name=current_node or "unknown",
                status=NodeHealthStatus.UNHEALTHY,
                error_message="请求超时",
            )
        except httpx.RequestError as e:
            current_node = await self._get_current_node_name()
            logger.error("节点健康检查网络错误: %s", e)
            return NodeHealthResult(
                node_name=current_node or "unknown",
                status=NodeHealthStatus.UNHEALTHY,
                error_message=str(e),
            )
        except Exception as e:
            logger.exception("节点健康检查异常: %s", e)
            return NodeHealthResult(
                node_name="unknown",
                status=NodeHealthStatus.UNKNOWN,
                error_message=str(e),
            )

    def get_current_exit_ip_sync(self) -> str | None:
        """同步获取当前出口IP。"""
        try:
            client = self._get_sync_client(use_proxy=True)
            response = client.get(self._config.ip_check_url)
            if response.status_code == 200:
                data = response.json()
                return data.get("ip")
            return None
        except Exception as e:
            logger.error("获取出口IP失败: %s", e)
            return None

    async def get_current_exit_ip(self) -> str | None:
        """异步获取当前出口IP。"""
        try:
            client = await self._get_async_client(use_proxy=True)
            response = await client.get(self._config.ip_check_url)
            if response.status_code == 200:
                data = response.json()
                return data.get("ip")
            return None
        except Exception as e:
            logger.error("获取出口IP失败: %s", e)
            return None

    def is_ip_in_whitelist(self, ip: str | None) -> bool:
        """检查IP是否在白名单中。

        Args:
            ip: 要检查的IP地址

        Returns:
            是否在白名单中
        """
        if not ip:
            return False
        return ip in self._config.whitelist_ips

    def _get_current_node_name_sync(self) -> str | None:
        """同步获取当前选择的节点名称。"""
        try:
            client = self._get_sync_client(use_proxy=False)
            response = client.get(f"{self._config.mihomo_api_url}/proxies/PROXY")
            if response.status_code == 200:
                data = response.json()
                self._current_node = data.get("now")
                return self._current_node
            return None
        except Exception as e:
            logger.error("获取当前节点名称失败: %s", e)
            return None

    async def _get_current_node_name(self) -> str | None:
        """异步获取当前选择的节点名称。"""
        try:
            client = await self._get_async_client(use_proxy=False)
            response = await client.get(f"{self._config.mihomo_api_url}/proxies/PROXY")
            if response.status_code == 200:
                data = response.json()
                self._current_node = data.get("now")
                return self._current_node
            return None
        except Exception as e:
            logger.error("获取当前节点名称失败: %s", e)
            return None

    def _get_available_nodes_sync(self) -> list[str]:
        """同步获取所有可用节点列表。"""
        try:
            client = self._get_sync_client(use_proxy=False)
            response = client.get(f"{self._config.mihomo_api_url}/proxies/PROXY")
            if response.status_code == 200:
                data = response.json()
                return data.get("all", [])
            return []
        except Exception as e:
            logger.error("获取可用节点列表失败: %s", e)
            return []

    async def _get_available_nodes(self) -> list[str]:
        """异步获取所有可用节点列表。"""
        try:
            client = await self._get_async_client(use_proxy=False)
            response = await client.get(f"{self._config.mihomo_api_url}/proxies/PROXY")
            if response.status_code == 200:
                data = response.json()
                return data.get("all", [])
            return []
        except Exception as e:
            logger.error("获取可用节点列表失败: %s", e)
            return []

    def switch_node_sync(self, node_name: str) -> SwitchResult:
        """同步切换到指定节点。

        Args:
            node_name: 目标节点名称

        Returns:
            切换结果
        """
        try:
            # 获取当前节点
            previous_node = self._get_current_node_name_sync()

            # 检查节点是否可用
            available_nodes = self._get_available_nodes_sync()
            if node_name not in available_nodes:
                return SwitchResult(
                    success=False,
                    previous_node=previous_node,
                    error_message=f"节点 {node_name} 不在可用列表中",
                )

            # 通过mihomo API切换节点
            client = self._get_sync_client(use_proxy=False)
            response = client.put(
                f"{self._config.mihomo_api_url}/proxies/PROXY",
                json={"name": node_name},
            )

            if response.status_code == 204 or response.status_code == 200:
                self._current_node = node_name

                # 验证切换后的出口IP
                exit_ip = self.get_current_exit_ip_sync()
                is_whitelisted = self.is_ip_in_whitelist(exit_ip)

                logger.info(
                    "VPN节点切换成功: %s -> %s, 出口IP: %s (白名单: %s)",
                    previous_node,
                    node_name,
                    exit_ip,
                    is_whitelisted,
                )

                return SwitchResult(
                    success=True,
                    previous_node=previous_node,
                    current_node=node_name,
                    exit_ip=exit_ip,
                    is_whitelisted=is_whitelisted,
                )
            else:
                error_msg = f"切换失败: HTTP {response.status_code}"
                logger.error("VPN节点切换失败: %s", error_msg)
                return SwitchResult(
                    success=False,
                    previous_node=previous_node,
                    error_message=error_msg,
                )

        except httpx.RequestError as e:
            logger.error("VPN节点切换网络错误: %s", e)
            return SwitchResult(
                success=False,
                previous_node=self._current_node,
                error_message=str(e),
            )
        except Exception as e:
            logger.exception("VPN节点切换异常: %s", e)
            return SwitchResult(
                success=False,
                previous_node=self._current_node,
                error_message=str(e),
            )

    async def switch_node(self, node_name: str) -> SwitchResult:
        """异步切换到指定节点。

        Args:
            node_name: 目标节点名称

        Returns:
            切换结果
        """
        try:
            # 获取当前节点
            previous_node = await self._get_current_node_name()

            # 检查节点是否可用
            available_nodes = await self._get_available_nodes()
            if node_name not in available_nodes:
                return SwitchResult(
                    success=False,
                    previous_node=previous_node,
                    error_message=f"节点 {node_name} 不在可用列表中",
                )

            # 通过mihomo API切换节点
            client = await self._get_async_client(use_proxy=False)
            response = await client.put(
                f"{self._config.mihomo_api_url}/proxies/PROXY",
                json={"name": node_name},
            )

            if response.status_code == 204 or response.status_code == 200:
                self._current_node = node_name

                # 验证切换后的出口IP
                exit_ip = await self.get_current_exit_ip()
                is_whitelisted = self.is_ip_in_whitelist(exit_ip)

                logger.info(
                    "VPN节点切换成功: %s -> %s, 出口IP: %s (白名单: %s)",
                    previous_node,
                    node_name,
                    exit_ip,
                    is_whitelisted,
                )

                return SwitchResult(
                    success=True,
                    previous_node=previous_node,
                    current_node=node_name,
                    exit_ip=exit_ip,
                    is_whitelisted=is_whitelisted,
                )
            else:
                error_msg = f"切换失败: HTTP {response.status_code}"
                logger.error("VPN节点切换失败: %s", error_msg)
                return SwitchResult(
                    success=False,
                    previous_node=previous_node,
                    error_message=error_msg,
                )

        except httpx.RequestError as e:
            logger.error("VPN节点切换网络错误: %s", e)
            return SwitchResult(
                success=False,
                previous_node=self._current_node,
                error_message=str(e),
            )
        except Exception as e:
            logger.exception("VPN节点切换异常: %s", e)
            return SwitchResult(
                success=False,
                previous_node=self._current_node,
                error_message=str(e),
            )

    def auto_switch_to_healthy_node_sync(self) -> SwitchResult:
        """同步自动切换到健康的白名单节点。

        按优先级尝试切换到健康的白名单节点：
        1. 首先检查当前节点是否健康且在白名单
        2. 如果不健康，按优先级尝试其他节点
        3. 找到第一个健康的白名单节点后切换

        Returns:
            切换结果
        """
        from services.api.app.services.alert_push_service import (
            AlertEventType,
            AlertLevel,
            AlertMessage,
            alert_push_service,
        )

        # 1. 检查当前节点健康状态
        health_result = self.check_node_health_sync()

        if health_result.status == NodeHealthStatus.HEALTHY and health_result.is_whitelisted:
            logger.info(
                "当前节点 %s 健康，出口IP %s 在白名单中，无需切换",
                health_result.node_name,
                health_result.exit_ip,
            )
            return SwitchResult(
                success=True,
                current_node=health_result.node_name,
                exit_ip=health_result.exit_ip,
                is_whitelisted=True,
            )

        # 2. 当前节点不健康或不在白名单，尝试切换
        logger.warning(
            "当前节点 %s 状态: %s, IP: %s, 白名单: %s, 开始尝试切换...",
            health_result.node_name,
            health_result.status.value,
            health_result.exit_ip,
            health_result.is_whitelisted,
        )

        # 3. 获取可用节点列表
        available_nodes = self._get_available_nodes_sync()
        if not available_nodes:
            error_msg = "无法获取可用节点列表"
            logger.error(error_msg)
            self._send_switch_failure_alert(error_msg, health_result)
            return SwitchResult(
                success=False,
                previous_node=health_result.node_name,
                error_message=error_msg,
            )

        # 4. 按优先级尝试节点
        tried_nodes: list[str] = []
        for node in self._config.available_nodes:
            if node not in available_nodes:
                continue
            if node == health_result.node_name:
                continue  # 跳过当前已失败的节点

            tried_nodes.append(node)
            logger.info("尝试切换到节点: %s", node)

            switch_result = self.switch_node_sync(node)
            if not switch_result.success:
                logger.warning("切换到节点 %s 失败: %s", node, switch_result.error_message)
                continue

            # 验证新节点的健康状态
            new_health = self.check_node_health_sync()
            if new_health.status == NodeHealthStatus.HEALTHY and new_health.is_whitelisted:
                logger.info(
                    "成功切换到健康的白名单节点 %s, 出口IP: %s",
                    node,
                    new_health.exit_ip,
                )
                self._send_switch_success_alert(switch_result, health_result)
                return switch_result

            logger.warning(
                "节点 %s 切换成功但不满足条件 (健康: %s, 白名单: %s)",
                node,
                new_health.status.value,
                new_health.is_whitelisted,
            )

        # 5. 所有节点都尝试失败
        error_msg = f"所有节点尝试失败，已尝试: {tried_nodes}"
        logger.error(error_msg)
        self._send_switch_failure_alert(error_msg, health_result)
        return SwitchResult(
            success=False,
            previous_node=health_result.node_name,
            error_message=error_msg,
        )

    async def auto_switch_to_healthy_node(self) -> SwitchResult:
        """异步自动切换到健康的白名单节点。

        按优先级尝试切换到健康的白名单节点：
        1. 首先检查当前节点是否健康且在白名单
        2. 如果不健康，按优先级尝试其他节点
        3. 找到第一个健康的白名单节点后切换

        Returns:
            切换结果
        """
        from services.api.app.services.alert_push_service import (
            AlertEventType,
            AlertLevel,
            AlertMessage,
            alert_push_service,
        )

        # 1. 检查当前节点健康状态
        health_result = await self.check_node_health()

        if health_result.status == NodeHealthStatus.HEALTHY and health_result.is_whitelisted:
            logger.info(
                "当前节点 %s 健康，出口IP %s 在白名单中，无需切换",
                health_result.node_name,
                health_result.exit_ip,
            )
            return SwitchResult(
                success=True,
                current_node=health_result.node_name,
                exit_ip=health_result.exit_ip,
                is_whitelisted=True,
            )

        # 2. 当前节点不健康或不在白名单，尝试切换
        logger.warning(
            "当前节点 %s 状态: %s, IP: %s, 白名单: %s, 开始尝试切换...",
            health_result.node_name,
            health_result.status.value,
            health_result.exit_ip,
            health_result.is_whitelisted,
        )

        # 3. 获取可用节点列表
        available_nodes = await self._get_available_nodes()
        if not available_nodes:
            error_msg = "无法获取可用节点列表"
            logger.error(error_msg)
            await self._send_switch_failure_alert_async(error_msg, health_result)
            return SwitchResult(
                success=False,
                previous_node=health_result.node_name,
                error_message=error_msg,
            )

        # 4. 按优先级尝试节点
        tried_nodes: list[str] = []
        for node in self._config.available_nodes:
            if node not in available_nodes:
                continue
            if node == health_result.node_name:
                continue  # 跳过当前已失败的节点

            tried_nodes.append(node)
            logger.info("尝试切换到节点: %s", node)

            switch_result = await self.switch_node(node)
            if not switch_result.success:
                logger.warning("切换到节点 %s 失败: %s", node, switch_result.error_message)
                continue

            # 验证新节点的健康状态
            new_health = await self.check_node_health()
            if new_health.status == NodeHealthStatus.HEALTHY and new_health.is_whitelisted:
                logger.info(
                    "成功切换到健康的白名单节点 %s, 出口IP: %s",
                    node,
                    new_health.exit_ip,
                )
                await self._send_switch_success_alert_async(switch_result, health_result)
                return switch_result

            logger.warning(
                "节点 %s 切换成功但不满足条件 (健康: %s, 白名单: %s)",
                node,
                new_health.status.value,
                new_health.is_whitelisted,
            )

        # 5. 所有节点都尝试失败
        error_msg = f"所有节点尝试失败，已尝试: {tried_nodes}"
        logger.error(error_msg)
        await self._send_switch_failure_alert_async(error_msg, health_result)
        return SwitchResult(
            success=False,
            previous_node=health_result.node_name,
            error_message=error_msg,
        )

    def _send_switch_success_alert(
        self,
        switch_result: SwitchResult,
        previous_health: NodeHealthResult,
    ) -> None:
        """发送切换成功告警。"""
        try:
            alert_push_service.push_sync(
                AlertMessage(
                    event_type=AlertEventType.NODE_FAILURE,
                    level=AlertLevel.WARNING,
                    title="VPN节点自动切换成功",
                    message=(
                        f"已从故障节点 {previous_health.node_name} 切换到 {switch_result.current_node}，"
                        f"新出口IP: {switch_result.exit_ip}"
                    ),
                    details={
                        "previous_node": previous_health.node_name,
                        "previous_status": previous_health.status.value,
                        "previous_ip": previous_health.exit_ip,
                        "new_node": switch_result.current_node,
                        "new_ip": switch_result.exit_ip,
                        "is_whitelisted": switch_result.is_whitelisted,
                    },
                )
            )
        except Exception as e:
            logger.warning("发送VPN切换成功告警失败: %s", e)

    async def _send_switch_success_alert_async(
        self,
        switch_result: SwitchResult,
        previous_health: NodeHealthResult,
    ) -> None:
        """异步发送切换成功告警。"""
        try:
            await alert_push_service.push_async(
                AlertMessage(
                    event_type=AlertEventType.NODE_FAILURE,
                    level=AlertLevel.WARNING,
                    title="VPN节点自动切换成功",
                    message=(
                        f"已从故障节点 {previous_health.node_name} 切换到 {switch_result.current_node}，"
                        f"新出口IP: {switch_result.exit_ip}"
                    ),
                    details={
                        "previous_node": previous_health.node_name,
                        "previous_status": previous_health.status.value,
                        "previous_ip": previous_health.exit_ip,
                        "new_node": switch_result.current_node,
                        "new_ip": switch_result.exit_ip,
                        "is_whitelisted": switch_result.is_whitelisted,
                    },
                )
            )
        except Exception as e:
            logger.warning("发送VPN切换成功告警失败: %s", e)

    def _send_switch_failure_alert(
        self,
        error_message: str,
        health_result: NodeHealthResult,
    ) -> None:
        """发送切换失败告警。"""
        try:
            alert_push_service.push_sync(
                AlertMessage(
                    event_type=AlertEventType.NODE_FAILURE,
                    level=AlertLevel.ERROR,
                    title="VPN节点自动切换失败",
                    message=f"无法切换到健康的白名单节点: {error_message}",
                    details={
                        "current_node": health_result.node_name,
                        "current_status": health_result.status.value,
                        "current_ip": health_result.exit_ip,
                        "error": error_message,
                    },
                )
            )
        except Exception as e:
            logger.warning("发送VPN切换失败告警失败: %s", e)

    async def _send_switch_failure_alert_async(
        self,
        error_message: str,
        health_result: NodeHealthResult,
    ) -> None:
        """异步发送切换失败告警。"""
        try:
            await alert_push_service.push_async(
                AlertMessage(
                    event_type=AlertEventType.NODE_FAILURE,
                    level=AlertLevel.ERROR,
                    title="VPN节点自动切换失败",
                    message=f"无法切换到健康的白名单节点: {error_message}",
                    details={
                        "current_node": health_result.node_name,
                        "current_status": health_result.status.value,
                        "current_ip": health_result.exit_ip,
                        "error": error_message,
                    },
                )
            )
        except Exception as e:
            logger.warning("发送VPN切换失败告警失败: %s", e)

    def get_last_health_check(self) -> dict[str, Any]:
        """获取最近一次健康检查结果。"""
        return {k: v.to_dict() for k, v in self._last_health_check.items()}

    def close(self) -> None:
        """关闭客户端连接。"""
        if self._sync_client:
            self._sync_client.close()
            self._sync_client = None

    async def aclose(self) -> None:
        """异步关闭客户端连接。"""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
        self.close()


# 全局实例
vpn_switch_service = VPNSwitchService()