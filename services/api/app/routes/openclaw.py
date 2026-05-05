"""Openclaw 快照和安全动作 API 路由。"""

from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel

from services.api.app.services.openclaw_snapshot_service import OpenclawSnapshotService
from services.api.app.services.openclaw_action_service import OpenclawActionService
from services.api.app.services.openclaw_patrol_service import OpenclawPatrolService, openclaw_patrol_service
from services.api.app.services.automation_service import automation_service
from services.api.app.services.strategy_dispatch_service import strategy_dispatch_service
from services.api.app.services.automation_workflow_service import automation_workflow_service
from services.api.app.services.openclaw_audit_service import openclaw_audit_service
from services.api.app.services.openclaw_restart_history_service import openclaw_restart_history_service
from services.api.app.services.auth_service import auth_service


router = APIRouter(prefix="/api/v1/openclaw", tags=["openclaw"])


def get_snapshot_service() -> OpenclawSnapshotService:
    """获取快照服务实例。"""
    return OpenclawSnapshotService(
        automation=automation_service,
        strategies=strategy_dispatch_service,
    )


def get_action_service() -> OpenclawActionService:
    """获取动作服务实例。"""
    snapshot_service = get_snapshot_service()
    return OpenclawActionService(
        automation=automation_service,
        snapshot_service=snapshot_service,
        workflow_service=automation_workflow_service,
    )


class ExecuteActionRequest(BaseModel):
    """执行动作请求。"""
    action: str
    payload: dict | None = None


@router.get("/snapshot")
def get_snapshot(
    service: OpenclawSnapshotService = Depends(get_snapshot_service),
):
    """获取统一运维快照。"""
    try:
        snapshot = service.get_snapshot()
        return snapshot
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/actions")
def execute_action(
    request: ExecuteActionRequest,
    service: OpenclawActionService = Depends(get_action_service),
    token: str = "",
    authorization: str = Header(""),
):
    """执行安全动作。需要控制平面认证。

    支持的动作包括：
    - automation_run_cycle: 运行一轮自动化
    - automation_dry_run_only: 切换到 dry-run only 模式
    - automation_clear_non_error_alerts: 清理非错误级告警
    - system_restart_web: 重启 Web 服务
    - system_restart_freqtrade: 重启 Freqtrade 服务
    """
    auth_service.require_control_plane_access(auth_service.resolve_access_token(token, authorization))

    try:
        result = service.execute_action(
            action=request.action,
            payload=request.payload,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/audit")
def get_audit_records(limit: int = 10):
    """获取最近的审计记录。

    Args:
        limit: 返回的最大记录数，默认 10 条

    Returns:
        最近的审计记录列表
    """
    try:
        records = openclaw_audit_service.get_recent_records(limit=limit)
        return {
            "items": records,
            "total": len(records),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/restart-history")
def get_restart_history():
    """获取重启历史摘要。

    Returns:
        各服务的重启历史记录
    """
    try:
        history = openclaw_restart_history_service.get_all_history()
        # 按服务分类返回
        return {
            "api": history.get("api", {}),
            "web": history.get("web", {}),
            "freqtrade": history.get("freqtrade", {}),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/patrol")
def execute_patrol(patrol_type: str = "full", token: str = "", authorization: str = Header("")):
    """执行一轮巡检。需要控制平面认证。

    Args:
        patrol_type: 巡检类型，可选 "health_check", "state_sync", "cycle_check", "full"
        默认为 "full" 执行完整巡检

    Returns:
        巡检结果，包含执行的动作列表
    """
    auth_service.require_control_plane_access(auth_service.resolve_access_token(token, authorization))

    try:
        result = openclaw_patrol_service.patrol(patrol_type=patrol_type)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/patrol-history")
def get_patrol_history(limit: int = 10):
    """获取最近的巡检记录。

    Args:
        limit: 返回的最大记录数，默认 10 条

    Returns:
        最近的巡检记录列表
    """
    try:
        records = openclaw_patrol_service.get_recent_patrols(limit=limit)
        return {
            "items": records,
            "total": len(records),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/patrol-counters")
def get_patrol_counters():
    """获取动作计数器状态。

    Returns:
        所有动作的节流计数器状态
    """
    try:
        counters = openclaw_patrol_service.get_action_counters()
        return {
            "counters": counters,
            "config": {
                "throttle_window_seconds": openclaw_patrol_service.THROTTLE_WINDOW_SECONDS,
                "max_action_count_per_window": openclaw_patrol_service.MAX_ACTION_COUNT_PER_WINDOW,
                "max_consecutive_failures": openclaw_patrol_service.MAX_CONSECUTIVE_FAILURES,
                "alert_threshold": openclaw_patrol_service.ALERT_THRESHOLD,
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/patrol-reset")
def reset_patrol_counter(action: str):
    """重置指定动作的计数器。

    Args:
        action: 要重置的动作名称

    Returns:
        重置结果
    """
    try:
        openclaw_patrol_service.reset_action_counter(action=action)
        return {
            "success": True,
            "action": action,
            "message": f"已重置动作 {action} 的计数器",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
