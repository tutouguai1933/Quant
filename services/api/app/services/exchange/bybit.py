"""Bybit 交易所适配器。

使用 ccxt 库实现 Bybit 交易所的统一接口。
"""

from __future__ import annotations

import logging
from typing import Any

try:
    import ccxt.async_support as ccxt
except ImportError:
    ccxt = None  # pragma: no cover - ccxt not installed

from services.api.app.services.exchange.base import (
    Balance,
    ExchangeBase,
    ExchangeConfig,
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
    Position,
    Ticker,
)

logger = logging.getLogger(__name__)


class BybitExchange(ExchangeBase):
    """Bybit 交易所适配器。

    使用 ccxt 统一接口实现 Bybit 交易所的所有操作。
    """

    name = "bybit"
    display_name = "Bybit"
    description = "Bybit 交易所适配器，支持现货和合约交易"

    def __init__(self, config: ExchangeConfig) -> None:
        super().__init__(config)
        self._client: ccxt.bybit | None = None

    async def initialize(self) -> bool:
        """初始化 Bybit 连接。"""
        if ccxt is None:
            logger.error("ccxt 库未安装，无法初始化 Bybit 交易所")
            return False
        try:
            self._client = ccxt.bybit(
                {
                    "apiKey": self.config.api_key,
                    "secret": self.config.api_secret,
                    "enableRateLimit": True,
                    "options": {
                        "defaultType": self.config.default_type,
                    },
                }
            )

            if self.config.sandbox:
                self._client.set_sandbox_mode(True)

            # 加载市场信息
            await self._client.load_markets()
            logger.info("Bybit 交易所初始化成功")
            return True
        except Exception as e:
            logger.error("Bybit 交易所初始化失败: %s", e)
            return False

    async def close(self) -> None:
        """关闭 Bybit 连接。"""
        if self._client:
            await self._client.close()
            self._client = None
            logger.info("Bybit 交易所连接已关闭")

    async def get_balance(self, asset: str | None = None) -> list[Balance]:
        """获取账户余额。"""
        if not self._client:
            raise RuntimeError("交易所未初始化")

        balance_data = await self._client.fetch_balance()
        balances = []

        for currency, data in balance_data.items():
            if currency in ["info", "timestamp", "datetime", "free", "used", "total"]:
                continue

            if asset and currency != asset:
                continue

            free = float(data.get("free", 0) or 0)
            used = float(data.get("used", 0) or 0)
            total = float(data.get("total", 0) or 0)

            if total > 0:
                balances.append(
                    Balance(
                        asset=currency,
                        free=free,
                        used=used,
                        total=total,
                    )
                )

        return balances

    async def get_positions(self, symbol: str | None = None) -> list[Position]:
        """获取持仓信息。"""
        if not self._client:
            raise RuntimeError("交易所未初始化")

        positions_data = await self._client.fetch_positions([symbol] if symbol else None)
        positions = []

        for pos in positions_data:
            if symbol and pos.get("symbol") != symbol:
                continue

            size = float(pos.get("contracts", 0) or 0)
            if size == 0:
                continue

            side = pos.get("side", "long")
            if isinstance(side, str):
                side = "long" if side.lower() == "long" else "short"

            positions.append(
                Position(
                    symbol=pos.get("symbol", ""),
                    side=side,
                    size=size,
                    entry_price=float(pos.get("entryPrice", 0) or 0),
                    mark_price=float(pos.get("markPrice", 0) or 0),
                    unrealized_pnl=float(pos.get("unrealizedPnl", 0) or 0),
                    leverage=float(pos.get("leverage", 1) or 1),
                    liquidation_price=pos.get("liquidationPrice"),
                    metadata=pos,
                )
            )

        return positions

    async def place_order(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        amount: float,
        price: float | None = None,
        **kwargs: Any,
    ) -> Order:
        """下单。"""
        if not self._client:
            raise RuntimeError("交易所未初始化")

        order_params = kwargs.get("params", {})

        if order_type == OrderType.LIMIT and price is None:
            raise ValueError("限价单必须指定价格")

        order = await self._client.create_order(
            symbol=symbol,
            type=order_type.value,
            side=side.value,
            amount=amount,
            price=price,
            params=order_params,
        )

        return self._parse_order(order)

    async def cancel_order(self, order_id: str, symbol: str | None = None) -> bool:
        """撤单。"""
        if not self._client:
            raise RuntimeError("交易所未初始化")

        try:
            await self._client.cancel_order(order_id, symbol)
            logger.info("Bybit 订单撤销成功: %s", order_id)
            return True
        except Exception as e:
            logger.error("Bybit 订单撤销失败: %s - %s", order_id, e)
            return False

    async def get_order(self, order_id: str, symbol: str | None = None) -> Order | None:
        """查询订单。"""
        if not self._client:
            raise RuntimeError("交易所未初始化")

        try:
            order = await self._client.fetch_order(order_id, symbol)
            return self._parse_order(order)
        except Exception as e:
            logger.error("Bybit 查询订单失败: %s - %s", order_id, e)
            return None

    async def get_open_orders(self, symbol: str | None = None) -> list[Order]:
        """获取未完成订单。"""
        if not self._client:
            raise RuntimeError("交易所未初始化")

        orders = await self._client.fetch_open_orders(symbol)
        return [self._parse_order(o) for o in orders]

    async def get_ticker(self, symbol: str) -> Ticker:
        """获取行情数据。"""
        if not self._client:
            raise RuntimeError("交易所未初始化")

        ticker = await self._client.fetch_ticker(symbol)

        return Ticker(
            symbol=symbol,
            last=float(ticker.get("last", 0) or 0),
            bid=float(ticker.get("bid", 0) or 0),
            ask=float(ticker.get("ask", 0) or 0),
            high=float(ticker.get("high", 0) or 0),
            low=float(ticker.get("low", 0) or 0),
            volume=float(ticker.get("baseVolume", 0) or 0),
            timestamp=int(ticker.get("timestamp", 0) or 0),
        )

    async def get_market_info(self, symbol: str) -> dict[str, Any]:
        """获取市场信息。"""
        if not self._client:
            raise RuntimeError("交易所未初始化")

        market = self._client.market(symbol)

        return {
            "symbol": symbol,
            "base": market.get("base"),
            "quote": market.get("quote"),
            "active": market.get("active", False),
            "type": market.get("type"),
            "spot": market.get("spot", False),
            "swap": market.get("swap", False),
            "future": market.get("future", False),
            "precision": {
                "price": market.get("precision", {}).get("price"),
                "amount": market.get("precision", {}).get("amount"),
            },
            "limits": {
                "amount": {
                    "min": market.get("limits", {}).get("amount", {}).get("min"),
                    "max": market.get("limits", {}).get("amount", {}).get("max"),
                },
                "price": {
                    "min": market.get("limits", {}).get("price", {}).get("min"),
                    "max": market.get("limits", {}).get("price", {}).get("max"),
                },
                "cost": {
                    "min": market.get("limits", {}).get("cost", {}).get("min"),
                    "max": market.get("limits", {}).get("cost", {}).get("max"),
                },
            },
        }

    async def set_leverage(self, symbol: str, leverage: int) -> bool:
        """设置杠杆。"""
        if not self._client:
            raise RuntimeError("交易所未初始化")

        try:
            await self._client.set_leverage(leverage, symbol)
            logger.info("Bybit 杠杆设置成功: %s - %dx", symbol, leverage)
            return True
        except Exception as e:
            logger.error("Bybit 杠杆设置失败: %s - %s", symbol, e)
            return False

    def _parse_order(self, order: dict[str, Any]) -> Order:
        """解析订单数据。"""
        status_map = {
            "open": OrderStatus.OPEN,
            "closed": OrderStatus.CLOSED,
            "canceled": OrderStatus.CANCELED,
            "expired": OrderStatus.EXPIRED,
            "rejected": OrderStatus.REJECTED,
        }

        return Order(
            id=str(order.get("id", "")),
            symbol=order.get("symbol", ""),
            side=OrderSide(order.get("side", "buy")),
            type=OrderType(order.get("type", "market")),
            price=order.get("price"),
            amount=float(order.get("amount", 0) or 0),
            filled=float(order.get("filled", 0) or 0),
            remaining=float(order.get("remaining", 0) or 0),
            status=status_map.get(order.get("status", "open"), OrderStatus.OPEN),
            timestamp=int(order.get("timestamp", 0) or 0),
            metadata=order,
        )