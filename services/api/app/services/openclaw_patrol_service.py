"""OpenClaw 定时巡检服务。

按固定间隔检查系统状态并执行安全动作。
遵循三条铁规则：
1. 只能做白名单动作
2. 只能降风险，不能放大风险
3. 高风险场景收口到人工处理
"""

from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any
import json
import logging
import threading

from services.api.app.services.alert_push_service import (
    AlertEventType,
    AlertLevel,
    AlertMessage,
    alert_push_service,
)
from services.api.app.services.openclaw_snapshot_service import OpenclawSnapshotService
from services.api.app.services.openclaw_action_service import OpenclawActionService
from services.api.app.services.openclaw_action_policy_service import openclaw_action_policy_service
from services.api.app.services.service_health_service import ServiceHealthService, service_health_service

logger = logging.getLogger(__name__)


class OpenclawPatrolService:
    """定时巡检服务，按固定间隔检查系统状态并执行安全动作。"""

    PATROL_INTERVALS = {
        "health_check": 60,      # 每分钟健康检查
        "state_sync": 300,       # 每5分钟状态同步
        "cycle_check": 900,      # 每15分钟周期检查
    }

    # 节流配置
    THROTTLE_WINDOW_SECONDS = 3600  # 1小时窗口
    MAX_ACTION_COUNT_PER_WINDOW = 3  # 同一动作每小时最多执行3次
    MAX_CONSECUTIVE_FAILURES = 2     # 连续失败2次后停止自动执行

    # 告警阈值
    ALERT_THRESHOLD = 5               # 告警数超过5条触发清理
    SYNC_STALE_THRESHOLD_MINUTES = 10  # 同步超过10分钟视为过期

    MAX_PATROL_RECORDS = 50

    def __init__(
        self,
        snapshot_service: OpenclawSnapshotService,
        action_service: OpenclawActionService,
        health_service: ServiceHealthService | None = None,
        state_path: Path | None = None,
    ):
        """初始化巡检服务。

        Args:
            snapshot_service: 快照服务
            action_service: 动作执行服务
            health_service: 服务健康检查服务
            state_path: 存储巡检记录的文件路径
        """
        self._snapshot_service = snapshot_service
        self._action_service = action_service
        self._health_service = health_service or service_health_service
        self._state_path = state_path or Path(".runtime/openclaw_patrol_records.json")
        self._records: list[dict[str, Any]] = []
        self._action_counters: dict[str, dict[str, Any]] = {}  # 动作节流计数器
        self._lock = threading.Lock()
        self._load()

    def _load(self) -> None:
        """从文件加载巡检记录。"""
        if self._state_path.exists():
            try:
                with open(self._state_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._records = list(data.get("records", []))
                    self._action_counters = dict(data.get("action_counters", {}))
            except (json.JSONDecodeError, IOError):
                self._records = []
                self._action_counters = {}
        else:
            self._records = []
            self._action_counters = {}

    def _save(self) -> None:
        """保存巡检记录到文件。"""
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._state_path, "w", encoding="utf-8") as f:
            json.dump({
                "records": self._records,
                "action_counters": self._action_counters,
            }, f, ensure_ascii=False, indent=2)

    def patrol(self, patrol_type: str = "full") -> dict[str, Any]:
        """执行一轮巡检。

        Args:
            patrol_type: 巡检类型，可选 "health_check", "state_sync", "cycle_check", "full"

        Returns:
            巡检结果，包含 actions_taken 列表
        """
        now = datetime.now(timezone.utc)
        executed_at = now.isoformat()

        # 获取当前快照
        snapshot = self._snapshot_service.get_snapshot()
        snapshot_id = str(snapshot.get("snapshot_id", ""))

        actions_taken: list[dict[str, Any]] = []
        patrol_status = "normal"
        patrol_message = "巡检正常，无需执行动作"

        # 1. 健康检查（所有类型都执行）
        health_result = self._check_service_health(snapshot)
        if health_result.get("action_taken"):
            actions_taken.append(health_result)
            patrol_status = health_result.get("patrol_status", patrol_status)
            patrol_message = health_result.get("message", patrol_message)

        # 2. 周期就绪检查（cycle_check 或 full）
        if patrol_type in ("cycle_check", "full") and patrol_status == "normal":
            cycle_result = self._check_cycle_ready(snapshot)
            if cycle_result.get("action_taken"):
                actions_taken.append(cycle_result)
                patrol_status = cycle_result.get("patrol_status", patrol_status)
                patrol_message = cycle_result.get("message", patrol_message)

        # 3. 告警清理检查（full）
        if patrol_type == "full" and patrol_status == "normal":
            alert_result = self._check_alert_cleanup(snapshot)
            if alert_result.get("action_taken"):
                actions_taken.append(alert_result)
                patrol_status = alert_result.get("patrol_status", patrol_status)
                patrol_message = alert_result.get("message", patrol_message)

        # 记录巡检结果
        patrol_record = {
            "patrol_type": patrol_type,
            "executed_at": executed_at,
            "snapshot_id": snapshot_id,
            "status": patrol_status,
            "message": patrol_message,
            "actions_taken": actions_taken,
            "actions_count": len(actions_taken),
        }

        with self._lock:
            self._records.append(patrol_record)
            if len(self._records) > self.MAX_PATROL_RECORDS:
                self._records = self._records[-self.MAX_PATROL_RECORDS:]
            self._save()

        return {
            "patrolled": True,
            "patrol_type": patrol_type,
            "executed_at": executed_at,
            "status": patrol_status,
            "message": patrol_message,
            "actions_taken": actions_taken,
            "snapshot_id": snapshot_id,
        }

    def _check_service_health(self, snapshot: dict) -> dict[str, Any]:
        """检查服务健康状态。

        Args:
            snapshot: 当前快照

        Returns:
            检查结果
        """
        runtime_guard = dict(snapshot.get("runtime_guard") or {})
        execution_health = dict(snapshot.get("execution_health") or {})
        connection_status = str(execution_health.get("connection_status", "connected"))

        # 执行器连接异常时，切到 dry_run_only
        if connection_status == "error":
            action = "automation_dry_run_only"
            can_execute, reason = self._can_execute_action(action)

            # 推送执行器异常告警
            try:
                alert_push_service.push_sync(
                    AlertMessage(
                        event_type=AlertEventType.NODE_FAILURE,
                        level=AlertLevel.ERROR,
                        title="执行器连接异常",
                        message=f"Freqtrade 执行器连接状态异常 ({connection_status})",
                        details={
                            "connection_status": connection_status,
                            "suggested_action": action,
                            "can_execute": can_execute,
                        },
                    )
                )
            except Exception as alert_exc:
                logger.warning("告警推送失败: %s", alert_exc)

            if can_execute:
                result = self._action_service.execute_action(action)
                success = bool(result.get("success"))
                self._record_action_result(action, success)
                return {
                    "action_taken": True,
                    "action": action,
                    "success": success,
                    "message": f"执行器异常，已切换到 dry-run only",
                    "patrol_status": "action_taken",
                }
            else:
                return {
                    "action_taken": False,
                    "action": action,
                    "blocked_reason": reason,
                    "message": f"执行器异常但动作被节流: {reason}",
                    "patrol_status": "throttled",
                }

        return {
            "action_taken": False,
            "message": "服务健康检查正常",
            "patrol_status": "normal",
        }

    def _check_cycle_ready(self, snapshot: dict) -> dict[str, Any]:
        """检查周期就绪状态。

        Args:
            snapshot: 当前快照

        Returns:
            检查结果
        """
        runtime_guard = dict(snapshot.get("runtime_guard") or {})
        suggested_action = dict(snapshot.get("suggested_action") or {})

        # 检查是否建议运行周期
        action = str(suggested_action.get("action", ""))
        auto_run_allowed = bool(suggested_action.get("auto_run_allowed", False))

        # 只有当 suggested_action 是 run_cycle 且 auto_run_allowed=True 时才自动执行
        if action == "run_cycle" and auto_run_allowed:
            can_execute, reason = self._can_execute_action("automation_run_cycle")
            if can_execute:
                result = self._action_service.execute_action("automation_run_cycle")
                success = bool(result.get("success"))
                self._record_action_result("automation_run_cycle", success)
                return {
                    "action_taken": True,
                    "action": "automation_run_cycle",
                    "success": success,
                    "message": "周期就绪，已执行自动化周期",
                    "patrol_status": "action_taken",
                }
            else:
                return {
                    "action_taken": False,
                    "action": "automation_run_cycle",
                    "blocked_reason": reason,
                    "message": f"周期就绪但动作被节流: {reason}",
                    "patrol_status": "throttled",
                }

        return {
            "action_taken": False,
            "message": "周期未就绪或禁止自动运行",
            "patrol_status": "normal",
        }

    def _check_alert_cleanup(self, snapshot: dict) -> dict[str, Any]:
        """检查告警堆积。

        Args:
            snapshot: 当前快照

        Returns:
            检查结果
        """
        automation_state = dict(snapshot.get("automation_state") or {})
        alerts = list(automation_state.get("alerts", []))

        # 统计非错误级告警数
        non_error_alerts = [
            a for a in alerts
            if str(a.get("level", "")) in ("info", "warning")
        ]

        if len(non_error_alerts) > self.ALERT_THRESHOLD:
            action = "automation_clear_non_error_alerts"
            can_execute, reason = self._can_execute_action(action)
            if can_execute:
                result = self._action_service.execute_action(action)
                success = bool(result.get("success"))
                self._record_action_result(action, success)
                return {
                    "action_taken": True,
                    "action": action,
                    "success": success,
                    "message": f"告警堆积（{len(non_error_alerts)}条），已清理非错误告警",
                    "patrol_status": "action_taken",
                }
            else:
                return {
                    "action_taken": False,
                    "action": action,
                    "blocked_reason": reason,
                    "message": f"告警堆积但动作被节流: {reason}",
                    "patrol_status": "throttled",
                }

        return {
            "action_taken": False,
            "message": "告警数量正常",
            "patrol_status": "normal",
        }

    def _can_execute_action(self, action: str) -> tuple[bool, str]:
        """检查是否可以执行指定动作（节流校验）。

        Args:
            action: 动作名称

        Returns:
            (是否可执行, 原因)
        """
        now = datetime.now(timezone.utc)

        # 检查动作是否在白名单
        if not openclaw_action_policy_service.is_safe_action(action):
            return False, f"动作 {action} 不在白名单中"

        # 检查窗口内执行次数
        counter = self._action_counters.get(action, {})
        window_start = datetime.fromisoformat(str(counter.get("window_start", ""))) if counter.get("window_start") else None
        count_in_window = int(counter.get("count", 0))
        consecutive_failures = int(counter.get("consecutive_failures", 0))

        # 如果窗口过期，重置计数器
        if window_start and (now - window_start).total_seconds() > self.THROTTLE_WINDOW_SECONDS:
            count_in_window = 0
            consecutive_failures = 0
            window_start = None

        # 检查连续失败次数
        if consecutive_failures >= self.MAX_CONSECUTIVE_FAILURES:
            return False, f"动作 {action} 连续失败 {consecutive_failures} 次，已停止自动执行"

        # 检查窗口内执行次数
        if count_in_window >= self.MAX_ACTION_COUNT_PER_WINDOW:
            return False, f"动作 {action} 在窗口内已执行 {count_in_window} 次，已达上限"

        return True, "允许执行"

    def _record_action_result(self, action: str, success: bool) -> None:
        """记录动作执行结果用于节流计算。

        Args:
            action: 动作名称
            success: 是否成功
        """
        now = datetime.now(timezone.utc)

        with self._lock:
            counter = self._action_counters.get(action, {})
            window_start = datetime.fromisoformat(str(counter.get("window_start", ""))) if counter.get("window_start") else None

            # 如果窗口过期或不存在，重置窗口
            if not window_start or (now - window_start).total_seconds() > self.THROTTLE_WINDOW_SECONDS:
                window_start = now
                counter = {
                    "window_start": window_start.isoformat(),
                    "count": 0,
                    "consecutive_failures": 0,
                }

            # 更新计数
            counter["count"] = int(counter.get("count", 0)) + 1
            if success:
                counter["consecutive_failures"] = 0
            else:
                counter["consecutive_failures"] = int(counter.get("consecutive_failures", 0)) + 1

            self._action_counters[action] = counter
            self._save()

    def get_recent_patrols(self, limit: int = 10) -> list[dict]:
        """获取最近的巡检记录。

        Args:
            limit: 返回的最大记录数

        Returns:
            最近的巡检记录列表，按时间倒序
        """
        with self._lock:
            return list(reversed(self._records[-limit:]))

    def get_action_counters(self) -> dict[str, dict[str, Any]]:
        """获取动作计数器状态。

        Returns:
            所有动作的计数器状态
        """
        with self._lock:
            return dict(self._action_counters)

    def reset_action_counter(self, action: str) -> None:
        """重置指定动作的计数器。

        Args:
            action: 动作名称
        """
        with self._lock:
            if action in self._action_counters:
                del self._action_counters[action]
                self._save()


# 默认实例（延迟初始化）
_openclaw_patrol_service: OpenclawPatrolService | None = None


def get_openclaw_patrol_service() -> OpenclawPatrolService:
    """获取默认巡检服务实例。"""
    global _openclaw_patrol_service
    if _openclaw_patrol_service is None:
        from services.api.app.services.openclaw_action_service import OpenclawActionService
        from services.api.app.services.automation_service import AutomationService, automation_service
        from services.api.app.services.automation_workflow_service import AutomationWorkflowService, automation_workflow_service
        from services.api.app.services.strategy_dispatch_service import strategy_dispatch_service

        snapshot_service = OpenclawSnapshotService(
            automation=automation_service,
            strategies=strategy_dispatch_service,
        )
        action_service = OpenclawActionService(
            automation=automation_service,
            snapshot_service=snapshot_service,
            workflow_service=automation_workflow_service,
        )
        _openclaw_patrol_service = OpenclawPatrolService(
            snapshot_service=snapshot_service,
            action_service=action_service,
        )
    return _openclaw_patrol_service


openclaw_patrol_service = get_openclaw_patrol_service()