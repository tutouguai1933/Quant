"""订单查询路由。"""

from __future__ import annotations

from services.api.app.core.settings import Settings
from services.api.app.services.account_sync_service import account_sync_service
from services.api.app.services.sync_service import sync_service


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


router = APIRouter(prefix="/api/v1/orders", tags=["orders"])


def _success(data: dict, meta: dict | None = None) -> dict:
    return {"data": data, "error": None, "meta": meta or {}}


@router.get("")
def list_orders(limit: int = 100) -> dict:
    runtime_mode = Settings.from_env().runtime_mode
    if runtime_mode in {"demo", "dry-run"}:
        items = sync_service.list_orders(limit=limit)
        get_runtime_snapshot = getattr(sync_service, "get_runtime_snapshot", None)
        runtime_snapshot = get_runtime_snapshot() if callable(get_runtime_snapshot) else {"backend": "memory"}
        source = "freqtrade-rest-sync" if runtime_snapshot.get("backend") == "rest" else "freqtrade-sync"
        return _success(
            {"items": items},
            {
                "limit": limit,
                "source": source,
                "truth_source": "freqtrade",
            },
        )

    items = account_sync_service.list_orders(limit=limit)
    return _success(
        {"items": items},
        {
            "limit": limit,
            "source": "binance-account-sync",
            "truth_source": "binance",
        },
    )
