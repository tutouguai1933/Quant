"""特征工作台路由。"""

from __future__ import annotations

from services.api.app.services.feature_workspace_service import feature_workspace_service

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


router = APIRouter(prefix="/api/v1/features", tags=["features"])


def _success(data: dict[str, object], meta: dict[str, object] | None = None) -> dict[str, object]:
    """统一成功包裹。"""

    return {"data": data, "error": None, "meta": meta or {}}


@router.get("/workspace")
def get_feature_workspace() -> dict[str, object]:
    """返回特征工作台聚合结果。"""

    workspace = feature_workspace_service.get_workspace()
    return _success({"item": workspace}, {"source": "feature-workspace"})
