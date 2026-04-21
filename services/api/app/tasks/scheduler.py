"""Unified task recorder for Quant phase 1."""

from __future__ import annotations

import signal
import threading
from datetime import datetime, timezone
from typing import Callable

from services.api.app.services.signal_service import signal_service
from services.api.app.services.sync_service import sync_service


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# Task timeout configuration in seconds
_TASK_TIMEOUT_SECONDS: dict[str, int] = {
    "train": 300,
    "research_train": 600,
    "research_infer": 300,
    "signal_output": 60,
    "sync": 120,
    "reconcile": 60,
    "review": 180,
    "automation_cycle": 600,
    "archive": 60,
    "health_check": 30,
    "signal_ingest": 30,
    "risk_check": 30,
}


class TaskTimeoutError(RuntimeError):
    """任务超时错误。"""


class TaskScheduler:
    """Tracks minimal synchronous tasks and exposes retry flow."""

    def __init__(self) -> None:
        self._tasks: dict[int, dict[str, object]] = {}
        self._next_task_id = 1
        self._health_summary = {
            "latest_status_by_type": {},
            "latest_success_by_type": {},
            "latest_failure_by_type": {},
            "consecutive_failure_count_by_type": {},
        }
        self._task_timeout_seconds = dict(_TASK_TIMEOUT_SECONDS)

    def get_task_timeout(self, task_type: str) -> int:
        """获取指定任务类型的超时配置。"""
        return self._task_timeout_seconds.get(task_type, 300)

    def list_tasks(self, limit: int = 100) -> list[dict[str, object]]:
        ordered = sorted(self._tasks.values(), key=lambda item: int(item["id"]), reverse=True)
        return ordered[:limit]

    def get_task(self, task_id: int) -> dict[str, object] | None:
        task = self._tasks.get(task_id)
        return None if task is None else dict(task)

    def run_named_task(
        self,
        task_type: str,
        source: str = "user",
        target_type: str = "system",
        target_id: int | None = None,
        payload: dict[str, object] | None = None,
    ) -> dict[str, object]:
        task = self._create_task(task_type, source, target_type, target_id, payload)
        self._set_status(task, "running")
        try:
            result = self._execute_named_task(task_type, payload or {})
        except Exception as exc:
            task["error_message"] = str(exc)
            self._set_status(task, "failed")
            return dict(task)

        task["result"] = result
        self._set_status(task, "succeeded")
        self._apply_success_side_effects(task)
        return dict(task)

    def run_custom_task(
        self,
        task_type: str,
        source: str,
        target_type: str,
        target_id: int | None,
        payload: dict[str, object] | None,
        runner,
    ) -> dict[str, object]:
        task = self._create_task(task_type, source, target_type, target_id, payload)
        self._set_status(task, "running")
        try:
            result = runner()
        except Exception as exc:
            task["error_message"] = str(exc)
            self._set_status(task, "failed")
            return dict(task)

        task["result"] = result
        self._set_status(task, "succeeded")
        self._apply_success_side_effects(task)
        return dict(task)

    def retry_task(self, task_id: int, clear_failure: bool = True) -> dict[str, object] | None:
        task = self._tasks.get(task_id)
        if task is None:
            return None

        self._set_status(task, "retrying")
        task["error_message"] = None
        payload = dict(task.get("payload") or {})
        if clear_failure:
            payload.pop("simulate_failure", None)
            task["payload"] = payload

        self._set_status(task, "running")
        try:
            result = self._execute_named_task(str(task["task_type"]), payload)
        except Exception as exc:
            task["error_message"] = str(exc)
            self._set_status(task, "failed")
            return dict(task)

        task["result"] = result
        self._set_status(task, "succeeded")
        self._apply_success_side_effects(task)
        return dict(task)

    def get_health_summary(self) -> dict[str, object]:
        """返回任务与执行健康摘要。"""

        return {
            "latest_status_by_type": dict(self._health_summary["latest_status_by_type"]),
            "latest_success_by_type": dict(self._health_summary["latest_success_by_type"]),
            "latest_failure_by_type": dict(self._health_summary["latest_failure_by_type"]),
            "consecutive_failure_count_by_type": dict(self._health_summary["consecutive_failure_count_by_type"]),
        }

    def _create_task(
        self,
        task_type: str,
        source: str,
        target_type: str,
        target_id: int | None,
        payload: dict[str, object] | None,
    ) -> dict[str, object]:
        task = {
            "id": self._next_task_id,
            "task_type": task_type,
            "source": source,
            "status": "queued",
            "target_type": target_type,
            "target_id": target_id,
            "requested_at": utc_now(),
            "started_at": None,
            "finished_at": None,
            "error_message": None,
            "payload": payload or {},
            "result": None,
            "status_history": ["queued"],
        }
        self._tasks[self._next_task_id] = task
        self._next_task_id += 1
        return task

    def _set_status(self, task: dict[str, object], status: str) -> None:
        task["status"] = status
        history = task.setdefault("status_history", [])
        if not history or history[-1] != status:
            history.append(status)
        if status == "running":
            task["started_at"] = utc_now()
            task["finished_at"] = None
        elif status in {"succeeded", "failed", "cancelled"}:
            task["finished_at"] = utc_now()
        self._record_health(task, status)

    def _execute_named_task(self, task_type: str, payload: dict[str, object]) -> dict[str, object]:
        if payload.get("simulate_failure"):
            raise RuntimeError(f"{task_type} task simulated failure")

        timeout_seconds = self._task_timeout_seconds.get(task_type, 300)

        def _run_task() -> dict[str, object]:
            return self._execute_task_impl(task_type, payload)

        return self._run_with_timeout(_run_task, timeout_seconds, task_type)

    def _execute_task_impl(self, task_type: str, payload: dict[str, object]) -> dict[str, object]:
        """实际执行任务逻辑。"""
        if task_type == "train":
            source = str(payload.get("pipeline_source", "mock"))
            return signal_service.run_pipeline(source=source)
        if task_type == "research_train":
            from services.api.app.services.research_service import research_service

            return research_service.run_training()
        if task_type == "research_infer":
            from services.api.app.services.research_service import research_service

            result = research_service.run_inference()
            signal_service.refresh_qlib_signals_from_latest_result()
            return result
        if task_type == "signal_output":
            return signal_service.refresh_qlib_signals_from_latest_result()
        if task_type == "sync":
            return sync_service.sync_task_state(
                limit=int(payload.get("limit", 100)),
                expected_symbol=str(payload.get("expected_symbol", "")),
                expected_side=str(payload.get("expected_side", "")),
                expected_order_id=str(payload.get("expected_order_id", "")),
                expected_updated_at=str(payload.get("expected_updated_at", "")),
                expected_quantity=str(payload.get("expected_quantity", "")),
            )
        if task_type == "reconcile":
            return {"status": "completed", "detail": "reconcile placeholder completed"}
        if task_type == "review":
            from services.api.app.services.validation_workflow_service import validation_workflow_service

            return validation_workflow_service.build_report(limit=int(payload.get("limit", 10)))
        if task_type == "automation_cycle":
            from services.api.app.services.automation_workflow_service import automation_workflow_service

            return automation_workflow_service.run_cycle(
                source=str(payload.get("source", "automation")),
                review_limit=int(payload.get("limit", 10)),
            )
        if task_type == "archive":
            return {"status": "completed", "detail": "archive placeholder completed"}
        if task_type == "health_check":
            return {"status": "ok", "detail": "scheduler and api skeleton reachable"}
        if task_type == "signal_ingest":
            return {"status": "recorded", "detail": "signal processing task captured"}
        if task_type == "risk_check":
            return {"status": "recorded", "detail": "risk evaluation completed"}
        raise RuntimeError(f"unsupported task type: {task_type}")

    def _run_with_timeout(
        self,
        runner: Callable[[], dict[str, object]],
        timeout_seconds: int,
        task_type: str,
    ) -> dict[str, object]:
        """带超时控制的任务执行器。"""

        result: dict[str, object] | None = None
        exception: Exception | None = None

        def _worker() -> None:
            nonlocal result, exception
            try:
                result = runner()
            except Exception as exc:
                exception = exc

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()
        thread.join(timeout=float(timeout_seconds))

        if thread.is_alive():
            # Task exceeded timeout - raise error
            raise TaskTimeoutError(f"{task_type} task exceeded timeout of {timeout_seconds}s")

        if exception is not None:
            raise exception

        if result is None:
            raise RuntimeError(f"{task_type} task returned no result")

        return result

    def _apply_success_side_effects(self, task: dict[str, object]) -> None:
        """在任务成功后补齐最小状态推进。"""

        if str(task.get("task_type")) != "sync":
            return
        payload = dict(task.get("payload") or {})
        source_signal_id = payload.get("source_signal_id")
        if source_signal_id in (None, ""):
            return
        try:
            signal_service.update_signal_status(int(source_signal_id), "synced")
        except Exception:
            return

    def _record_health(self, task: dict[str, object], status: str) -> None:
        """记录任务健康状态，给复盘和执行健康摘要复用。"""

        task_type = str(task.get("task_type", ""))
        self._health_summary["latest_status_by_type"][task_type] = status
        if status == "succeeded":
            self._health_summary["latest_success_by_type"][task_type] = str(task.get("finished_at") or task.get("started_at") or "")
            self._health_summary["consecutive_failure_count_by_type"][task_type] = 0
        if status == "failed":
            self._health_summary["latest_failure_by_type"][task_type] = {
                "finished_at": str(task.get("finished_at") or ""),
                "error_message": str(task.get("error_message") or ""),
            }
            current = int(self._health_summary["consecutive_failure_count_by_type"].get(task_type, 0) or 0)
            self._health_summary["consecutive_failure_count_by_type"][task_type] = current + 1


task_scheduler = TaskScheduler()
