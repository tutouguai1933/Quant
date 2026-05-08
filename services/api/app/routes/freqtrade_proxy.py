"""Freqtrade API 代理路由。

将 Freqtrade 的 API 代理到前端，统一入口管理。
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from services.api.app.services.workbench_config_service import workbench_config_service

try:
    from fastapi import APIRouter
except ImportError:
    class APIRouter:  # pragma: no cover
        def __init__(self, *args, **kwargs) -> None: ...
        def get(self, *args, **kwargs): ...

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/freqtrade", tags=["freqtrade"])

# Freqtrade API 配置
FREQTRADE_HOST = "http://127.0.0.1:9013"


def _get_auth() -> tuple[str, str]:
    """获取 Freqtrade 认证信息。"""
    config = workbench_config_service.get_config_section("thresholds")
    username = str(config.get("freqtrade_username") or "Freqtrader")
    password = str(config.get("freqtrade_password") or "jianyu0.0.")
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
