"""Openclaw 统一快照服务。

聚合自动化状态、执行器状态、服务健康和安全动作白名单，
输出给 Openclaw 的唯一结构化快照。
"""

from datetime import datetime, timezone
import uuid
from typing import Any

from services.api.app.services.automation_service import AutomationService
from services.api.app.services.strategy_dispatch_service import StrategyDispatchService


class OpenclawSnapshotService:
    """Openclaw 统一快照服务。"""

    def __init__(
        self,
        automation: AutomationService,
        strategies: StrategyDispatchService,
    ):
        self._automation = automation
        self._strategies = strategies

    def get_snapshot(self) -> dict[str, Any]:
        """获取统一运维快照。"""
        snapshot_id = str(uuid.uuid4())
        generated_at = datetime.now(timezone.utc).isoformat()

        state = self._automation.get_state()
        mode = str(state.get("mode", "manual"))
        paused = bool(state.get("paused", False))
        manual_takeover = bool(state.get("manual_takeover", False))

        runtime_guard = dict(state.get("runtime_guard") or {})
        recovery_review = dict(state.get("recovery_review") or {})

        executor_runtime = dict(state.get("executor_runtime") or {})
        connection_status = str(executor_runtime.get("connection_status", "unknown"))

        account_state = dict(state.get("account_state") or {})
        account_status = str(account_state.get("status", "unknown"))

        ready_for_cycle = bool(runtime_guard.get("ready_for_cycle", False))
        blocked_reason = str(runtime_guard.get("blocked_reason", ""))

        overall_status = self._resolve_overall_status(
            paused=paused,
            manual_takeover=manual_takeover,
            ready_for_cycle=ready_for_cycle,
            blocked_reason=blocked_reason,
        )

        allowed_actions = self._resolve_allowed_actions(
            overall_status=overall_status,
            connection_status=connection_status,
            account_status=account_status,
            paused=paused,
            manual_takeover=manual_takeover,
            ready_for_cycle=ready_for_cycle,
        )

        return {
            "snapshot_id": snapshot_id,
            "generated_at": generated_at,
            "overall_status": overall_status,
            "mode": mode,
            "paused": paused,
            "manual_takeover": manual_takeover,
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
            "allowed_safe_actions": allowed_actions,
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
        """解析允许的安全动作列表。"""
        actions = []

        if overall_status == "ready" and not manual_takeover:
            actions.append({
                "action": "automation_run_cycle",
                "reason": "当前允许继续下一轮自动化",
            })

        if connection_status in ("error", "disconnected") or account_status == "error":
            actions.append({
                "action": "automation_dry_run_only",
                "reason": "执行器异常，建议切到 dry-run only",
            })

        if not manual_takeover:
            actions.append({
                "action": "automation_clear_non_error_alerts",
                "reason": "清理非错误级告警",
            })

        return actions
