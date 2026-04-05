"""Task query routes for the Control Plane API skeleton."""

from __future__ import annotations

from services.api.app.services.automation_service import automation_service
from services.api.app.services.automation_workflow_service import automation_workflow_service
from services.api.app.services.auth_service import auth_service
from services.api.app.tasks.scheduler import task_scheduler


try:
    from fastapi import APIRouter, Header
except ImportError:
    class APIRouter:  # pragma: no cover - lightweight local fallback
        def __init__(self, *args, **kwargs) -> None:
            self.args = args
            self.kwargs = kwargs

        def get(self, *args, **kwargs):
            def decorator(func):
                return func

            return decorator

        def post(self, *args, **kwargs):
            def decorator(func):
                return func

            return decorator

    def Header(default=""):  # pragma: no cover - lightweight local fallback
        return default


router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])


def _success(data: dict, meta: dict | None = None) -> dict:
    return {"data": data, "error": None, "meta": meta or {}}


def _unauthorized() -> dict:
    return {
        "data": None,
        "error": {"code": "unauthorized", "message": "当前页面需要先登录"},
        "meta": {"source": "auth-service"},
    }


@router.get("")
def list_tasks(limit: int = 100, token: str = "", authorization: str = Header("")) -> dict:
    try:
        auth_service.require_control_plane_access(auth_service.resolve_access_token(token, authorization))
    except PermissionError:
        return _unauthorized()
    items = task_scheduler.list_tasks(limit=limit)
    return _success({"items": items}, {"limit": limit, "source": "task-scheduler"})


@router.post("/train")
def run_train_task(
    source: str = "user",
    token: str = "",
    authorization: str = Header(""),
) -> dict:
    try:
        auth_service.require_control_plane_access(auth_service.resolve_access_token(token, authorization))
    except PermissionError:
        return _unauthorized()
    item = task_scheduler.run_named_task(
        task_type="research_train",
        source=source,
        target_type="system",
    )
    return _success({"item": item}, {"source": "task-scheduler", "action": "research-train"})


@router.post("/sync")
def run_sync_task(source: str = "user", token: str = "", authorization: str = Header("")) -> dict:
    try:
        auth_service.require_control_plane_access(auth_service.resolve_access_token(token, authorization))
    except PermissionError:
        return _unauthorized()
    item = task_scheduler.run_named_task(task_type="sync", source=source, target_type="system")
    return _success({"item": item}, {"source": "task-scheduler", "action": "sync"})


@router.post("/reconcile")
def run_reconcile_task(
    source: str = "user",
    simulate_failure: bool = False,
    token: str = "",
    authorization: str = Header(""),
) -> dict:
    try:
        auth_service.require_control_plane_access(auth_service.resolve_access_token(token, authorization))
    except PermissionError:
        return _unauthorized()
    item = task_scheduler.run_named_task(
        task_type="reconcile",
        source=source,
        target_type="system",
        payload={"simulate_failure": simulate_failure},
    )
    return _success({"item": item}, {"source": "task-scheduler", "action": "reconcile"})


@router.post("/archive")
def run_archive_task(
    source: str = "user",
    simulate_failure: bool = False,
    token: str = "",
    authorization: str = Header(""),
) -> dict:
    try:
        auth_service.require_control_plane_access(auth_service.resolve_access_token(token, authorization))
    except PermissionError:
        return _unauthorized()
    item = task_scheduler.run_named_task(
        task_type="archive",
        source=source,
        target_type="system",
        payload={"simulate_failure": simulate_failure},
    )
    return _success({"item": item}, {"source": "task-scheduler", "action": "archive"})


@router.post("/health-check")
def run_health_check_task(source: str = "scheduler", token: str = "", authorization: str = Header("")) -> dict:
    try:
        auth_service.require_control_plane_access(auth_service.resolve_access_token(token, authorization))
    except PermissionError:
        return _unauthorized()
    item = task_scheduler.run_named_task(task_type="health_check", source=source, target_type="system")
    return _success({"item": item}, {"source": "task-scheduler", "action": "health-check"})


@router.get("/validation-review")
def get_validation_review(limit: int = 10, token: str = "", authorization: str = Header("")) -> dict:
    try:
        auth_service.require_control_plane_access(auth_service.resolve_access_token(token, authorization))
    except PermissionError:
        return _unauthorized()
    from services.api.app.services.validation_workflow_service import validation_workflow_service

    item = validation_workflow_service.build_report(limit=limit)
    return _success({"item": item}, {"source": "validation-workflow", "limit": limit})


