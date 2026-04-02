"""Strategy query routes for the Control Plane API skeleton."""

from __future__ import annotations

from services.api.app.adapters.freqtrade.client import freqtrade_client
from services.api.app.services.auth_service import auth_service
from services.api.app.services.execution_service import execution_service
from services.api.app.services.risk_service import risk_service
from services.api.app.services.signal_service import signal_service
from services.api.app.services.strategy_catalog import strategy_catalog_service
from services.api.app.services.strategy_workspace_service import strategy_workspace_service
from services.api.app.services.sync_service import sync_service
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


router = APIRouter(prefix="/api/v1/strategies", tags=["strategies"])


def _success(data: dict, meta: dict | None = None) -> dict:
    return {"data": data, "error": None, "meta": meta or {}}


def _unauthorized() -> dict:
    return {
        "data": None,
        "error": {"code": "unauthorized", "message": "当前页面需要先登录"},
        "meta": {"source": "auth-service"},
    }


def _unsupported_scope(strategy_id: int) -> dict:
    return {
        "data": None,
        "error": {
            "code": "unsupported_control_scope",
            "message": "当前阶段的启动、暂停、停止只控制整台 Freqtrade 执行器，请使用 strategy_id=1",
        },
        "meta": {"strategy_id": strategy_id, "scope": "executor", "source": "control-plane-api"},
    }


@router.get("")
def list_strategies(limit: int = 50, token: str = "", authorization: str = Header("")) -> dict:
    try:
        auth_service.require_control_plane_access(auth_service.resolve_access_token(token, authorization))
    except PermissionError:
        return _unauthorized()
    items = sync_service.list_strategies(limit=limit)
    runtime_snapshot = sync_service.get_runtime_snapshot()
    source = "freqtrade-rest-sync" if runtime_snapshot.get("backend") == "rest" else "freqtrade-sync"
    return _success(
        {"items": items},
        {
            "limit": limit,
            "source": source,
            "truth_source": "freqtrade",
        },
    )


@router.get("/catalog")
def get_strategy_catalog(token: str = "", authorization: str = Header("")) -> dict:
    try:
        auth_service.require_control_plane_access(auth_service.resolve_access_token(token, authorization))
    except PermissionError:
        return _unauthorized()
    catalog = strategy_catalog_service.get_catalog()
    return _success(
        catalog,
        {
            "source": "strategy-catalog",
            "truth_source": "strategy-catalog",
        },
    )


@router.get("/workspace")
def get_strategy_workspace(token: str = "", authorization: str = Header("")) -> dict:
    try:
        auth_service.require_control_plane_access(auth_service.resolve_access_token(token, authorization))
    except PermissionError:
        return _unauthorized()
    workspace = strategy_workspace_service.get_workspace()
    return _success(
        workspace,
        {
            "source": "strategy-workspace",
            "truth_source": "strategy-catalog+signal-store+freqtrade",
        },
    )


@router.get("/{strategy_id}")
def get_strategy(strategy_id: int, token: str = "", authorization: str = Header("")) -> dict:
    try:
        auth_service.require_control_plane_access(auth_service.resolve_access_token(token, authorization))
    except PermissionError:
        return _unauthorized()
    item = sync_service.get_strategy(strategy_id)
    runtime_snapshot = sync_service.get_runtime_snapshot()
    source = "freqtrade-rest-sync" if runtime_snapshot.get("backend") == "rest" else "freqtrade-sync"
    return _success(
        {"item": item},
        {
            "strategy_id": strategy_id,
            "source": source,
            "truth_source": "freqtrade",
        },
    )


@router.post("/{strategy_id}/start")
def start_strategy(strategy_id: int, token: str = "", authorization: str = Header("")) -> dict:
    try:
        auth_service.require_control_plane_access(auth_service.resolve_access_token(token, authorization))
    except PermissionError:
        return _unauthorized()
    if strategy_id != 1:
        return _unsupported_scope(strategy_id)
    item = freqtrade_client.control_strategy(strategy_id, "start")
    return _success(
        {"item": item},
        {
            "strategy_id": strategy_id,
            "action": "start",
            "scope": "executor",
            "source": "control-plane-api",
        },
    )


