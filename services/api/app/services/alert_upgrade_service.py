"""告警级别升级服务。

监控告警重复出现次数，自动升级告警级别。
支持级别: INFO -> WARNING -> ERROR -> CRITICAL。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class AlertLevel(str, Enum):
    """告警级别枚举。"""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class UpgradeThresholds:
    """升级阈值配置。"""

    info_to_warning: int = 3  # 连续3次INFO升级为WARNING
    warning_to_error: int = 2  # 连续2次WARNING升级为ERROR
    error_to_critical: int = 1  # 连续1次ERROR升级为CRITICAL


@dataclass
class AlertCounter:
    """告警计数器。"""

    level: AlertLevel
    count: int = 0
    first_seen_at: str = ""
    last_seen_at: str = ""
    upgraded_at: str = ""
    original_level: AlertLevel = AlertLevel.INFO


class AlertUpgradeService:
    """告警级别升级服务。"""

    LEVEL_ORDER = [AlertLevel.INFO, AlertLevel.WARNING, AlertLevel.ERROR, AlertLevel.CRITICAL]

    def __init__(self, thresholds: UpgradeThresholds | None = None) -> None:
        """初始化告警升级服务。

        Args:
            thresholds: 升级阈值配置
        """
        self._thresholds = thresholds or UpgradeThresholds()
        self._counters: dict[str, AlertCounter] = {}
        self._upgrade_history: list[dict[str, Any]] = []

    @property
    def thresholds(self) -> UpgradeThresholds:
        """返回当前阈值配置。"""
        return self._thresholds

    def _get_threshold_for_level(self, level: AlertLevel) -> int:
        """获取指定级别的升级阈值。

        Args:
            level: 当前级别

        Returns:
            升级到下一级别需要的连续次数
        """
        threshold_map = {
            AlertLevel.INFO: self._thresholds.info_to_warning,
            AlertLevel.WARNING: self._thresholds.warning_to_error,
            AlertLevel.ERROR: self._thresholds.error_to_critical,
            AlertLevel.CRITICAL: 0,  # CRITICAL 无需升级
        }
        return threshold_map.get(level, 0)

    def _get_next_level(self, level: AlertLevel) -> AlertLevel | None:
        """获取下一级别。

        Args:
            level: 当前级别

        Returns:
            下一级别，CRITICAL返回None
        """
        try:
            current_idx = self.LEVEL_ORDER.index(level)
            if current_idx < len(self.LEVEL_ORDER) - 1:
                return self.LEVEL_ORDER[current_idx + 1]
        except ValueError:
            pass
        return None

    def check_upgrade(self, alert_key: str, current_level: str | AlertLevel = AlertLevel.INFO) -> AlertLevel:
        """检查并升级告警级别。

        Args:
            alert_key: 告警唯一标识（如 "container_quant-api_unhealthy"）
            current_level: 当前告警级别

        Returns:
            升级后的告警级别
        """
        now = datetime.now(timezone.utc).isoformat()

        if isinstance(current_level, str):
            try:
                current_level = AlertLevel(current_level)
            except ValueError:
                current_level = AlertLevel.INFO

        counter = self._counters.get(alert_key)

        if counter is None:
            counter = AlertCounter(
                level=current_level,
                count=1,
                first_seen_at=now,
                last_seen_at=now,
                original_level=current_level,
            )
            self._counters[alert_key] = counter
            logger.debug("新告警计数器: key=%s, level=%s", alert_key, current_level.value)
            return current_level

        if counter.level != current_level:
            counter.level = current_level
            counter.count = 1
            counter.last_seen_at = now
            logger.debug("告警级别变化，重置计数: key=%s, new_level=%s", alert_key, current_level.value)
            return current_level

        counter.count += 1
        counter.last_seen_at = now

        threshold = self._get_threshold_for_level(counter.level)
        next_level = self._get_next_level(counter.level)

        if threshold > 0 and counter.count >= threshold and next_level:
            old_level = counter.level
            counter.level = next_level
            counter.upgraded_at = now
            counter.count = 0

            upgrade_record = {
                "alert_key": alert_key,
                "from_level": old_level.value,
                "to_level": next_level.value,
                "triggered_at": now,
                "trigger_count": threshold,
                "original_level": counter.original_level.value,
            }
            self._upgrade_history.append(upgrade_record)

            logger.warning(
                "告警级别升级: key=%s, %s -> %s (连续%d次)",
                alert_key,
                old_level.value,
                next_level.value,
                threshold,
            )

            return next_level

        logger.debug(
            "告警计数更新: key=%s, level=%s, count=%d/%d",
            alert_key,
            counter.level.value,
            counter.count,
            threshold,
        )
        return counter.level

    def reset_counter(self, alert_key: str) -> bool:
        """重置计数器（问题解决后）。

        Args:
            alert_key: 告警唯一标识

        Returns:
            是否成功重置
        """
        if alert_key in self._counters:
            counter = self._counters[alert_key]
            logger.info(
                "告警计数器已重置: key=%s, level=%s, count=%d",
                alert_key,
                counter.level.value,
                counter.count,
            )
            del self._counters[alert_key]
            return True
        return False

    def get_counter_status(self, alert_key: str) -> dict[str, Any] | None:
        """获取告警计数器状态。

        Args:
            alert_key: 告警唯一标识

        Returns:
            计数器状态字典
        """
        counter = self._counters.get(alert_key)
        if counter is None:
            return None

        return {
            "alert_key": alert_key,
            "level": counter.level.value,
            "count": counter.count,
            "first_seen_at": counter.first_seen_at,
            "last_seen_at": counter.last_seen_at,
            "upgraded_at": counter.upgraded_at,
            "original_level": counter.original_level.value,
        }

    def get_all_counters(self) -> dict[str, dict[str, Any]]:
        """获取所有告警计数器状态。

        Returns:
            所有计数器状态字典
        """
        return {
            key: self.get_counter_status(key)
            for key in self._counters
            if self.get_counter_status(key) is not None
        }

    def get_upgrade_history(self, limit: int = 50) -> list[dict[str, Any]]:
        """获取升级历史。

        Args:
            limit: 返回数量限制

        Returns:
            升级历史列表
        """
        return self._upgrade_history[-limit:]

    def get_current_level(self, alert_key: str) -> AlertLevel:
        """获取告警当前级别。

        Args:
            alert_key: 告警唯一标识

        Returns:
            当前告警级别
        """
        counter = self._counters.get(alert_key)
        return counter.level if counter else AlertLevel.INFO

    def clear_expired_counters(self, max_age_hours: int = 24) -> int:
        """清理过期计数器。

        Args:
            max_age_hours: 最大保留时间（小时）

        Returns:
            清理的计数器数量
        """
        now = datetime.now(timezone.utc)
        cleared = 0

        for key, counter in list(self._counters.items()):
            try:
                last_seen = datetime.fromisoformat(counter.last_seen_at)
                age_hours = (now - last_seen).total_seconds() / 3600
                if age_hours > max_age_hours:
                    del self._counters[key]
                    cleared += 1
                    logger.debug("清理过期计数器: key=%s, age=%.1fh", key, age_hours)
            except Exception:
                pass

        if cleared > 0:
            logger.info("清理了 %d 个过期告警计数器", cleared)

        return cleared


alert_upgrade_service = AlertUpgradeService()