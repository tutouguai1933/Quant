"""自动化工作流服务。

这个文件负责把训练、推理、自动 dry-run、小额 live 和复盘收成一条统一流程。
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Any

from services.api.app.services.candidate_priority_service import candidate_priority_service
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
from services.api.app.services.cycle_lock import CycleLock


class AutomationWorkflowService:
    """按当前自动化模式执行统一工作流。"""

    # get_status() 缓存 TTL（秒）
    _STATUS_CACHE_TTL = 10.0

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
        self._cycle_lock = CycleLock()
        # get_status() 缓存
        self._status_cache: dict[str, Any] | None = None
        self._status_cache_time: float = 0.0

    def get_status(self) -> dict[str, object]:
        """返回自动化状态和健康摘要（带缓存）。"""

        # 检查缓存是否有效
        now = time.time()
        if self._status_cache is not None and (now - self._status_cache_time) < self._STATUS_CACHE_TTL:
            return self._status_cache

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
        try:
            report = self._reviewer.build_report(limit=review_limit)
        except Exception:
            report = {
                "overview": {
                    "workflow_status": "unavailable",
                    "next_action": "review_backend",
                    "detail": "统一复盘暂时不可用，请先检查复盘服务。",
                }
            }
        health = self._automation.build_health_summary(task_health=task_health)
        runtime_window = self._build_runtime_window(state=state, operations=operations, automation_config=automation_config)
        resume_status = self._build_resume_status(
            state=state,
            runtime_window=runtime_window,
            resume_checklist=list(health.get("resume_checklist") or []),
        )
        control_actions = list(automation_status.get("control_actions") or health.get("control_actions") or [])
        control_matrix = self._build_control_matrix(
            state=state,
            resume_status=resume_status,
            control_actions=control_actions,
        )
        priority_queue_payload = self._build_priority_queue_payload(
            mode=str(state.get("mode", "manual") or "manual"),
            armed_symbol=str(state.get("armed_symbol", "") or ""),
        )
        try:
            execution_health = self._syncer.get_execution_health_summary(
                task_health=task_health,
                automation_state=state,
            )
        except Exception:
            execution_health = {
                "status": "unavailable",
                "connection_status": "disconnected",
                "detail": "执行同步暂时不可用，请先检查执行器和账户同步。",
            }
        runtime_guard = self._build_runtime_guard(
            state=state,
            task_health=task_health,
            runtime_window=runtime_window,
            resume_status=resume_status,
            execution_health=execution_health,
        )
        active_blockers = list(health.get("active_blockers") or [])
        operator_actions = list(health.get("operator_actions") or [])
        latest_alert = alerts[-1] if alerts else None
        recovery_review = self._build_recovery_review(
            state=state,
            task_health=task_health,
            runtime_window=runtime_window,
            resume_status=resume_status,
            execution_health=execution_health,
            active_blockers=active_blockers,
            operator_actions=operator_actions,
            latest_alert=latest_alert,
        )
        status_payload = {
            "state": state,
            "health": health,
            "operations": operations,
            "automation_config": automation_config,
            "execution_policy": dict(automation_status.get("execution_policy") or {}),
            "active_blockers": active_blockers,
            "operator_actions": operator_actions,
            "control_actions": control_actions,
            "control_matrix": control_matrix,
            "takeover_summary": dict(health.get("takeover_summary") or {}),
            "alert_summary": dict(health.get("alert_summary") or {}),
            "review_overview": dict(report.get("overview") or {}),
            "execution_health": execution_health,
            "daily_summary": dict(automation_status.get("daily_summary") or {}),
            "runtime_window": runtime_window,
            "runtime_guard": runtime_guard,
            "resume_status": resume_status,
            "recovery_review": recovery_review,
            "priority_queue": list(priority_queue_payload.get("items") or []),
            "priority_queue_summary": dict(priority_queue_payload.get("summary") or {}),
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
        # 保存到缓存
        self._status_cache = status_payload
        self._status_cache_time = now
        return status_payload

    def run_cycle(self, *, source: str = "automation", review_limit: int = 10) -> dict[str, object]:
        """执行一轮自动化工作流。"""

        # 尝试获取互斥锁，如果已被占用则立即返回
        if not self._cycle_lock.acquire(blocking=False):
            state = self._automation.get_state()
            mode = str(state.get("mode", "manual"))
            armed_symbol = str(state.get("armed_symbol", "")).strip().upper()
            return {
                "status": "running",
                "mode": mode,
                "recommended_symbol": "",
                "next_action": "wait_current_cycle",
                "message": "自动化工作流正在执行中，请等待当前周期完成。",
                "armed_symbol": armed_symbol,
            }

        try:
            return self._run_cycle_impl(source=source, review_limit=review_limit)
        finally:
            self._cycle_lock.release()

    def _run_cycle_impl(self, *, source: str = "automation", review_limit: int = 10) -> dict[str, object]:
        """执行一轮自动化工作流的实际实现。"""

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

        # 手动模式早期返回，不执行任何自动化任务
        if mode == "manual":
            summary = {
                "status": "waiting",
                "mode": mode,
                "recommended_symbol": "",
                "recommended_strategy_id": 0,
                "next_action": "manual_review",
                "message": "当前处于手动模式，请先人工确认再继续。",
                "failure_reason": "",
                "failure_policy_action": "",
                "armed_symbol": armed_symbol,
                "priority_queue_summary": {},
                "train_task": None,
                "infer_task": None,
                "signal_task": None,
                "review_task": None,
                "dispatch": None,
                "review_overview": {},
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

        priority_queue_payload = self._build_priority_queue_payload(
            mode=mode,
            armed_symbol=armed_symbol,
        )
        dispatch_queue = [
            dict(item)
            for item in list(priority_queue_payload.get("items") or [])
            if isinstance(item, dict)
        ]
        active_candidate = next((item for item in dispatch_queue if str(item.get("dispatch_status", "")) == "active"), None)
        focus_candidate = dict(active_candidate or (dispatch_queue[0] if dispatch_queue else {}) or {})
        next_action = str(focus_candidate.get("next_action", "")) or "continue_research"
        recommended_symbol = str(focus_candidate.get("symbol", ""))
        recommended_strategy_id = strategy_catalog_service.resolve_strategy_id(str(focus_candidate.get("strategy_template", ""))) or 1
        live_ready = bool(
            focus_candidate.get("allowed_to_live")
            if focus_candidate.get("allowed_to_live") is not None
            else focus_candidate.get("allowed_to_dry_run")
        )
        dispatch_result: dict[str, object] | None = None
        dispatch_status = "waiting"
        cycle_message = ""
        failure_reason = ""

        if mode == "manual":
            next_action = "manual_review"
            recommended_symbol = ""
            recommended_strategy_id = 0
            cycle_message = "当前处于手动模式，请先人工确认再继续。"
        elif not active_candidate:
            next_action = "continue_dry_run" if mode == "auto_live" else (next_action or "continue_research")
            dispatch_status = "blocked"
            failure_reason = str(focus_candidate.get("dispatch_code", "") or "candidate_queue_blocked")
            cycle_message = str(
                focus_candidate.get("dispatch_reason", "")
                or dict(priority_queue_payload.get("summary") or {}).get("detail", "")
                or "当前还没有可推进候选。"
            )
            self._automation.record_alert(
                level="warning",
                code=failure_reason,
                message=cycle_message,
                source=source,
                detail=recommended_symbol,
            )
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
            try:
                dispatch_result = self._dispatcher.dispatch_latest_signal(recommended_strategy_id, source=source)
            except Exception as e:
                self._automation.record_alert(
                    level="error",
                    code="execution_failed",
                    message="执行信号派发异常",
                    source=source,
                    detail=str(e),
                )
                if auto_pause_on_error:
                    self._automation.manual_takeover(reason="dispatch_execution_failed", actor=source)
                return self._finalize_failed_cycle(
                    mode=mode,
                    next_action="review_and_decide",
                    review_limit=review_limit,
                    tasks={"train": train_task, "infer": infer_task, "signal_output": signal_task},
                    failure_policy_action="review_and_decide",
                    takeover_reason="dispatch_execution_failed",
                    source=source,
                    auto_pause_on_error=auto_pause_on_error,
                    failure_reason="execution_failed",
                )
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
            "priority_queue_summary": dict(priority_queue_payload.get("summary") or {}),
            "priority_queue": {"items": dispatch_queue[:5]},  # 添加前5个候选
            "train_task": train_task,
            "infer_task": infer_task,
            "signal_task": signal_task,
            "dispatch": dispatch_result,
            "review_task": review_task,
            "review_overview": dict(report.get("overview") or {}),
        }
        self._automation.record_cycle(summary)
        return summary

    def _build_priority_queue_payload(self, *, mode: str, armed_symbol: str) -> dict[str, object]:
        """读取研究队列，并转换成当前模式可直接消费的调度摘要。"""

        getter = getattr(self._research, "get_research_priority_queue", None)
        if callable(getter):
            payload = getter()
            if isinstance(payload, dict):
                return candidate_priority_service.build_dispatch_queue(
                    priority_queue=payload,
                    mode=mode,
                    armed_symbol=armed_symbol,
                )
        recommendation_getter = getattr(self._research, "get_research_recommendation", None)
        recommendation = recommendation_getter() if callable(recommendation_getter) else None
        fallback_queue = {
            "items": [
                {
                    **dict(recommendation or {}),
                    "queue_status": "ready" if bool(dict(recommendation or {}).get("allowed_to_dry_run")) else "blocked",
                    "recommended_stage": "live"
                    if bool(dict(recommendation or {}).get("allowed_to_live"))
                    else "dry_run"
                    if bool(dict(recommendation or {}).get("allowed_to_dry_run"))
                    else "research",
                }
            ]
            if isinstance(recommendation, dict) and recommendation
            else [],
            "summary": {},
        }
        return candidate_priority_service.build_dispatch_queue(
            priority_queue=fallback_queue,
            mode=mode,
            armed_symbol=armed_symbol,
        )

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
        failure_reason: str = "workflow_failed",
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
            "failure_reason": failure_reason,
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
    def _build_runtime_guard(
        cls,
        *,
        state: dict[str, object],
        task_health: dict[str, object],
        runtime_window: dict[str, object],
        resume_status: dict[str, object],
        execution_health: dict[str, object],
    ) -> dict[str, object]:
        """构建运行时守卫状态，包括降级模式判断和完整阻塞列表。"""

        ready_for_cycle = bool(runtime_window.get("ready_for_cycle", False))
        blocked_reason = str(runtime_window.get("blocked_reason", ""))
        paused = bool(state.get("paused", False))
        manual_takeover = bool(state.get("manual_takeover", False))
        mode = str(state.get("mode", "manual"))
        paused_reason = str(state.get("paused_reason", ""))

        executor_status = str(execution_health.get("executor_status", "unknown"))
        sync_status = str(execution_health.get("sync_status", "unknown"))
        connection_status = str(execution_health.get("connection_status", "unknown"))

        # 检查是否有正在运行的自动化周期
        latest_status_by_type = dict(task_health.get("latest_status_by_type") or {})
        automation_cycle_running = str(latest_status_by_type.get("automation_cycle", "")) == "running"

        # 判断降级模式和状态
        degrade_mode = "none"
        status = "ready"
        operator_route = "/tasks"
        degrade_reason = ""

        # 如果执行器或同步异常，进入 task_hub_only 模式
        if connection_status == "disconnected" or executor_status in {"error", "disconnected"} or sync_status in {"error", "stale"}:
            degrade_mode = "task_hub_only"
            status = "degraded"
            degrade_reason = "执行器或同步服务异常，仅允许任务页操作"
        # 如果正在运行周期，进入 cycle_running 模式
        elif automation_cycle_running:
            degrade_mode = "cycle_running"
            status = "running"
            degrade_reason = "自动化周期正在执行中"
        # 如果人工接管或暂停，进入 manual_only 模式
        elif manual_takeover or (paused and blocked_reason in {"manual_takeover_active", "paused_waiting_review"}):
            degrade_mode = "manual_only"
            status = "attention_required"
            degrade_reason = "人工接管或暂停中，需要人工确认后才能继续"
        # 如果手动模式，进入 manual_only
        elif mode == "manual":
            degrade_mode = "manual_only"
            status = "ready"
            degrade_reason = "手动模式下系统不会自动推进"
        # 如果在等待窗口（冷却或日限），进入 window_wait 模式
        elif blocked_reason in {"cooldown_active", "daily_limit_reached"}:
            degrade_mode = "window_wait"
            status = "waiting"
            if blocked_reason == "cooldown_active":
                degrade_reason = "冷却窗口未结束，需等待后才能继续"
            else:
                degrade_reason = "今日轮次已用完，需等待下一轮时间窗口"
        # 否则进入 full 模式
        else:
            degrade_mode = "full"
            status = "ready"
            degrade_reason = "无阻塞，系统可完全自动运行"

        # 构建告警上下文
        alert_context = {}

        # 如果正在运行周期，设置 info 级别告警
        if automation_cycle_running:
            alert_context = {
                "level": "info",
                "code": "automation_cycle_running",
                "message": "自动化工作流正在执行中",
            }
        # 如果连接断开，设置 error 级别告警
        elif connection_status == "disconnected":
            alert_context = {
                "level": "error",
                "code": "dependency_unavailable",
                "message": "执行器或同步服务连接断开",
            }
        # 如果人工接管，设置 warning 级别告警
        elif manual_takeover:
            alert_context = {
                "level": "warning",
                "code": "manual_takeover_enabled",
                "message": "当前处于人工接管模式",
            }
        # 否则从状态中读取最新告警
        else:
            alerts = list(state.get("alerts") or [])
            if alerts:
                latest_alert = alerts[-1] if isinstance(alerts[-1], dict) else {}
                alert_context = {
                    "level": str(latest_alert.get("level", "")),
                    "code": str(latest_alert.get("code", "")),
                    "message": str(latest_alert.get("message", "")),
                }

        # 构建阻塞列表
        blockers: list[dict[str, str]] = []
        if connection_status == "disconnected":
            blockers.append({
                "code": "dependency_unavailable",
                "label": "执行器或同步服务连接断开",
                "severity": "error",
            })
        if executor_status in {"error", "disconnected"}:
            blockers.append({
                "code": "executor_error",
                "label": "执行器状态异常",
                "severity": "error",
            })
        if sync_status in {"error", "stale"}:
            blockers.append({
                "code": "sync_error",
                "label": "同步状态异常或陈旧",
                "severity": "error",
            })
        if manual_takeover:
            blockers.append({
                "code": "manual_takeover_active",
                "label": "人工接管中",
                "severity": "warning",
            })
        if paused and blocked_reason == "paused_waiting_review":
            blockers.append({
                "code": "paused_waiting_review",
                "label": "自动化暂停等待复核",
                "severity": "warning",
            })
        if mode == "manual":
            blockers.append({
                "code": "manual_mode",
                "label": "手动模式",
                "severity": "info",
            })
        if blocked_reason == "cooldown_active":
            blockers.append({
                "code": "cooldown_active",
                "label": "冷却窗口中",
                "severity": "info",
            })
        if blocked_reason == "daily_limit_reached":
            blockers.append({
                "code": "daily_limit_reached",
                "label": "今日轮次已用完",
                "severity": "info",
            })
        if automation_cycle_running:
            blockers.append({
                "code": "automation_cycle_running",
                "label": "自动化周期执行中",
                "severity": "info",
            })
        # 如果没有任何阻塞项，添加一个空阻塞表示可运行
        if not blockers:
            blockers.append({
                "code": "none",
                "label": "无阻塞",
                "severity": "info",
            })

        # 构建建议动作
        suggested_action = ""
        suggested_action_reason = ""
        if status == "ready" and ready_for_cycle:
            suggested_action = "run_cycle"
            suggested_action_reason = "当前无阻塞，可以启动下一轮自动化周期"
        elif status == "ready" and not ready_for_cycle:
            suggested_action = "wait"
            suggested_action_reason = "当前无阻塞但暂未准备好，等待条件满足后自动启动"
        elif status == "running":
            suggested_action = "wait"
            suggested_action_reason = "自动化周期正在执行中，等待完成后检查结果"
        elif status == "waiting":
            if blocked_reason == "cooldown_active":
                suggested_action = "wait_cooldown"
                suggested_action_reason = "冷却窗口中，等待冷却结束后可继续"
            elif blocked_reason == "daily_limit_reached":
                suggested_action = "wait_next_window"
                suggested_action_reason = "今日轮次已用完，等待下一轮时间窗口"
            else:
                suggested_action = "wait"
                suggested_action_reason = "等待条件满足后可继续"
        elif status == "attention_required":
            if manual_takeover:
                suggested_action = "review_takeover"
                suggested_action_reason = "人工接管中，需确认执行器、同步和账户状态后再决定是否恢复"
            elif paused:
                suggested_action = "resume_after_review"
                suggested_action_reason = "自动化暂停中，处理阻塞原因后可恢复"
            else:
                suggested_action = "review"
                suggested_action_reason = "需要人工确认后才能继续"
        elif status == "blocked" or status == "degraded":
            suggested_action = "resolve_blocker"
            suggested_action_reason = "存在阻塞项，需先处理阻塞原因后才能继续"
        else:
            suggested_action = "observe"
            suggested_action_reason = "当前状态无需特殊操作，继续观察"

        # 获取额外时间字段
        cooldown_ends_at = str(runtime_window.get("next_run_at", "") or "")
        last_cycle = dict(state.get("last_cycle") or {})
        last_cycle_at = str(last_cycle.get("recorded_at", "") or "")
        cycles_today = int(runtime_window.get("current_cycle_count", 0) or 0)

        # 判断是否允许 OpenClaw 自动运行
        auto_run_allowed = (
            status in {"ready", "waiting"}
            and degrade_mode in {"full", "window_wait"}
            and mode in {"auto_dry_run", "auto_live"}
            and not paused
            and not manual_takeover
        )

        return {
            "status": status,
            "ready_for_cycle": ready_for_cycle,
            "blocked_reason": blocked_reason,
            "blockers": blockers,
            "degrade_mode": degrade_mode,
            "degrade_reason": degrade_reason,
            "suggested_action": suggested_action,
            "suggested_action_reason": suggested_action_reason,
            "cooldown_ends_at": cooldown_ends_at,
            "last_cycle_at": last_cycle_at,
            "cycles_today": cycles_today,
            "auto_run_allowed": auto_run_allowed,
            "operator_route": operator_route,
            "takeover_review_due_at": str(runtime_window.get("takeover_review_due_at", "")),
            "alert_context": alert_context,
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
        state: dict[str, object],
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
        next_action = str(runtime_window.get("next_action", "") or "")
        blocked_reason = str(runtime_window.get("blocked_reason", "") or "")
        next_run_at = str(runtime_window.get("next_run_at", "") or "")
        story = dict(runtime_window.get("story") or {})
        ready_for_cycle = bool(runtime_window.get("ready_for_cycle"))
        mode = str(state.get("mode", "manual") or "manual")
        armed_symbol = str(state.get("armed_symbol", "") or "").strip().upper()
        paused_reason = str(state.get("paused_reason", "") or "").strip()
        resume_needed = blocked_reason in {"manual_takeover_active", "paused_waiting_review"}
        hard_pause_reasons = {
            "kill_switch",
            "risk_guard_triggered",
            "consecutive_failure_guard_triggered",
            "stale_sync_guard_triggered",
            "workflow_train_failed",
            "workflow_infer_failed",
            "workflow_signal_output_failed",
            "dispatch_execution_failed",
        }
        manual_required_reasons = hard_pause_reasons | {"manual_takeover", "manual_review"}
        manual_required_reason = bool(state.get("manual_takeover")) or paused_reason in manual_required_reasons
        if blocked_reason == "manual_takeover_active" and next_action == "review_takeover" and not blocked_items:
            blocked_items = [
                {
                    "label": "人工接管复核",
                    "detail": "人工接管已持续较久，先确认执行器、同步和账户状态，再决定是否恢复。",
                }
            ]
        blocked_labels = [str(item.get("label", "") or "检查项") for item in blocked_items]
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
        recovery_state = "waiting"
        primary_action = ""
        primary_action_label = ""
        primary_action_detail = ""
        if blocked_reason == "manual_mode":
            primary_action = "automation_dry_run_only"
            primary_action_label = "切到 dry-run only"
            primary_action_detail = "当前是手动模式，想重新打开自动化时，先从 dry-run only 开始更安全。"
            cannot_resume_reason = "当前不需要点恢复按钮，系统现在就在手动模式；想继续自动化请先切回 dry-run only 或自动模式。"
        elif blocked_items:
            recovery_state = "manual_required"
            primary_action = "automation_mode_manual"
            primary_action_label = "先人工处理"
            primary_action_detail = "恢复清单还有未通过项，先处理这些阻塞，再决定是否恢复自动化。"
            cannot_resume_reason = f"还不能恢复，因为恢复清单还有 {len(blocked_items)} 项未通过：{'、'.join(blocked_labels)}。"
        elif manual_required_reason:
            recovery_state = "manual_required"
            primary_action = "automation_mode_manual"
            primary_action_label = "保持手动"
            primary_action_detail = "当前还有风控、失败或执行异常需要人工处理，先保持手动并完成收口。"
            cannot_resume_reason = "当前还有风险或异常需要人工处理，先保持手动并处理完接管原因，再决定是否恢复自动化。"
        elif resume_needed and mode == "auto_live" and not armed_symbol:
            recovery_state = "dry_run_only"
            primary_action = "automation_dry_run_only"
            primary_action_label = "只恢复到 dry-run"
            primary_action_detail = "当前还没有 dry-run 验证通过的候选，先只恢复到 dry-run，再决定是否重新进入 live。"
            cannot_resume_reason = "当前还没有 dry-run 验证通过的候选，不能直接恢复 live，先只恢复到 dry-run 更安全。"
        elif resume_needed:
            recovery_state = "recoverable"
            primary_action = "automation_resume"
            primary_action_label = "确认后恢复自动化"
            primary_action_detail = "暂停原因已经处理完成，现在可以恢复当前自动化模式。"
            cannot_resume_reason = "现在可以恢复，而且恢复后就能继续下一轮自动化。"
        elif not resume_needed and ready_for_cycle:
            primary_action = "automation_run_cycle"
            primary_action_label = "运行自动化工作流"
            primary_action_detail = "当前没有恢复阻塞，可以直接继续下一轮训练、推理、执行和复盘。"
            cannot_resume_reason = "当前不需要点恢复按钮，系统已经可以直接继续下一轮。"
        elif not resume_needed and blocked_reason == "cooldown_active":
            cannot_resume_reason = "当前不需要点恢复按钮，系统会在冷却结束后自动具备继续条件。"
        elif not resume_needed and blocked_reason == "daily_limit_reached":
            cannot_resume_reason = "当前不需要点恢复按钮，系统会等下一日窗口后再继续下一轮。"
        else:
            cannot_resume_reason = str(story.get("why_not_resume", "") or "当前没有额外恢复限制说明。")
        if recovery_state == "dry_run_only":
            earliest_continue_text = "先切回 dry-run only 后可继续。"
        elif blocked_reason == "manual_mode":
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
            "recovery_state": recovery_state,
            "primary_action": primary_action,
            "primary_action_label": primary_action_label,
            "primary_action_detail": primary_action_detail,
        }

    @classmethod
    def _build_recovery_review(
        cls,
        *,
        state: dict[str, object],
        task_health: dict[str, object],
        runtime_window: dict[str, object],
        resume_status: dict[str, object],
        execution_health: dict[str, object],
        active_blockers: list[dict[str, object]],
        operator_actions: list[dict[str, object]],
        latest_alert: dict[str, object] | None,
    ) -> dict[str, object]:
        """构建恢复复核摘要，整合运行时守卫、恢复状态和执行健康。"""

        runtime_guard_status = str(runtime_window.get("blocked_reason", ""))
        recovery_state = str(resume_status.get("recovery_state", "waiting"))
        connection_status = str(execution_health.get("connection_status", "unknown"))
        execution_status = str(execution_health.get("status", "unknown"))
        mode = str(state.get("mode", "manual"))
        manual_takeover = bool(state.get("manual_takeover"))
        paused = bool(state.get("paused"))
        ready_for_cycle = bool(runtime_window.get("ready_for_cycle", False))

        # 检查是否有正在运行的自动化周期
        latest_status_by_type = dict(task_health.get("latest_status_by_type") or {})
        automation_cycle_running = str(latest_status_by_type.get("automation_cycle", "")) == "running"

        # 确定状态
        if automation_cycle_running:
            status = "running"
        elif connection_status == "disconnected" or execution_status == "unavailable":
            status = "attention_required"
        elif manual_takeover and active_blockers:
            status = "attention_required"
        elif recovery_state == "recoverable":
            status = "ready"
        elif recovery_state == "manual_required":
            status = "attention_required"
        elif recovery_state == "dry_run_only":
            status = "ready"
        elif mode == "manual":
            status = "blocked"
        elif runtime_guard_status in {"cooldown_active", "daily_limit_reached"}:
            status = "waiting"
        elif ready_for_cycle:
            status = "ready"
        else:
            status = "waiting"

        # 确定 issue_code
        issue_code = ""
        if connection_status == "disconnected" or execution_status == "unavailable":
            issue_code = "execution_unavailable"
        elif manual_takeover:
            issue_code = "manual_takeover"
        elif runtime_guard_status == "paused_waiting_review":
            issue_code = "paused_review"
        elif runtime_guard_status == "cooldown_active":
            issue_code = "cooldown_active"
        elif runtime_guard_status == "daily_limit_reached":
            issue_code = "daily_limit_reached"
        elif mode == "manual":
            issue_code = "manual_mode"

        # 获取 detail
        story = dict(runtime_window.get("story") or {})
        detail = ""
        if automation_cycle_running:
            detail = "系统正在执行自动化工作流，请等待当前周期完成。"
        elif connection_status == "disconnected" or execution_status == "unavailable":
            detail = str(execution_health.get("detail", "执行同步暂时不可用，请先检查执行器和账户同步。"))
        elif runtime_guard_status == "daily_limit_reached":
            # 对于日限的情况，使用固定文本
            detail = "需等到下一日窗口后继续。"
        elif runtime_guard_status == "cooldown_active":
            # 对于冷却的情况，使用 note（包含冷却时间）
            detail = str(runtime_window.get("note", ""))
        else:
            detail = str(runtime_window.get("note", "") or story.get("next_step", ""))

        # 获取 waiting_for
        waiting_for = str(resume_status.get("waiting_for", "none"))
        if automation_cycle_running:
            waiting_for = "active_cycle"

        # 获取 next_action 和 next_action_label
        if automation_cycle_running:
            next_action = "observe_current_run"
            next_action_label = "观察当前运行"
        else:
            next_action = str(resume_status.get("primary_action", "") or runtime_window.get("next_action", ""))
            next_action_label = str(resume_status.get("primary_action_label", ""))

            # 如果 label 为空，使用默认映射
            if not next_action_label and next_action:
                action_label_map = {
                    "automation_resume": "确认后恢复自动化",
                    "automation_dry_run_only": "只恢复到 dry-run",
                    "automation_mode_manual": "保持手动",
                    "automation_run_cycle": "运行自动化工作流",
                    "wait_cooldown": "等待冷却窗口",
                    "wait_next_window": "等待下一日窗口",
                    "manual_review": "人工复核",
                    "resume_after_review": "复核后恢复",
                    "review_takeover": "复核接管状态",
                    "manual_takeover": "人工接管",
                    "run_next_cycle": "运行下一轮",
                    "observe_current_run": "观察当前运行",
                }
                next_action_label = action_label_map.get(next_action, next_action)

        # 获取 headline - 根据 recovery_state 调整
        if automation_cycle_running:
            headline = "系统正在执行自动化工作流"
        elif recovery_state == "recoverable" and runtime_guard_status == "paused_waiting_review":
            headline = "当前可以恢复自动化"
        else:
            headline = str(story.get("headline", ""))

        # 获取 blockers
        resume_blockers = list(resume_status.get("resume_blockers") or [])
        blockers = cls._normalize_recovery_blockers(
            resume_blockers=resume_blockers,
            active_blockers=active_blockers,
        )

        # 获取 earliest_resume_at
        earliest_resume_at = str(resume_status.get("earliest_continue_at", ""))

        return {
            "status": status,
            "issue_code": issue_code,
            "detail": detail,
            "waiting_for": waiting_for,
            "next_action": next_action,
            "next_action_label": next_action_label,
            "headline": headline,
            "blockers": blockers,
            "earliest_resume_at": earliest_resume_at,
        }

    @staticmethod
    def _normalize_recovery_blockers(
        *,
        resume_blockers: list[dict[str, object]],
        active_blockers: list[dict[str, object]],
    ) -> list[dict[str, str]]:
        """合并恢复阻塞和活跃阻塞，去重并保留必要字段。"""

        seen: set[str] = set()
        result: list[dict[str, str]] = []

        # 先添加 resume_blockers
        for item in resume_blockers:
            if not isinstance(item, dict):
                continue
            label = str(item.get("label", ""))
            detail = str(item.get("detail", ""))
            if label and label not in seen:
                seen.add(label)
                result.append({"label": label, "detail": detail})

        # 再添加 active_blockers（只添加没有 code 字段的，或者 code 为空的）
        for item in active_blockers:
            if not isinstance(item, dict):
                continue
            # 如果有 code 字段且不为空，跳过
            if item.get("code"):
                continue
            label = str(item.get("label", ""))
            detail = str(item.get("detail", ""))
            if label and label not in seen:
                seen.add(label)
                result.append({"label": label, "detail": detail})

        return result

    @classmethod
    def _build_control_matrix(
        cls,
        *,
        state: dict[str, object],
        resume_status: dict[str, object],
        control_actions: list[dict[str, object]],
    ) -> dict[str, object]:
        """把恢复流程和人工接管入口统一成同一份动作矩阵。"""

        recovery_state = str(resume_status.get("recovery_state", "waiting") or "waiting")
        primary_action = str(resume_status.get("primary_action", "") or "")
        primary_action_label = str(resume_status.get("primary_action_label", "") or "")
        primary_action_detail = str(resume_status.get("primary_action_detail", "") or "")
        cannot_resume_reason = str(resume_status.get("cannot_resume_reason", "") or "")
        mode = str(state.get("mode", "manual") or "manual")
        paused = bool(state.get("paused"))
        manual_takeover = bool(state.get("manual_takeover"))
        defaults: dict[str, dict[str, object]] = {
            "automation_resume": {
                "action": "automation_resume",
                "label": "确认后恢复自动化",
                "detail": "只有在告警、同步和暂停原因都处理完后，才恢复当前自动化模式。",
                "danger": False,
            },
            "automation_dry_run_only": {
                "action": "automation_dry_run_only",
                "label": "只恢复到 dry-run",
                "detail": "如果你还不想放开真实资金，先切回只保留 dry-run。",
                "danger": False,
            },
            "automation_mode_manual": {
                "action": "automation_mode_manual",
                "label": "保持手动",
                "detail": "继续停在手动模式，先人工判断和处理异常。",
                "danger": False,
            },
            "automation_kill_switch": {
                "action": "automation_kill_switch",
                "label": "Kill Switch",
                "detail": "一键停机，继续保持最保守状态。",
                "danger": True,
            },
            "automation_pause": {
                "action": "automation_pause",
                "label": "暂停自动化",
                "detail": "先停住后续自动推进，回到人工判断。",
                "danger": False,
            },
            "automation_manual_takeover": {
                "action": "automation_manual_takeover",
                "label": "转人工接管",
                "detail": "立刻切到人工接管，先人工确认，再决定下一步。",
                "danger": True,
            },
            "automation_run_cycle": {
                "action": "automation_run_cycle",
                "label": "运行自动化工作流",
                "detail": "按当前模式推进一轮训练、推理、执行和复盘。",
                "danger": False,
            },
        }
        merged_actions: dict[str, dict[str, object]] = {}
        for item in control_actions:
            action = str(item.get("action", "") or "").strip()
            if not action:
                continue
            merged_actions[action] = {
                **defaults.get(action, {}),
                **dict(item),
            }
        if recovery_state in {"recoverable", "dry_run_only", "manual_required"}:
            action_order = ["automation_resume", "automation_dry_run_only", "automation_mode_manual", "automation_kill_switch"]
        elif paused or manual_takeover:
            action_order = ["automation_resume", "automation_dry_run_only", "automation_mode_manual", "automation_kill_switch"]
        elif mode == "manual":
            action_order = ["automation_mode_manual", "automation_dry_run_only", "automation_kill_switch"]
        else:
            action_order = [
                str(item.get("action", "") or "").strip()
                for item in control_actions
                if str(item.get("action", "") or "").strip()
            ]
            if not action_order:
                action_order = [
                    "automation_pause",
                    "automation_manual_takeover",
                    "automation_mode_manual",
                    "automation_dry_run_only",
                    "automation_kill_switch",
                ]
        items: list[dict[str, object]] = []
        for action in action_order:
            row = {
                **defaults.get(action, {"action": action, "label": action, "detail": "当前没有额外说明。", "danger": False}),
                **merged_actions.get(action, {}),
            }
            enabled = True
            disabled_reason = ""
            if action == "automation_resume":
                enabled = recovery_state == "recoverable"
                if not enabled:
                    if recovery_state == "dry_run_only":
                        disabled_reason = "当前还没有 dry-run 验证通过的候选，先只恢复到 dry-run。"
                    elif recovery_state == "manual_required":
                        disabled_reason = "当前还有风险或异常需要先人工处理，暂时不能直接恢复自动化。"
                    else:
                        disabled_reason = cannot_resume_reason or "当前不需要点恢复按钮。"
            elif action == "automation_dry_run_only" and recovery_state == "manual_required":
                enabled = False
                disabled_reason = "当前还有风险或异常需要先人工处理，先保持手动更安全。"
            row["enabled"] = enabled
            row["disabled_reason"] = disabled_reason
            items.append(row)
        return {
            "state": recovery_state,
            "primary_action": primary_action,
            "primary_action_label": primary_action_label,
            "primary_action_detail": primary_action_detail,
            "items": items,
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