@router.post("/{strategy_id}/pause")
def pause_strategy(strategy_id: int, token: str = "", authorization: str = Header("")) -> dict:
    try:
        auth_service.require_control_plane_access(auth_service.resolve_access_token(token, authorization))
    except PermissionError:
        return _unauthorized()
    if strategy_id != 1:
        return _unsupported_scope(strategy_id)
    item = freqtrade_client.control_strategy(strategy_id, "pause")
    return _success(
        {"item": item},
        {
            "strategy_id": strategy_id,
            "action": "pause",
            "scope": "executor",
            "source": "control-plane-api",
        },
    )


@router.post("/{strategy_id}/stop")
def stop_strategy(strategy_id: int, token: str = "", authorization: str = Header("")) -> dict:
    try:
        auth_service.require_control_plane_access(auth_service.resolve_access_token(token, authorization))
    except PermissionError:
        return _unauthorized()
    if strategy_id != 1:
        return _unsupported_scope(strategy_id)
    item = freqtrade_client.control_strategy(strategy_id, "stop")
    return _success(
        {"item": item},
        {
            "strategy_id": strategy_id,
            "action": "stop",
            "scope": "executor",
            "source": "control-plane-api",
        },
    )


@router.post("/{strategy_id}/dispatch-latest-signal")
def dispatch_latest_signal(strategy_id: int, token: str = "", authorization: str = Header("")) -> dict:
    try:
        auth_service.require_control_plane_access(auth_service.resolve_access_token(token, authorization))
    except PermissionError:
        return _unauthorized()
    signals = signal_service.list_signals(limit=100)
    latest = next((signal for signal in signals if signal.get("strategy_id") == strategy_id), None)
    if latest is None:
        return {
            "data": None,
            "error": {"code": "signal_not_found", "message": f"no signal available for strategy {strategy_id}"},
            "meta": {"strategy_id": strategy_id, "source": "control-plane-api"},
        }

    risk_task = task_scheduler.run_custom_task(
        task_type="risk_check",
        source="system",
        target_type="signal",
        target_id=int(latest["signal_id"]),
        payload={"strategy_id": strategy_id},
        runner=lambda: risk_service.evaluate_signal(int(latest["signal_id"])),
    )
    decision = risk_task.get("result")
    if risk_task["status"] != "succeeded" or decision["status"] == "block":
        return {
            "data": None,
            "error": {
                "code": "risk_blocked",
                "message": decision["reason"] if decision is not None else "risk evaluation failed",
            },
            "meta": {
                "strategy_id": strategy_id,
                "source": "control-plane-api",
                "risk_task_id": risk_task["id"],
            },
        }

    try:
        result = execution_service.dispatch_signal(int(latest["signal_id"]))
    except Exception as exc:
        return {
            "data": None,
            "error": {
                "code": "execution_failed",
                "message": str(exc),
            },
            "meta": {
                "strategy_id": strategy_id,
                "source": "control-plane-api",
                "risk_task_id": risk_task["id"],
            },
        }
    signal_service.update_signal_status(int(latest["signal_id"]), "dispatched")
    sync_task = task_scheduler.run_named_task(
        task_type="sync",
        source="system",
        target_type="strategy",
        target_id=strategy_id,
    )
    if sync_task["status"] == "succeeded":
        signal_service.update_signal_status(int(latest["signal_id"]), "synced")
    return _success(
        {"item": result, "risk_decision": decision, "risk_task": risk_task, "sync_task": sync_task},
        {
            "strategy_id": strategy_id,
            "action": "dispatch-latest-signal",
            "source": "control-plane-api",
            "truth_source": "freqtrade",
        },
    )
