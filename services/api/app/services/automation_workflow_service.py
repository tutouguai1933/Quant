"""自动化工作流服务。

这个文件负责把训练、推理、自动 dry-run、小额 live 和复盘收成一条统一流程。
"""

from __future__ import annotations

from datetime import datetime, timezone

from services.api.app.core.settings import Settings
from services.api.app.services.automation_service import automation_service
from services.api.app.services.research_service import research_service
from services.api.app.services.signal_service import signal_service
from services.api.app.services.strategy_catalog import strategy_catalog_service
from services.api.app.services.sync_service import sync_service
from services.api.app.services.strategy_dispatch_service import strategy_dispatch_service
from services.api.app.services.validation_workflow_service import validation_workflow_service
from services.api.app.services.workbench_config_service import workbench_config_service
from services.api.app.tasks.scheduler import task_scheduler


class AutomationWorkflowService:
    """按当前自动化模式执行统一工作流。"""

    def __init__(self, *, scheduler=None, automation=None, research=None, signals=None, dispatcher=None, reviewer=None, syncer=None) -> None:
        self._scheduler = scheduler or task_scheduler
        self._automation = automation or automation_service
        self._research = research or research_service
        self._signals = signals or signal_service
        self._dispatcher = dispatcher or strategy_dispatch_service
        self._reviewer = reviewer or validation_workflow_service
        self._syncer = syncer or sync_service

    def get_status(self) -> dict[str, object]:
        """返回自动化状态和健康摘要。"""

        task_health = self._scheduler.get_health_summary()
        automation_status = self._automation.get_status(task_health=task_health)
        state = dict(automation_status.get("state") or {})
        operations = self._get_operations_config()
        review_limit = int(operations.get("review_limit", 10) or 10)
        report = self._reviewer.build_report(limit=review_limit)
        health = self._automation.build_health_summary(task_health=task_health)
        return {
            "state": state,
            "health": health,
            "operations": operations,
            "execution_policy": dict(automation_status.get("execution_policy") or {}),
            "active_blockers": list(health.get("active_blockers") or []),
            "operator_actions": list(health.get("operator_actions") or []),
            "takeover_summary": dict(health.get("takeover_summary") or {}),
            "alert_summary": dict(health.get("alert_summary") or {}),
            "review_overview": dict(report.get("overview") or {}),
            "execution_health": self._syncer.get_execution_health_summary(
                task_health=task_health,
                automation_state=state,
            ),
            "daily_summary": dict(automation_status.get("daily_summary") or {}),
            "scheduler_plan": self._build_scheduler_plan(review_limit=review_limit),
            "failure_policy": self._build_failure_policy(operations=operations),
        }

    def run_cycle(self, *, source: str = "automation", review_limit: int = 10) -> dict[str, object]:
        """执行一轮自动化工作流。"""

        operations = self._get_operations_config()
        review_limit = int(operations.get("review_limit", review_limit) or review_limit)
        auto_pause_on_error = bool(operations.get("auto_pause_on_error", True))
        state = self._automation.get_state()
        mode = str(state.get("mode", "manual"))
        armed_symbol = str(state.get("armed_symbol", "")).strip().upper()
        if bool(state.get("paused")):
            summary = {
                "status": "paused",
                "mode": mode,
                "recommended_symbol": "",
                "next_action": "manual_takeover",
                "message": "自动化当前处于暂停状态",
                "armed_symbol": armed_symbol,
            }
            self._automation.record_cycle(summary)
            return summary

        daily_limit = int(operations.get("max_daily_cycle_count", 8) or 8)
        current_cycle_count = int((state.get("daily_summary") or {}).get("cycle_count", 0) or 0)
        if current_cycle_count >= daily_limit:
            self._automation.record_alert(
                level="warning",
                code="daily_cycle_limit_reached",
                message="今日自动化轮次已达到上限",
                source=source,
                detail=str(current_cycle_count),
            )
            summary = {
                "status": "waiting",
                "mode": mode,
                "recommended_symbol": "",
                "next_action": "wait_next_window",
                "message": f"今日轮次上限已用完（{current_cycle_count}/{daily_limit}），先等下一轮窗口再继续。",
                "failure_reason": "daily_cycle_limit_reached",
                "armed_symbol": armed_symbol,
            }
            self._automation.record_cycle(summary)
            return summary

        cooldown_minutes = int(operations.get("cycle_cooldown_minutes", 15) or 0)
        cooldown_remaining = self._resolve_cooldown_remaining_minutes(last_cycle=dict(state.get("last_cycle") or {}), cooldown_minutes=cooldown_minutes)
        if cooldown_remaining > 0:
            self._automation.record_alert(
                level="warning",
                code="cycle_cooldown_active",
                message="自动化仍在冷却窗口内",
                source=source,
                detail=str(cooldown_remaining),
            )
            summary = {
                "status": "waiting",
                "mode": mode,
                "recommended_symbol": "",
                "next_action": "wait_next_window",
                "message": f"自动化仍在冷却窗口内，还需等待约 {cooldown_remaining} 分钟。",
                "failure_reason": "cycle_cooldown_active",
                "armed_symbol": armed_symbol,
            }
            self._automation.record_cycle(summary)
            return summary

        train_task = self._scheduler.run_named_task(task_type="research_train", source=source, target_type="system")
        if train_task["status"] != "succeeded":
            self._automation.record_alert(
                level="error",
                code="train_failed",
                message="自动训练失败",
                source=source,
                detail=str(train_task.get("error_message") or ""),
            )
            return self._finalize_failed_cycle(
                mode=mode,
                next_action="stop",
                review_limit=review_limit,
                tasks={"train": train_task},
                failure_policy_action="manual_takeover" if auto_pause_on_error else "review_before_retry",
                takeover_reason="workflow_train_failed",
                source=source,
                auto_pause_on_error=auto_pause_on_error,
            )

        infer_task = self._scheduler.run_named_task(task_type="research_infer", source=source, target_type="system")
        if infer_task["status"] != "succeeded":
            self._automation.record_alert(
                level="error",
                code="infer_failed",
                message="自动推理失败",
                source=source,
                detail=str(infer_task.get("error_message") or ""),
            )
            return self._finalize_failed_cycle(
                mode=mode,
                next_action="stop",
                review_limit=review_limit,
                tasks={"train": train_task, "infer": infer_task},
                failure_policy_action="manual_takeover" if auto_pause_on_error else "review_before_retry",
                takeover_reason="workflow_infer_failed",
                source=source,
                auto_pause_on_error=auto_pause_on_error,
            )

        signal_task = self._scheduler.run_named_task(task_type="signal_output", source=source, target_type="system")
        if signal_task["status"] != "succeeded":
            self._automation.record_alert(
                level="error",
                code="signal_output_failed",
                message="研究信号输出失败",
                source=source,
                detail=str(signal_task.get("error_message") or ""),
            )
            return self._finalize_failed_cycle(
                mode=mode,
                next_action="stop",
                review_limit=review_limit,
                tasks={"train": train_task, "infer": infer_task, "signal_output": signal_task},
                failure_policy_action="manual_takeover" if auto_pause_on_error else "review_before_retry",
                takeover_reason="workflow_signal_output_failed",
                source=source,
                auto_pause_on_error=auto_pause_on_error,
            )

        recommendation = self._research.get_research_recommendation() or {}
        next_action = str(recommendation.get("next_action", "")) or "continue_research"
        recommended_symbol = str(recommendation.get("symbol", ""))
        recommended_strategy_id = strategy_catalog_service.resolve_strategy_id(str(recommendation.get("strategy_template", ""))) or 1
        live_ready = bool(
            recommendation.get("allowed_to_live")
            if recommendation.get("allowed_to_live") is not None
            else recommendation.get("allowed_to_dry_run")
        )
        dispatch_result: dict[str, object] | None = None
        dispatch_status = "waiting"
        cycle_message = ""
        failure_reason = ""

        if mode == "manual":
            next_action = "manual_review"
            cycle_message = "当前处于手动模式，请先人工确认再继续。"
        elif next_action != "enter_dry_run":
            self._automation.record_alert(
                level="warning",
                code="screening_blocked",
                message="当前候选还没有通过研究筛选门",
                source=source,
                detail=recommended_symbol,
            )
            dispatch_status = "blocked"
            cycle_message = "当前候选还没有通过研究筛选门"
            failure_reason = "screening_blocked"
        elif mode == "auto_live" and Settings.from_env().runtime_mode != "live":
            next_action = "continue_dry_run"
            self._automation.record_alert(
                level="warning",
                code="live_mode_not_ready",
                message="自动 live 已开启，但当前运行模式不是 live",
                source=source,
            )
            dispatch_status = "blocked"
            cycle_message = "自动 live 已开启，但当前运行模式不是 live"
            failure_reason = "runtime_not_live"
        elif mode == "auto_live" and not live_ready:
            next_action = "continue_dry_run"
            self._automation.record_alert(
                level="warning",
                code="live_gate_blocked",
                message="当前候选还没有通过 live 门槛",
                source=source,
                detail=recommended_symbol,
            )
            dispatch_status = "blocked"
            cycle_message = "当前候选还没有通过 live 门槛"
            failure_reason = "live_gate_blocked"
        elif mode == "auto_live" and armed_symbol != recommended_symbol:
            next_action = "continue_dry_run"
            self._automation.record_alert(
                level="warning",
                code="live_requires_dry_run",
                message="当前候选还没有完成上一轮 dry-run 验证",
                source=source,
                detail=recommended_symbol,
            )
            dispatch_status = "blocked"
            cycle_message = "当前候选还没有完成上一轮 dry-run 验证"
            failure_reason = "dry_run_not_confirmed"
        else:
            dispatch_result = self._dispatcher.dispatch_latest_signal(recommended_strategy_id, source=source)
            if dispatch_result["status"] != "succeeded":
                level = "warning" if dispatch_result["error_code"] in {"signal_not_ready", "risk_blocked"} else "error"
                self._automation.record_alert(
                    level=level,
                    code=str(dispatch_result["error_code"]),
                    message=str(dispatch_result["message"]),
                    source=source,
                    detail=recommended_symbol,
                )
                next_action = "continue_research" if dispatch_result["error_code"] == "signal_not_ready" else "review_and_decide"
                dispatch_status = dispatch_result["status"]
                cycle_message = str(dispatch_result.get("message") or "")
                failure_reason = str(dispatch_result.get("error_code") or "")
                if dispatch_result["error_code"] not in {"signal_not_ready", "risk_blocked"} and auto_pause_on_error:
                    self._automation.manual_takeover(reason=f"dispatch_{failure_reason}", actor=source)
            else:
                dispatch_status = "succeeded"
                if mode == "auto_live":
                    self._automation.clear_armed_symbol()
                    next_action = "retain_small_live"
                    cycle_message = "自动小额 live 已完成，本轮结果可进入统一复盘。"
                else:
                    self._automation.arm_symbol(recommended_symbol)
                    next_action = "continue_dry_run"
                    cycle_message = "候选已通过自动 dry-run，等待下一轮 live 验证。"

        review_task = self._scheduler.run_named_task(
            task_type="review",
            source=source,
            target_type="system",
            payload={"limit": review_limit},
        )
        report = self._reviewer.build_report(limit=review_limit)
        review_status = str(review_task.get("status", "waiting"))
        if review_status != "succeeded":
            status = "attention_required"
        else:
            status = "succeeded" if dispatch_status == "succeeded" else ("waiting" if next_action in {"continue_research", "manual_review", "continue_dry_run"} else "attention_required")
        summary = {
            "status": status,
            "mode": mode,
            "recommended_symbol": recommended_symbol,
            "recommended_strategy_id": recommended_strategy_id,
            "next_action": next_action,
            "message": cycle_message,
            "failure_reason": failure_reason,
            "failure_policy_action": next_action if dispatch_status == "failed" else "",
            "armed_symbol": str(self._automation.get_state().get("armed_symbol", "")),
            "train_task": train_task,
            "infer_task": infer_task,
            "signal_task": signal_task,
            "dispatch": dispatch_result,
            "review_task": review_task,
            "review_overview": dict(report.get("overview") or {}),
        }
        self._automation.record_cycle(summary)
        return summary

    def _finalize_failed_cycle(
        self,
        *,
        mode: str,
        next_action: str,
        review_limit: int,
        tasks: dict[str, object],
        failure_policy_action: str,
        takeover_reason: str,
        source: str,
        auto_pause_on_error: bool,
    ) -> dict[str, object]:
        """在训练或推理失败时统一收口工作流。"""

        if auto_pause_on_error:
            self._automation.manual_takeover(reason=takeover_reason, actor=source)
        review_task = self._scheduler.run_named_task(
            task_type="review",
            source="automation",
            target_type="system",
            payload={"limit": review_limit},
        )
        report = self._reviewer.build_report(limit=review_limit)
        summary = {
            "status": "attention_required",
            "mode": mode,
            "recommended_symbol": "",
            "next_action": next_action,
            "message": "自动化本轮在训练或推理阶段失败，请先看统一复盘。",
            "failure_reason": "workflow_failed",
            "failure_policy_action": failure_policy_action,
            "review_task": review_task,
            "review_overview": dict(report.get("overview") or {}),
            **tasks,
        }
        self._automation.record_cycle(summary)
        return summary

    @staticmethod
    def _build_scheduler_plan(*, review_limit: int) -> list[dict[str, str]]:
        """返回固定自动化调度顺序。"""

        return [
            {"task_type": "research_train", "detail": "先训练，刷新最新研究模型"},
            {"task_type": "research_infer", "detail": "再推理，产出候选和推荐动作"},
            {"task_type": "signal_output", "detail": "把研究结果写成统一信号"},
            {"task_type": "dispatch", "detail": "按当前模式进入 dry-run 或小额 live"},
            {"task_type": "review", "detail": f"最后统一复盘和健康摘要（最近 {review_limit} 条）"},
        ]

    @staticmethod
    def _build_failure_policy(*, operations: dict[str, object]) -> dict[str, str]:
        """返回失败后的固定处理规则。"""

        manual_policy = "manual_takeover" if bool(operations.get("auto_pause_on_error", True)) else "review_before_retry"
        return {
            "research_train": manual_policy,
            "research_infer": manual_policy,
            "signal_output": manual_policy,
            "dispatch": "review_and_decide",
            "sync": "retry_then_review",
        }

    @staticmethod
    def _get_operations_config() -> dict[str, object]:
        """读取长期运行配置。"""

        config = workbench_config_service.get_config()
        operations = dict(config.get("operations") or {})
        return {
            "pause_after_consecutive_failures": int(operations.get("pause_after_consecutive_failures", 2) or 2),
            "stale_sync_failure_threshold": int(operations.get("stale_sync_failure_threshold", 1) or 1),
            "auto_pause_on_error": bool(operations.get("auto_pause_on_error", True)),
            "review_limit": int(operations.get("review_limit", 10) or 10),
            "cycle_cooldown_minutes": int(operations.get("cycle_cooldown_minutes", 15) or 0),
            "max_daily_cycle_count": int(operations.get("max_daily_cycle_count", 8) or 8),
        }

    @staticmethod
    def _resolve_cooldown_remaining_minutes(*, last_cycle: dict[str, object], cooldown_minutes: int) -> int:
        """根据最近一轮完成时间计算还剩多少冷却时间。"""

        if cooldown_minutes <= 0:
            return 0
        recorded_at = str(last_cycle.get("recorded_at", "") or "").strip()
        if not recorded_at:
            return 0
        try:
            recorded = datetime.fromisoformat(recorded_at)
        except ValueError:
            return 0
        if recorded.tzinfo is None:
            recorded = recorded.replace(tzinfo=timezone.utc)
        elapsed_minutes = (datetime.now(timezone.utc) - recorded.astimezone(timezone.utc)).total_seconds() / 60
        remaining = int(round(cooldown_minutes - elapsed_minutes))
        return remaining if remaining > 0 else 0


automation_workflow_service = AutomationWorkflowService()
