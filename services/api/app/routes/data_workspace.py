"""数据工作台路由。"""

from __future__ import annotations

from services.api.app.services.data_workspace_service import data_workspace_service

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


router = APIRouter(prefix="/api/v1/data", tags=["data"])


def _success(data: dict[str, object], meta: dict[str, object] | None = None) -> dict[str, object]:
    """统一成功包裹。"""

    return {"data": data, "error": None, "meta": meta or {}}


@router.get("/workspace")
def get_data_workspace(symbol: str = "", interval: str = "4h", limit: int = 200) -> dict[str, object]:
    """返回数据工作台聚合结果。"""

    workspace = data_workspace_service.get_workspace(symbol=symbol, interval=interval, limit=limit)
    return _success({"item": workspace}, {"source": "data-workspace"})
