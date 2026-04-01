"""余额查询路由。"""

from __future__ import annotations

from services.api.app.core.settings import Settings
from services.api.app.services.account_sync_service import account_sync_service


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


router = APIRouter(prefix="/api/v1/balances", tags=["balances"])


def _success(data: dict, meta: dict | None = None) -> dict:
    return {"data": data, "error": None, "meta": meta or {}}


@router.get("")
def list_balances(limit: int = 100) -> dict:
    runtime_mode = Settings.from_env().runtime_mode
    if runtime_mode == "demo":
        return _success({"items": []}, {"limit": limit, "source": "api-skeleton"})

    items = account_sync_service.list_balances(limit=limit)
    return _success(
        {"items": items},
        {
            "limit": limit,
            "source": "binance-account-sync",
            "truth_source": "binance",
        },
    )
