"""交易所管理路由。

提供交易所列表、切换、初始化等 API 接口。
"""

from __future__ import annotations

from typing import Any

try:
    from fastapi import APIRouter, Body
except ImportError:
    class APIRouter:  # pragma: no cover - lightweight local fallback
        def __init__(self, *args, **kwargs) -> None:
            self.args = args
            self.kwargs = kwargs

        def get(self, *args, **kwargs):
            def decorator(func):
                return func
            return decorator

        def post(self, *args, **kwargs):
            def decorator(func):
                return func
            return decorator

    def Body(default=None):  # pragma: no cover - lightweight local fallback
        return default


from services.api.app.services.exchange.exchange_service import (
    exchange_service,
    SUPPORTED_EXCHANGES,
)


router = APIRouter(prefix="/api/v1/exchange", tags=["exchange"])


def _success(data: dict, meta: dict | None = None) -> dict:
    return {"data": data, "error": None, "meta": meta or {}}


def _error(code: str, message: str, meta: dict | None = None) -> dict:
    return {"data": None, "error": {"code": code, "message": message}, "meta": meta or {}}


@router.get("/list")
def get_exchange_list() -> dict:
    """获取支持的交易所列表。

    Returns:
        支持的交易所列表
    """
    exchanges = exchange_service.get_supported_exchanges()
    return _success(
        {"items": exchanges, "total": len(exchanges)},
        {"source": "exchange-service", "action": "list"}
    )


@router.get("/current")
def get_current_exchange() -> dict:
    """获取当前交易所信息。

    Returns:
        当前交易所信息
    """
    name = exchange_service.get_current_exchange_name()
    exchange = exchange_service.get_current_exchange()

    if not exchange:
        return _success(
            {"current": None, "message": "当前没有激活的交易所"},
            {"source": "exchange-service", "action": "current"}
        )

    return _success(
        {
            "current": name,
            "exchange": exchange.to_dict(),
        },
        {"source": "exchange-service", "action": "current"}
    )


@router.post("/switch")
async def switch_exchange(payload: dict[str, Any] | None = Body(None)) -> dict:
    """切换当前交易所。

    Args:
        payload: {"name": "okx" | "bybit"}

    Returns:
        切换结果
    """
    request = payload if isinstance(payload, dict) else {}
    name = request.get("name", "")

    if not name:
        return _error("missing_parameter", "缺少交易所名称", {"source": "exchange-service"})

    result = await exchange_service.switch_exchange(name)

    if result["success"]:
        return _success(
            {"message": result["message"], "current_exchange": result["current_exchange"]},
            {"source": "exchange-service", "action": "switch"}
        )
    else:
        return _error("switch_failed", result["message"], {"source": "exchange-service"})


@router.post("/initialize")
async def initialize_exchange(payload: dict[str, Any] | None = Body(None)) -> dict:
    """初始化交易所。

    Args:
        payload: {
            "name": "okx" | "bybit",
            "api_key": "...",
            "api_secret": "...",
            "password": "...",  # OKX 需要
            "sandbox": false,
            "default_type": "swap"
        }

    Returns:
        初始化结果
    """
    request = payload if isinstance(payload, dict) else {}

    name = request.get("name", "")
    api_key = request.get("api_key", "")
    api_secret = request.get("api_secret", "")
    password = request.get("password")
    sandbox = request.get("sandbox", False)
    default_type = request.get("default_type", "swap")

    if not name:
        return _error("missing_parameter", "缺少交易所名称", {"source": "exchange-service"})

    if not api_key or not api_secret:
        return _error("missing_parameter", "缺少 API Key 或 API Secret", {"source": "exchange-service"})

    result = await exchange_service.initialize_exchange(
        name=name,
        api_key=api_key,
        api_secret=api_secret,
        password=password,
        sandbox=sandbox,
        default_type=default_type,
    )

    if result["success"]:
        return _success(
            {"message": result["message"], "exchange": result.get("exchange")},
            {"source": "exchange-service", "action": "initialize"}
        )
    else:
        return _error("initialize_failed", result["message"], {"source": "exchange-service"})


@router.post("/close")
async def close_exchange(payload: dict[str, Any] | None = Body(None)) -> dict:
    """关闭交易所连接。

    Args:
        payload: {"name": "okx" | "bybit"}

    Returns:
        关闭结果
    """
    request = payload if isinstance(payload, dict) else {}
    name = request.get("name", "")

    if not name:
        return _error("missing_parameter", "缺少交易所名称", {"source": "exchange-service"})

    result = await exchange_service.close_exchange(name)

    if result["success"]:
        return _success(
            {"message": result["message"]},
            {"source": "exchange-service", "action": "close"}
        )
    else:
        return _error("close_failed", result["message"], {"source": "exchange-service"})


