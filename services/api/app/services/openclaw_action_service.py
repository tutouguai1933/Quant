"""Openclaw 安全动作执行服务。

执行 HTTP 安全动作，记录动作结果，返回标准执行结果。
"""

from datetime import datetime, timezone
from typing import Any

from services.api.app.services.automation_service import AutomationService
from services.api.app.services.openclaw_action_policy_service import openclaw_action_policy_service
from services.api.app.services.openclaw_snapshot_service import OpenclawSnapshotService
from services.api.app.services.automation_workflow_service import AutomationWorkflowService
from services.api.app.services.openclaw_audit_service import OpenclawAuditService, openclaw_audit_service
from services.api.app.services.openclaw_restart_history_service import OpenclawRestartHistoryService, openclaw_restart_history_service
from services.api.app.services.system_action_executor import SystemActionExecutor, system_action_executor
from services.api.app.services.service_health_service import ServiceHealthService, service_health_service


class OpenclawActionService:
    """Openclaw 安全动作执行服务。"""

    def __init__(
        self,
        automation: AutomationService,
        snapshot_service: OpenclawSnapshotService,
        workflow_service: AutomationWorkflowService,
        audit_service: OpenclawAuditService | None = None,
        restart_history_service: OpenclawRestartHistoryService | None = None,
        system_executor: SystemActionExecutor | None = None,
        health_service: ServiceHealthService | None = None,
    ):
        self._automation = automation
        self._snapshot_service = snapshot_service
        self._workflow_service = workflow_service
        # 使用传入实例或默认实例
        self._audit_service = audit_service or openclaw_audit_service
        self._restart_history = restart_history_service or openclaw_restart_history_service
        self._system_executor = system_executor or system_action_executor
        self._health_service = health_service or service_health_service

    def execute_action(
        self,
        action: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """执行安全动作。

        Args:
            action: 动作名称
            payload: 动作参数

        Returns:
            标准执行结果
        """
        payload = payload or {}
        executed_at = datetime.now(timezone.utc).isoformat()

        # 获取当前快照
        snapshot = self._snapshot_service.get_snapshot()
        snapshot_id = str(snapshot.get("snapshot_id", ""))

        # 验证前置条件
        allowed, reason = openclaw_action_policy_service.validate_action_preconditions(
            action=action,
            snapshot=snapshot,
        )

        if not allowed:
            self._record_audit(
                action=action,
                snapshot_id=snapshot_id,
                success=False,
                reason=reason,
                executed_at=executed_at,
            )
            return {
                "success": False,
                "action": action,
                "reason": reason,
                "snapshot_id": snapshot_id,
                "executed_at": executed_at,
            }

        # 执行动作
        try:
            # 系统重启动作使用专门的处理方法
            if action.startswith("system_restart_"):
                result = self._execute_system_restart(action=action, payload=payload)
            else:
                result = self._execute_action_impl(action=action, payload=payload)

            success = bool(result.get("success", False))
            message = str(result.get("message", ""))

            self._record_audit(
                action=action,
                snapshot_id=snapshot_id,
                success=success,
                reason=message,
                executed_at=executed_at,
                result=result,
            )

            return {
                "success": success,
                "action": action,
                "reason": message,
                "snapshot_id": snapshot_id,
                "executed_at": executed_at,
                "result": result,
            }

        except Exception as e:
            error_message = f"执行动作失败: {e}"
            self._record_audit(
                action=action,
                snapshot_id=snapshot_id,
                success=False,
                reason=error_message,
                executed_at=executed_at,
            )
            return {
                "success": False,
                "action": action,
                "reason": error_message,
                "snapshot_id": snapshot_id,
                "executed_at": executed_at,
            }

    def _execute_action_impl(
        self,
        action: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """执行动作的实际实现。"""
        if action == "automation_run_cycle":
            result = self._workflow_service.run_cycle(source="openclaw")
            return {
                "success": result.get("status") != "error",
                "message": str(result.get("message", "")),
                "detail": result,
            }

        if action == "automation_dry_run_only":
            self._automation.set_mode(mode="auto_dry_run")
            return {
                "success": True,
                "message": "已切换到 dry-run only 模式",
            }

        if action == "automation_clear_non_error_alerts":
            self._automation.clear_alerts(levels=["info", "warning"], actor="openclaw")
            return {
                "success": True,
                "message": "已清理非错误级告警",
            }

        if action == "automation_confirm_alert":
            alert_id = payload.get("alert_id")
            if not alert_id or not isinstance(alert_id, int):
                return {
                    "success": False,
                    "message": "缺少有效的 alert_id 参数",
                }
            self._automation.confirm_alert(alert_id=alert_id, actor="openclaw")
            return {
                "success": True,
                "message": f"已确认告警 {alert_id}",
            }

        return {
            "success": False,
            "message": f"未实现动作 {action}",
        }

    def _execute_system_restart(
        self,
        action: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """执行系统重启动作。

        Args:
            action: 动作名称，格式为 system_restart_{service}
            payload: 动作参数

        Returns:
            执行结果
        """
        # 从动作名称提取服务名称
        # 格式: system_restart_{service}
        service = action.replace("system_restart_", "")

        # 验证服务名称
        supported_services = ("web", "freqtrade")
        if service not in supported_services:
            return {
                "success": False,
                "message": f"不支持重启服务: {service}，支持的服务: {supported_services}",
            }

        # 检查重启条件
        can_restart, reason = self._restart_history.can_restart(service)
        if not can_restart:
            return {
                "success": False,
                "message": f"重启被拒绝: {reason}",
            }

        # 检查服务当前状态
        health = self._health_service.get_all_health().get("services", {}).get(service, {})
        was_healthy = health.get("reachable", False)

        # 执行重启
        result = self._system_executor.restart_service(service)
        success = result.get("success", False)

        # 记录重启历史
        self._restart_history.record_restart(service=service, success=success)

        if success:
            return {
                "success": True,
                "message": f"服务 {service} 重启成功",
                "was_healthy": was_healthy,
                "detail": result,
            }
        else:
            return {
                "success": False,
                "message": result.get("message", "重启失败"),
                "was_healthy": was_healthy,
                "detail": result,
            }

    def _record_audit(
        self,
        action: str,
        snapshot_id: str,
        success: bool,
        reason: str,
        executed_at: str,
        result: dict[str, Any] | None = None,
    ) -> None:
        """记录动作审计日志。

        同时记录到 OpenclawAuditService 和 AutomationService。

        Args:
            action: 动作名称
            snapshot_id: 快照 ID
            success: 是否成功
            reason: 原因/消息
            executed_at: 执行时间
            result: 执行结果详情
        """
        # 记录到 OpenclawAuditService
        self._audit_service.record_action({
            "action": action,
            "snapshot_id": snapshot_id,
            "success": success,
            "reason": reason,
            "executed_at": executed_at,
            "result": result,
        })

        # 同时记录到 AutomationService 告警系统
        self._automation.record_alert(
            level="info" if success else "error",
            code=f"openclaw_action_{action}",
            message=f"Openclaw 执行动作: {action}",
            source="openclaw",
            detail=str({
                "action": action,
                "snapshot_id": snapshot_id,
                "success": success,
                "reason": reason,
                "executed_at": executed_at,
                "result": result,
            }),
        )
