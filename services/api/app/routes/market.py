"""市场数据路由。"""

from __future__ import annotations

from datetime import datetime, timezone

from decimal import Decimal

from services.api.app.core.settings import Settings
from services.api.app.services.market_service import MarketService, normalize_kline_series
from services.api.app.services.research_service import research_service
from services.api.app.services.indicator_service import _rsi, _to_decimal

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
# 新路径别名（绕过阿里云WAF拦截）
alias_router = APIRouter(prefix="/api/v1/quotes", tags=["quotes"])
service = MarketService(research_reader=research_service)


def _success(data: dict, meta: dict | None = None) -> dict:
    """统一成功 envelope。"""

    return {"data": data, "error": None, "meta": meta or {}}


@router.get("")
@alias_router.get("")
def list_market() -> dict:
    settings = Settings.from_env()
    items = service.list_market_snapshots(settings.market_symbols)
    return _success({"items": items}, {"source": "binance"})


@router.get("/{symbol}/chart")
@alias_router.get("/{symbol}/chart")
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


@router.get("/{symbol}/rsi-history")
@alias_router.get("/{symbol}/rsi-history")
def get_rsi_history(symbol: str, interval: str = "4h", limit: int = 200) -> dict:
    """返回指定币种的RSI历史序列。

    Args:
        symbol: 交易对符号（如 BTCUSDT）
        interval: K线周期（默认4h）
        limit: K线数量限制（默认200）

    Returns:
        RSI历史序列，每项包含时间、RSI值、状态和信号
    """
    normalized_symbol = symbol.strip().upper()
    settings = Settings.from_env()

    # 获取K线数据
    rows = service._client.get_klines(symbol=normalized_symbol, interval=interval, limit=limit)
    items = normalize_kline_series(rows)

    if len(items) < 15:
        return _success(
            {"items": [], "symbol": normalized_symbol, "interval": interval, "total": 0},
            {"source": "binance", "reason": "insufficient_data"},
        )

    # 计算RSI历史序列
    rsi_items = _build_rsi_history(items, period=14)

    return _success(
        {"items": rsi_items, "symbol": normalized_symbol, "interval": interval, "total": len(rsi_items)},
        {"source": "binance"},
    )


def _build_rsi_history(items: list[dict], period: int = 14) -> list[dict]:
    """从K线收盘价序列构建RSI历史。

    Args:
        items: K线数据列表
        period: RSI周期（默认14）

    Returns:
        RSI历史记录列表
    """
    if len(items) < period + 1:
        return []

    rsi_series: list[dict] = []
    closes: list[Decimal] = []

    for item in items:
        try:
            close = _to_decimal(item.get("close", 0))
            closes.append(close)
        except Exception:
            continue

    # 从第period+1根K线开始计算RSI
    for i in range(period, len(closes)):
        segment = closes[: i + 1]
        rsi_value = _rsi(segment, period)

        # 确定状态和信号
        state = "neutral"
        signal = "hold"
        if rsi_value >= Decimal("70"):
            state = "overbought"
            signal = "potential_sell"
        elif rsi_value <= Decimal("30"):
            state = "oversold"
            signal = "potential_buy"

        close_time = items[i].get("close_time", 0)
        time_str = _format_timestamp(close_time)

        rsi_series.append({
            "timestamp": close_time,
            "time": time_str,
            "rsi_value": str(rsi_value.quantize(Decimal("0.01"))),
            "state": state,
            "signal": signal,
            "close_price": str(closes[i]),
        })

    return rsi_series


def _format_timestamp(ms: int) -> str:
    """格式化毫秒时间戳为可读字符串。"""
    try:
        dt = datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return str(ms)
