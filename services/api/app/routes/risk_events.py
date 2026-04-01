"""Risk-event query routes for the Control Plane API skeleton."""

from __future__ import annotations

from services.api.app.services.auth_service import auth_service
from services.api.app.services.risk_service import risk_service


try:
    from fastapi import APIRouter, Header
except ImportError:
    class APIRouter:  # pragma: no cover - lightweight local fallback
        def __init__(self, *args, **kwargs) -> None:
            self.args = args
            self.kwargs = kwargs

        def get(self, *args, **kwargs):
            def decorator(func):
                return func

            return decorator

    def Header(default=""):  # pragma: no cover - lightweight local fallback
        return default


router = APIRouter(prefix="/api/v1/risk-events", tags=["risk-events"])


def _success(data: dict, meta: dict | None = None) -> dict:
    return {"data": data, "error": None, "meta": meta or {}}


def _unauthorized() -> dict:
    return {
        "data": None,
        "error": {"code": "unauthorized", "message": "当前页面需要先登录"},
        "meta": {"source": "auth-service"},
    }


@router.get("")
def list_risk_events(limit: int = 100, token: str = "", authorization: str = Header("")) -> dict:
    try:
        auth_service.require_control_plane_access(auth_service.resolve_access_token(token, authorization))
    except PermissionError:
        return _unauthorized()
    items = risk_service.list_events(limit=limit)
    return _success({"items": items}, {"limit": limit, "source": "risk-service"})


@router.get("/{risk_event_id}")
def get_risk_event(risk_event_id: int, token: str = "", authorization: str = Header("")) -> dict:
    try:
        auth_service.require_control_plane_access(auth_service.resolve_access_token(token, authorization))
    except PermissionError:
        return _unauthorized()
    item = risk_service.get_event(risk_event_id)
    return _success({"item": item}, {"risk_event_id": risk_event_id, "source": "risk-service"})
