"""市场数据路由。"""

from __future__ import annotations

from services.api.app.core.settings import Settings
from services.api.app.services.market_service import MarketService

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


router = APIRouter(prefix="/api/v1/market", tags=["market"])
service = MarketService()


def _success(data: dict, meta: dict | None = None) -> dict:
    """统一成功 envelope。"""

    return {"data": data, "error": None, "meta": meta or {}}


@router.get("")
def list_market() -> dict:
    settings = Settings.from_env()
    items = service.list_market_snapshots(settings.market_symbols)
    return _success({"items": items}, {"source": "binance"})


@router.get("/{symbol}/chart")
def get_market_chart(symbol: str, interval: str = "4h", limit: int = 200) -> dict:
    normalized_symbol = symbol.strip().upper()
    settings = Settings.from_env()
    chart = service.get_symbol_chart(
        symbol=normalized_symbol,
        interval=interval,
        limit=limit,
        allowed_symbols=settings.market_symbols,
    )
    chart["freqtrade_readiness"] = _build_freqtrade_readiness(settings)
    return _success(chart, {"source": "binance"})


def _build_freqtrade_readiness(settings: Settings) -> dict[str, object]:
    """返回当前是否具备接真实 Freqtrade dry-run 的最小条件。"""

    if settings.runtime_mode != "dry-run":
        return {
            "executor": "freqtrade",
            "backend": "memory",
            "runtime_mode": settings.runtime_mode,
            "ready_for_real_freqtrade": False,
            "reason": "runtime_mode_must_be_dry_run",
            "next_step": "先把 QUANT_RUNTIME_MODE 设为 dry-run，再接真实 Freqtrade。",
        }
    if not settings.has_freqtrade_rest_config():
        return {
            "executor": "freqtrade",
            "backend": "memory",
            "runtime_mode": settings.runtime_mode,
            "ready_for_real_freqtrade": False,
            "reason": "missing_freqtrade_rest_config",
            "next_step": "补齐 QUANT_FREQTRADE_API_URL、用户名和密码后，才能做真实 Freqtrade dry-run 验收。",
        }
    return {
        "executor": "freqtrade",
        "backend": "rest",
        "runtime_mode": settings.runtime_mode,
        "ready_for_real_freqtrade": True,
        "reason": "ready",
        "next_step": "当前已经具备接真实 Freqtrade dry-run 的最小条件，可以按运维文档继续联调。",
    }
