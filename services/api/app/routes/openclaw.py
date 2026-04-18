"""Openclaw 快照和安全动作 API 路由。"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from services.api.app.services.openclaw_snapshot_service import OpenclawSnapshotService
from services.api.app.services.openclaw_action_service import OpenclawActionService
from services.api.app.services.automation_service import automation_service
from services.api.app.services.strategy_dispatch_service import strategy_dispatch_service
from services.api.app.services.automation_workflow_service import automation_workflow_service


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
):
    """执行安全动作。"""
    try:
        result = service.execute_action(
            action=request.action,
            payload=request.payload,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
