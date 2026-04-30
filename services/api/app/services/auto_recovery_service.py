"""自动恢复服务。

监控服务健康状态，尝试自动恢复异常服务。
支持 Docker 容器重启、恢复冷却时间、恢复历史记录。
"""
from __future__ import annotations

import asyncio
import logging
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class RecoveryStatus(str, Enum):
    """恢复状态枚举。"""

    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    COOLING = "cooling"
    SILENCED = "silenced"


class RecoveryAction(str, Enum):
    """恢复动作类型。"""

    RESTART_CONTAINER = "restart_container"
    HEALTH_CHECK = "health_check"
    MANUAL_INTERVENTION = "manual_intervention"
    NO_ACTION = "no_action"


@dataclass
class RecoveryRecord:
    """恢复记录。"""

    service_name: str
    action: RecoveryAction
    status: RecoveryStatus
    timestamp: str = ""
    duration_ms: int = 0
    error: str = ""
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class RecoveryConfig:
    """恢复配置。"""

    cooldown_seconds: int = 300  # 冷却时间，防止频繁重启
    max_recovery_attempts: int = 3  # 最大恢复尝试次数
    recovery_timeout_seconds: int = 60  # 单次恢复超时时间
    enabled_services: list[str] = field(
        default_factory=lambda: [
            "quant-api",
            "quant-web",
            "quant-freqtrade",
            "quant-mihomo",
            "quant-openclaw",
        ]
    )
    auto_recovery_enabled: bool = True


@dataclass
class SilenceRecord:
    """静默记录。"""

    alert_key: str
    duration_seconds: int
    started_at: str
    reason: str = ""
    expires_at: str = ""


