"""Strategy query routes for the Control Plane API skeleton."""

from __future__ import annotations

from services.api.app.adapters.freqtrade.client import freqtrade_client
from services.api.app.services.automation_workflow_service import automation_workflow_service
from services.api.app.services.auth_service import auth_service
from services.api.app.services.strategy_catalog import strategy_catalog_service
from services.api.app.services.strategy_dispatch_service import strategy_dispatch_service
from services.api.app.services.strategy_engine_service import strategy_engine_service
from services.api.app.services.strategy_workspace_service import strategy_workspace_service
from services.api.app.services.sync_service import sync_service


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


@router.get("/public/status")
def get_public_status() -> dict:
    """公开的执行器状态端点，无需认证。用于首页显示系统状态。"""
    try:
        runtime = sync_service.get_runtime_snapshot()
        return _success(
            {
                "executor": runtime.get("executor", "freqtrade"),
                "connection_status": runtime.get("connection_status", "error"),
                "mode": runtime.get("mode", "unknown"),
                "status": runtime.get("status", "unavailable"),
                "strategy_count": runtime.get("strategy_count", 0),
                "order_count": runtime.get("order_count", 0),
                "position_count": runtime.get("position_count", 0),
            },
            {"source": "freqtrade"},
        )
    except Exception as exc:
        return _success(
            {
                "executor": "freqtrade",
                "connection_status": "error",
                "mode": "unknown",
                "status": "error",
                "strategy_count": 0,
                "order_count": 0,
                "position_count": 0,
                "detail": str(exc),
            },
            {"source": "freqtrade", "error": True},
        )


@router.get("/public/cycle-history")
def get_public_cycle_history(limit: int = 50) -> dict:
    """公开的自动化周期历史端点，无需认证。用于查看系统运行记录。"""
    from services.api.app.services.automation_cycle_history_service import automation_cycle_history_service

    history = automation_cycle_history_service.get_history(limit=limit)
    summary = automation_cycle_history_service.get_summary()
    return _success(
        {
            "items": history,
            "summary": summary,
        },
        {"source": "automation-cycle-history"},
    )


def _unsupported_scope(strategy_id: int) -> dict:
    return {
        "data": None,
        "error": {
            "code": "unsupported_control_scope",
            "message": "当前阶段的启动、暂停、停止只控制整台 Freqtrade 执行器，请使用 strategy_id=1",
        },
        "meta": {"strategy_id": strategy_id, "scope": "executor", "source": "control-plane-api"},
    }


def _runtime_meta(*, limit: int | None = None, strategy_id: int | None = None, detail: str = "") -> dict[str, object]:
    """统一整理执行器来源和降级状态。"""

    try:
        runtime_snapshot = dict(sync_service.get_runtime_snapshot())
    except Exception as exc:
        runtime_snapshot = {
            "backend": "memory",
            "connection_status": "error",
            "detail": str(exc),
        }
    source = "freqtrade-rest-sync" if runtime_snapshot.get("backend") == "rest" else "freqtrade-sync"
    meta: dict[str, object] = {
        "source": source,
        "truth_source": "freqtrade",
    }
    if limit is not None:
        meta["limit"] = limit
    if strategy_id is not None:
        meta["strategy_id"] = strategy_id
    unavailable_detail = detail or str(runtime_snapshot.get("detail", "") or "")
    if unavailable_detail:
        meta["status"] = "unavailable"
        meta["detail"] = unavailable_detail
    return meta


@router.get("")
def list_strategies(limit: int = 50, token: str = "", authorization: str = Header("")) -> dict:
    try:
        auth_service.require_control_plane_access(auth_service.resolve_access_token(token, authorization))
    except PermissionError:
        return _unauthorized()
    try:
        items = sync_service.list_strategies(limit=limit)
        return _success({"items": items}, _runtime_meta(limit=limit))
    except Exception as exc:
        return _success({"items": []}, _runtime_meta(limit=limit, detail=str(exc)))


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
    workspace["automation"] = automation_workflow_service.get_status()
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
    try:
        item = sync_service.get_strategy(strategy_id)
        return _success({"item": item}, _runtime_meta(strategy_id=strategy_id))
    except Exception as exc:
        return _success({"item": None}, _runtime_meta(strategy_id=strategy_id, detail=str(exc)))


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
    result = strategy_dispatch_service.dispatch_latest_signal(strategy_id, source="system")
    if result.get("status") != "succeeded":
        return {
            "data": None,
            "error": {"code": str(result.get("error_code", "dispatch_failed")), "message": str(result.get("message", "dispatch failed"))},
            "meta": {
                "strategy_id": strategy_id,
                "source": "control-plane-api",
                "risk_task_id": result.get("risk_task", {}).get("id") if isinstance(result.get("risk_task"), dict) else None,
            },
        }
    return _success(
        {
            "item": result.get("item"),
            "risk_decision": result.get("risk_decision"),
            "risk_task": result.get("risk_task"),
            "sync_task": result.get("sync_task"),
        },
        {
            "strategy_id": strategy_id,
            "action": "dispatch-latest-signal",
            "source": "control-plane-api",
            "truth_source": "freqtrade",
        },
    )


@router.post("/{strategy_id}/entry-score")
def calculate_entry_score(
    strategy_id: int,
    symbol: str = "",
    signal_side: str = "long",
    signal_score: str = "",
    token: str = "",
    authorization: str = Header(""),
) -> dict:
    """计算入场评分。

    返回入场决策，包括：
    - allowed: 是否允许入场
    - score: 综合评分
    - reason: 原因说明
    - confidence: 置信度
    - trend_confirmed: 趋势是否确认
    - research_aligned: 研究信号是否一致
    - suggested_position_ratio: 建议仓位比例
    """
    try:
        auth_service.require_control_plane_access(auth_service.resolve_access_token(token, authorization))
    except PermissionError:
        return _unauthorized()

    if not symbol or not symbol.strip():
        return {
            "data": None,
            "error": {"code": "invalid_request", "message": "symbol 参数必须提供"},
            "meta": {"strategy_id": strategy_id, "source": "control-plane-api"},
        }

    from decimal import Decimal

    parsed_score = None
    if signal_score and signal_score.strip():
        try:
            parsed_score = Decimal(signal_score.strip())
        except Exception:
            parsed_score = None

    entry_decision = strategy_engine_service.calculate_entry_score(
        symbol=symbol.strip(),
        signal_side=signal_side.strip().lower() if signal_side else "long",
        signal_score=parsed_score,
    )

    return _success(
        {"entry_decision": entry_decision.to_dict()},
        {
            "strategy_id": strategy_id,
            "symbol": symbol.strip(),
            "source": "strategy-engine-service",
        },
    )
