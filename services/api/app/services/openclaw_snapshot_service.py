"""Openclaw 统一快照服务。

聚合自动化状态、执行器状态、服务健康和安全动作白名单，
输出给 Openclaw 的唯一结构化快照。
"""

from datetime import datetime, timezone
import uuid
from typing import Any

from services.api.app.services.automation_service import AutomationService
from services.api.app.services.strategy_dispatch_service import StrategyDispatchService
from services.api.app.services.automation_workflow_service import automation_workflow_service
from services.api.app.services.service_health_service import ServiceHealthService, service_health_service
from services.api.app.services.openclaw_restart_history_service import OpenclawRestartHistoryService, openclaw_restart_history_service
from services.api.app.services.openclaw_audit_service import OpenclawAuditService, openclaw_audit_service


class OpenclawSnapshotService:
    """Openclaw 统一快照服务。"""

    def __init__(
        self,
        automation: AutomationService,
        strategies: StrategyDispatchService,
        health_service: ServiceHealthService | None = None,
        restart_history_service: OpenclawRestartHistoryService | None = None,
        audit_service: OpenclawAuditService | None = None,
    ):
        self._automation = automation
        self._strategies = strategies
        self._health_service = health_service or service_health_service
        self._restart_history = restart_history_service or openclaw_restart_history_service
        self._audit_service = audit_service or openclaw_audit_service

    def get_snapshot(self) -> dict[str, Any]:
        """获取统一运维快照。"""
        snapshot_id = str(uuid.uuid4())
        generated_at = datetime.now(timezone.utc).isoformat()

        state = self._automation.get_state()
        mode = str(state.get("mode", "manual"))
        paused = bool(state.get("paused", False))
        manual_takeover = bool(state.get("manual_takeover", False))

        # 从 automation_workflow_service 获取完整的 runtime_guard 信息
        try:
            workflow_status = automation_workflow_service.get_status()
            runtime_guard = dict(workflow_status.get("runtime_guard") or {})
        except Exception:
            runtime_guard = dict(state.get("runtime_guard") or {})

        recovery_review = dict(state.get("recovery_review") or {})

        executor_runtime = dict(state.get("executor_runtime") or {})
        connection_status = str(executor_runtime.get("connection_status", "unknown"))

        account_state = dict(state.get("account_state") or {})
        account_status = str(account_state.get("status", "unknown"))

        ready_for_cycle = bool(runtime_guard.get("ready_for_cycle", False))
        blocked_reason = str(runtime_guard.get("blocked_reason", ""))

        # 从 runtime_guard 获取建议动作
        suggested_action = str(runtime_guard.get("suggested_action", "") or "")
        suggested_action_reason = str(runtime_guard.get("suggested_action_reason", "") or "")
        auto_run_allowed = bool(runtime_guard.get("auto_run_allowed", False))

        overall_status = self._resolve_overall_status(
            paused=paused,
            manual_takeover=manual_takeover,
            ready_for_cycle=ready_for_cycle,
            blocked_reason=blocked_reason,
        )

        # 获取服务健康状态
        service_health = self._health_service.get_all_health()

        # 获取重启历史摘要
        restart_history = self._restart_history.get_all_history()

        # 获取最近动作记录
        recent_audit = self._audit_service.get_recent_records(limit=1)
        last_openclaw_action = recent_audit[0] if recent_audit else None

        allowed_actions = self._resolve_allowed_actions(
            overall_status=overall_status,
            connection_status=connection_status,
            account_status=account_status,
            paused=paused,
            manual_takeover=manual_takeover,
            ready_for_cycle=ready_for_cycle,
        )

        # 为每个允许的动作添加前置条件检查
        allowed_actions_with_preconditions = []
        for action in allowed_actions:
            can_execute, precondition_reason = self._check_action_preconditions(
                action_name=action["action"],
                overall_status=overall_status,
                service_health=service_health,
            )
            allowed_actions_with_preconditions.append({
                **action,
                "preconditions_met": can_execute,
                "precondition_reason": precondition_reason,
            })

        return {
            "snapshot_id": snapshot_id,
            "generated_at": generated_at,
            "overall_status": overall_status,
            "mode": mode,
            "paused": paused,
            "manual_takeover": manual_takeover,
            "suggested_action": {
                "action": suggested_action,
                "reason": suggested_action_reason,
                "auto_run_allowed": auto_run_allowed,
            },
            "runtime_guard": {
                "ready_for_cycle": ready_for_cycle,
                "blocked_reason": blocked_reason,
            },
            "recovery_review": {
                "resume_needed": bool(recovery_review.get("resume_needed", False)),
                "cannot_resume_reason": str(recovery_review.get("cannot_resume_reason", "")),
            },
            "executor_runtime": {
                "connection_status": connection_status,
            },
            "account_state": {
                "status": account_status,
            },
            "service_status": {
                "api_expected_up": True,
                "web_expected_up": True,
                "freqtrade_expected_up": True,
            },
            "service_health": service_health,
            "restart_history": restart_history,
            "last_openclaw_action": last_openclaw_action,
            "allowed_safe_actions": allowed_actions_with_preconditions,
            "protection_boundaries": {
                "live_enable_allowed": False,
                "manual_takeover_release_allowed": False,
                "max_restart_attempts": 3,
                "restart_cooldown_seconds": 300,
            },
        }

    def _resolve_overall_status(
        self,
        *,
        paused: bool,
        manual_takeover: bool,
        ready_for_cycle: bool,
        blocked_reason: str,
    ) -> str:
        """解析整体状态。"""
        if manual_takeover:
            return "manual_takeover"
        if paused:
            return "paused"
        if ready_for_cycle:
            return "ready"
        if blocked_reason:
            return "blocked"
        return "waiting"

    def _resolve_allowed_actions(
        self,
        *,
        overall_status: str,
        connection_status: str,
        account_status: str,
        paused: bool,
        manual_takeover: bool,
        ready_for_cycle: bool,
    ) -> list[dict[str, Any]]:
        """解析允许的安全动作列表，包含 auto_execute 和 priority 字段。"""
        actions = []

        if overall_status == "ready" and not manual_takeover:
            actions.append({
                "action": "automation_run_cycle",
                "reason": "当前允许继续下一轮自动化",
                "auto_execute": ready_for_cycle and not paused,
                "priority": 2,
            })

        if connection_status in ("error", "disconnected") or account_status == "error":
            actions.append({
                "action": "automation_dry_run_only",
                "reason": "执行器异常，建议切到 dry-run only",
                "auto_execute": True,
                "priority": 3,
            })

        if not manual_takeover:
            actions.append({
                "action": "automation_clear_non_error_alerts",
                "reason": "清理非错误级告警",
                "auto_execute": True,
                "priority": 1,
            })

        # 按优先级排序（高优先级在前）
        actions.sort(key=lambda x: -int(x.get("priority", 0)))

        return actions

    def _check_action_preconditions(
        self,
        action_name: str,
        overall_status: str,
        service_health: dict[str, Any],
    ) -> tuple[bool, str]:
        """检查动作前置条件。

        Args:
            action_name: 动作名称
            overall_status: 整体状态
            service_health: 服务健康状态

        Returns:
            (是否满足前置条件, 原因说明)
        """
        # 检查系统重启动作的前置条件
        if action_name.startswith("system_restart_"):
            service = action_name.replace("system_restart_", "")
            if service not in ("web", "freqtrade"):
                return False, f"不支持重启服务: {service}"

            # 检查重启节流
            can_restart, reason = self._restart_history.can_restart(service)
            if not can_restart:
                return False, reason

            # 检查服务当前健康状态
            services = service_health.get("services", {})
            service_info = services.get(service, {})
            if service_info.get("reachable", False):
                return True, "服务当前健康，允许重启"

            return True, "服务当前不健康，允许尝试重启"

        # 检查自动化动作的前置条件
        if action_name == "automation_run_cycle":
            if overall_status != "ready":
                return False, f"当前状态 {overall_status}，不允许运行周期"
            return True, "前置条件满足"

        if action_name == "automation_dry_run_only":
            # dry_run_only 总是允许
            return True, "切换到 dry-run 总是允许"

        if action_name == "automation_clear_non_error_alerts":
            # 清理告警总是允许
            return True, "清理非错误告警总是允许"

        # 默认情况
        return True, "前置条件检查通过"