class AutoRecoveryService:
    """自动恢复服务。"""

    def __init__(self, config: RecoveryConfig | None = None) -> None:
        """初始化自动恢复服务。

        Args:
            config: 恢复配置
        """
        self._config = config or RecoveryConfig()
        self._recovery_history: list[RecoveryRecord] = []
        self._last_recovery_time: dict[str, str] = {}
        self._recovery_attempts: dict[str, int] = {}
        self._silences: dict[str, SilenceRecord] = {}
        self._recovery_task: asyncio.Task | None = None
        self._running = False

    @property
    def config(self) -> RecoveryConfig:
        """返回当前配置。"""
        return self._config

    @property
    def is_running(self) -> bool:
        """返回是否正在运行恢复监控。"""
        return self._running

    def _run_docker_command(self, args: list[str]) -> tuple[bool, str]:
        """执行 docker 命令。

        Args:
            args: docker 命令参数

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
            return False, "docker 命令不可用"
        except Exception as e:
            return False, str(e)

    def check_service_health(self, service_name: str) -> dict[str, Any]:
        """检查服务健康状态。

        Args:
            service_name: 服务名称

        Returns:
            服务健康状态字典
        """
        now = datetime.now(timezone.utc).isoformat()

        success, output = self._run_docker_command([
            "inspect",
            "--format",
            "{{.State.Status}}|{{.State.Health.Status}}|{{.Id}}",
            service_name,
        ])

        if not success:
            return {
                "service_name": service_name,
                "status": "unknown",
                "health": "none",
                "healthy": False,
                "error": output,
                "checked_at": now,
            }

        try:
            parts = output.split("|")
            status = parts[0] if len(parts) > 0 else "unknown"
            health = parts[1] if len(parts) > 1 else "none"
            container_id = parts[2][:12] if len(parts) > 2 else ""

            is_healthy = status == "running" and health in ("healthy", "none")

            return {
                "service_name": service_name,
                "status": status,
                "health": health,
                "container_id": container_id,
                "healthy": is_healthy,
                "checked_at": now,
                "error": None,
            }
        except Exception as e:
            return {
                "service_name": service_name,
                "status": "unknown",
                "healthy": False,
                "error": str(e),
                "checked_at": now,
            }

    def check_all_services_health(self) -> dict[str, Any]:
        """检查所有服务健康状态。

        Returns:
            包含所有服务健康状态的字典
        """
        now = datetime.now(timezone.utc).isoformat()
        services: dict[str, dict[str, Any]] = {}
        unhealthy_services: list[str] = []

        for service_name in self._config.enabled_services:
            health = self.check_service_health(service_name)
            services[service_name] = health
            if not health.get("healthy", False):
                unhealthy_services.append(service_name)

        return {
            "checked_at": now,
            "all_healthy": len(unhealthy_services) == 0,
            "services": services,
            "unhealthy_services": unhealthy_services,
            "summary": {
                "total": len(self._config.enabled_services),
                "healthy": len(self._config.enabled_services) - len(unhealthy_services),
                "unhealthy": len(unhealthy_services),
            },
        }

    def _is_in_cooldown(self, service_name: str) -> bool:
        """检查服务是否在冷却期。

        Args:
            service_name: 服务名称

        Returns:
            是否在冷却期
        """
        last_recovery = self._last_recovery_time.get(service_name)
        if not last_recovery:
            return False

        try:
            last_time = datetime.fromisoformat(last_recovery)
            now = datetime.now(timezone.utc)
            elapsed = (now - last_time).total_seconds()
            return elapsed < self._config.cooldown_seconds
        except Exception:
            return False

    def _get_remaining_cooldown(self, service_name: str) -> int:
        """获取剩余冷却时间。

        Args:
            service_name: 服务名称

        Returns:
            剩余冷却秒数
        """
        last_recovery = self._last_recovery_time.get(service_name)
        if not last_recovery:
            return 0

        try:
            last_time = datetime.fromisoformat(last_recovery)
            now = datetime.now(timezone.utc)
            elapsed = (now - last_time).total_seconds()
            remaining = self._config.cooldown_seconds - elapsed
            return max(0, int(remaining))
        except Exception:
            return 0

    def attempt_recovery(self, service_name: str, force: bool = False) -> RecoveryRecord:
        """尝试恢复服务。

        Args:
            service_name: 服务名称
            force: 是否强制恢复（忽略冷却时间）

        Returns:
            恢复记录
        """
        now = datetime.now(timezone.utc).isoformat()
        start_time = datetime.now(timezone.utc)

        if service_name not in self._config.enabled_services:
            return RecoveryRecord(
                service_name=service_name,
                action=RecoveryAction.NO_ACTION,
                status=RecoveryStatus.SKIPPED,
                timestamp=now,
                error="服务不在允许恢复列表中",
            )

        if not force and self._is_in_cooldown(service_name):
            remaining = self._get_remaining_cooldown(service_name)
            return RecoveryRecord(
                service_name=service_name,
                action=RecoveryAction.NO_ACTION,
                status=RecoveryStatus.COOLING,
                timestamp=now,
                error=f"服务在冷却期，剩余 {remaining} 秒",
                details={"remaining_cooldown_seconds": remaining},
            )

        if not self._config.auto_recovery_enabled and not force:
            return RecoveryRecord(
                service_name=service_name,
                action=RecoveryAction.NO_ACTION,
                status=RecoveryStatus.SKIPPED,
                timestamp=now,
                error="自动恢复未启用",
            )

        attempts = self._recovery_attempts.get(service_name, 0)
        if attempts >= self._config.max_recovery_attempts and not force:
            return RecoveryRecord(
                service_name=service_name,
                action=RecoveryAction.NO_ACTION,
                status=RecoveryStatus.SKIPPED,
                timestamp=now,
                error=f"已达到最大恢复尝试次数 ({self._config.max_recovery_attempts})",
                details={"attempts": attempts},
            )

        logger.info("尝试恢复服务: %s (尝试次数: %d)", service_name, attempts + 1)

        success, output = self._run_docker_command(["restart", service_name])

        end_time = datetime.now(timezone.utc)
        duration_ms = int((end_time - start_time).total_seconds() * 1000)

        record = RecoveryRecord(
            service_name=service_name,
            action=RecoveryAction.RESTART_CONTAINER,
            timestamp=now,
            duration_ms=duration_ms,
            details={
                "attempt_number": attempts + 1,
                "docker_output": output[:200] if output else None,
            },
        )

        if success:
            record.status = RecoveryStatus.SUCCESS
            self._recovery_attempts[service_name] = 0
            self._last_recovery_time[service_name] = now
            logger.info("服务恢复成功: %s, 耗时 %dms", service_name, duration_ms)
        else:
            record.status = RecoveryStatus.FAILED
            record.error = output
            self._recovery_attempts[service_name] = attempts + 1
            logger.error("服务恢复失败: %s, 错误: %s", service_name, output)

        self._recovery_history.append(record)
        return record

    def manual_recovery(self, service_name: str) -> RecoveryRecord:
        """手动触发恢复。

        Args:
            service_name: 服务名称

        Returns:
            恢复记录
        """
        return self.attempt_recovery(service_name, force=True)

    def get_recovery_history(self, limit: int = 50) -> list[dict[str, Any]]:
        """获取恢复历史。

        Args:
            limit: 返回数量限制

        Returns:
            恢复历史列表
        """
        history = self._recovery_history[-limit:]
        return [
            {
                "service_name": r.service_name,
                "action": r.action.value,
                "status": r.status.value,
                "timestamp": r.timestamp,
                "duration_ms": r.duration_ms,
                "error": r.error,
                "details": r.details,
            }
            for r in history
        ]

    def reset_recovery_attempts(self, service_name: str) -> None:
        """重置恢复尝试次数。

        Args:
            service_name: 服务名称
        """
        if service_name in self._recovery_attempts:
            del self._recovery_attempts[service_name]
            logger.info("重置服务恢复尝试次数: %s", service_name)

    def clear_recovery_history(self) -> int:
        """清空恢复历史。

        Returns:
            清除的记录数量
        """
        count = len(self._recovery_history)
        self._recovery_history.clear()
        return count


class AlertSilenceService:
    """告警静默服务。"""

    DEFAULT_SILENCE_DURATION = 300  # 5分钟静默

    def __init__(self) -> None:
        """初始化静默服务。"""
        self._silences: dict[str, SilenceRecord] = {}

    def should_silence(self, alert_key: str) -> bool:
        """判断是否应该静默告警。

        Args:
            alert_key: 告警唯一标识

        Returns:
            是否应该静默
        """
        silence = self._silences.get(alert_key)
        if silence is None:
            return False

        try:
            expires_at = datetime.fromisoformat(silence.expires_at)
            now = datetime.now(timezone.utc)
            if now > expires_at:
                del self._silences[alert_key]
                logger.debug("静默已过期: key=%s", alert_key)
                return False
            return True
        except Exception:
            del self._silences[alert_key]
            return False

    def add_silence(
        self,
        alert_key: str,
        duration_seconds: int | None = None,
        reason: str = "",
    ) -> dict[str, Any]:
        """添加告警静默。

        Args:
            alert_key: 告警唯一标识
            duration_seconds: 静默时长（秒），默认5分钟
            reason: 静默原因

        Returns:
            静默记录
        """
        now = datetime.now(timezone.utc)
        duration = duration_seconds or self.DEFAULT_SILENCE_DURATION
        expires_at = now + timedelta(seconds=duration)

        silence = SilenceRecord(
            alert_key=alert_key,
            duration_seconds=duration,
            started_at=now.isoformat(),
            reason=reason,
            expires_at=expires_at.isoformat(),
        )

        self._silences[alert_key] = silence
        logger.info("添加告警静默: key=%s, duration=%ds, reason=%s", alert_key, duration, reason)

        return {
            "alert_key": alert_key,
            "duration_seconds": duration,
            "started_at": silence.started_at,
            "expires_at": silence.expires_at,
            "reason": reason,
        }

    def remove_silence(self, alert_key: str) -> bool:
        """移除告警静默。

        Args:
            alert_key: 告警唯一标识

        Returns:
            是否成功移除
        """
        if alert_key in self._silences:
            del self._silences[alert_key]
            logger.info("移除告警静默: key=%s", alert_key)
            return True
        return False

    def get_active_silences(self) -> list[dict[str, Any]]:
        """获取所有活跃的静默。

        Returns:
            静默列表
        """
        now = datetime.now(timezone.utc)
        active: list[dict[str, Any]] = []

        for key, silence in list(self._silences.items()):
            try:
                expires_at = datetime.fromisoformat(silence.expires_at)
                if now > expires_at:
                    del self._silences[key]
                    continue

                remaining = int((expires_at - now).total_seconds())
                active.append({
                    "alert_key": key,
                    "duration_seconds": silence.duration_seconds,
                    "started_at": silence.started_at,
                    "expires_at": silence.expires_at,
                    "reason": silence.reason,
                    "remaining_seconds": remaining,
                })
            except Exception:
                del self._silences[key]

        return active

    def clear_expired_silences(self) -> int:
        """清理过期静默。

        Returns:
            清理的静默数量
        """
        now = datetime.now(timezone.utc)
        cleared = 0

        for key, silence in list(self._silences.items()):
            try:
                expires_at = datetime.fromisoformat(silence.expires_at)
                if now > expires_at:
                    del self._silences[key]
                    cleared += 1
            except Exception:
                del self._silences[key]
                cleared += 1

        if cleared > 0:
            logger.info("清理了 %d 个过期静默", cleared)

        return cleared


auto_recovery_service = AutoRecoveryService()
alert_silence_service = AlertSilenceService()