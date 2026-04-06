"""工作台配置路由。"""

from __future__ import annotations

from services.api.app.services.auth_service import auth_service
from services.api.app.services.workbench_config_service import workbench_config_service

try:
    from fastapi import APIRouter, Header
except ImportError:
    class APIRouter:  # pragma: no cover
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

    def Header(default: str = "") -> str:  # pragma: no cover
        return default


router = APIRouter(prefix="/api/v1/workbench", tags=["workbench"])


def _success(data: dict[str, object], meta: dict[str, object] | None = None) -> dict[str, object]:
    """统一成功包裹。"""

    return {"data": data, "error": None, "meta": meta or {}}


def _unauthorized() -> dict[str, object]:
    """统一登录失败响应。"""

    return {
        "data": None,
        "error": {"code": "unauthorized", "message": "当前操作需要管理员登录"},
        "meta": {"source": "auth-service"},
    }


@router.get("/config")
def get_workbench_config() -> dict[str, object]:
    """返回统一工作台配置。"""

    item = workbench_config_service.build_workspace_controls()
    return _success({"item": item}, {"source": "workbench-config"})


@router.post("/config")
def update_workbench_config(payload: dict[str, object], token: str = "", authorization: str = Header("")) -> dict[str, object]:
    """更新某一段工作台配置。"""

    try:
        auth_service.require_control_plane_access(auth_service.resolve_access_token(token, authorization))
    except PermissionError:
        return _unauthorized()

    section = str(payload.get("section", "")).strip()
    values = payload.get("values")
    if not section:
        return {
            "data": None,
            "error": {"code": "invalid_request", "message": "缺少 section"},
            "meta": {"source": "workbench-config"},
        }
    if not isinstance(values, dict):
        return {
            "data": None,
            "error": {"code": "invalid_request", "message": "缺少 values"},
            "meta": {"source": "workbench-config"},
        }
    try:
        item = workbench_config_service.update_section(section, values)
    except ValueError as exc:
        return {
            "data": None,
            "error": {"code": "invalid_request", "message": str(exc)},
            "meta": {"source": "workbench-config", "section": section},
        }
    return _success({"item": item}, {"source": "workbench-config", "section": section})
