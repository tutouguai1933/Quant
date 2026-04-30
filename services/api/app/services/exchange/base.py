"""交易所抽象基类。

定义统一的交易所接口，所有交易所适配器必须实现此接口。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class OrderSide(str, Enum):
    """订单方向。"""

    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    """订单类型。"""

    MARKET = "market"
    LIMIT = "limit"


class OrderStatus(str, Enum):
    """订单状态。"""

    OPEN = "open"
    CLOSED = "closed"
    CANCELED = "canceled"
    EXPIRED = "expired"
    REJECTED = "rejected"


@dataclass
class Balance:
    """账户余额。"""

    asset: str
    free: float
    used: float
    total: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "asset": self.asset,
            "free": self.free,
            "used": self.used,
            "total": self.total,
        }


@dataclass
class Position:
    """持仓信息。"""

    symbol: str
    side: str  # "long" or "short"
    size: float
    entry_price: float
    mark_price: float
    unrealized_pnl: float
    leverage: float
    liquidation_price: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "side": self.side,
            "size": self.size,
            "entry_price": self.entry_price,
            "mark_price": self.mark_price,
            "unrealized_pnl": self.unrealized_pnl,
            "leverage": self.leverage,
            "liquidation_price": self.liquidation_price,
            "metadata": self.metadata,
        }


@dataclass
class Order:
    """订单信息。"""

    id: str
    symbol: str
    side: OrderSide
    type: OrderType
    price: float | None
    amount: float
    filled: float
    remaining: float
    status: OrderStatus
    timestamp: int
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "symbol": self.symbol,
            "side": self.side.value,
            "type": self.type.value,
            "price": self.price,
            "amount": self.amount,
            "filled": self.filled,
            "remaining": self.remaining,
            "status": self.status.value,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


@dataclass
class Ticker:
    """行情数据。"""

    symbol: str
    last: float
    bid: float
    ask: float
    high: float
    low: float
    volume: float
    timestamp: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "last": self.last,
            "bid": self.bid,
            "ask": self.ask,
            "high": self.high,
            "low": self.low,
            "volume": self.volume,
            "timestamp": self.timestamp,
        }


@dataclass
class ExchangeConfig:
    """交易所配置。"""

    api_key: str
    api_secret: str
    password: str | None = None  # OKX 需要 passphrase
    sandbox: bool = False
    default_type: str = "swap"  # "spot", "swap", "future"

    def to_dict(self) -> dict[str, Any]:
        return {
            "api_key": "***" if self.api_key else None,
            "api_secret": "***" if self.api_secret else None,
            "password": "***" if self.password else None,
            "sandbox": self.sandbox,
            "default_type": self.default_type,
        }


class ExchangeBase(ABC):
    """交易所抽象基类。

    所有交易所适配器必须继承此类并实现所有抽象方法。
    """

    name: str = "base"
    display_name: str = "基础交易所"
    description: str = "交易所抽象基类"

    def __init__(self, config: ExchangeConfig) -> None:
        self.config = config
        self._client: Any = None

    @abstractmethod
    async def initialize(self) -> bool:
        """初始化交易所连接。

        Returns:
            True 如果初始化成功
        """
        raise NotImplementedError

    @abstractmethod
    async def close(self) -> None:
        """关闭交易所连接。"""
        raise NotImplementedError

    @abstractmethod
    async def get_balance(self, asset: str | None = None) -> list[Balance]:
        """获取账户余额。

        Args:
            asset: 可选，指定资产类型。如果为 None，返回所有资产余额。

        Returns:
            余额列表
        """
        raise NotImplementedError

    @abstractmethod
    async def get_positions(self, symbol: str | None = None) -> list[Position]:
        """获取持仓信息。

        Args:
            symbol: 可选，指定交易对。如果为 None，返回所有持仓。

        Returns:
            持仓列表
        """
        raise NotImplementedError

    @abstractmethod
    async def place_order(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        amount: float,
        price: float | None = None,
        **kwargs: Any,
    ) -> Order:
        """下单。

        Args:
            symbol: 交易对
            side: 订单方向
            order_type: 订单类型
            amount: 数量
            price: 价格（限价单必须）
            **kwargs: 其他参数

        Returns:
            订单信息
        """
        raise NotImplementedError

    @abstractmethod
    async def cancel_order(self, order_id: str, symbol: str | None = None) -> bool:
        """撤单。

        Args:
            order_id: 订单 ID
            symbol: 可选，交易对

        Returns:
            True 如果撤单成功
        """
        raise NotImplementedError

    @abstractmethod
    async def get_order(self, order_id: str, symbol: str | None = None) -> Order | None:
        """查询订单。

        Args:
            order_id: 订单 ID
            symbol: 可选，交易对

        Returns:
            订单信息，如果不存在返回 None
        """
        raise NotImplementedError

    @abstractmethod
    async def get_open_orders(self, symbol: str | None = None) -> list[Order]:
        """获取未完成订单。

        Args:
            symbol: 可选，指定交易对

        Returns:
            订单列表
        """
        raise NotImplementedError

    @abstractmethod
    async def get_ticker(self, symbol: str) -> Ticker:
        """获取行情数据。

        Args:
            symbol: 交易对

        Returns:
            行情数据
        """
        raise NotImplementedError

    @abstractmethod
    async def get_market_info(self, symbol: str) -> dict[str, Any]:
        """获取市场信息。

        Args:
            symbol: 交易对

        Returns:
            市场信息，包含精度、限制等
        """
        raise NotImplementedError

    @abstractmethod
    async def set_leverage(self, symbol: str, leverage: int) -> bool:
        """设置杠杆。

        Args:
            symbol: 交易对
            leverage: 杠杆倍数

        Returns:
            True 如果设置成功
        """
        raise NotImplementedError

    def to_dict(self) -> dict[str, Any]:
        """序列化交易所信息。"""
        return {
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "config": self.config.to_dict(),
        }