@router.get("/config/{name}")
def get_exchange_config(name: str) -> dict:
    """获取交易所配置。

    Args:
        name: 交易所名称

    Returns:
        配置信息
    """
    config = exchange_service.get_exchange_config(name)

    if not config:
        return _error(
            "config_not_found",
            f"交易所 {name} 配置不存在",
            {"source": "exchange-service"}
        )

    return _success(
        {"config": config},
        {"source": "exchange-service", "action": "config"}
    )


@router.post("/config/{name}")
def update_exchange_config(name: str, payload: dict[str, Any] | None = Body(None)) -> dict:
    """更新交易所配置。

    注意：更新配置后需要重新初始化交易所才能生效。

    Args:
        name: 交易所名称
        payload: 配置更新

    Returns:
        更新结果
    """
    request = payload if isinstance(payload, dict) else {}

    result = exchange_service.update_exchange_config(
        name=name,
        api_key=request.get("api_key"),
        api_secret=request.get("api_secret"),
        password=request.get("password"),
        sandbox=request.get("sandbox"),
        default_type=request.get("default_type"),
    )

    if result["success"]:
        return _success(
            {"message": result["message"], "config": result.get("config")},
            {"source": "exchange-service", "action": "update-config"}
        )
    else:
        return _error("update_failed", result["message"], {"source": "exchange-service"})


@router.get("/balance")
async def get_balance(asset: str | None = None) -> dict:
    """获取当前交易所账户余额。

    Args:
        asset: 可选，指定资产

    Returns:
        余额信息
    """
    exchange = exchange_service.get_current_exchange()

    if not exchange:
        return _error(
            "no_active_exchange",
            "当前没有激活的交易所",
            {"source": "exchange-service"}
        )

    try:
        balances = await exchange.get_balance(asset)
        return _success(
            {"items": [b.to_dict() for b in balances], "total": len(balances)},
            {"source": "exchange-service", "action": "balance"}
        )
    except Exception as e:
        return _error(
            "balance_failed",
            f"获取余额失败: {str(e)}",
            {"source": "exchange-service"}
        )


@router.get("/positions")
async def get_positions(symbol: str | None = None) -> dict:
    """获取当前交易所持仓信息。

    Args:
        symbol: 可选，指定交易对

    Returns:
        持仓信息
    """
    exchange = exchange_service.get_current_exchange()

    if not exchange:
        return _error(
            "no_active_exchange",
            "当前没有激活的交易所",
            {"source": "exchange-service"}
        )

    try:
        positions = await exchange.get_positions(symbol)
        return _success(
            {"items": [p.to_dict() for p in positions], "total": len(positions)},
            {"source": "exchange-service", "action": "positions"}
        )
    except Exception as e:
        return _error(
            "positions_failed",
            f"获取持仓失败: {str(e)}",
            {"source": "exchange-service"}
        )


@router.get("/ticker/{symbol}")
async def get_ticker(symbol: str) -> dict:
    """获取行情数据。

    Args:
        symbol: 交易对

    Returns:
        行情数据
    """
    exchange = exchange_service.get_current_exchange()

    if not exchange:
        return _error(
            "no_active_exchange",
            "当前没有激活的交易所",
            {"source": "exchange-service"}
        )

    try:
        ticker = await exchange.get_ticker(symbol)
        return _success(
            {"ticker": ticker.to_dict()},
            {"source": "exchange-service", "action": "ticker"}
        )
    except Exception as e:
        return _error(
            "ticker_failed",
            f"获取行情失败: {str(e)}",
            {"source": "exchange-service"}
        )


@router.get("/market/{symbol}")
async def get_market_info(symbol: str) -> dict:
    """获取市场信息。

    Args:
        symbol: 交易对

    Returns:
        市场信息
    """
    exchange = exchange_service.get_current_exchange()

    if not exchange:
        return _error(
            "no_active_exchange",
            "当前没有激活的交易所",
            {"source": "exchange-service"}
        )

    try:
        market = await exchange.get_market_info(symbol)
        return _success(
            {"market": market},
            {"source": "exchange-service", "action": "market"}
        )
    except Exception as e:
        return _error(
            "market_failed",
            f"获取市场信息失败: {str(e)}",
            {"source": "exchange-service"}
        )