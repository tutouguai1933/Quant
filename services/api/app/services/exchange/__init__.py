"""多交易所支持模块。

提供统一的交易所抽象接口和 OKX、Bybit 适配器实现。
"""

from services.api.app.services.exchange.base import ExchangeBase

# Lazy imports for adapters that require ccxt
# Use this pattern to avoid import errors when ccxt is not installed
__all__ = ["ExchangeBase", "OKXExchange", "BybitExchange"]


def __getattr__(name: str):
    """Lazy import for ccxt-dependent modules."""
    if name == "OKXExchange":
        from services.api.app.services.exchange.okx import OKXExchange
        return OKXExchange
    elif name == "BybitExchange":
        from services.api.app.services.exchange.bybit import BybitExchange
        return BybitExchange
    raise AttributeError(f"module {__name__} has no attribute {name}")