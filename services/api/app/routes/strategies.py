"""Strategy query routes for the Control Plane API skeleton."""

from __future__ import annotations

import threading
import time
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

# strategies/workspace 30 秒缓存（get_workspace 聚合约 13 秒）
_workspace_cache: dict[str, object] | None = None
_workspace_cache_time: float = 0.0

# 执行器公开状态缓存：首页高频请求，过期后用旧值兜底并后台刷新，
# 避免在 freqtrade 慢时把请求线程拖住几十秒
_PUBLIC_STATUS_CACHE_TTL = 5.0
_public_status_cache: dict | None = None
_public_status_cache_time: float = 0.0
_public_status_lock = threading.Lock()
_public_status_refreshing = False

# 周期历史缓存：首页/任务页按 60s 轮询，5 秒内重复请求直接复用
_CYCLE_HISTORY_CACHE_TTL = 5.0
_cycle_history_cache: dict[str, tuple[float, dict]] = {}


def _compute_public_status_payload() -> dict:
    """计算执行器公开状态载荷（可能较慢，只在缓存过期时调用）。"""
    runtime = sync_service.get_runtime_snapshot()
    return {
        "executor": runtime.get("executor", "freqtrade"),
        "connection_status": runtime.get("connection_status", "error"),
        "mode": runtime.get("mode", "unknown"),
        "status": runtime.get("status", "unavailable"),
        "strategy_count": runtime.get("strategy_count", 0),
        "order_count": runtime.get("order_count", 0),
        "position_count": runtime.get("position_count", 0),
    }


def _refresh_public_status_in_background() -> None:
    """后台刷新执行器状态缓存。"""
    global _public_status_refreshing
    try:
        payload = _compute_public_status_payload()
        global _public_status_cache, _public_status_cache_time
        with _public_status_lock:
            _public_status_cache = payload
            _public_status_cache_time = time.monotonic()
    finally:
        with _public_status_lock:
            _public_status_refreshing = False


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
    """公开的执行器状态端点，无需认证。用于首页显示系统状态。

    缓存 5 秒；过期时先返回旧值并后台刷新，只有首次访问才同步等待。
    """
    global _public_status_cache, _public_status_cache_time, _public_status_refreshing
    now = time.monotonic()
    with _public_status_lock:
        cached = _public_status_cache
        fresh = cached is not None and now - _public_status_cache_time < _PUBLIC_STATUS_CACHE_TTL
        if cached is not None and not _public_status_refreshing:
            # 过期：后台刷新，本次直接用旧值响应（不阻塞首页）
            _public_status_refreshing = True
            threading.Thread(target=_refresh_public_status_in_background, name="public-status-refresh", daemon=True).start()
        if cached is not None:
            return _success(cached, {"source": "freqtrade", "cache": "fresh" if fresh else "stale"})

    # 首次访问没有缓存：同步计算（慢，但只发生一次；后续请求走缓存）
    try:
        payload = _compute_public_status_payload()
        with _public_status_lock:
            _public_status_cache = payload
            _public_status_cache_time = time.monotonic()
        return _success(payload, {"source": "freqtrade"})
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

    # 5 秒内相同 limit 的重复请求直接返回缓存，避免多卡片轮询重复计算
    cache_key = str(int(limit))
    now = time.monotonic()
    cached = _cycle_history_cache.get(cache_key)
    if cached is not None and now - cached[0] < _CYCLE_HISTORY_CACHE_TTL:
        return _success(cached[1], {"source": "automation-cycle-history", "cache": "fresh"})

    history = automation_cycle_history_service.get_history(limit=limit)
    summary = automation_cycle_history_service.get_summary()
    payload = {
        "items": history,
        "summary": summary,
    }
    _cycle_history_cache[cache_key] = (time.monotonic(), payload)
    return _success(
        payload,
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
    global _workspace_cache, _workspace_cache_time
    try:
        auth_service.require_control_plane_access(auth_service.resolve_access_token(token, authorization))
    except PermissionError:
        return _unauthorized()
    # 30 秒缓存：get_workspace 聚合 freqtrade+信号等约 13 秒，缓存避免高频访问拖慢 api
    now = time.time()
    cached_backend = str(((_workspace_cache or {}).get("executor_runtime") or {}).get("backend", ""))
    if (
        _workspace_cache is not None
        and now - _workspace_cache_time < 30.0
        and cached_backend not in ("", "memory")
    ):
        return _success(
            _workspace_cache,
            {"source": "strategy-workspace-cache", "truth_source": "strategy-catalog+signal-store+freqtrade"},
        )
    workspace = strategy_workspace_service.get_workspace()
    workspace["automation"] = automation_workflow_service.get_status()
    # 降级数据（memory/demo）不缓存：避免缓存假数据，下次请求重新拉真实数据
    backend = str((workspace.get("executor_runtime") or {}).get("backend", ""))
    if backend not in ("", "memory"):
        _workspace_cache = workspace
        _workspace_cache_time = now
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
