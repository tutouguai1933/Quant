"""Docker容器健康监控服务。

监控所有Docker容器状态，异常时推送通知。
"""

from __future__ import annotations

import asyncio
import json
import logging
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from services.api.app.services.alert_push_service import (
    AlertEventType,
    AlertLevel,
    AlertMessage,
    alert_push_service,
)

logger = logging.getLogger(__name__)


class ContainerStatus(str, Enum):
    """容器状态枚举。"""

    RUNNING = "running"
    EXITED = "exited"
    PAUSED = "paused"
    RESTARTING = "restarting"
    DEAD = "dead"
    UNKNOWN = "unknown"


class HealthStatus(str, Enum):
    """健康状态枚举。"""

    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    STARTING = "starting"
    NONE = "none"


@dataclass
class ContainerInfo:
    """容器信息。"""

    name: str
    status: ContainerStatus
    health: HealthStatus
    container_id: str = ""
    image: str = ""
    error: str = ""
    last_check_at: str = ""
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class MonitorConfig:
    """监控配置。"""

    enabled: bool = True
    interval_seconds: int = 60
    alert_on_unhealthy: bool = True
    alert_on_exit: bool = True
    monitored_containers: list[str] = field(
        default_factory=lambda: [
            "quant-api",
            "quant-web",
            "quant-freqtrade",
            "quant-mihomo",
            "quant-openclaw",
        ]
    )


