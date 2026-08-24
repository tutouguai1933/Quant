"""Freqtrade API 代理路由。

将 Freqtrade 的 API 代理到前端，统一入口管理。
所有只读请求共享 5 秒缓存 + 并发单飞，
避免前端多个卡片/页面同时轮询时重复打爆 Freqtrade。
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any

import httpx

try:
    from fastapi import APIRouter
except ImportError:
    class APIRouter:  # pragma: no cover
        def __init__(self, *args, **kwargs) -> None: ...
        def get(self, *args, **kwargs): ...

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/freqtrade", tags=["freqtrade"])

# Freqtrade API 配置
# 优先使用环境变量，否则使用 Docker 网关地址
FREQTRADE_HOST = (
    os.getenv("QUANT_FREQTRADE_API_URL")
    or os.getenv("FREQTRADE_HOST")
    or "http://172.17.0.1:9013"  # Docker bridge 网关
)

# 只读代理缓存：path -> (写入时间, 响应数据)；5 秒内重复请求直接复用
_PROXY_CACHE_TTL_SECONDS = 30.0
_PROXY_FAIL_WINDOW_SECONDS = 10.0
_proxy_fail_until: dict[str, float] = {}
_proxy_cache: dict[str, tuple[float, Any]] = {}
# 并发单飞：同一个 path 同时只有一个真实请求，其余等待同一个结果
_proxy_inflight: dict[str, asyncio.Future[Any]] = {}


async def _cached_freqtrade_get(path: str, params: dict[str, Any] | None = None) -> Any:
    """带缓存与单飞的只读 GET：并发轮询只打一次 Freqtrade。"""

    cache_key = f"{path}?{params}" if params else path
    now = time.monotonic()
    # 失败冷却：freqtrade 刚失败过（10 秒内）时快速抛错，不排队打它
    fail_until = _proxy_fail_until.get(cache_key)
    if fail_until is not None and now < fail_until:
        raise RuntimeError(f"freqtrade recently failed (cooldown), path={path}")
    cached = _proxy_cache.get(cache_key)
    if cached is not None and now - cached[0] < _PROXY_CACHE_TTL_SECONDS:
        return cached[1]

    # 并发单飞：已有同路径请求在途时共享其结果
    inflight = _proxy_inflight.get(cache_key)
    if inflight is not None:
        try:
            return await asyncio.shield(inflight)
        except Exception:
            # 在途请求失败后按无缓存继续处理，由下方逻辑重试一次
            _proxy_inflight.pop(cache_key, None)

    loop = asyncio.get_running_loop()
    future: asyncio.Future[Any] = loop.create_future()
    _proxy_inflight[cache_key] = future
    try:
        auth = _get_auth()
        # 全局客户端复用，不用 async with（避免每次请求关闭连接池）
        client = _freqtrade_client()
        resp = await client.get(f"{FREQTRADE_HOST}{path}", params=params, auth=auth)
        resp.raise_for_status()
        payload = resp.json()
        _proxy_cache[cache_key] = (time.monotonic(), payload)
        _proxy_fail_until.pop(cache_key, None)
        future.set_result(payload)
        return payload
    except Exception as exc:
        # 失败记录失败时间：freqtrade 挂起时 10 秒内的新请求直接快速抛错，
        # 不再排队打无响应的 freqtrade（曾致线程池占满卡死）。
        # 各接口自行捕获异常降级（现有逻辑已支持）。
        _proxy_fail_until[cache_key] = time.monotonic() + 10.0
        if not future.done():
            future.set_exception(exc)
        raise
    finally:
        _proxy_inflight.pop(cache_key, None)


# 全局复用的 AsyncClient：每次请求新建/销毁连接池会在事件循环里触发
# httpcore 懒加载 import 与池初始化（磁盘慢时卡数秒~数十秒，曾致事件循环阻塞卡死）
_shared_freqtrade_client: httpx.AsyncClient | None = None


def _freqtrade_client() -> httpx.AsyncClient:
    """返回全局复用的 Freqtrade 直连客户端（避免本机执行器请求误走系统代理）。"""

    global _shared_freqtrade_client
    if _shared_freqtrade_client is None or _shared_freqtrade_client.is_closed:
        _shared_freqtrade_client = httpx.AsyncClient(
            timeout=10.0,
            trust_env=False,
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )
    return _shared_freqtrade_client


def _get_auth() -> tuple[str, str]:
    """获取 Freqtrade 认证信息。"""
    # 支持两种环境变量格式
    username = os.getenv("FREQTRADE_USERNAME") or os.getenv("QUANT_FREQTRADE_API_USERNAME", "Freqtrader")
    password = os.getenv("FREQTRADE_PASSWORD") or os.getenv("QUANT_FREQTRADE_API_PASSWORD", "jianyu0.0.")
    return (username, password)


def _success(data: Any) -> dict[str, Any]:
    return {"data": data, "error": None, "meta": {"source": "freqtrade-proxy"}}


def _error(message: str, code: str = "freqtrade_error") -> dict[str, Any]:
    return {"data": None, "error": {"code": code, "message": message}, "meta": {"source": "freqtrade-proxy"}}


@router.get("/status")
async def get_freqtrade_status() -> dict[str, Any]:
    """获取 Freqtrade 运行状态。"""
    try:
        # 状态与收益均走共享缓存/单飞，多卡片轮询只打一次 Freqtrade
        trades = await _cached_freqtrade_get("/api/v1/status")
        profit = await _cached_freqtrade_get("/api/v1/profit")

        # 统计当前持仓
        open_trades = [t for t in trades if t.get("is_open")]
        open_symbols = [t.get("pair") for t in open_trades]

        return _success({
            "running": True,
            "strategy": "EnhancedStrategy",
            "open_trades": len(open_trades),
            "open_symbols": open_symbols,
            "profit": {
                "total_percent": profit.get("profit_all_percent", 0),
                "total_ratio": profit.get("profit_all_ratio", 0),
                "winrate": profit.get("winrate", 0),
                "trade_count": profit.get("trade_count", 0),
                "winning_trades": profit.get("winning_trades", 0),
                "losing_trades": profit.get("losing_trades", 0),
                "best_pair": profit.get("best_pair", ""),
                "best_rate": profit.get("best_rate", 0),
                "sharpe": profit.get("sharpe", 0),
            },
            "latest_trade": profit.get("latest_trade_date", ""),
            "bot_start_date": profit.get("bot_start_date", ""),
        })
    except httpx.HTTPError as e:
        logger.warning("Freqtrade API 请求失败: %s", e)
        return _success({
            "running": False,
            "error": str(e),
        })
    except Exception as e:
        logger.exception("Freqtrade 状态获取异常: %s", e)
        return _error(f"Freqtrade 连接失败: {e}")


@router.get("/profit")
async def get_freqtrade_profit() -> dict[str, Any]:
    """获取 Freqtrade 收益统计。"""
    try:
        payload = await _cached_freqtrade_get("/api/v1/profit")
        return _success(payload)
    except Exception as e:
        logger.exception("Freqtrade 收益获取异常: %s", e)
        return _error(f"Freqtrade 连接失败: {e}")


@router.get("/trades")
async def get_freqtrade_trades(limit: int = 10) -> dict[str, Any]:
    """获取 Freqtrade 最近交易记录。"""
    try:
        payload = await _cached_freqtrade_get("/api/v1/trades", params={"limit": limit})
        return _success(payload)
    except Exception as e:
        logger.exception("Freqtrade 交易记录获取异常: %s", e)
        return _error(f"Freqtrade 连接失败: {e}")


@router.get("/profit-by-source")
async def get_freqtrade_profit_by_source() -> dict[str, Any]:
    """按策略来源分组的收益统计。

    通过 enter_tag 字段区分交易来源：
    - 空字符串 "" = EnhancedStrategy (Freqtrade 自主决策)
    - "quant-control-plane" = 自动化周期派发
    """
    try:
        # 获取已平仓交易
        trades_data = await _cached_freqtrade_get("/api/v1/trades", params={"limit": 100})
        trades = list(trades_data.get("trades") or [])

        # 获取当前持仓
        open_trades = await _cached_freqtrade_get("/api/v1/status") or []

        # 按来源分组统计
        enhanced = _init_source_stats()
        automation = _init_source_stats()

        for trade in trades:
            enter_tag = str(trade.get("enter_tag") or "")
            profit = float(trade.get("close_profit_abs") or 0)
            is_win = profit > 0

            if enter_tag == "quant-control-plane":
                automation["trade_count"] += 1
                automation["total_profit"] += profit
                if is_win:
                    automation["winning_trades"] += 1
                else:
                    automation["losing_trades"] += 1
            else:
                enhanced["trade_count"] += 1
                enhanced["total_profit"] += profit
                if is_win:
                    enhanced["winning_trades"] += 1
                else:
                    enhanced["losing_trades"] += 1

        # 统计当前持仓
        for trade in open_trades:
            enter_tag = str(trade.get("enter_tag") or "")
            symbol = str(trade.get("pair", "")).replace("/USDT", "")
            if enter_tag == "quant-control-plane":
                automation["open_trades"] += 1
                automation["open_symbols"].append(symbol)
            else:
                enhanced["open_trades"] += 1
                enhanced["open_symbols"].append(symbol)

        # 计算胜率
        enhanced["winrate"] = (
            enhanced["winning_trades"] / enhanced["trade_count"]
            if enhanced["trade_count"] > 0 else 0
        )
        automation["winrate"] = (
            automation["winning_trades"] / automation["trade_count"]
            if automation["trade_count"] > 0 else 0
        )

        # 计算总计
        total = {
            "trade_count": enhanced["trade_count"] + automation["trade_count"],
            "winning_trades": enhanced["winning_trades"] + automation["winning_trades"],
            "losing_trades": enhanced["losing_trades"] + automation["losing_trades"],
            "total_profit": enhanced["total_profit"] + automation["total_profit"],
            "winrate": 0.0,
        }
        total["winrate"] = (
            total["winning_trades"] / total["trade_count"]
            if total["trade_count"] > 0 else 0
        )

        return _success({
            "enhanced_strategy": enhanced,
            "automation_cycle": automation,
            "total": total,
        })
    except Exception as e:
        logger.exception("Freqtrade 收益统计获取异常: %s", e)
        return _error(f"Freqtrade 连接失败: {e}")


def _init_source_stats() -> dict[str, Any]:
    """初始化来源统计数据结构。"""
    return {
        "trade_count": 0,
        "winning_trades": 0,
        "losing_trades": 0,
        "total_profit": 0.0,
        "winrate": 0.0,
        "open_trades": 0,
        "open_symbols": [],
    }


@router.get("/open-trades")
async def get_freqtrade_open_trades() -> dict[str, Any]:
    """获取 Freqtrade 当前持仓详情。"""
    try:
        trades = await _cached_freqtrade_get("/api/v1/status")

        open_trades = [t for t in trades if t.get("is_open")]

        items = []
        for t in open_trades:
            enter_tag = str(t.get("enter_tag") or "")
            items.append({
                "trade_id": t.get("trade_id"),
                "symbol": t.get("pair", "").replace("/USDT", ""),
                "pair": t.get("pair"),
                "side": "short" if t.get("is_short") else "long",
                "open_rate": t.get("open_rate"),
                "amount": t.get("amount"),
                "stake_amount": t.get("stake_amount"),
                "current_rate": t.get("current_rate"),
                "open_trade_value": t.get("open_trade_value"),
                "profit_pct": t.get("profit_pct"),
                "profit_abs": t.get("profit_abs"),
                "open_date": t.get("open_date"),
                "stop_loss_abs": t.get("stop_loss_abs"),
                "strategy": str(t.get("strategy") or ""),
                "source": "automation_cycle" if enter_tag == "quant-control-plane" else "enhanced_strategy",
            })

        total_stake = sum(float(t.get("stake_amount", 0) or 0) for t in open_trades)
        total_profit = sum(float(t.get("profit_abs", 0) or 0) for t in open_trades)
        total_profit_pct = (total_profit / total_stake * 100) if total_stake > 0 else 0
        total_market_value = sum(float(t.get("open_trade_value", 0) or 0) for t in open_trades)

        return _success({
            "items": items,
            "total_stake": round(total_stake, 2),
            "total_market_value": round(total_market_value, 2),
            "total_profit": round(total_profit, 4),
            "total_profit_pct": round(total_profit_pct, 2),
            "count": len(items),
        })
    except httpx.HTTPError as e:
        logger.warning("Freqtrade API 请求失败: %s", e)
        return _success({
            "items": [],
            "total_stake": 0,
            "total_profit": 0,
            "total_profit_pct": 0,
            "count": 0,
            "error": str(e),
        })
    except Exception as e:
        logger.exception("Freqtrade 持仓获取异常: %s", e)
        return _error(f"Freqtrade 连接失败: {e}")
