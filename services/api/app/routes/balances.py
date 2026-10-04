"""余额查询路由。"""

from __future__ import annotations

from services.api.app.core.settings import Settings
from services.api.app.routes._helpers import _success, _unauthorized
from services.api.app.services.auth_service import auth_service
from services.api.app.services.account_sync_service import account_sync_service
from services.api.app.services.sync_service import sync_service


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


if "Header" not in globals():
    def Header(default=""):
        """兼容轻量本地运行的请求头默认值。"""
        return default


router = APIRouter(prefix="/api/v1/balances", tags=["balances"])


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
def list_balances(limit: int = 100) -> dict:
    runtime_mode = Settings.from_env().runtime_mode
    if runtime_mode == "demo":
        return _success({"items": []}, {"limit": limit, "source": "api-skeleton"})

    if runtime_mode in {"dry-run"}:
        try:
            items = sync_service.list_balances(limit=limit)
            return _success({"items": items}, _build_freqtrade_meta(limit))
        except Exception as exc:
            return _success({"items": []}, _build_freqtrade_meta(limit, str(exc)))

    try:
        items = account_sync_service.list_balances(limit=limit)
        return _success(
            {"items": items},
            {
                "limit": limit,
                "source": "binance-account-sync",
                "truth_source": "binance",
            },
        )
    except Exception as exc:
        return _success(
            {"items": []},
            {
                "limit": limit,
                "source": "binance-account-sync",
                "truth_source": "binance",
                "status": "unavailable",
                "detail": str(exc),
            },
        )


@router.get("/summary")
def get_balance_summary(authorization: str = Header(default="")) -> dict:
    """提供现货和合约权益合计，模拟环境不读取实盘账户。"""
    try:
        auth_service.require_control_plane_access(auth_service.resolve_access_token(authorization=authorization))
    except PermissionError:
        return _unauthorized()
    if Settings.from_env().runtime_mode != "live":
        return _success({"status": "unavailable", "total_equity": None, "spot_equity": None,
                         "futures_equity": None, "assets": [], "issues": ["当前不是实盘账户"],
                         "scope": "现货 + U本位合约"})
    from services.api.app.services.balance_equity_service import balance_equity_service
    return _success(balance_equity_service.get_summary(), {"source": "binance-account-equity", "truth_source": "binance"})