@router.post("/review")
def run_review_task(source: str = "user", limit: int = 10, token: str = "", authorization: str = Header("")) -> dict:
    try:
        auth_service.require_control_plane_access(auth_service.resolve_access_token(token, authorization))
    except PermissionError:
        return _unauthorized()
    item = task_scheduler.run_named_task(
        task_type="review",
        source=source,
        target_type="system",
        payload={"limit": limit},
    )
    return _success({"item": item}, {"source": "task-scheduler", "action": "review"})


@router.get("/automation")
def get_automation_status(token: str = "", authorization: str = Header("")) -> dict:
    try:
        auth_service.require_control_plane_access(auth_service.resolve_access_token(token, authorization))
    except PermissionError:
        return _unauthorized()
    item = automation_workflow_service.get_status()
    return _success({"item": item}, {"source": "automation-workflow"})


@router.post("/automation/configure")
def set_automation_mode(mode: str, actor: str = "user", token: str = "", authorization: str = Header("")) -> dict:
    try:
        auth_service.require_control_plane_access(auth_service.resolve_access_token(token, authorization))
    except PermissionError:
        return _unauthorized()
    item = automation_service.configure_mode(mode, actor=actor)
    return _success({"item": item}, {"source": "automation-service", "action": "configure"})


@router.post("/automation/pause")
def halt_automation(reason: str = "manual_pause", actor: str = "user", token: str = "", authorization: str = Header("")) -> dict:
    try:
        auth_service.require_control_plane_access(auth_service.resolve_access_token(token, authorization))
    except PermissionError:
        return _unauthorized()
    item = automation_service.pause(reason=reason, actor=actor)
    return _success({"item": item}, {"source": "automation-service", "action": "pause"})


@router.post("/automation/resume")
def resume_automation(mode: str = "", actor: str = "user", token: str = "", authorization: str = Header("")) -> dict:
    try:
        auth_service.require_control_plane_access(auth_service.resolve_access_token(token, authorization))
    except PermissionError:
        return _unauthorized()
    if str(mode).strip():
        automation_service.configure_mode(mode, actor=actor)
    item = automation_service.resume(actor=actor)
    return _success({"item": item}, {"source": "automation-service", "action": "resume"})


@router.post("/automation/dry-run-only")
def enable_dry_run_only(actor: str = "user", token: str = "", authorization: str = Header("")) -> dict:
    try:
        auth_service.require_control_plane_access(auth_service.resolve_access_token(token, authorization))
    except PermissionError:
        return _unauthorized()
    item = automation_service.enable_dry_run_only(actor=actor)
    return _success({"item": item}, {"source": "automation-service", "action": "dry-run-only"})


@router.post("/automation/kill-switch")
def trigger_kill_switch(actor: str = "user", token: str = "", authorization: str = Header("")) -> dict:
    try:
        auth_service.require_control_plane_access(auth_service.resolve_access_token(token, authorization))
    except PermissionError:
        return _unauthorized()
    item = automation_service.kill_switch(actor=actor)
    return _success({"item": item}, {"source": "automation-service", "action": "kill-switch"})


@router.post("/automation/run")
def run_automation_cycle(actor: str = "user", token: str = "", authorization: str = Header("")) -> dict:
    try:
        auth_service.require_control_plane_access(auth_service.resolve_access_token(token, authorization))
    except PermissionError:
        return _unauthorized()
    item = task_scheduler.run_named_task(
        task_type="automation_cycle",
        source=actor,
        target_type="system",
        payload={"source": actor},
    )
    return _success({"item": item}, {"source": "task-scheduler", "action": "automation-cycle"})


@router.post("/{task_id}/retry")
def retry_task(task_id: int, clear_failure: bool = True, token: str = "", authorization: str = Header("")) -> dict:
    try:
        auth_service.require_control_plane_access(auth_service.resolve_access_token(token, authorization))
    except PermissionError:
        return _unauthorized()
    item = task_scheduler.retry_task(task_id, clear_failure=clear_failure)
    return _success({"item": item}, {"task_id": task_id, "source": "task-scheduler", "action": "retry"})


@router.get("/{task_id}")
def get_task(task_id: int, token: str = "", authorization: str = Header("")) -> dict:
    try:
        auth_service.require_control_plane_access(auth_service.resolve_access_token(token, authorization))
    except PermissionError:
        return _unauthorized()
    item = task_scheduler.get_task(task_id)
    return _success({"item": item}, {"task_id": task_id, "source": "task-scheduler"})
