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

    # 明确禁止的危险动作
    FORBIDDEN_ACTIONS = {
        "automation_auto_live",
        "automation_resume",
        "automation_release_takeover",
        "execute_order",
        "modify_strategy",
        "modify_risk_params",
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


openclaw_action_policy_service = OpenclawActionPolicyService()
