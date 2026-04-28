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
from services.api.app.services.vpn_switch_service import vpn_switch_service
from services.api.app.services.alert_push_service import alert_push_service, AlertMessage, AlertEventType, AlertLevel
from services.api.app.services.config_center_service import config_center_service
from services.api.app.services.risk_guard_service import risk_guard_service


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

        # 验证频率限制
        action_history = self._audit_service.get_action_history_for_rate_limit(action)
        rate_limit_allowed, rate_limit_reason = openclaw_action_policy_service.validate_rate_limit(
            action=action,
            action_history=action_history,
        )

        if not rate_limit_allowed:
            self._record_audit(
                action=action,
                snapshot_id=snapshot_id,
                success=False,
                reason=rate_limit_reason,
                executed_at=executed_at,
            )
            return {
                "success": False,
                "action": action,
                "reason": rate_limit_reason,
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

        # 新增安全动作执行逻辑
        if action == "vpn_switch_node":
            return self._execute_vpn_switch_node(payload)

        if action == "alert_test_push":
            return self._execute_alert_test_push(payload)

        if action == "config_backup":
            return self._execute_config_backup(payload)

        if action == "risk_guard_reset":
            return self._execute_risk_guard_reset(payload)

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

    def _execute_vpn_switch_node(
        self,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """执行VPN节点健康切换。

        Args:
            payload: 动作参数，可包含：
                - target_node: 目标节点名称（可选，不指定则自动选择）

        Returns:
            执行结果
        """
        import logging
        logger = logging.getLogger("openclaw")

        target_node = payload.get("target_node")

        try:
            # 先检查当前节点健康状态
            health_result = vpn_switch_service.check_node_health_sync()

            if target_node:
                # 切换到指定节点
                logger.info(f"VPN切换：手动指定目标节点 {target_node}")
                switch_result = vpn_switch_service.switch_node_sync(target_node)
            else:
                # 自动切换到健康的白名单节点
                logger.info("VPN切换：自动选择健康节点")
                switch_result = vpn_switch_service.auto_switch_to_healthy_node_sync()

            if switch_result.success:
                logger.info(
                    f"VPN节点切换成功: {switch_result.previous_node} -> {switch_result.current_node}, "
                    f"出口IP: {switch_result.exit_ip} (白名单: {switch_result.is_whitelisted})"
                )
                return {
                    "success": True,
                    "message": f"VPN节点切换成功，当前节点: {switch_result.current_node}",
                    "previous_node": switch_result.previous_node,
                    "current_node": switch_result.current_node,
                    "exit_ip": switch_result.exit_ip,
                    "is_whitelisted": switch_result.is_whitelisted,
                }
            else:
                logger.error(f"VPN节点切换失败: {switch_result.error_message}")
                return {
                    "success": False,
                    "message": f"VPN节点切换失败: {switch_result.error_message}",
                    "previous_node": switch_result.previous_node,
                }

        except Exception as e:
            logger.exception(f"VPN节点切换异常: {e}")
            return {
                "success": False,
                "message": f"VPN节点切换异常: {e}",
            }

    def _execute_alert_test_push(
        self,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """执行测试告警推送。

        Args:
            payload: 动作参数，可包含：
                - test_message: 测试消息内容（可选）
                - test_level: 测试告警级别（可选，默认info）

        Returns:
            执行结果
        """
        import logging
        logger = logging.getLogger("openclaw")

        test_message = payload.get("test_message", "OpenClaw 告警推送测试")
        test_level_str = payload.get("test_level", "info")

        # 转换告警级别
        level_map = {
            "info": AlertLevel.INFO,
            "warning": AlertLevel.WARNING,
            "error": AlertLevel.ERROR,
        }
        test_level = level_map.get(test_level_str, AlertLevel.INFO)

        try:
            # 创建测试告警消息
            test_alert = AlertMessage(
                event_type=AlertEventType.SYSTEM_ERROR,
                level=test_level,
                title="OpenClaw 告警测试",
                message=test_message,
                details={
                    "source": "openclaw_test",
                    "test_level": test_level_str,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )

            # 推送告警
            push_result = alert_push_service.push_sync(test_alert)

            logger.info(f"告警测试推送结果: {push_result}")

            telegram_status = push_result.get("telegram", {}).get("status", "unknown")
            webhook_status = push_result.get("webhook", {}).get("status", "unknown")

            # 至少一个推送成功就算成功
            success = telegram_status == "success" or webhook_status == "success"

            if success:
                return {
                    "success": True,
                    "message": "告警测试推送成功",
                    "telegram_status": telegram_status,
                    "webhook_status": webhook_status,
                    "detail": push_result,
                }
            else:
                return {
                    "success": False,
                    "message": f"告警测试推送失败: Telegram={telegram_status}, Webhook={webhook_status}",
                    "detail": push_result,
                }

        except Exception as e:
            logger.exception(f"告警测试推送异常: {e}")
            return {
                "success": False,
                "message": f"告警测试推送异常: {e}",
            }

    def _execute_config_backup(
        self,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """执行配置备份（只读取，不修改）。

        Args:
            payload: 动作参数，可包含：
                - include_sections: 要备份的配置段列表（可选）

        Returns:
            执行结果
        """
        import logging
        import json
        from pathlib import Path

        logger = logging.getLogger("openclaw")

        include_sections = payload.get("include_sections")

        try:
            # 获取所有配置（不包含敏感信息）
            config_data = config_center_service.get_all_config(include_secrets=False)

            # 如果指定了配置段，只返回指定部分
            if include_sections:
                filtered_config = {
                    "sections": {},
                    "sources": config_data.get("sources", {}),
                }
                for section in include_sections:
                    if section in config_data.get("sections", {}):
                        filtered_config["sections"][section] = config_data["sections"][section]
                config_data = filtered_config

            # 保存备份到文件
            backup_dir = Path(".runtime/config_backups")
            backup_dir.mkdir(parents=True, exist_ok=True)

            backup_time = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            backup_file = backup_dir / f"config_backup_{backup_time}.json"

            with open(backup_file, "w", encoding="utf-8") as f:
                json.dump(config_data, f, ensure_ascii=False, indent=2)

            logger.info(f"配置备份成功，保存到: {backup_file}")

            # 验证配置完整性
            validation_result = config_center_service.validate_config()

            return {
                "success": True,
                "message": f"配置备份成功，保存到: {backup_file}",
                "backup_file": str(backup_file),
                "config_valid": validation_result.get("valid", False),
                "validation_warnings": validation_result.get("warnings", []),
                "timestamp": backup_time,
            }

        except Exception as e:
            logger.exception(f"配置备份异常: {e}")
            return {
                "success": False,
                "message": f"配置备份异常: {e}",
            }

    def _execute_risk_guard_reset(
        self,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """执行风控熔断重置（高风险，需确认）。

        Args:
            payload: 动作参数，必须包含：
                - confirmation: 二次确认字符串 "CONFIRM_RISK_GUARD_RESET"

        Returns:
            执行结果
        """
        import logging

        logger = logging.getLogger("openclaw")

        # 检查二次确认
        confirmation = payload.get("confirmation", "")
        if confirmation != "CONFIRM_RISK_GUARD_RESET":
            return {
                "success": False,
                "message": "缺少二次确认，需要传入 confirmation='CONFIRM_RISK_GUARD_RESET'",
            }

        try:
            # 检查当前熔断状态
            circuit_breaker_state = risk_guard_service.get_circuit_breaker_state()

            if not circuit_breaker_state.get("triggered", False):
                return {
                    "success": False,
                    "message": "风控熔断未触发，无需重置",
                    "circuit_breaker_state": circuit_breaker_state,
                }

            # 记录重置前的状态
            logger.warning(
                f"准备重置风控熔断，触发原因: {circuit_breaker_state.get('trigger_reason', 'unknown')}"
            )

            # 执行重置
            reset_result = risk_guard_service.reset_circuit_breaker()

            logger.info(f"风控熔断重置结果: {reset_result}")

            return {
                "success": reset_result.get("status") == "reset",
                "message": reset_result.get("message", "风控熔断重置完成"),
                "previous_state": circuit_breaker_state,
                "current_state": reset_result.get("circuit_breaker_state", {}),
            }

        except Exception as e:
            logger.exception(f"风控熔断重置异常: {e}")
            return {
                "success": False,
                "message": f"风控熔断重置异常: {e}",
            }
