"""Openclaw 安全动作策略服务。

定义哪些动作允许执行，以及每个动作的前置条件。
"""

from typing import Any


class OpenclawActionPolicyService:
    """Openclaw 安全动作策略服务。"""

    # 允许的 HTTP 安全动作白名单
    ALLOWED_HTTP_ACTIONS = {
        "automation_run_cycle",
        "automation_dry_run_only",
        "automation_clear_non_error_alerts",
        "automation_confirm_alert",
    }

    # 系统动作白名单（允许系统自动执行的动作）
    SYSTEM_ACTION_WHITELIST = {
        "restart_api",
        "restart_web",
        "restart_freqtrade",
        "reload_config",
        "sync_state",
        "health_check",
    }

    # 明确禁止的危险动作
    FORBIDDEN_ACTIONS = {
        "automation_auto_live",
        "automation_resume",
        "automation_release_takeover",
        "execute_order",
        "modify_strategy",
        "modify_risk_params",
    }

    # 重启节流配置
    RESTART_THROTTLE_CONFIG = {
        "max_attempts_per_window": 3,
        "window_seconds": 3600,
        "cooldown_seconds": 300,
        "consecutive_failure_limit": 2,
    }

    def is_action_allowed(self, action: str) -> bool:
        """检查动作是否在白名单中。"""
        return action in self.ALLOWED_HTTP_ACTIONS

    def is_action_forbidden(self, action: str) -> bool:
        """检查动作是否被明确禁止。"""
        return action in self.FORBIDDEN_ACTIONS

    def validate_action_preconditions(
        self,
        action: str,
        snapshot: dict[str, Any],
    ) -> tuple[bool, str]:
        """验证动作的前置条件。

        Returns:
            (是否允许执行, 原因说明)
        """
        if self.is_action_forbidden(action):
            return False, f"动作 {action} 被明确禁止"

        if not self.is_action_allowed(action):
            return False, f"动作 {action} 不在安全白名单中"

        overall_status = str(snapshot.get("overall_status", ""))
        manual_takeover = bool(snapshot.get("manual_takeover", False))
        ready_for_cycle = bool(snapshot.get("runtime_guard", {}).get("ready_for_cycle", False))

        if action == "automation_run_cycle":
            if manual_takeover:
                return False, "当前处于人工接管状态，不允许自动运行周期"
            if not ready_for_cycle:
                return False, "当前不满足运行周期的条件"
            return True, "允许运行自动化周期"

        if action == "automation_dry_run_only":
            if manual_takeover:
                return False, "当前处于人工接管状态，不允许自动切换模式"
            return True, "允许切换到 dry-run only 模式"

        if action == "automation_clear_non_error_alerts":
            if manual_takeover:
                return False, "当前处于人工接管状态，不允许清理告警"
            return True, "允许清理非错误级告警"

        if action == "automation_confirm_alert":
            return True, "允许确认告警"

        return False, f"未定义动作 {action} 的前置条件"

    def validate_restart_conditions(
        self,
        service: str,
        restart_history: dict[str, Any],
    ) -> tuple[bool, str]:
        """验证重启条件是否满足。

        Args:
            service: 要重启的服务名称
            restart_history: 重启历史记录

        Returns:
            (是否允许重启, 原因说明)
        """
        # 检查服务是否在允许重启的列表中
        allowed_services = {"api", "web", "freqtrade"}
        if service not in allowed_services:
            return False, f"服务 {service} 不在允许重启的服务列表中"

        # 获取服务历史
        service_history = restart_history.get(service, {})
        consecutive_failures = int(service_history.get("consecutive_failures", 0))
        last_attempt_at = service_history.get("last_attempt_at")

        # 检查连续失败次数
        limit = self.RESTART_THROTTLE_CONFIG["consecutive_failure_limit"]
        if consecutive_failures >= limit:
            return False, f"连续失败 {consecutive_failures} 次，已达限制 {limit} 次，需人工介入"

        # 检查冷却时间
        if last_attempt_at:
            from datetime import datetime, timezone
            try:
                last_time = datetime.fromisoformat(str(last_attempt_at))
                now = datetime.now(timezone.utc)
                elapsed = (now - last_time).total_seconds()
                cooldown = self.RESTART_THROTTLE_CONFIG["cooldown_seconds"]
                if elapsed < cooldown:
                    remaining = int(cooldown - elapsed)
                    return False, f"冷却中，还需等待 {remaining} 秒"
            except (ValueError, TypeError):
                pass

        return True, "允许重启"

    def is_system_action_allowed(self, action: str) -> bool:
        """检查系统动作是否允许执行。

        系统动作由 OpenClaw 自动执行，不通过 HTTP 接口触发。

        Args:
            action: 动作名称

        Returns:
            是否允许执行
        """
        return action in self.SYSTEM_ACTION_WHITELIST


openclaw_action_policy_service = OpenclawActionPolicyService()
