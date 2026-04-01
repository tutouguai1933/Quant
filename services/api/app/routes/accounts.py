"""Account query routes for the Control Plane API skeleton."""

from __future__ import annotations


try:
    from fastapi import APIRouter
except ImportError:
    class APIRouter:  # pragma: no cover - lightweight local fallback
        def __init__(self, *args, **kwargs) -> None:
            self.args = args
            self.kwargs = kwargs

        def get(self, *args, **kwargs):
            def decorator(func):
                return func

            return decorator


router = APIRouter(prefix="/api/v1/accounts", tags=["accounts"])


def _success(data: dict, meta: dict | None = None) -> dict:
    return {"data": data, "error": None, "meta": meta or {}}


@router.get("")
def list_accounts(limit: int = 50) -> dict:
    return _success({"items": []}, {"limit": limit, "source": "api-skeleton"})

