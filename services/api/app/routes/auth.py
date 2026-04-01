"""鉴权路由。

这个文件暴露最小登录、会话查询和登出接口，供控制平面使用。
"""

from __future__ import annotations

from services.api.app.services.auth_service import auth_service


try:
    from fastapi import APIRouter, Body
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

    def Body(default=None):  # pragma: no cover - lightweight local fallback
        return default


router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _success(data: dict, meta: dict | None = None) -> dict:
    return {"data": data, "error": None, "meta": meta or {}}


def _error(code: str, message: str, meta: dict | None = None) -> dict:
    return {"data": None, "error": {"code": code, "message": message}, "meta": meta or {}}


@router.post("/login")
def login(payload: dict[str, object] | None = Body(None), username: str = "admin", password: str = "1933") -> dict:
    request = payload if isinstance(payload, dict) else {}
    resolved_username = str(request.get("username", username))
    resolved_password = str(request.get("password", password))
    try:
        item = auth_service.login(username=resolved_username, password=resolved_password)
    except ValueError:
        return _error("invalid_credentials", "管理员账号或密码错误", {"source": "auth-service"})
    return _success({"item": item}, {"source": "auth-service", "action": "login"})


@router.get("/session")
def get_session(token: str = "") -> dict:
    item = auth_service.get_session(token)
    if item is None:
        return _error("session_not_found", "当前会话不存在或已失效", {"source": "auth-service"})
    return _success({"item": item}, {"source": "auth-service", "action": "session"})


@router.get("/model")
def get_login_model() -> dict:
    item = auth_service.get_login_model()
    return _success({"item": item}, {"source": "auth-service", "action": "login-model"})


@router.post("/logout")
def logout(token: str = "") -> dict:
    item = auth_service.logout(token)
    if item is None:
        return _error("session_not_found", "当前会话不存在或已失效", {"source": "auth-service"})
    return _success({"item": item}, {"source": "auth-service", "action": "logout"})
