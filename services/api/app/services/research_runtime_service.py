"""研究动作运行状态服务。

这个文件负责把研究训练、研究推理和 Qlib 流水线改成后台执行，并提供进度、预计时长和结果去向。
"""

from __future__ import annotations

import json
import math
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from services.api.app.services.automation_service import automation_service
from services.api.app.services.research_service import research_service
from services.api.app.services.signal_service import signal_service
from services.api.app.services.validation_workflow_service import validation_workflow_service
from services.api.app.services.workbench_config_service import workbench_config_service
from services.api.app.tasks.scheduler import task_scheduler
from services.api.app.websocket.push_bridge import push_bridge
from services.worker.qlib_config import load_qlib_config


def _utc_now() -> str:
    """返回当前 UTC 时间。"""

    return datetime.now(timezone.utc).isoformat()


class ResearchRuntimeService:
    """负责后台研究任务状态。"""

    def __init__(
        self,
        *,
        config_loader: Callable[[], object] | None = None,
        research_service_instance=None,
        signal_service_instance=None,
        scheduler_instance=None,
        reviewer_instance=None,
        automation_instance=None,
        async_runner: Callable[[Callable[[], None]], None] | None = None,
    ) -> None:
        self._config_loader = config_loader or load_qlib_config
        self._research_service = research_service_instance or research_service
        self._signal_service = signal_service_instance or signal_service
        self._scheduler = scheduler_instance or task_scheduler
        self._reviewer = reviewer_instance or validation_workflow_service
        self._automation = automation_instance or automation_service
        self._lock = threading.Lock()
        self._active_thread: threading.Thread | None = None
        self._async_runner = async_runner or self._spawn_thread

    def get_status(self) -> dict[str, object]:
        """读取当前运行状态。"""

        config = self._config_loader()
        state = self._read_state(self._status_path(config))
        if state.get("status") == "running" and not self._is_thread_alive():
            state["status"] = "interrupted"
            state["message"] = "上一次研究任务在服务重启或中断前未完整结束，请重新发起。"
            state["current_stage"] = "interrupted"
        estimated = self._build_estimates(state)
        action = str(state.get("action") or "")
        return {
            "status": str(state.get("status") or "idle"),
            "action": action,
            "current_stage": str(state.get("current_stage") or "idle"),
            "progress_pct": int(state.get("progress_pct") or 0),
            "started_at": str(state.get("started_at") or ""),
            "finished_at": str(state.get("finished_at") or ""),
            "message": str(state.get("message") or "当前没有研究任务在运行。"),
            "last_completed_action": str(state.get("last_completed_action") or ""),
            "last_finished_at": str(state.get("last_finished_at") or ""),
            "result_paths": list(state.get("result_paths") or ["/research", "/evaluation", "/signals"]),
            "history": dict(state.get("history") or {}),
            "estimated_seconds": estimated,
            "current_estimate_seconds": int(estimated.get(action) or 0),
        }

    def start_training(self) -> dict[str, object]:
        """后台启动研究训练。"""

        return self._start("training")

    def start_inference(self) -> dict[str, object]:
        """后台启动研究推理。"""

        latest = self._research_service.get_latest_result()
        if not latest.get("latest_training"):
            raise RuntimeError("研究层还没有训练结果，请先运行研究训练。")
        return self._start("inference")

    def start_pipeline(self) -> dict[str, object]:
        """后台启动完整 Qlib 流水线。"""

        return self._start("pipeline")

    def _start(self, action: str) -> dict[str, object]:
        """写入起始状态并异步运行。"""

        config = self._config_loader()
        config.ensure_ready()
        with self._lock:
            current = self.get_status()
            if current.get("status") == "running":
                raise RuntimeError("研究任务正在运行，请等当前任务完成后再发起。")

            state = {
                "status": "running",
                "action": action,
                "current_stage": "queued",
                "progress_pct": 5,
                "started_at": _utc_now(),
                "finished_at": "",
                "message": self._queued_message(action),
                "last_completed_action": str(current.get("last_completed_action") or ""),
                "last_finished_at": str(current.get("last_finished_at") or ""),
                "result_paths": ["/research", "/evaluation", "/signals"],
                "history": dict(current.get("history") or {}),
            }
            self._write_state(self._status_path(config), state)
            if action == "pipeline":
                self._record_manual_cycle_started()
        self._async_runner(lambda: self._run_job(action))
        return self.get_status()

    def _run_job(self, action: str) -> None:
        """执行后台任务。"""

        started_at = time.perf_counter()
        try:
            if action == "training":
                self._update_state(action, "preparing_dataset", 15, "正在准备训练样本和特征。")
                task = self._scheduler.run_named_task(task_type="research_train", source="manual_training", target_type="system")
                self._ensure_task_succeeded(task, "研究训练失败")
                self._mark_success(action, started_at, "研究训练已完成，可继续运行研究推理。")
                return
            if action == "inference":
                self._update_state(action, "loading_model", 20, "正在读取最新模型并准备推理。")
                task = self._scheduler.run_named_task(task_type="research_infer", source="manual_inference", target_type="system")
                self._ensure_task_succeeded(task, "研究推理失败")
                self._mark_success(action, started_at, "研究推理已完成，可查看候选排行和统一研究报告。")
                return
            if action == "pipeline":
                self._update_state(action, "training_model", 20, "正在训练研究模型。")
                train_task = self._scheduler.run_named_task(task_type="research_train", source="manual_pipeline", target_type="system")
                self._ensure_task_succeeded(train_task, "研究训练失败")
                self._update_state(action, "running_inference", 65, "训练完成，正在生成候选和推荐动作。")
                infer_task = self._scheduler.run_named_task(task_type="research_infer", source="manual_pipeline", target_type="system")
                self._ensure_task_succeeded(infer_task, "研究推理失败")
                self._update_state(action, "writing_signals", 85, "候选已生成，正在回写统一信号。")
                signal_task = self._scheduler.run_named_task(task_type="signal_output", source="manual_pipeline", target_type="system")
                self._ensure_task_succeeded(signal_task, "统一信号回写失败")
                review_task = self._scheduler.run_named_task(
                    task_type="review",
                    source="manual_pipeline",
                    target_type="system",
                    payload={"limit": self._resolve_review_limit()},
                )
                review_report = self._reviewer.build_report(limit=self._resolve_review_limit())
                self._record_manual_cycle(
                    review_report=review_report,
                    train_task=train_task,
                    infer_task=infer_task,
                    signal_task=signal_task,
                    review_task=review_task,
                )
                self._mark_success(action, started_at, "Qlib 信号流水线已完成，可去信号页、评估页和策略页查看结果。")
                return
            raise RuntimeError(f"unsupported research runtime action: {action}")
        except Exception as exc:
            if action == "pipeline":
                self._record_manual_failure(message=str(exc))
            self._mark_failed(action, started_at, str(exc))

    @staticmethod
    def _ensure_task_succeeded(task: dict[str, object], fallback_message: str) -> None:
        """确保任务成功，否则抛出统一错误。"""

        if str(task.get("status", "")) == "succeeded":
            return
        result = task.get("result")
        detail = result.get("detail") if isinstance(result, dict) else ""
        message = str(task.get("error_message") or detail or fallback_message)
        raise RuntimeError(message)

    def _record_manual_cycle(
        self,
        *,
        review_report: dict[str, object],
        train_task: dict[str, object],
        infer_task: dict[str, object],
        signal_task: dict[str, object],
        review_task: dict[str, object],
    ) -> None:
        """把手动流水线写进统一工作流摘要。"""

        overview = dict(review_report.get("overview") or {})
        latest_result = self._read_latest_result()
        recommendation = self._read_recommendation()
        summary = {
            "status": "succeeded" if str(review_task.get("status", "")) == "succeeded" else "attention_required",
            "mode": "manual",
            "source": "manual_pipeline",
            "recommended_symbol": str(recommendation.get("symbol") or overview.get("recommended_symbol") or ""),
            "recommended_strategy_id": recommendation.get("strategy_id") or "",
            "research_template": self._resolve_research_template(latest_result=latest_result, recommendation=recommendation),
            "strategy_template": str(recommendation.get("strategy_template") or ""),
            "next_action": str(overview.get("next_action") or recommendation.get("next_action") or "continue_research"),
            "message": "手动信号流水线已完成，这一轮结果已经同步进统一复盘和任务页。",
            "failure_reason": "",
            "dispatch": {"status": "manual_pipeline", "meta": {"source": "manual_pipeline"}},
            "train_task": train_task,
            "infer_task": infer_task,
            "signal_task": signal_task,
            "review_task": review_task,
            "review_overview": overview,
        }
        self._automation.record_cycle(summary, count_towards_daily=False)

    def _record_manual_cycle_started(self) -> None:
        """把手动流水线已进入后台的状态提前写进统一工作流摘要。"""

        latest_result = self._read_latest_result()
        recommendation = self._read_recommendation()
        self._automation.record_cycle(
            {
                "status": "running",
                "mode": "manual",
                "source": "manual_pipeline",
                "recommended_symbol": str(recommendation.get("symbol") or ""),
                "recommended_strategy_id": recommendation.get("strategy_id") or "",
                "research_template": self._resolve_research_template(latest_result=latest_result, recommendation=recommendation),
                "strategy_template": str(recommendation.get("strategy_template") or ""),
                "next_action": "wait_pipeline_completion",
                "message": "手动信号流水线已进入后台，当前可以去研究页、评估页和任务页跟进阶段变化。",
                "failure_reason": "",
                "dispatch": {"status": "running", "meta": {"source": "manual_pipeline"}},
            },
            count_towards_daily=False,
        )

    def _record_manual_failure(self, *, message: str) -> None:
        """把手动流水线失败写入统一告警和工作流摘要。"""

        self._automation.record_alert(
            level="error",
            code="manual_pipeline_failed",
            message="手动 Qlib 信号流水线失败",
            source="manual_pipeline",
            detail=message,
        )
        self._automation.record_cycle(
            {
                "status": "attention_required",
                "mode": "manual",
                "source": "manual_pipeline",
                "recommended_symbol": "",
                "recommended_strategy_id": "",
                "research_template": "",
                "strategy_template": "",
                "next_action": "manual_review",
                "message": message,
                "failure_reason": "manual_pipeline_failed",
                "dispatch": {"status": "failed", "meta": {"source": "manual_pipeline"}},
            },
            count_towards_daily=False,
        )

    def _read_latest_result(self) -> dict[str, object]:
        """读取最近一次研究结果。"""

        payload = self._research_service.get_latest_result()
        return payload if isinstance(payload, dict) else {}

    def _read_recommendation(self) -> dict[str, object]:
        """读取最近一次研究推荐。"""

        payload = self._research_service.get_research_recommendation()
        return payload if isinstance(payload, dict) else {}

    @staticmethod
    def _resolve_research_template(
        *,
        latest_result: dict[str, object],
        recommendation: dict[str, object],
    ) -> str:
        """统一提取当前这轮流水线应归属的研究模板。"""

        latest_training = dict(latest_result.get("latest_training") or {})
        training_context = dict(latest_training.get("training_context") or {})
        training_parameters = dict(training_context.get("parameters") or {})
        latest_inference = dict(latest_result.get("latest_inference") or {})
        inference_context = dict(latest_inference.get("inference_context") or {})
        input_summary = dict(inference_context.get("input_summary") or {})
        configured_research = dict(workbench_config_service.get_config().get("research") or {})
        return str(
            latest_inference.get("research_template")
            or input_summary.get("research_template")
            or latest_training.get("research_template")
            or training_parameters.get("research_template")
            or recommendation.get("research_template")
            or configured_research.get("research_template")
            or ""
        )

    @staticmethod
    def _resolve_review_limit() -> int:
        """读取统一复盘条数。"""

        try:
            operations = dict(workbench_config_service.get_config().get("operations") or {})
            return max(int(operations.get("review_limit") or 10), 1)
        except (TypeError, ValueError):
            return 10

    def _mark_success(self, action: str, started_at: float, message: str) -> None:
        """记录成功状态。"""

        self._finish(action=action, started_at=started_at, status="succeeded", message=message)

    def _mark_failed(self, action: str, started_at: float, message: str) -> None:
        """记录失败状态。"""

        self._finish(action=action, started_at=started_at, status="failed", message=message)

    def _finish(self, *, action: str, started_at: float, status: str, message: str) -> None:
        """写入完成状态。"""

        config = self._config_loader()
        with self._lock:
            state = self._read_state(self._status_path(config))
            history = dict(state.get("history") or {})
            duration_seconds = max(1, round(time.perf_counter() - started_at))
            action_history = list(history.get(action) or [])
            action_history.append(duration_seconds)
            history[action] = action_history[-5:]
            next_action = "run_inference" if action == "training" and status == "succeeded" else "review_results"
            finished_at = _utc_now()
            completed = {
                "status": status,
                "action": action,
                "current_stage": "completed" if status == "succeeded" else "failed",
                "progress_pct": 100 if status == "succeeded" else int(state.get("progress_pct") or 0),
                "started_at": str(state.get("started_at") or _utc_now()),
                "finished_at": finished_at,
                "message": message,
                "last_completed_action": action if status == "succeeded" else str(state.get("last_completed_action") or ""),
                "last_finished_at": finished_at if status == "succeeded" else str(state.get("last_finished_at") or ""),
                "result_paths": ["/research", "/evaluation", "/signals"],
                "history": history,
                "last_duration_seconds": duration_seconds,
                "next_action": next_action,
            }
            self._write_state(self._status_path(config), completed)

        # WebSocket 推送完成状态
        push_bridge.push_research_runtime_complete(
            action=action,
            status=status,
            message=message,
            finished_at=finished_at,
        )

        # 失败时触发告警
        if status == "failed":
            push_bridge.push_automation_alert(
                level="error",
                code=f"research_{action}_failed",
                message=f"研究任务 {action} 执行失败: {message}",
                source="research_runtime",
                detail=f"持续时间: {duration_seconds}秒",
            )

    def _update_state(self, action: str, stage: str, progress_pct: int, message: str) -> None:
        """更新运行中的阶段。"""

        config = self._config_loader()
        with self._lock:
            state = self._read_state(self._status_path(config))
            state.update(
                {
                    "status": "running",
                    "action": action,
                    "current_stage": stage,
                    "progress_pct": progress_pct,
                    "message": message,
                }
            )
            self._write_state(self._status_path(config), state)

        # WebSocket 推送状态变更
        push_bridge.push_research_runtime_update(
            status="running",
            action=action,
            current_stage=stage,
            progress_pct=progress_pct,
            message=message,
        )

    def _status_path(self, config: object) -> Path:
        """返回状态文件路径。"""

        return getattr(config, "paths").runtime_root / "research_runtime_status.json"

    def _read_state(self, path: Path) -> dict[str, object]:
        """读取状态文件。"""

        if not path.exists():
            return {
                "status": "idle",
                "action": "",
                "current_stage": "idle",
                "progress_pct": 0,
                "started_at": "",
                "finished_at": "",
                "message": "当前没有研究任务在运行。",
                "last_completed_action": "",
                "last_finished_at": "",
                "result_paths": ["/research", "/evaluation", "/signals"],
                "history": {},
            }
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {
                "status": "attention_required",
                "action": "",
                "current_stage": "invalid_state",
                "progress_pct": 0,
                "started_at": "",
                "finished_at": "",
                "message": "研究运行状态文件暂时不可读，请重新发起一次研究动作。",
                "last_completed_action": "",
                "last_finished_at": "",
                "result_paths": ["/research", "/evaluation", "/signals"],
                "history": {},
            }

    def _write_state(self, path: Path, state: dict[str, object]) -> None:
        """写入状态文件。"""

        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(f"{path.suffix}.tmp")
        temp_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        temp_path.replace(path)

    def _build_estimates(self, state: dict[str, object]) -> dict[str, int]:
        """根据最近耗时估算运行时长。"""

        history = dict(state.get("history") or {})
        estimates: dict[str, int] = {}
        for action in ("training", "inference", "pipeline"):
            values = [float(item) for item in list(history.get(action) or []) if float(item) > 0]
            estimates[action] = math.ceil(sum(values) / len(values)) if values else self._default_estimate(action)
        return estimates

    @staticmethod
    def _default_estimate(action: str) -> int:
        """返回默认预计时长。"""

        defaults = {
            "training": 25,
            "inference": 12,
            "pipeline": 40,
        }
        return defaults.get(action, 20)

    @staticmethod
    def _queued_message(action: str) -> str:
        """返回排队提示文案。"""

        mapping = {
            "training": "研究训练已进入后台，正在准备市场样本。",
            "inference": "研究推理已进入后台，正在读取最新训练结果。",
            "pipeline": "Qlib 信号流水线已进入后台，会依次完成训练、推理和信号回写。",
        }
        return mapping.get(action, "研究任务已进入后台。")

    def _spawn_thread(self, runner: Callable[[], None]) -> None:
        """启动后台线程。"""

        thread = threading.Thread(target=runner, daemon=True)
        self._active_thread = thread
        thread.start()

    def _is_thread_alive(self) -> bool:
        """判断当前线程是否仍在运行。"""

        return bool(self._active_thread and self._active_thread.is_alive())


research_runtime_service = ResearchRuntimeService()
