"""系统动作执行器。

执行系统级动作（重启服务）。
"""

import subprocess
from datetime import datetime, timezone
from typing import Any


class SystemActionExecutor:
    """执行系统级动作（重启服务）。"""

    # Docker 容器名称前缀
    CONTAINER_PREFIX = "quant-"

    # 支持重启的服务列表
    SUPPORTED_SERVICES = ("api", "web", "freqtrade")

    # 健康检查等待时间（秒）
    HEALTH_CHECK_WAIT = 10

    def __init__(self) -> None:
        """初始化系统动作执行器。"""
        self._last_restart_results: dict[str, Any] = {}

    def _get_container_name(self, service: str) -> str:
        """获取 Docker 容器名称。

        Args:
            service: 服务名称

        Returns:
            Docker 容器名称
        """
        return f"{self.CONTAINER_PREFIX}{service}"

    def _is_docker_environment(self) -> bool:
        """检查是否在 Docker 环境中运行。

        Returns:
            是否在 Docker 环境中
        """
        # 检查 /.dockerenv 文件是否存在
        try:
            import os
            return os.path.exists("/.dockerenv")
        except OSError:
            return False

    def restart_service(self, service: str) -> dict[str, Any]:
        """重启指定的服务。

        Args:
            service: 服务名称 ("api" | "web" | "freqtrade")

        Returns:
            执行结果 {"success": bool, "message": str, "executed_at": str}
        """
        executed_at = datetime.now(timezone.utc).isoformat()

        # 验证服务名称
        if service not in self.SUPPORTED_SERVICES:
            return {
                "success": False,
                "message": f"不支持的服务: {service}，支持的服务: {self.SUPPORTED_SERVICES}",
                "executed_at": executed_at,
            }

        # API 服务不能通过此方法重启（会导致当前请求中断）
        if service == "api":
            return {
                "success": False,
                "message": "API 服务不支持通过此接口重启",
                "executed_at": executed_at,
            }

        container_name = self._get_container_name(service)

        try:
            # 执行 docker restart 命令
            result = subprocess.run(
                ["docker", "restart", container_name],
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.returncode == 0:
                self._last_restart_results[service] = {
                    "success": True,
                    "message": f"服务 {service} 重启成功",
                    "container": container_name,
                    "executed_at": executed_at,
                }
                return {
                    "success": True,
                    "message": f"服务 {service} 重启成功",
                    "executed_at": executed_at,
                }
            else:
                error_msg = result.stderr.strip() or result.stdout.strip() or "未知错误"
                return {
                    "success": False,
                    "message": f"重启失败: {error_msg}",
                    "executed_at": executed_at,
                }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "message": f"重启超时: 服务 {service} 未在指定时间内响应",
                "executed_at": executed_at,
            }
        except FileNotFoundError:
            return {
                "success": False,
                "message": "Docker 命令不可用，请确认环境配置",
                "executed_at": executed_at,
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"重启异常: {str(e)}",
                "executed_at": executed_at,
            }

    def check_service_health(self, service: str) -> dict[str, Any]:
        """检查服务健康状态。

        通过 docker inspect 检查容器状态。

        Args:
            service: 服务名称

        Returns:
            健康检查结果
        """
        now = datetime.now(timezone.utc).isoformat()

        if service not in self.SUPPORTED_SERVICES:
            return {
                "service": service,
                "healthy": False,
                "error": f"不支持的服务: {service}",
                "checked_at": now,
            }

        container_name = self._get_container_name(service)

        try:
            # 使用 docker inspect 检查容器状态
            result = subprocess.run(
                ["docker", "inspect", "--format", "{{.State.Status}}", container_name],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode != 0:
                return {
                    "service": service,
                    "healthy": False,
                    "error": f"容器不存在或无法访问: {result.stderr.strip()}",
                    "checked_at": now,
                }

            status = result.stdout.strip()

            if status == "running":
                return {
                    "service": service,
                    "healthy": True,
                    "status": status,
                    "error": None,
                    "checked_at": now,
                }
            else:
                return {
                    "service": service,
                    "healthy": False,
                    "status": status,
                    "error": f"容器状态异常: {status}",
                    "checked_at": now,
                }

        except subprocess.TimeoutExpired:
            return {
                "service": service,
                "healthy": False,
                "error": "健康检查超时",
                "checked_at": now,
            }
        except FileNotFoundError:
            return {
                "service": service,
                "healthy": False,
                "error": "Docker 命令不可用",
                "checked_at": now,
            }
        except Exception as e:
            return {
                "service": service,
                "healthy": False,
                "error": str(e),
                "checked_at": now,
            }

    def get_service_status(self) -> dict[str, Any]:
        """获取所有服务的状态。

        Returns:
            所有服务的状态摘要
        """
        now = datetime.now(timezone.utc).isoformat()
        statuses: dict[str, Any] = {}

        for service in self.SUPPORTED_SERVICES:
            health = self.check_service_health(service)
            statuses[service] = health

        all_healthy = all(
            statuses.get(s, {}).get("healthy", False)
            for s in self.SUPPORTED_SERVICES
        )

        return {
            "checked_at": now,
            "all_healthy": all_healthy,
            "services": statuses,
            "summary": {
                "total": len(self.SUPPORTED_SERVICES),
                "healthy": sum(
                    1 for s in self.SUPPORTED_SERVICES
                    if statuses.get(s, {}).get("healthy", False)
                ),
                "unhealthy": sum(
                    1 for s in self.SUPPORTED_SERVICES
                    if not statuses.get(s, {}).get("healthy", False)
                ),
            },
        }


# 默认实例
system_action_executor = SystemActionExecutor()