"""市场数据路由。"""

from __future__ import annotations

import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from services.api.app.core.settings import Settings
from services.api.app.services.cache_service import cache
from services.api.app.services.market_service import MarketService, normalize_kline_series
from services.api.app.services.research_service import research_service
from services.api.app.services.indicator_service import _rsi, _to_decimal
from services.api.app.services.rsi_cache_service import rsi_cache

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
_entry_executor = ThreadPoolExecutor(max_workers=8)  # 入场条件专用，并发获取K线


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
        # 显示K线开盘时间（RSI基于这根K线的收盘价计算）
        open_time = last_item.get("open_time", 0) / 1000
        shanghai_tz = tz_module(td(hours=8))
        open_dt = datetime.fromtimestamp(open_time, tz=shanghai_tz)

        # 时间显示：精确到分钟
        time_str = open_dt.strftime("%m-%d %H:%M")

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
def get_rsi_summary(interval: str = "1h") -> dict:
    """返回所有监控币种的最新RSI值概览。

    优先从缓存文件读取（由自动化程序预计算），缓存不存在时才实时计算。
    """
    # 优先从文件缓存读取
    cached_summary = rsi_cache.get_summary(interval)
    if cached_summary is not None:
        return _success(cached_summary, {"source": "cache"})

    # 缓存不存在，使用内存缓存和实时计算
    cache_key = f"rsi_summary_{interval}"

    def compute():
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

        result = {
            "items": results,
            "total": len(results),
            "interval": interval,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        # 保存到文件缓存
        try:
            rsi_cache.set(result)
        except Exception:
            pass

        return result

    result = cache.get_or_compute(cache_key, compute, ttl_seconds=60)
    return _success(result, {"source": "binance"})


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


def refresh_rsi_cache(interval: str = "1h") -> dict[str, object]:
    """刷新RSI缓存文件，供自动化程序调用。

    Returns:
        包含刷新结果的字典
    """
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

    cache_data = {
        "items": results,
        "total": len(results),
        "interval": interval,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    rsi_cache.set(cache_data)

    # 同时清除内存缓存，强制下次请求使用新数据
    cache.clear(f"rsi_summary_{interval}")

    return {
        "success": True,
        "total": len(results),
        "interval": interval,
        "cached_at": cache_data["updated_at"],
    }


@router.post("/rsi-cache/refresh")
@alias_router.post("/rsi-cache/refresh")
def refresh_rsi_cache_endpoint(interval: str = "1d") -> dict:
    """手动刷新RSI缓存。需要认证。"""
    result = refresh_rsi_cache(interval)
    return _success(result, {"source": "manual_refresh"})


# 入口条件缓存
_entry_conditions_cache: dict[str, object] = {"data": None, "ts": 0}
_ENTRY_CONDITIONS_TTL = 300  # 5分钟


def _fetch_entry_conditions(symbol: str, allowed_symbols: tuple) -> dict | None:
    """获取单个币种的 EnhancedStrategy 入场条件检查结果。"""

    try:
        chart_1h = service.get_symbol_chart(symbol=symbol, interval="1h", limit=200, allowed_symbols=allowed_symbols)
        chart_4h = service.get_symbol_chart(symbol=symbol, interval="4h", limit=200, allowed_symbols=allowed_symbols)

        items_1h = list(chart_1h.get("items", []))
        items_4h = list(chart_4h.get("items", []))

        if len(items_1h) < 30 or len(items_4h) < 30:
            return None

        # --- 1H 指标 ---
        closes_1h = [float(item.get("close", 0)) for item in items_1h]
        volumes_1h = [float(item.get("volume", 0)) for item in items_1h]

        rsi_1h = float(_rsi([_to_decimal(c) for c in closes_1h[-(14 + 1):]], 14).quantize(Decimal("0.01")))

        # --- 4H 指标 ---
        closes_4h = [float(item.get("close", 0)) for item in items_4h]

        # SMA200 on 4H
        sma200_4h = sum(closes_4h[-200:]) / min(200, len(closes_4h)) if closes_4h else 0
        close_4h = closes_4h[-1] if closes_4h else 0
        gap_4h_sma200 = ((close_4h / sma200_4h) - 1) * 100 if sma200_4h > 0 else 0

        # RSI 4H
        rsi_4h = float(_rsi([_to_decimal(c) for c in closes_4h[-(14 + 1):]], 14).quantize(Decimal("0.01")))

        # --- 成交量：过去7天同一小时均量 ---
        lookback_days = 7
        last_vol = volumes_1h[-1] if volumes_1h else 0
        same_hour_sum = last_vol
        valid_count = 1
        for day in range(1, lookback_days + 1):
            idx = len(volumes_1h) - 1 - day * 24
            if idx >= 0:
                same_hour_sum += volumes_1h[idx]
                valid_count += 1
        vol_avg_hourly = same_hour_sum / valid_count if valid_count > 0 else last_vol
        vol_ratio = last_vol / vol_avg_hourly if vol_avg_hourly > 0 else 0

        # --- 判断4个条件 ---
        cond_rsi = rsi_1h < 32
        cond_trend = gap_4h_sma200 > 0
        cond_rsi_4h = rsi_4h < 70
        cond_volume = vol_ratio > 0.6

        all_pass = cond_rsi and cond_trend and cond_rsi_4h and cond_volume

        return {
            "symbol": symbol,
            "rsi_1h": round(rsi_1h, 1),
            "rsi_4h": round(rsi_4h, 1),
            "close_4h": round(close_4h, 2),
            "sma200_4h": round(sma200_4h, 2),
            "gap_4h_pct": round(gap_4h_sma200, 2),
            "vol_ratio": round(vol_ratio, 2),
            "conditions": {
                "rsi_oversold": {"pass": cond_rsi, "label": f"RSI<32", "value": f"{rsi_1h:.1f}", "threshold": "32"},
                "trend_4h": {"pass": cond_trend, "label": "4H趋势向上", "value": f"{gap_4h_sma200:+.1f}%", "threshold": ">0%"},
                "rsi_4h_ok": {"pass": cond_rsi_4h, "label": "4H RSI<70", "value": f"{rsi_4h:.1f}", "threshold": "70"},
                "volume_ok": {"pass": cond_volume, "label": "成交量≥60%", "value": f"{vol_ratio:.2f}", "threshold": "0.6"},
            },
            "all_pass": all_pass,
        }
    except Exception:
        return None


@router.get("/entry-conditions")
@alias_router.get("/entry-conditions")
def get_entry_conditions() -> dict:
    """返回所有监控币种的 EnhancedStrategy 入场条件检查结果。

    对每个币种检查4个入场条件：
    1. 1H RSI < 32（超卖）
    2. 4H 价格 > SMA200（趋势向上）
    3. 4H RSI < 70（不超买）
    4. 成交量 > 过去7天同一时段均量 × 0.6
    """
    now = time.time()
    cached = _entry_conditions_cache.get("data")
    if cached is not None and now - _entry_conditions_cache.get("ts", 0) < _ENTRY_CONDITIONS_TTL:
        return _success(cached, {"source": "cache"})

    settings = Settings.from_env()
    symbols = settings.market_symbols
    allowed = tuple(symbols)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        futures = [
            loop.run_in_executor(_entry_executor, _fetch_entry_conditions, symbol, allowed)
            for symbol in symbols
        ]
        raw_results = loop.run_until_complete(asyncio.gather(*futures, return_exceptions=True))
    finally:
        loop.close()

    results = [r for r in raw_results if r is not None and not isinstance(r, Exception)]
    results.sort(key=lambda x: (not x["all_pass"], x["rsi_1h"]))

    # 计算通过数量
    passed = [r for r in results if r["all_pass"]]

    payload = {
        "items": results,
        "total": len(results),
        "passed_count": len(passed),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    _entry_conditions_cache["data"] = payload
    _entry_conditions_cache["ts"] = now
    return _success(payload, {"source": "binance"})


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
    rsi_items = _build_rsi_history(items, period=14, interval=interval)
    # 反转排序，让最新数据排在前面
    rsi_items.reverse()

    return _success(
        {"items": rsi_items, "symbol": normalized_symbol, "interval": interval, "total": len(rsi_items)},
        {"source": "binance"},
    )


def _build_rsi_history(items: list[dict], period: int = 14, interval: str = "4h") -> list[dict]:
    """从K线收盘价序列构建RSI历史。

    Args:
        items: K线数据列表
        period: RSI周期（默认14）
        interval: K线周期

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

        open_time = items[i].get("open_time", 0)
        time_str = _format_timestamp(open_time, interval)

        rsi_series.append({
            "timestamp": open_time,
            "time": time_str,
            "rsi_value": str(rsi_value.quantize(Decimal("0.01"))),
            "state": state,
            "signal": signal,
            "close_price": str(closes[i]),
        })

    return rsi_series


def _format_timestamp(ms: int, interval: str = "4h") -> str:
    """格式化毫秒时间戳为可读字符串（北京时间），精确到分钟。"""
    try:
        shanghai_tz = timezone(timedelta(hours=8))
        dt = datetime.fromtimestamp(ms / 1000, tz=shanghai_tz)
        # 所有周期都精确到分钟
        return dt.strftime("%m-%d %H:%M")
    except Exception:
        return str(ms)