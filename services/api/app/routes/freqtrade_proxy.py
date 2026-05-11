"""Freqtrade API 代理路由。

将 Freqtrade 的 API 代理到前端，统一入口管理。
"""

from __future__ import annotations

import logging
import os
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
        auth = _get_auth()
        async with httpx.AsyncClient(timeout=10.0) as client:
            # 获取状态
            status_resp = await client.get(f"{FREQTRADE_HOST}/api/v1/status", auth=auth)
            status_resp.raise_for_status()
            trades = status_resp.json()

            # 获取收益
            profit_resp = await client.get(f"{FREQTRADE_HOST}/api/v1/profit", auth=auth)
            profit_resp.raise_for_status()
            profit = profit_resp.json()

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
        auth = _get_auth()
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{FREQTRADE_HOST}/api/v1/profit", auth=auth)
            resp.raise_for_status()
            return _success(resp.json())
    except Exception as e:
        logger.exception("Freqtrade 收益获取异常: %s", e)
        return _error(f"Freqtrade 连接失败: {e}")


@router.get("/trades")
async def get_freqtrade_trades(limit: int = 10) -> dict[str, Any]:
    """获取 Freqtrade 最近交易记录。"""
    try:
        auth = _get_auth()
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{FREQTRADE_HOST}/api/v1/trades",
                params={"limit": limit},
                auth=auth,
            )
            resp.raise_for_status()
            return _success(resp.json())
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
        auth = _get_auth()
        async with httpx.AsyncClient(timeout=10.0) as client:
            # 获取已平仓交易
            trades_resp = await client.get(
                f"{FREQTRADE_HOST}/api/v1/trades",
                params={"limit": 100},
                auth=auth,
            )
            trades_resp.raise_for_status()
            trades_data = trades_resp.json()
            trades = list(trades_data.get("trades") or [])

            # 获取当前持仓
            status_resp = await client.get(f"{FREQTRADE_HOST}/api/v1/status", auth=auth)
            status_resp.raise_for_status()
            open_trades = status_resp.json() or []

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
        auth = _get_auth()
        async with httpx.AsyncClient(timeout=10.0) as client:
            status_resp = await client.get(f"{FREQTRADE_HOST}/api/v1/status", auth=auth)
            status_resp.raise_for_status()
            trades = status_resp.json()

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
                    "profit_pct": t.get("profit_pct"),
                    "profit_abs": t.get("profit_abs"),
                    "open_date": t.get("open_date"),
                    "source": "automation_cycle" if enter_tag == "quant-control-plane" else "enhanced_strategy",
                })

            total_stake = sum(float(t.get("stake_amount", 0) or 0) for t in open_trades)
            total_profit = sum(float(t.get("profit_abs", 0) or 0) for t in open_trades)
            total_profit_pct = (total_profit / total_stake * 100) if total_stake > 0 else 0

            return _success({
                "items": items,
                "total_stake": round(total_stake, 2),
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
