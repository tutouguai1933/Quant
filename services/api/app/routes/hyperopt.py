"""Freqtrade Hyperopt 参数优化路由。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Header

from services.api.app.core.settings import Settings
from services.api.app.adapters.freqtrade.client import freqtrade_client
from services.api.app.services.auth_service import auth_service


router = APIRouter(prefix="/api/v1/hyperopt", tags=["hyperopt"])


def _success(data: dict, meta: dict | None = None) -> dict:
    return {"data": data, "error": None, "meta": meta or {}}


def _error(code: str, message: str) -> dict:
    return {"data": None, "error": {"code": code, "message": message}, "meta": {}}


# 内存态存储优化任务（生产环境应使用数据库）
_hyperopt_jobs: dict[str, dict[str, Any]] = {}
_hyperopt_status: dict[str, Any] = {"status": "idle"}
_job_counter = 0


@router.get("/status")
def get_hyperopt_status() -> dict:
    """获取当前优化状态。"""
    settings = Settings.from_env()
    runtime_mode = settings.runtime_mode

    if runtime_mode == "live":
        # Live 模式：调用 Freqtrade REST API
        try:
            response = freqtrade_client._request("GET", "/api/v1/hyperopt")
            if response.get("status") == "running":
                return _success({
                    "status": "running",
                    "current_epoch": response.get("current_epoch", 0),
                    "total_epochs": response.get("epochs", 100),
                    "best_result": response.get("best_result"),
                    "started_at": response.get("started_at"),
                })
            return _success({"status": "idle"})
        except Exception as exc:
            return _success({"status": "idle", "error": str(exc)})

    # Demo/Dry-run 模式：返回内存状态
    return _success(_hyperopt_status)


@router.get("/jobs")
def list_hyperopt_jobs(limit: int = 20) -> dict:
    """列出历史优化任务。"""
    settings = Settings.from_env()
    runtime_mode = settings.runtime_mode

    if runtime_mode == "live":
        try:
            response = freqtrade_client._request("GET", "/api/v1/hyperopt/list")
            jobs = response.get("jobs", [])
            return _success({"jobs": jobs[:limit]})
        except Exception:
            pass

    # Demo/Dry-run 模式：返回内存任务
    jobs = sorted(
        _hyperopt_jobs.values(),
        key=lambda x: x.get("created_at", ""),
        reverse=True,
    )[:limit]
    return _success({"jobs": jobs})


@router.post("/start")
def start_hyperopt(
    strategy: str = "EnhancedStrategy",
    epochs: int = 100,
    spaces: list[str] | None = None,
    timeframe: str = "1h",
    timerange: str | None = None,
    token: str = "",
    authorization: str = Header(""),
) -> dict:
    """启动参数优化。需要控制平面认证。"""
    auth_service.require_control_plane_access(auth_service.resolve_access_token(token, authorization))

    global _job_counter, _hyperopt_status

    if spaces is None:
        spaces = ["buy", "sell", "roi", "stoploss"]

    settings = Settings.from_env()
    runtime_mode = settings.runtime_mode

    if runtime_mode == "live":
        try:
            response = freqtrade_client._request("POST", "/api/v1/hyperopt/start", json={
                "strategy": strategy,
                "epochs": epochs,
                "spaces": spaces,
                "timeframe": timeframe,
                "timerange": timerange,
            })
            return _success({
                "status": "running",
                "job_id": response.get("job_id"),
                "started_at": datetime.now(timezone.utc).isoformat(),
            })
        except Exception as exc:
            return _error("hyperopt_start_failed", str(exc))

    # Demo/Dry-run 模式：模拟启动
    _job_counter += 1
    job_id = f"hyperopt-{_job_counter}"

    _hyperopt_status = {
        "status": "running",
        "job_id": job_id,
        "strategy": strategy,
        "epochs": epochs,
        "spaces": spaces,
        "timeframe": timeframe,
        "current_epoch": 0,
        "total_epochs": epochs,
        "best_result": None,
        "started_at": datetime.now(timezone.utc).isoformat(),
    }

    _hyperopt_jobs[job_id] = {
        "id": job_id,
        "strategy": strategy,
        "timeframe": timeframe,
        "epochs": epochs,
        "status": "running",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    return _success(_hyperopt_status)


@router.post("/stop")
def stop_hyperopt(token: str = "", authorization: str = Header("")) -> dict:
    """停止参数优化。需要控制平面认证。"""
    auth_service.require_control_plane_access(auth_service.resolve_access_token(token, authorization))

    global _hyperopt_status

    settings = Settings.from_env()
    runtime_mode = settings.runtime_mode

    if runtime_mode == "live":
        try:
            response = freqtrade_client._request("POST", "/api/v1/hyperopt/stop")
            return _success({"status": "stopped"})
        except Exception as exc:
            return _error("hyperopt_stop_failed", str(exc))

    # Demo/Dry-run 模式：模拟停止
    if _hyperopt_status.get("status") == "running":
        job_id = _hyperopt_status.get("job_id")
        if job_id and job_id in _hyperopt_jobs:
            _hyperopt_jobs[job_id]["status"] = "stopped"
        _hyperopt_status = {"status": "idle"}

    return _success({"status": "stopped"})


@router.get("/result/{job_id}")
def get_hyperopt_result(job_id: str) -> dict:
    """获取优化结果详情。"""
    settings = Settings.from_env()
    runtime_mode = settings.runtime_mode

    if runtime_mode == "live":
        try:
            response = freqtrade_client._request("GET", f"/api/v1/hyperopt/result/{job_id}")
            return _success(response)
        except Exception as exc:
            return _error("hyperopt_result_not_found", str(exc))

    # Demo/Dry-run 模式：返回内存任务
    job = _hyperopt_jobs.get(job_id)
    if not job:
        return _error("job_not_found", f"Job {job_id} not found")

    return _success(job)
