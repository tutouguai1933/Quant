"""Openclaw 安全动作策略服务。

定义哪些动作允许执行，以及每个动作的前置条件。
"""

from datetime import datetime, timezone
from typing import Any


class OpenclawActionPolicyService:
    """Openclaw 安全动作策略服务。"""

    # 允许的 HTTP 安全动作白名单
    ALLOWED_HTTP_ACTIONS = {
        "automation_run_cycle",
        "automation_dry_run_only",
        "automation_clear_non_error_alerts",
        "automation_confirm_alert",
        # 新增安全动作
        "vpn_switch_node",        # VPN节点健康切换
        "alert_test_push",        # 测试告警推送功能
        "config_backup",          # 配置备份（只读取）
        "risk_guard_reset",       # 重置风控熔断计数（需确认）
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

    # 新增动作频率限制配置（每小时最多执行次数）
    ACTION_RATE_LIMITS = {
        "vpn_switch_node": {
            "max_per_hour": 3,           # 每小时最多切换3次
            "cooldown_seconds": 600,     # 切换后冷却10分钟
            "require_health_check": True, # 切换前需检查健康状态
        },
        "alert_test_push": {
            "max_per_hour": 2,           # 每小时最多测试推送2次
            "cooldown_seconds": 300,     # 推送后冷却5分钟
        },
        "config_backup": {
            "max_per_hour": 5,           # 每小时最多备份5次
            "cooldown_seconds": 60,      # 冷却1分钟
            "safe_read_only": True,      # 只读取，不修改
        },
        "risk_guard_reset": {
            "max_per_hour": 1,           # 每小时最多重置1次（高风险）
            "cooldown_seconds": 3600,    # 重置后冷却1小时
            "require_confirmation": True, # 需要二次确认
            "require_circuit_breaker_triggered": True, # 只有熔断触发时才能重置
        },
    }

    # 允许的安全动作白名单（只有这些动作可以 auto_execute=True）
    ALLOWED_SAFE_ACTIONS = ALLOWED_HTTP_ACTIONS | SYSTEM_ACTION_WHITELIST

    def is_action_allowed(self, action: str) -> bool:
        """检查动作是否在白名单中。"""
        return action in self.ALLOWED_HTTP_ACTIONS

    def is_action_forbidden(self, action: str) -> bool:
        """检查动作是否被明确禁止。"""
        return action in self.FORBIDDEN_ACTIONS

    def is_safe_action(self, action: str) -> bool:
        """检查动作是否在安全动作白名单中（允许 auto_execute）。"""
        return action in self.ALLOWED_SAFE_ACTIONS

    def validate_suggested_action(
        self,
        suggested_action: str,
    ) -> tuple[bool, str]:
        """验证程序建议的动作是否在白名单中。

        Args:
            suggested_action: 程序建议的动作名称

        Returns:
            (is_valid, reason) - 是否有效及原因说明
        """
        if not suggested_action:
            return False, "未提供 suggested_action"

        if self.is_action_forbidden(suggested_action):
            return False, f"建议动作 {suggested_action} 被明确禁止"

        if not self.is_safe_action(suggested_action):
            return False, f"建议动作 {suggested_action} 不在安全白名单中，不允许 auto_execute"

        return True, f"建议动作 {suggested_action} 通过白名单校验"

    def validate_action_preconditions(
        self,
        action: str,
        snapshot: dict[str, Any],
        suggested_action: str | None = None,
    ) -> tuple[bool, str, bool]:
        """验证动作的前置条件。

        Args:
            action: 要执行的动作名称
            snapshot: 系统状态快照
            suggested_action: 程序建议的动作（可选）

        Returns:
            (是否允许执行, 原因说明, 是否允许 auto_execute)
        """
        if self.is_action_forbidden(action):
            return False, f"动作 {action} 被明确禁止", False

        if not self.is_action_allowed(action):
            return False, f"动作 {action} 不在安全白名单中", False

        # 校验 suggested_action
        auto_execute = False
        if suggested_action:
            is_valid, reason = self.validate_suggested_action(suggested_action)
            if is_valid and suggested_action == action:
                # 只有 suggested_action 通过白名单校验且与要执行的动作一致时，
                # 才允许标记为 auto_execute=True
                auto_execute = True
            elif not is_valid:
                # suggested_action 校验失败，记录原因但不阻止手动执行
                pass

        overall_status = str(snapshot.get("overall_status", ""))
        manual_takeover = bool(snapshot.get("manual_takeover", False))
        ready_for_cycle = bool(snapshot.get("runtime_guard", {}).get("ready_for_cycle", False))

        if action == "automation_run_cycle":
            if manual_takeover:
                return False, "当前处于人工接管状态，不允许自动运行周期", False
            if not ready_for_cycle:
                return False, "当前不满足运行周期的条件", False
            return True, "允许运行自动化周期", auto_execute

        if action == "automation_dry_run_only":
            if manual_takeover:
                return False, "当前处于人工接管状态，不允许自动切换模式", False
            return True, "允许切换到 dry-run only 模式", auto_execute

        if action == "automation_clear_non_error_alerts":
            if manual_takeover:
                return False, "当前处于人工接管状态，不允许清理告警", False
            return True, "允许清理非错误级告警", auto_execute

        if action == "automation_confirm_alert":
            return True, "允许确认告警", auto_execute

        # 新增安全动作的前置条件验证
        if action == "vpn_switch_node":
            if manual_takeover:
                return False, "当前处于人工接管状态，不允许自动切换VPN节点", False
            # VPN切换需要健康检查
            vpn_status = snapshot.get("vpn", {})
            current_node_healthy = vpn_status.get("current_node_healthy", True)
            if current_node_healthy:
                return True, "当前节点健康，但仍允许切换（手动干预或预切换）", auto_execute
            return True, "当前节点不健康，允许切换到健康节点", auto_execute

        if action == "alert_test_push":
            # 告警测试推送相对安全，但需要检查配置
            alert_config = snapshot.get("alert_config", {})
            if not alert_config.get("enabled", False):
                return False, "告警推送功能未启用，无法测试", False
            return True, "允许测试告警推送功能", auto_execute

        if action == "config_backup":
            # 配置备份是只读操作，非常安全
            return True, "允许执行配置备份（只读取，不修改）", auto_execute

        if action == "risk_guard_reset":
            # 风控熔断重置是高风险操作，需要严格检查
            if manual_takeover:
                return False, "当前处于人工接管状态，不允许自动重置风控熔断", False
            # 只有熔断触发时才能重置
            circuit_breaker = snapshot.get("circuit_breaker", {})
            if not circuit_breaker.get("triggered", False):
                return False, "风控熔断未触发，无需重置", False
            # 需要二次确认（通过payload传入）
            # 这里只做基础检查，确认检查在执行层进行
            return True, "风控熔断已触发，允许重置（需二次确认）", False  # 不允许auto_execute，必须手动确认

        return False, f"未定义动作 {action} 的前置条件", False

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

    def validate_rate_limit(
        self,
        action: str,
        action_history: dict[str, Any],
    ) -> tuple[bool, str]:
        """验证动作频率限制是否满足。

        Args:
            action: 动作名称
            action_history: 动作执行历史记录

        Returns:
            (是否允许执行, 原因说明)
        """
        # 如果动作没有频率限制配置，默认允许
        if action not in self.ACTION_RATE_LIMITS:
            return True, "无频率限制"

        config = self.ACTION_RATE_LIMITS[action]
        max_per_hour = config.get("max_per_hour", 5)
        cooldown_seconds = config.get("cooldown_seconds", 60)

        now = datetime.now(timezone.utc)
        window_start = datetime.fromtimestamp(now.timestamp() - 3600, tz=timezone.utc)

        # 获取动作历史
        history = action_history.get(action, {})
        attempts = history.get("attempts", [])
        last_attempt_at = history.get("last_attempt_at")

        # 计算时间窗口内的执行次数
        recent_attempts = []
        for attempt in attempts:
            try:
                attempt_time = datetime.fromisoformat(str(attempt.get("executed_at", "")))
                if attempt_time >= window_start:
                    recent_attempts.append(attempt)
            except (ValueError, TypeError):
                continue

        # 检查执行次数限制
        if len(recent_attempts) >= max_per_hour:
            return False, f"已达到每小时最大执行次数 {max_per_hour}"

        # 检查冷却时间
        if last_attempt_at:
            try:
                last_time = datetime.fromisoformat(str(last_attempt_at))
                elapsed = (now - last_time).total_seconds()
                if elapsed < cooldown_seconds:
                    remaining = int(cooldown_seconds - elapsed)
                    return False, f"冷却中，还需等待 {remaining} 秒"
            except (ValueError, TypeError):
                pass

        return True, "频率限制检查通过"

    def get_action_config(self, action: str) -> dict[str, Any]:
        """获取动作的配置信息。

        Args:
            action: 动作名称

        Returns:
            动作配置字典
        """
        return dict(self.ACTION_RATE_LIMITS.get(action, {}))


openclaw_action_policy_service = OpenclawActionPolicyService()
