"""Unified task recorder for Quant phase 1."""

from __future__ import annotations

from datetime import datetime, timezone

from services.api.app.services.signal_service import signal_service
from services.api.app.services.sync_service import sync_service


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class TaskScheduler:
    """Tracks minimal synchronous tasks and exposes retry flow."""

    def __init__(self) -> None:
        self._tasks: dict[int, dict[str, object]] = {}
        self._next_task_id = 1

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
        return dict(task)

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

    def _execute_named_task(self, task_type: str, payload: dict[str, object]) -> dict[str, object]:
        if payload.get("simulate_failure"):
            raise RuntimeError(f"{task_type} task simulated failure")

        if task_type == "train":
            source = str(payload.get("pipeline_source", "mock"))
            return signal_service.run_pipeline(source=source)
        if task_type == "sync":
            return sync_service.sync_task_state()
        if task_type == "reconcile":
            return {"status": "completed", "detail": "reconcile placeholder completed"}
        if task_type == "archive":
            return {"status": "completed", "detail": "archive placeholder completed"}
        if task_type == "health_check":
            return {"status": "ok", "detail": "scheduler and api skeleton reachable"}
        if task_type == "signal_ingest":
            return {"status": "recorded", "detail": "signal processing task captured"}
        if task_type == "risk_check":
            return {"status": "recorded", "detail": "risk evaluation completed"}
        raise RuntimeError(f"unsupported task type: {task_type}")


task_scheduler = TaskScheduler()
