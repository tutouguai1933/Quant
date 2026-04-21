"""服务健康检查服务。

检查 API、Web 和 Freqtrade 服务的健康状态。
"""

import socket
from datetime import datetime, timezone
from typing import Any
import urllib.request
import urllib.error

from services.api.app.adapters.freqtrade.client import freqtrade_client
from services.api.app.core.settings import Settings


class ServiceHealthService:
    """服务健康检查。"""

    # 默认端口配置
    DEFAULT_PORTS = {
        "api": 9011,
        "web": 9012,
        "freqtrade": 8080,
    }

    # 健康检查超时时间（秒）
    CHECK_TIMEOUT = 5

    def __init__(self, settings: Settings | None = None):
        """初始化健康检查服务。

        Args:
            settings: 应用配置，用于获取运行时模式
        """
        self._settings = settings or Settings.from_env()

    def _check_tcp_port(self, host: str, port: int) -> tuple[bool, str]:
        """检查 TCP 端口是否可达。

        Args:
            host: 主机地址
            port: 端口号

        Returns:
            (是否可达, 错误信息)
        """
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.CHECK_TIMEOUT)
            result = sock.connect_ex((host, port))
            sock.close()
            if result == 0:
                return True, ""
            return False, f"连接被拒绝 (code: {result})"
        except socket.timeout:
            return False, "连接超时"
        except OSError as e:
            return False, str(e)

    def _check_http_endpoint(
        self,
        url: str,
        method: str = "GET",
    ) -> tuple[bool, str]:
        """检查 HTTP 端点是否可达。

        Args:
            url: HTTP URL
            method: HTTP 方法

        Returns:
            (是否可达, 错误信息)
        """
        try:
            request = urllib.request.Request(url, method=method)
            request.add_header("Accept", "application/json")
            with urllib.request.urlopen(request, timeout=self.CHECK_TIMEOUT) as response:
                if 200 <= response.status < 300:
                    return True, ""
                return False, f"HTTP {response.status}"
        except urllib.error.HTTPError as e:
            return False, f"HTTP {e.code}"
        except urllib.error.URLError as e:
            return False, str(e.reason)
        except Exception as e:
            return False, str(e)

    def check_api_health(self) -> dict:
        """检查 API 自身健康状态。

        Returns:
            健康状态字典
        """
        now = datetime.now(timezone.utc).isoformat()
        port = self.DEFAULT_PORTS["api"]
        host = "127.0.0.1"

        # API 服务检查自身，直接返回健康
        # 如果能执行到这里，说明 API 服务正在运行
        return {
            "service": "api",
            "reachable": True,
            "last_check_at": now,
            "error": None,
            "detail": {
                "host": host,
                "port": port,
            },
        }

    def check_web_health(self) -> dict:
        """检查 Web 服务健康状态。

        Returns:
            健康状态字典
        """
        now = datetime.now(timezone.utc).isoformat()
        port = self.DEFAULT_PORTS["web"]
        host = "127.0.0.1"

        # 先尝试 TCP 端口检查
        reachable, error = self._check_tcp_port(host, port)

        if reachable:
            return {
                "service": "web",
                "reachable": True,
                "last_check_at": now,
                "error": None,
                "detail": {
                    "host": host,
                    "port": port,
                },
            }

        return {
            "service": "web",
            "reachable": False,
            "last_check_at": now,
            "error": error,
            "detail": {
                "host": host,
                "port": port,
            },
        }

    def check_freqtrade_health(self) -> dict:
        """检查 Freqtrade 服务健康状态。

        Returns:
            健康状态字典
        """
        now = datetime.now(timezone.utc).isoformat()
        port = self.DEFAULT_PORTS["freqtrade"]
        host = "127.0.0.1"

        # 获取运行时快照来判断 Freqtrade 状态
        try:
            runtime = freqtrade_client.get_runtime_snapshot()
            backend = str(runtime.get("backend", ""))
            connection_status = str(runtime.get("connection_status", ""))

            # 内存后端视为非真实连接
            if backend == "memory":
                return {
                    "service": "freqtrade",
                    "reachable": True,
                    "last_check_at": now,
                    "error": None,
                    "detail": {
                        "host": host,
                        "port": port,
                        "backend": backend,
                        "connection_status": connection_status,
                        "mode": str(runtime.get("mode", "")),
                    },
                }

            # REST 后端检查连接状态
            if connection_status in ("connected", "not_configured"):
                return {
                    "service": "freqtrade",
                    "reachable": True,
                    "last_check_at": now,
                    "error": None,
                    "detail": {
                        "host": host,
                        "port": port,
                        "backend": backend,
                        "connection_status": connection_status,
                        "mode": str(runtime.get("mode", "")),
                    },
                }

            return {
                "service": "freqtrade",
                "reachable": False,
                "last_check_at": now,
                "error": f"连接状态异常: {connection_status}",
                "detail": {
                    "host": host,
                    "port": port,
                    "backend": backend,
                    "connection_status": connection_status,
                },
            }

        except Exception as e:
            return {
                "service": "freqtrade",
                "reachable": False,
                "last_check_at": now,
                "error": str(e),
                "detail": {
                    "host": host,
                    "port": port,
                },
            }

    def get_all_health(self) -> dict:
        """返回所有服务状态。

        Returns:
            包含所有服务健康状态的字典
        """
        now = datetime.now(timezone.utc).isoformat()

        api_health = self.check_api_health()
        web_health = self.check_web_health()
        freqtrade_health = self.check_freqtrade_health()

        all_healthy = (
            api_health.get("reachable", False)
            and web_health.get("reachable", False)
            and freqtrade_health.get("reachable", False)
        )

        return {
            "checked_at": now,
            "all_healthy": all_healthy,
            "services": {
                "api": api_health,
                "web": web_health,
                "freqtrade": freqtrade_health,
            },
            "summary": {
                "total": 3,
                "healthy": sum(
                    1
                    for h in [api_health, web_health, freqtrade_health]
                    if h.get("reachable", False)
                ),
                "unhealthy": sum(
                    1
                    for h in [api_health, web_health, freqtrade_health]
                    if not h.get("reachable", False)
                ),
            },
        }


# 默认实例
service_health_service = ServiceHealthService()