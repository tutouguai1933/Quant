"""自动化工作流服务。

这个文件负责把训练、推理、自动 dry-run、小额 live 和复盘收成一条统一流程。
"""

from __future__ import annotations

from services.api.app.core.settings import Settings
from services.api.app.services.automation_service import automation_service
from services.api.app.services.research_service import research_service
from services.api.app.services.signal_service import signal_service
from services.api.app.services.strategy_catalog import strategy_catalog_service
from services.api.app.services.sync_service import sync_service
from services.api.app.services.strategy_dispatch_service import strategy_dispatch_service
from services.api.app.services.validation_workflow_service import validation_workflow_service
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
        state = self._automation.get_state()
        report = self._reviewer.build_report(limit=10)
        return {
            "state": state,
            "health": self._automation.build_health_summary(task_health=task_health),
            "review_overview": dict(report.get("overview") or {}),
            "execution_health": self._syncer.get_execution_health_summary(task_health=task_health),
        }

    def run_cycle(self, *, source: str = "automation", review_limit: int = 10) -> dict[str, object]:
        """执行一轮自动化工作流。"""

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

        train_task = self._scheduler.run_named_task(task_type="research_train", source=source, target_type="system")
        if train_task["status"] != "succeeded":
            self._automation.record_alert(
                level="error",
                code="train_failed",
                message="自动训练失败",
                source=source,
                detail=str(train_task.get("error_message") or ""),
            )
            return self._finalize_failed_cycle(mode=mode, next_action="stop", review_limit=review_limit, tasks={"train": train_task})

        infer_task = self._scheduler.run_named_task(task_type="research_infer", source=source, target_type="system")
        if infer_task["status"] != "succeeded":
            self._automation.record_alert(
                level="error",
                code="infer_failed",
                message="自动推理失败",
                source=source,
                detail=str(infer_task.get("error_message") or ""),
            )
            return self._finalize_failed_cycle(mode=mode, next_action="stop", review_limit=review_limit, tasks={"train": train_task, "infer": infer_task})

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
            )

        recommendation = self._research.get_research_recommendation() or {}
        next_action = str(recommendation.get("next_action", "")) or "continue_research"
        recommended_symbol = str(recommendation.get("symbol", ""))
        recommended_strategy_id = strategy_catalog_service.resolve_strategy_id(str(recommendation.get("strategy_template", ""))) or 1
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
                next_action = "continue_research" if dispatch_result["error_code"] == "signal_not_ready" else "stop"
                dispatch_status = dispatch_result["status"]
                cycle_message = str(dispatch_result.get("message") or "")
                failure_reason = str(dispatch_result.get("error_code") or "")
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
    ) -> dict[str, object]:
        """在训练或推理失败时统一收口工作流。"""

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
            "review_task": review_task,
            "review_overview": dict(report.get("overview") or {}),
            **tasks,
        }
        self._automation.record_cycle(summary)
        return summary


automation_workflow_service = AutomationWorkflowService()
