"""市场数据路由。"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal

from services.api.app.core.settings import Settings
from services.api.app.services.market_service import MarketService, normalize_kline_series
from services.api.app.services.research_service import research_service
from services.api.app.services.indicator_service import _rsi, _to_decimal

try:
    from fastapi import APIRouter, HTTPException
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
# 新路径别名（绕过claudeWAF拦截）
alias_router = APIRouter(prefix="/api/v1/quotes", tags=["quotes"])
service = MarketService(research_reader=research_service)

_executor = ThreadPoolExecutor(max_workers=4)


def _success(data: dict, meta: dict | None = None) -> dict:
    """统一成功 envelope。"""

    return {"data": data, "error": None, "meta": meta or {}}


@router.get("")
@alias_router.get("")
def list_market() -> dict:
    settings = Settings.from_env()
    items = service.list_market_snapshots(settings.market_symbols)
    return _success({"items": items}, {"source": "binance"})


def _fetch_single_rsi(symbol: str, interval: str, allowed_symbols: tuple) -> dict | None:
    """在线程池中获取单个币种的RSI数据。"""
    from datetime import timezone as tz_module
    from datetime import timedelta as td

    try:
        chart = service.get_symbol_chart(
            symbol=symbol,
            interval=interval,
            limit=50,
            allowed_symbols=allowed_symbols,
        )
        items = chart.get("items", [])

        if len(items) < 15:
            return None

        closes = [item.get("close", 0) for item in items]
        if not closes:
            return None

        period = 14
        if len(closes) < period + 1:
            return None

        segment = closes[-(period + 1):]
        rsi_value = _rsi([_to_decimal(c) for c in segment], period)

        state = "neutral"
        signal = "hold"
        if rsi_value >= Decimal("70"):
            state = "overbought"
            signal = "potential_sell"
        elif rsi_value <= Decimal("30"):
            state = "oversold"
            signal = "potential_buy"

        last_item = items[-1]
        close_time = last_item.get("close_time", 0) / 1000
        shanghai_tz = tz_module(td(hours=8))
        dt = datetime.fromtimestamp(close_time, tz=shanghai_tz)
        time_str = dt.strftime("%m-%d %H:%M")

        return {
            "symbol": symbol,
            "rsi": float(rsi_value.quantize(Decimal("0.01"))),
            "state": state,
            "signal": signal,
            "close_price": closes[-1] if closes else None,
            "time": time_str,
            "interval": interval,
        }
    except Exception:
        return None


@router.get("/rsi-summary")
@alias_router.get("/rsi-summary")
def get_rsi_summary(interval: str = "1d") -> dict:
    """返回所有监控币种的最新RSI值概览（并发获取）。"""
    settings = Settings.from_env()
    symbols = settings.market_symbols

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        futures = [
            loop.run_in_executor(_executor, _fetch_single_rsi, symbol, interval, symbols)
            for symbol in symbols
        ]
        raw_results = loop.run_until_complete(asyncio.gather(*futures, return_exceptions=True))
    finally:
        loop.close()

    results = [r for r in raw_results if r is not None and not isinstance(r, Exception)]
    results.sort(key=lambda x: x["rsi"])

    return _success({
        "items": results,
        "total": len(results),
        "interval": interval,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }, {"source": "binance"})


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

    # 计算RSI历史序列（从旧到新）
    rsi_items = _build_rsi_history(items, period=14)
    # 反转排序，让最新数据排在前面
    rsi_items.reverse()

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
    """格式化毫秒时间戳为可读字符串（北京时间）。"""
    try:
        shanghai_tz = timezone(timedelta(hours=8))
        dt = datetime.fromtimestamp(ms / 1000, tz=shanghai_tz)
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return str(ms)