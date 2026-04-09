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


def _build_freqtrade_meta(limit: int, detail: str = "") -> dict[str, object]:
    """整理 Freqtrade 相关元信息，并在不可用时给出降级提示。"""

    source = "freqtrade-sync"
    get_runtime_snapshot = getattr(sync_service, "get_runtime_snapshot", None)
    if callable(get_runtime_snapshot):
        try:
            runtime_snapshot = get_runtime_snapshot()
        except Exception:
            runtime_snapshot = {"backend": "memory"}
        source = "freqtrade-rest-sync" if runtime_snapshot.get("backend") == "rest" else "freqtrade-sync"
    meta: dict[str, object] = {
        "limit": limit,
        "source": source,
        "truth_source": "freqtrade",
    }
    if detail:
        meta["status"] = "unavailable"
        meta["detail"] = detail
    return meta


@router.get("")
def list_orders(limit: int = 100) -> dict:
    runtime_mode = Settings.from_env().runtime_mode
    if runtime_mode in {"demo", "dry-run"}:
        try:
            items = sync_service.list_orders(limit=limit)
            return _success({"items": items}, _build_freqtrade_meta(limit))
        except Exception as exc:
            return _success({"items": []}, _build_freqtrade_meta(limit, str(exc)))

    items = account_sync_service.list_orders(limit=limit)
    return _success(
        {"items": items},
        {
            "limit": limit,
            "source": "binance-account-sync",
            "truth_source": "binance",
        },
    )
