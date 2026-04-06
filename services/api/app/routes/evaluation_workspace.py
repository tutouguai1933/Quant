"""评估与实验中心路由。"""

from __future__ import annotations

from services.api.app.services.evaluation_workspace_service import evaluation_workspace_service

try:
    from fastapi import APIRouter
except ImportError:
    class APIRouter:  # pragma: no cover
        def __init__(self, *args, **kwargs) -> None:
            self.args = args
            self.kwargs = kwargs

        def get(self, *args, **kwargs):
            def decorator(func):
                return func

            return decorator


router = APIRouter(prefix="/api/v1/evaluation", tags=["evaluation"])


def _success(data: dict[str, object], meta: dict[str, object] | None = None) -> dict[str, object]:
    """统一成功包裹。"""

    return {"data": data, "error": None, "meta": meta or {}}


@router.get("/workspace")
def get_evaluation_workspace() -> dict[str, object]:
    """返回评估与实验中心聚合结果。"""

    workspace = evaluation_workspace_service.get_workspace()
    return _success({"item": workspace}, {"source": "evaluation-workspace"})
