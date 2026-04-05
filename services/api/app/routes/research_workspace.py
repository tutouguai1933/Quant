"""策略研究工作台路由。"""

from __future__ import annotations

from services.api.app.services.research_workspace_service import research_workspace_service

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


router = APIRouter(prefix="/api/v1/research", tags=["research"])


def _success(data: dict[str, object], meta: dict[str, object] | None = None) -> dict[str, object]:
    """统一成功包裹。"""

    return {"data": data, "error": None, "meta": meta or {}}


@router.get("/workspace")
def get_research_workspace() -> dict[str, object]:
    """返回策略研究工作台聚合结果。"""

    workspace = research_workspace_service.get_workspace()
    return _success({"item": workspace}, {"source": "research-workspace"})