class HealthMonitorService:
    """Docker容器健康监控服务。"""

    def __init__(self, config: MonitorConfig | None = None) -> None:
        """初始化健康监控服务。

        Args:
            config: 监控配置
        """
        self._config = config or MonitorConfig()
        self._container_status: dict[str, ContainerInfo] = {}
        self._monitoring_task: asyncio.Task | None = None
        self._running = False

    @property
    def config(self) -> MonitorConfig:
        """返回当前配置。"""
        return self._config

    @property
    def is_monitoring(self) -> bool:
        """返回是否正在监控。"""
        return self._running

    def _run_docker_command(self, args: list[str]) -> tuple[bool, str]:
        """执行docker命令。

        Args:
            args: docker命令参数

        Returns:
            (是否成功, 输出或错误信息)
        """
        try:
            result = subprocess.run(
                ["docker"] + args,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                return True, result.stdout.strip()
            return False, result.stderr.strip() or f"exit code: {result.returncode}"
        except subprocess.TimeoutExpired:
            return False, "命令执行超时"
        except FileNotFoundError:
            return False, "docker命令不可用"
        except Exception as e:
            return False, str(e)

    def check_container_health(self, container_name: str) -> ContainerInfo:
        """检查单个容器健康状态。

        Args:
            container_name: 容器名称

        Returns:
            容器信息
        """
        now = datetime.now(timezone.utc).isoformat()

        # 使用docker inspect获取容器详细信息
        success, output = self._run_docker_command([
            "inspect",
            "--format",
            "{{.State.Status}}|{{.State.Health.Status}}|{{.Id}}|{{.Config.Image}}",
            container_name,
        ])

        if not success:
            return ContainerInfo(
                name=container_name,
                status=ContainerStatus.UNKNOWN,
                health=HealthStatus.NONE,
                error=output,
                last_check_at=now,
            )

        try:
            parts = output.split("|")
            status_str = parts[0] if len(parts) > 0 else ""
            health_str = parts[1] if len(parts) > 1 else ""
            container_id = parts[2] if len(parts) > 2 else ""
            image = parts[3] if len(parts) > 3 else ""

            status = ContainerStatus(status_str) if status_str in [s.value for s in ContainerStatus] else ContainerStatus.UNKNOWN
            health = HealthStatus(health_str) if health_str in [h.value for h in HealthStatus] else HealthStatus.NONE

            return ContainerInfo(
                name=container_name,
                status=status,
                health=health,
                container_id=container_id[:12] if container_id else "",
                image=image,
                last_check_at=now,
            )
        except Exception as e:
            return ContainerInfo(
                name=container_name,
                status=ContainerStatus.UNKNOWN,
                health=HealthStatus.NONE,
                error=str(e),
                last_check_at=now,
            )

    def check_all_services(self) -> dict[str, Any]:
        """检查所有服务状态。

        Returns:
            包含所有服务健康状态的字典
        """
        now = datetime.now(timezone.utc).isoformat()
        containers: dict[str, ContainerInfo] = {}
        unhealthy_containers: list[str] = []
        exited_containers: list[str] = []

        for container_name in self._config.monitored_containers:
            info = self.check_container_health(container_name)
            containers[container_name] = info
            self._container_status[container_name] = info

            # 检查异常状态
            if info.status != ContainerStatus.RUNNING:
                exited_containers.append(container_name)
            elif info.health == HealthStatus.UNHEALTHY:
                unhealthy_containers.append(container_name)

        all_healthy = len(unhealthy_containers) == 0 and len(exited_containers) == 0

        return {
            "checked_at": now,
            "all_healthy": all_healthy,
            "containers": {
                name: {
                    "name": info.name,
                    "status": info.status.value,
                    "health": info.health.value,
                    "container_id": info.container_id,
                    "image": info.image,
                    "error": info.error,
                    "last_check_at": info.last_check_at,
                }
                for name, info in containers.items()
            },
            "summary": {
                "total": len(self._config.monitored_containers),
                "running": sum(1 for i in containers.values() if i.status == ContainerStatus.RUNNING),
                "healthy": sum(
                    1
                    for i in containers.values()
                    if i.status == ContainerStatus.RUNNING and i.health in (HealthStatus.HEALTHY, HealthStatus.NONE)
                ),
                "unhealthy": len(unhealthy_containers),
                "exited": len(exited_containers),
            },
            "unhealthy_containers": unhealthy_containers,
            "exited_containers": exited_containers,
        }

    def _push_health_alert(
        self,
        container_name: str,
        issue_type: str,
        details: dict[str, Any],
    ) -> None:
        """推送健康告警。

        Args:
            container_name: 容器名称
            issue_type: 问题类型
            details: 详情
        """
        if issue_type == "unhealthy":
            level = AlertLevel.WARNING
            title = f"容器健康检查失败: {container_name}"
            message = f"容器 {container_name} 健康检查状态为 unhealthy，请检查服务状态。"
        elif issue_type == "exited":
            level = AlertLevel.ERROR
            title = f"容器已停止: {container_name}"
            message = f"容器 {container_name} 已停止运行，请检查服务状态。"
        else:
            level = AlertLevel.WARNING
            title = f"容器异常: {container_name}"
            message = f"容器 {container_name} 存在异常，请检查服务状态。"

        alert = AlertMessage(
            event_type=AlertEventType.NODE_FAILURE,
            level=level,
            title=title,
            message=message,
            details={
                "container_name": container_name,
                "issue_type": issue_type,
                **details,
            },
        )

        try:
            result = alert_push_service.push_sync(alert)
            logger.info("健康告警已推送: %s, 结果: %s", title, result.get("status", "unknown"))
        except Exception as e:
            logger.error("推送健康告警失败: %s", e)

    async def _monitoring_loop(self) -> None:
        """监控循环。"""
        logger.info("健康监控服务已启动，监控间隔: %d秒", self._config.interval_seconds)

        while self._running:
            try:
                result = self.check_all_services()

                # 推送异常告警
                if self._config.alert_on_unhealthy:
                    for name in result.get("unhealthy_containers", []):
                        info = self._container_status.get(name)
                        if info:
                            self._push_health_alert(
                                name,
                                "unhealthy",
                                {
                                    "status": info.status.value,
                                    "health": info.health.value,
                                    "container_id": info.container_id,
                                },
                            )

                if self._config.alert_on_exit:
                    for name in result.get("exited_containers", []):
                        info = self._container_status.get(name)
                        if info:
                            self._push_health_alert(
                                name,
                                "exited",
                                {
                                    "status": info.status.value,
                                    "container_id": info.container_id,
                                },
                            )

                logger.debug(
                    "健康检查完成: 总数=%d, 运行=%d, 不健康=%d, 已停止=%d",
                    result["summary"]["total"],
                    result["summary"]["running"],
                    result["summary"]["unhealthy"],
                    result["summary"]["exited"],
                )

            except Exception as e:
                logger.error("健康监控循环出错: %s", e)

            await asyncio.sleep(self._config.interval_seconds)

    def start_monitoring(self, interval_seconds: int = 60) -> bool:
        """启动定时监控。

        Args:
            interval_seconds: 监控间隔（秒）

        Returns:
            是否成功启动
        """
        if self._running:
            logger.warning("健康监控已在运行中")
            return False

        self._config.interval_seconds = interval_seconds
        self._running = True

        try:
            loop = asyncio.get_running_loop()
            self._monitoring_task = loop.create_task(self._monitoring_loop())
            logger.info("健康监控任务已创建")
            return True
        except RuntimeError:
            logger.warning("没有运行中的事件循环，监控将在后台启动")
            self._running = False
            return False

    def stop_monitoring(self) -> None:
        """停止监控。"""
        self._running = False
        if self._monitoring_task:
            self._monitoring_task.cancel()
            self._monitoring_task = None
        logger.info("健康监控已停止")

    def get_cached_status(self) -> dict[str, Any]:
        """获取缓存的状态。

        Returns:
            缓存的状态字典
        """
        now = datetime.now(timezone.utc).isoformat()

        if not self._container_status:
            return {
                "checked_at": now,
                "all_healthy": True,
                "containers": {},
                "summary": {
                    "total": len(self._config.monitored_containers),
                    "running": 0,
                    "healthy": 0,
                    "unhealthy": 0,
                    "exited": 0,
                },
                "monitoring_active": self._running,
                "interval_seconds": self._config.interval_seconds,
            }

        containers = {
            name: {
                "name": info.name,
                "status": info.status.value,
                "health": info.health.value,
                "container_id": info.container_id,
                "image": info.image,
                "error": info.error,
                "last_check_at": info.last_check_at,
            }
            for name, info in self._container_status.items()
        }

        unhealthy = sum(
            1
            for i in self._container_status.values()
            if i.status == ContainerStatus.RUNNING and i.health == HealthStatus.UNHEALTHY
        )
        exited = sum(1 for i in self._container_status.values() if i.status != ContainerStatus.RUNNING)
        running = sum(1 for i in self._container_status.values() if i.status == ContainerStatus.RUNNING)

        return {
            "checked_at": now,
            "all_healthy": unhealthy == 0 and exited == 0,
            "containers": containers,
            "summary": {
                "total": len(self._config.monitored_containers),
                "running": running,
                "healthy": running - unhealthy,
                "unhealthy": unhealthy,
                "exited": exited,
            },
            "monitoring_active": self._running,
            "interval_seconds": self._config.interval_seconds,
        }


# 全局实例
health_monitor_service = HealthMonitorService()