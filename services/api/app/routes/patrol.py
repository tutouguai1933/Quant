"""定时巡检控制 API 路由。

提供巡检调度启动、停止、状态查询等控制接口。
"""

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel

from services.api.app.services.scheduled_patrol_service import scheduled_patrol_service
from services.api.app.services.auth_service import auth_service

router = APIRouter(prefix="/api/v1/patrol", tags=["patrol"])


class StartPatrolRequest(BaseModel):
    """启动巡检请求。"""
    interval_minutes: int = 60


class PatrolResponse(BaseModel):
    """巡检操作响应。"""
    success: bool
    message: str
    status: dict | None = None
    interval_minutes: int | None = None
    result: dict | None = None
    error: str | None = None


@router.post("/start", response_model=PatrolResponse)
def start_patrol(
    request: StartPatrolRequest = StartPatrolRequest(),
    token: str = "",
    authorization: str = Header(""),
):
    """启动定时巡检。需要控制平面认证。

    Args:
        request: 启动请求，包含巡检间隔分钟数

    Returns:
        启动结果，包含当前调度状态
    """
    auth_service.require_control_plane_access(auth_service.resolve_access_token(token, authorization))

    try:
        result = scheduled_patrol_service.start_schedule(
            interval_minutes=request.interval_minutes,
        )
        return PatrolResponse(
            success=result.get("success", False),
            message=result.get("message", ""),
            status=result.get("status"),
            interval_minutes=result.get("interval_minutes"),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stop", response_model=PatrolResponse)
def stop_patrol(token: str = "", authorization: str = Header("")):
    """停止定时巡检。需要控制平面认证。

    Returns:
        停止结果，包含当前调度状态
    """
    auth_service.require_control_plane_access(auth_service.resolve_access_token(token, authorization))

    try:
        result = scheduled_patrol_service.stop_schedule()
        return PatrolResponse(
            success=result.get("success", False),
            message=result.get("message", ""),
            status=result.get("status"),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/schedule")
def get_patrol_schedule():
    """查看巡检计划状态。

    Returns:
        调度状态信息，包括：
        - running: 是否正在运行
        - interval_minutes: 巡检间隔
        - last_run_at: 上次执行时间
        - last_run_status: 上次执行状态
        - total_runs: 总执行次数
        - failed_runs: 失败次数
        - success_rate: 成功率
    """
    try:
        status = scheduled_patrol_service.get_schedule_status()
        return status
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/run-now", response_model=PatrolResponse)
def run_patrol_now(patrol_type: str = "full", token: str = "", authorization: str = Header("")):
    """立即执行一次巡检（不依赖调度状态）。需要控制平面认证。

    Args:
        patrol_type: 巡检类型，可选 "health_check", "state_sync", "cycle_check", "vpn_check", "auto_dispatch", "full"

    Returns:
        巡检执行结果
    """
    auth_service.require_control_plane_access(auth_service.resolve_access_token(token, authorization))

    try:
        result = scheduled_patrol_service.run_patrol_now(patrol_type=patrol_type)
        return PatrolResponse(
            success=result.get("success", False),
            message=result.get("message", ""),
            result=result.get("result"),
            error=result.get("error"),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))