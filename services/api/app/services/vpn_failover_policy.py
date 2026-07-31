"""VPN 主备切换策略。

纯逻辑模块（无 IO），实现主备切换决策：
- 主节点连续失败 N 次触发故障切换
- 主节点连续成功 N 次触发回切
- 切换后观察期
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from services.api.app.services.vpn_node_registry import NodeRegistry
    from services.api.app.services.vpn_health_probe import NodeHealthProbe

logger = logging.getLogger(__name__)


@dataclass
class FailoverEvent:
    """切换事件记录。"""

    ts: float = field(default_factory=time.time)
    from_node: str = ""
    to_node: str = ""
    reason: str = ""
    success: bool = False

    def to_dict(self) -> dict:
        """序列化为字典。"""
        return {
            "ts": self.ts,
            "from": self.from_node,
            "to": self.to_node,
            "reason": self.reason,
            "success": self.success,
        }


class PrimaryBackupPolicy:
    """主备切换策略。

    纯逻辑，无 IO 依赖：
    - fail_threshold: 主节点连续失败多少次触发故障切换（默认 3）
    - recover_threshold: 主节点连续成功多少次触发回切（默认 3）
    - observe_seconds: 切换后观察期秒数（默认 300）
    """

    def __init__(
        self,
        fail_threshold: int = 3,
        recover_threshold: int = 3,
        observe_seconds: int = 300,
    ) -> None:
        """初始化策略。

        Args:
            fail_threshold: 连续失败阈值
            recover_threshold: 连续成功阈值
            observe_seconds: 观察期秒数
        """
        self.fail_threshold = fail_threshold
        self.recover_threshold = recover_threshold
        self.observe_seconds = observe_seconds

        # 内部状态
        self._consecutive_failures: dict[str, int] = {}
        self._consecutive_successes: dict[str, int] = {}
        self._switched_at: float | None = None
        self._current_backup: str | None = None
        self._events: list[FailoverEvent] = []

    def record_probe(self, node: str, ok: bool) -> None:
        """记录一次探测结果，更新连续成功/失败计数。

        Args:
            node: 节点名称
            ok: 探测是否通过
        """
        if ok:
            self._consecutive_successes[node] = (
                self._consecutive_successes.get(node, 0) + 1
            )
            self._consecutive_failures[node] = 0
        else:
            self._consecutive_failures[node] = (
                self._consecutive_failures.get(node, 0) + 1
            )
            self._consecutive_successes[node] = 0

        logger.debug(
            "节点 %s 探测: ok=%s, failures=%d, successes=%d",
            node,
            ok,
            self._consecutive_failures.get(node, 0),
            self._consecutive_successes.get(node, 0),
        )

    def should_failover(self, primary: str) -> bool:
        """判断是否应该从主节点故障切换。

        Args:
            primary: 主节点名称

        Returns:
            是否应触发故障切换
        """
        failures = self._consecutive_failures.get(primary, 0)
        return failures >= self.fail_threshold

    def pick_backup(
        self,
        registry: "NodeRegistry",
        probe: "NodeHealthProbe",
    ) -> str | None:
        """从注册表中选出最佳备选节点。

        按注册表优先级排序候选，依次预验证（探测），返回第一个通过的。
        所有候选失败返回 None（保持现状节点不动）。

        Args:
            registry: 节点注册表
            probe: 健康探针

        Returns:
            选中的节点名称，或 None
        """
        candidates = registry.candidates()
        if not candidates:
            logger.warning("没有可用的备选节点")
            return None

        for candidate in candidates:
            logger.info("预验证备选节点: %s", candidate.name)
            result = probe.check_with_interval(candidate.name)
            if result.ok:
                logger.info(
                    "备选节点 %s 预验证通过，IP: %s, 延迟: %.2fms",
                    candidate.name,
                    result.ip,
                    result.latency_ms or 0,
                )
                return candidate.name
            logger.warning(
                "备选节点 %s 预验证失败: %s",
                candidate.name,
                result.error,
            )

        logger.error("所有备选节点预验证失败，保持现状")
        return None

    def should_failback(self, primary: str) -> bool:
        """判断是否应该回切到主节点。

        Args:
            primary: 主节点名称

        Returns:
            是否应触发回切
        """
        successes = self._consecutive_successes.get(primary, 0)
        if successes < self.recover_threshold:
            return False

        # 还需要确认不在观察期内
        if self.in_observation(self._switched_at or 0):
            logger.debug(
                "主节点已恢复但仍在观察期，暂不回切"
            )
            return False

        return True

    def in_observation(self, switched_at: float) -> bool:
        """判断是否还在观察期内。

        Args:
            switched_at: 切换时间（Unix 时间戳）

        Returns:
            是否在观察期内
        """
        if switched_at <= 0:
            return False
        elapsed = time.time() - switched_at
        return elapsed < self.observe_seconds

    def mark_switched(self) -> None:
        """标记已切换，记录切换时间。"""
        self._switched_at = time.time()

    def record_event(
        self,
        from_node: str,
        to_node: str,
        reason: str,
        success: bool,
    ) -> FailoverEvent:
        """记录切换事件。

        Args:
            from_node: 切换前节点
            to_node: 切换后节点
            reason: 切换原因
            success: 是否成功

        Returns:
            FailoverEvent
        """
        event = FailoverEvent(
            ts=time.time(),
            from_node=from_node,
            to_node=to_node,
            reason=reason,
            success=success,
        )
        self._events.append(event)
        return event

    def get_events(self) -> list[FailoverEvent]:
        """返回所有切换事件。"""
        return list(self._events)

    def reset(self) -> None:
        """重置所有内部状态。"""
        self._consecutive_failures.clear()
        self._consecutive_successes.clear()
        self._switched_at = None
        self._current_backup = None
        self._events.clear()

    @property
    def switched_at(self) -> float | None:
        """返回切换时间。"""
        return self._switched_at

    @property
    def current_backup(self) -> str | None:
        """返回当前使用的备选节点。"""
        return self._current_backup

    @current_backup.setter
    def current_backup(self, value: str | None) -> None:
        """设置当前备选节点。"""
        self._current_backup = value
