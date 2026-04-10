"""自动化工作流服务。

这个文件负责把训练、推理、自动 dry-run、小额 live 和复盘收成一条统一流程。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from services.api.app.core.settings import Settings
from services.api.app.services.automation_service import automation_service
from services.api.app.services.research_service import research_service
from services.api.app.services.signal_service import signal_service
from services.api.app.services.strategy_catalog import strategy_catalog_service
from services.api.app.services.sync_service import sync_service
from services.api.app.services.strategy_dispatch_service import strategy_dispatch_service
from services.api.app.services.research_execution_arbitration_service import research_execution_arbitration_service
from services.api.app.services.validation_workflow_service import validation_workflow_service
from services.api.app.services.workbench_config_service import workbench_config_service
from services.api.app.tasks.scheduler import task_scheduler


class AutomationWorkflowService:
    """按当前自动化模式执行统一工作流。"""

    def __init__(
        self,
        *,
        scheduler=None,
        automation=None,
        research=None,
        signals=None,
        dispatcher=None,
        reviewer=None,
        syncer=None,
        arbiter=None,
    ) -> None:
        self._scheduler = scheduler or task_scheduler
        self._automation = automation or automation_service
        self._research = research or research_service
        self._signals = signals or signal_service
        self._dispatcher = dispatcher or strategy_dispatch_service
        self._reviewer = reviewer or validation_workflow_service
        self._syncer = syncer or sync_service
        self._arbiter = arbiter or research_execution_arbitration_service

    def get_status(self) -> dict[str, object]:
        """返回自动化状态和健康摘要。"""

        task_health = self._scheduler.get_health_summary()
        automation_status = self._automation.get_status(task_health=task_health)
        state = dict(automation_status.get("state") or {})
        state_alerts = state.get("alerts")
        alerts: list[dict[str, object]] = []
        if isinstance(state_alerts, list):
            for entry in state_alerts:
                if isinstance(entry, dict):
                    alerts.append(dict(entry))
        operations = self._get_operations_config()
        automation_config = dict(automation_status.get("automation_config") or self._get_automation_config())
        review_limit = int(operations.get("review_limit", 10) or 10)
        report = self._reviewer.build_report(limit=review_limit)
        health = self._automation.build_health_summary(task_health=task_health)
        runtime_window = self._build_runtime_window(state=state, operations=operations, automation_config=automation_config)
        resume_status = self._build_resume_status(
            runtime_window=runtime_window,
            resume_checklist=list(health.get("resume_checklist") or []),
        )
        status_payload = {
            "state": state,
            "health": health,
            "operations": operations,
            "automation_config": automation_config,
            "execution_policy": dict(automation_status.get("execution_policy") or {}),
            "active_blockers": list(health.get("active_blockers") or []),
            "operator_actions": list(health.get("operator_actions") or []),
            "control_actions": list(health.get("control_actions") or []),
            "takeover_summary": dict(health.get("takeover_summary") or {}),
            "alert_summary": dict(health.get("alert_summary") or {}),
            "review_overview": dict(report.get("overview") or {}),
            "execution_health": self._syncer.get_execution_health_summary(
                task_health=task_health,
                automation_state=state,
            ),
            "daily_summary": dict(automation_status.get("daily_summary") or {}),
            "runtime_window": runtime_window,
            "resume_status": resume_status,
            "scheduler_plan": self._build_scheduler_plan(review_limit=review_limit),
            "alerts": alerts,
            "failure_policy": self._build_failure_policy(operations=operations),
        }
        try:
            status_payload["arbitration"] = self._arbiter.build_decision(automation_status=status_payload)
        except Exception:
            status_payload["arbitration"] = research_execution_arbitration_service.build_decision(
                automation_status=status_payload,
                evaluation_workspace={},
            )
        return status_payload

    def run_cycle(self, *, source: str = "automation", review_limit: int = 10) -> dict[str, object]:
        """执行一轮自动化工作流。"""

        operations = self._get_operations_config()
        review_limit = int(operations.get("review_limit", review_limit) or review_limit)
        auto_pause_on_error = bool(operations.get("auto_pause_on_error", True))
        task_health = self._scheduler.get_health_summary()
        automation_health = self._automation.build_health_summary(task_health=task_health)
        run_health = dict(automation_health.get("run_health") or {})
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
            self._automation.record_cycle(summary, count_towards_daily=False)
            return summary

        pause_after_failures = int(operations.get("pause_after_consecutive_failures", 2) or 2)
        consecutive_failures = int(run_health.get("consecutive_failure_count", 0) or 0)
        if consecutive_failures >= pause_after_failures:
            if auto_pause_on_error:
                self._automation.manual_takeover(reason="consecutive_failure_guard_triggered", actor=source)
            self._automation.record_alert(
                level="error" if auto_pause_on_error else "warning",
                code="consecutive_failure_guard_triggered",
                message="连续失败已达到阈值，先暂停下一轮自动化。",
                source=source,
                detail=str(consecutive_failures),
            )
            summary = {
                "status": "waiting",
                "mode": mode,
                "recommended_symbol": "",
                "next_action": "manual_takeover" if auto_pause_on_error else "review_before_retry",
                "message": f"连续失败已达到阈值（{consecutive_failures}/{pause_after_failures}），先人工复核再继续。",
                "failure_reason": "consecutive_failure_guard_triggered",
                "failure_policy_action": "manual_takeover" if auto_pause_on_error else "review_before_retry",
                "armed_symbol": armed_symbol,
            }
            self._automation.record_cycle(summary, count_towards_daily=False)
            return summary

        stale_sync_threshold = int(operations.get("stale_sync_failure_threshold", 1) or 1)
        sync_failure_count = int(run_health.get("sync_failure_count", 0) or 0)
        stale_sync_state = str(run_health.get("stale_sync_state", "fresh") or "fresh")
        if stale_sync_state == "stale":
            if auto_pause_on_error:
                self._automation.manual_takeover(reason="stale_sync_guard_triggered", actor=source)
            self._automation.record_alert(
                level="error" if auto_pause_on_error else "warning",
                code="stale_sync_guard_triggered",
                message="同步失败已达到陈旧阈值，先暂停下一轮自动化。",
                source=source,
                detail=str(sync_failure_count),
            )
            summary = {
                "status": "waiting",
                "mode": mode,
                "recommended_symbol": "",
                "next_action": "manual_takeover" if auto_pause_on_error else "review_sync",
                "message": f"同步失败已达到陈旧阈值（{sync_failure_count}/{stale_sync_threshold}），先恢复同步再继续。",
                "failure_reason": "stale_sync_guard_triggered",
                "failure_policy_action": "manual_takeover" if auto_pause_on_error else "review_sync",
                "armed_symbol": armed_symbol,
            }
            self._automation.record_cycle(summary, count_towards_daily=False)
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
            self._automation.record_cycle(summary, count_towards_daily=False)
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
            self._automation.record_cycle(summary, count_towards_daily=False)
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

    @classmethod
    def _build_runtime_window(
        cls,
        *,
        state: dict[str, object],
        operations: dict[str, object],
        automation_config: dict[str, object],
    ) -> dict[str, object]:
        """整理长期运行窗口，方便页面说明当前还能不能继续跑下一轮。"""

        daily_summary = dict(state.get("daily_summary") or {})
        daily_limit = int(operations.get("max_daily_cycle_count", 8) or 8)
        current_cycle_count = int(daily_summary.get("cycle_count", 0) or 0)
        remaining_daily_cycle_count = max(daily_limit - current_cycle_count, 0)
        cooldown_minutes = int(operations.get("cycle_cooldown_minutes", 15) or 0)
        cooldown_remaining_minutes = cls._resolve_cooldown_remaining_minutes(
            last_cycle=dict(state.get("last_cycle") or {}),
            cooldown_minutes=cooldown_minutes,
        )
        long_run_seconds = int(automation_config.get("long_run_seconds", 300) or 300)
        mode = str(state.get("mode", "manual") or "manual")
        paused = bool(state.get("paused"))
        manual_takeover = bool(state.get("manual_takeover"))
        paused_since = cls._parse_timestamp(str(state.get("paused_at", "") or ""))
        takeover_since = cls._parse_timestamp(str(state.get("manual_takeover_at", "") or ""))
        takeover_elapsed_seconds = 0
        if manual_takeover and takeover_since is not None:
            takeover_elapsed_seconds = max(
                int((datetime.now(timezone.utc) - takeover_since.astimezone(timezone.utc)).total_seconds()),
                0,
            )
        if paused and manual_takeover:
            if takeover_elapsed_seconds >= long_run_seconds:
                next_action = "review_takeover"
                note = "人工接管已持续较久，先确认执行器、同步和账户状态，再决定是否恢复。"
            else:
                next_action = "manual_takeover"
                note = "当前已人工接管，先处理阻塞再考虑恢复自动化。"
        elif paused:
            next_action = "resume_after_review"
            note = "当前处于暂停状态，先看恢复清单再继续。"
        elif mode == "manual":
            next_action = "manual_review"
            note = "当前处于手动模式，只有切回自动模式后系统才会继续自动推进。"
        elif remaining_daily_cycle_count <= 0:
            next_action = "wait_next_window"
            note = "今日轮次已用完，先等下一轮时间窗口。"
        elif cooldown_remaining_minutes > 0:
            next_action = "wait_cooldown"
            note = f"冷却中，约 {cooldown_remaining_minutes} 分钟后可继续。"
        else:
            next_action = "run_next_cycle"
            note = "当前可以继续进入下一轮自动化。"
        next_run_at = cls._resolve_next_run_at(
            last_cycle=dict(state.get("last_cycle") or {}),
            cooldown_remaining_minutes=cooldown_remaining_minutes,
        )
        takeover_review_due_at = cls._resolve_takeover_review_due_at(
            takeover_since=takeover_since,
            long_run_seconds=long_run_seconds,
            manual_takeover=manual_takeover,
        )
        blocked_reason = ""
        if paused and manual_takeover:
            blocked_reason = "manual_takeover_active"
        elif paused:
            blocked_reason = "paused_waiting_review"
        elif mode == "manual":
            blocked_reason = "manual_mode"
        elif remaining_daily_cycle_count <= 0:
            blocked_reason = "daily_limit_reached"
        elif cooldown_remaining_minutes > 0:
            blocked_reason = "cooldown_active"
        ready_for_cycle = not paused and mode != "manual" and remaining_daily_cycle_count > 0 and cooldown_remaining_minutes <= 0
        story = cls._build_runtime_window_story(
            next_action=next_action,
            blocked_reason=blocked_reason,
            note=note,
            ready_for_cycle=ready_for_cycle,
            cooldown_remaining_minutes=cooldown_remaining_minutes,
            next_run_at=next_run_at,
            takeover_review_due_at=takeover_review_due_at,
        )
        return {
            "current_cycle_count": current_cycle_count,
            "daily_limit": daily_limit,
            "remaining_daily_cycle_count": remaining_daily_cycle_count,
            "cooldown_minutes": cooldown_minutes,
            "cooldown_remaining_minutes": cooldown_remaining_minutes,
            "long_run_seconds": long_run_seconds,
            "paused_since": str(state.get("paused_at", "") or ""),
            "takeover_since": str(state.get("manual_takeover_at", "") or ""),
            "takeover_elapsed_seconds": takeover_elapsed_seconds,
            "ready_for_cycle": ready_for_cycle,
            "next_action": next_action,
            "next_run_at": next_run_at,
            "takeover_review_due_at": takeover_review_due_at,
            "blocked_reason": blocked_reason,
            "note": note,
            "story": story,
        }

    @classmethod
    def _build_runtime_window_story(
        cls,
        *,
        next_action: str,
        blocked_reason: str,
        note: str,
        ready_for_cycle: bool,
        cooldown_remaining_minutes: int,
        next_run_at: str,
        takeover_review_due_at: str,
    ) -> dict[str, str]:
        """把等待和恢复流程压成任务页能直接读懂的摘要。"""

        next_run_label = cls._format_runtime_deadline(next_run_at)
        review_due_label = cls._format_runtime_deadline(takeover_review_due_at)
        if ready_for_cycle:
            return {
                "headline": "当前已经可以继续下一轮",
                "what_waiting_for": "系统现在不在等冷却窗口、轮次窗口或人工接管复核。",
                "when_it_runs": "下一步什么时候跑：保持当前模式即可继续下一轮自动化。",
                "why_not_resume": "为什么现在不能恢复：当前没有恢复阻塞，可以继续按当前模式推进。",
                "next_step": "恢复前先做什么：先看最近一轮结果，确认无误后继续自动化。",
            }
        if blocked_reason == "manual_takeover_active":
            due_text = f"最晚在 {review_due_label} 前先做接管复核。" if review_due_label else "接管持续较久时，先做接管复核。"
            return {
                "headline": "当前还在人工接管中",
                "what_waiting_for": "系统现在在等人工确认，执行器、同步和账户状态都要先收口。",
                "when_it_runs": f"下一步什么时候跑：{due_text}",
                "why_not_resume": "为什么现在不能恢复：接管原因还没清掉，直接恢复会把旧问题带进下一轮。",
                "next_step": f"恢复前先做什么：{note or '先处理接管原因，再决定是否恢复自动化。'}",
            }
        if blocked_reason == "paused_waiting_review":
            return {
                "headline": "当前处于暂停待复核状态",
                "what_waiting_for": "系统现在在等恢复清单通过，再决定是否继续自动化。",
                "when_it_runs": "下一步什么时候跑：先做完人工复核，再决定是否恢复当前模式。",
                "why_not_resume": "为什么现在不能恢复：暂停原因和恢复清单还没完全收口。",
                "next_step": f"恢复前先做什么：{note or '先看恢复清单和同步失败细节。'}",
            }
        if blocked_reason == "manual_mode":
            return {
                "headline": "当前处于手动模式",
                "what_waiting_for": "系统现在不在等冷却或恢复按钮，而是在等你决定是否重新打开自动化。",
                "when_it_runs": "下一步什么时候跑：只有切回 dry-run only 或自动模式后，系统才会继续下一轮。",
                "why_not_resume": "为什么现在不能恢复：当前不是暂停恢复问题，而是系统本来就在手动模式。",
                "next_step": f"恢复前先做什么：{note or '先人工确认，再决定是否切回自动模式。'}",
            }
        if blocked_reason == "daily_limit_reached":
            return {
                "headline": "今日自动化轮次已经用完",
                "what_waiting_for": "系统现在在等下一个时间窗口，今天不会再自动推进更多轮次。",
                "when_it_runs": "下一步什么时候跑：等到新的日内窗口后，才会继续下一轮。",
                "why_not_resume": "为什么现在不能恢复：不是按钮没生效，而是今日轮次上限已经触发。",
                "next_step": f"恢复前先做什么：{note or '先等下一轮时间窗口。'}",
            }
        if blocked_reason == "cooldown_active":
            when_text = (
                f"下一步什么时候跑：最早 {next_run_label} 后才能继续，当前还要等约 {cooldown_remaining_minutes} 分钟。"
                if next_run_label
                else f"下一步什么时候跑：当前还要等约 {cooldown_remaining_minutes} 分钟。"
            )
            return {
                "headline": "当前正在等待冷却窗口结束",
                "what_waiting_for": "系统现在在等这轮冷却时间走完，避免过于频繁地重复推进。",
                "when_it_runs": when_text,
                "why_not_resume": "为什么现在不能恢复：冷却窗口还没结束，重复点击恢复也不会提前开跑。",
                "next_step": f"恢复前先做什么：{note or '等冷却结束，期间先处理已有阻塞。'}",
            }
        return {
            "headline": f"当前还在等待 {next_action or '下一步调度'}",
            "what_waiting_for": "系统现在在等调度条件满足后，再继续自动推进。",
            "when_it_runs": "下一步什么时候跑：等当前阻塞解除后，系统会继续下一轮。",
            "why_not_resume": "为什么现在不能恢复：还有未完成的等待条件需要先清掉。",
            "next_step": f"恢复前先做什么：{note or '先处理当前阻塞。'}",
        }

    @classmethod
    def _build_resume_status(
        cls,
        *,
        runtime_window: dict[str, object],
        resume_checklist: list[dict[str, object]],
    ) -> dict[str, object]:
        """区分“能不能恢复”和“恢复后会不会立刻继续下一轮”。"""

        blocked_items = [
            {
                "label": str(item.get("label", "") or "检查项"),
                "detail": str(item.get("detail", "") or "当前没有额外说明。"),
            }
            for item in resume_checklist
            if str(item.get("status", "ready") or "ready").strip().lower() != "ready"
        ]
        blocked_labels = [str(item.get("label", "") or "检查项") for item in blocked_items]
        next_action = str(runtime_window.get("next_action", "") or "")
        blocked_reason = str(runtime_window.get("blocked_reason", "") or "")
        next_run_at = str(runtime_window.get("next_run_at", "") or "")
        story = dict(runtime_window.get("story") or {})
        ready_for_cycle = bool(runtime_window.get("ready_for_cycle"))
        resume_needed = blocked_reason in {"manual_takeover_active", "paused_waiting_review"}
        if blocked_reason == "manual_takeover_active":
            waiting_for = "manual_takeover_review"
            waiting_for_label = "系统在等人工接管处理完成"
        elif blocked_reason == "paused_waiting_review":
            waiting_for = "paused_review"
            waiting_for_label = "系统在等暂停原因复核完成"
        elif blocked_reason == "daily_limit_reached":
            waiting_for = "next_daily_window"
            waiting_for_label = "系统在等下一日调度窗口"
        elif blocked_reason == "cooldown_active":
            waiting_for = "cooldown_window"
            waiting_for_label = "系统在等冷却窗口结束"
        elif blocked_reason == "manual_mode":
            waiting_for = "manual_mode"
            waiting_for_label = "系统在等你切回自动模式"
        else:
            waiting_for = "none"
            waiting_for_label = "当前不需要等待"
        if blocked_reason == "manual_mode":
            cannot_resume_reason = "当前不需要点恢复按钮，系统现在就在手动模式；想继续自动化请先切回 dry-run only 或自动模式。"
        elif blocked_items:
            cannot_resume_reason = f"还不能恢复，因为恢复清单还有 {len(blocked_items)} 项未通过：{'、'.join(blocked_labels)}。"
        elif not resume_needed and ready_for_cycle:
            cannot_resume_reason = "当前不需要点恢复按钮，系统已经可以直接继续下一轮。"
        elif not resume_needed and blocked_reason == "cooldown_active":
            cannot_resume_reason = "当前不需要点恢复按钮，系统会在冷却结束后自动具备继续条件。"
        elif not resume_needed and blocked_reason == "daily_limit_reached":
            cannot_resume_reason = "当前不需要点恢复按钮，系统会等下一日窗口后再继续下一轮。"
        elif ready_for_cycle:
            cannot_resume_reason = "现在可以恢复，而且恢复后就能继续下一轮自动化。"
        else:
            cannot_resume_reason = str(story.get("why_not_resume", "") or "当前没有额外恢复限制说明。")
        if blocked_reason == "manual_mode":
            earliest_continue_text = "切回自动模式后可继续。"
        elif next_run_at:
            earliest_continue_text = f"最早可在 {cls._format_runtime_deadline(next_run_at)} 继续。"
        elif blocked_reason == "daily_limit_reached":
            earliest_continue_text = "需等到下一日窗口后继续。"
        elif blocked_items:
            earliest_continue_text = "处理完当前阻塞后可立即继续。"
        else:
            earliest_continue_text = "当前没有额外等待时间，确认无误后可继续。"
        return {
            "waiting_for": waiting_for,
            "waiting_for_label": waiting_for_label,
            "earliest_continue_at": next_run_at,
            "earliest_continue_text": earliest_continue_text,
            "resume_needed": resume_needed,
            "resume_ready": resume_needed and not blocked_items,
            "resume_blockers": blocked_items,
            "cannot_resume_reason": cannot_resume_reason,
            "continue_after_resume": resume_needed and next_action == "run_next_cycle" and not blocked_items,
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
            "comparison_run_limit": int(operations.get("comparison_run_limit", 5) or 5),
            "cycle_cooldown_minutes": int(operations.get("cycle_cooldown_minutes", 15) or 0),
            "max_daily_cycle_count": int(operations.get("max_daily_cycle_count", 8) or 8),
        }

    @staticmethod
    def _get_automation_config() -> dict[str, object]:
        """读取自动化长期运行与告警配置。"""

        config = workbench_config_service.get_config()
        automation = dict(config.get("automation") or {})
        return {
            "long_run_seconds": int(automation.get("long_run_seconds", 300) or 300),
            "alert_cleanup_minutes": int(automation.get("alert_cleanup_minutes", 15) or 15),
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

    @staticmethod
    def _resolve_next_run_at(*, last_cycle: dict[str, object], cooldown_remaining_minutes: int) -> str:
        """推算最早还能继续下一轮的时间。"""

        if cooldown_remaining_minutes <= 0:
            return ""
        recorded_at = str(last_cycle.get("recorded_at", "") or "").strip()
        if not recorded_at:
            return ""
        try:
            recorded = datetime.fromisoformat(recorded_at)
        except ValueError:
            return ""
        if recorded.tzinfo is None:
            recorded = recorded.replace(tzinfo=timezone.utc)
        return (recorded.astimezone(timezone.utc) + timedelta(minutes=cooldown_remaining_minutes)).isoformat()

    @staticmethod
    def _resolve_takeover_review_due_at(
        *,
        takeover_since: datetime | None,
        long_run_seconds: int,
        manual_takeover: bool,
    ) -> str:
        """推算人工接管最晚该复核的时间。"""

        if not manual_takeover or takeover_since is None or long_run_seconds <= 0:
            return ""
        return (takeover_since.astimezone(timezone.utc) + timedelta(seconds=long_run_seconds)).isoformat()

    @staticmethod
    def _format_runtime_deadline(value: str) -> str:
        """把运行时间点压成更适合页面说明的短格式。"""

        parsed = AutomationWorkflowService._parse_timestamp(value)
        if parsed is None:
            return ""
        return parsed.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    @staticmethod
    def _parse_timestamp(value: str) -> datetime | None:
        """解析时间字符串。"""

        normalized = str(value or "").strip()
        if not normalized:
            return None
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed


automation_workflow_service = AutomationWorkflowService()
