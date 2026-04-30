"""交易所模块测试。

测试交易所抽象接口、OKX/Bybit适配器和交易所管理服务。
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# Check if ccxt is available
try:
    import ccxt
    CCXT_AVAILABLE = True
except ImportError:
    CCXT_AVAILABLE = False

pytestmark = pytest.mark.anyio

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
from services.api.app.services.exchange.okx import OKXExchange
from services.api.app.services.exchange.bybit import BybitExchange
from services.api.app.services.exchange.exchange_service import (
    ExchangeService,
    SUPPORTED_EXCHANGES,
)


class TestExchangeBase:
    """测试交易所基类数据结构。"""

    def test_balance_creation(self) -> None:
        """测试余额数据结构。"""
        balance = Balance(
            asset="USDT",
            free=1000.0,
            used=500.0,
            total=1500.0,
        )
        assert balance.asset == "USDT"
        assert balance.free == 1000.0
        assert balance.used == 500.0
        assert balance.total == 1500.0
        assert balance.to_dict()["asset"] == "USDT"

    def test_position_creation(self) -> None:
        """测试持仓数据结构。"""
        position = Position(
            symbol="BTC/USDT:USDT",
            side="long",
            size=0.1,
            entry_price=50000.0,
            mark_price=51000.0,
            unrealized_pnl=100.0,
            leverage=10.0,
            liquidation_price=45000.0,
        )
        assert position.symbol == "BTC/USDT:USDT"
        assert position.side == "long"
        assert position.size == 0.1
        assert position.unrealized_pnl == 100.0

    def test_order_creation(self) -> None:
        """测试订单数据结构。"""
        order = Order(
            id="12345",
            symbol="BTC/USDT:USDT",
            side=OrderSide.BUY,
            type=OrderType.LIMIT,
            price=50000.0,
            amount=0.1,
            filled=0.05,
            remaining=0.05,
            status=OrderStatus.OPEN,
            timestamp=1609459200000,
        )
        assert order.id == "12345"
        assert order.side == OrderSide.BUY
        assert order.type == OrderType.LIMIT
        assert order.status == OrderStatus.OPEN

    def test_ticker_creation(self) -> None:
        """测试行情数据结构。"""
        ticker = Ticker(
            symbol="BTC/USDT:USDT",
            last=50000.0,
            bid=49990.0,
            ask=50010.0,
            high=51000.0,
            low=49000.0,
            volume=1000.0,
            timestamp=1609459200000,
        )
        assert ticker.symbol == "BTC/USDT:USDT"
        assert ticker.last == 50000.0
        assert ticker.bid == 49990.0

    def test_exchange_config_creation(self) -> None:
        """测试交易所配置。"""
        config = ExchangeConfig(
            api_key="test_key",
            api_secret="test_secret",
            password="test_password",
            sandbox=True,
            default_type="swap",
        )
        assert config.api_key == "test_key"
        assert config.sandbox is True
        assert config.default_type == "swap"
        # to_dict 应隐藏敏感信息
        config_dict = config.to_dict()
        assert config_dict["api_key"] == "***"
        assert config_dict["sandbox"] is True


class TestOKXExchange:
    """测试 OKX 交易所适配器。"""

    def test_okx_exchange_creation(self) -> None:
        """测试 OKX 交易所创建。"""
        config = ExchangeConfig(
            api_key="test_key",
            api_secret="test_secret",
            password="test_password",
            sandbox=False,
            default_type="swap",
        )
        exchange = OKXExchange(config)
        assert exchange.name == "okx"
        assert exchange.display_name == "OKX"
        assert exchange._client is None

    @pytest.mark.asyncio
    @pytest.mark.skipif(not CCXT_AVAILABLE, reason="ccxt not installed")
    async def test_okx_initialize_mock(self) -> None:
        """测试 OKX 初始化（模拟）。"""
        config = ExchangeConfig(
            api_key="test_key",
            api_secret="test_secret",
            password="test_password",
            sandbox=False,
            default_type="swap",
        )
        exchange = OKXExchange(config)

        with patch("ccxt.async_support.okx") as mock_ccxt:
            mock_client = MagicMock()
            mock_client.load_markets = AsyncMock()
            mock_ccxt.return_value = mock_client

            result = await exchange.initialize()
            assert result is True

    @pytest.mark.asyncio
    async def test_okx_close(self) -> None:
        """测试 OKX 关闭连接。"""
        config = ExchangeConfig(
            api_key="test_key",
            api_secret="test_secret",
            password="test_password",
        )
        exchange = OKXExchange(config)

        with patch("ccxt.async_support.okx") as mock_ccxt:
            mock_client = MagicMock()
            mock_client.close = AsyncMock()
            mock_client.load_markets = AsyncMock()
            mock_ccxt.return_value = mock_client

            await exchange.initialize()
            await exchange.close()
            assert exchange._client is None


class TestBybitExchange:
    """测试 Bybit 交易所适配器。"""

    def test_bybit_exchange_creation(self) -> None:
        """测试 Bybit 交易所创建。"""
        config = ExchangeConfig(
            api_key="test_key",
            api_secret="test_secret",
            sandbox=False,
            default_type="swap",
        )
        exchange = BybitExchange(config)
        assert exchange.name == "bybit"
        assert exchange.display_name == "Bybit"
        assert exchange._client is None

    @pytest.mark.asyncio
    async def test_bybit_initialize_mock(self) -> None:
        """测试 Bybit 初始化（模拟）。"""
        config = ExchangeConfig(
            api_key="test_key",
            api_secret="test_secret",
            sandbox=False,
            default_type="swap",
        )
        exchange = BybitExchange(config)

        with patch("ccxt.async_support.bybit") as mock_ccxt:
            mock_client = MagicMock()
            mock_client.load_markets = AsyncMock()
            mock_ccxt.return_value = mock_client

            result = await exchange.initialize()
            assert result is True

    @pytest.mark.asyncio
    async def test_bybit_close(self) -> None:
        """测试 Bybit 关闭连接。"""
        config = ExchangeConfig(
            api_key="test_key",
            api_secret="test_secret",
        )
        exchange = BybitExchange(config)

        with patch("ccxt.async_support.bybit") as mock_ccxt:
            mock_client = MagicMock()
            mock_client.close = AsyncMock()
            mock_client.load_markets = AsyncMock()
            mock_ccxt.return_value = mock_client

            await exchange.initialize()
            await exchange.close()
            assert exchange._client is None


class TestExchangeService:
    """测试交易所管理服务。"""

    def test_get_supported_exchanges(self) -> None:
        """测试获取支持的交易所列表。"""
        service = ExchangeService()
        exchanges = service.get_supported_exchanges()

        assert len(exchanges) >= 2
        assert any(e["name"] == "okx" for e in exchanges)
        assert any(e["name"] == "bybit" for e in exchanges)

    def test_get_current_exchange_name(self) -> None:
        """测试获取当前交易所名称。"""
        service = ExchangeService()
        assert service.get_current_exchange_name() == "okx"

    def test_get_current_exchange_none(self) -> None:
        """测试未初始化时获取当前交易所。"""
        service = ExchangeService()
        exchange = service.get_current_exchange()
        assert exchange is None

    @pytest.mark.asyncio
    async def test_initialize_exchange_unsupported(self) -> None:
        """测试初始化不支持的交易所。"""
        service = ExchangeService()
        result = await service.initialize_exchange(
            name="unsupported",
            api_key="test",
            api_secret="test",
        )
        assert result["success"] is False
        assert "不支持" in result["message"]

    @pytest.mark.asyncio
    async def test_initialize_okx_without_password(self) -> None:
        """测试 OKX 未提供密码时初始化。"""
        service = ExchangeService()
        result = await service.initialize_exchange(
            name="okx",
            api_key="test",
            api_secret="test",
            password=None,
        )
        assert result["success"] is False
        assert "password" in result["message"]

    @pytest.mark.asyncio
    async def test_switch_exchange_not_initialized(self) -> None:
        """测试切换未初始化的交易所。"""
        service = ExchangeService()
        result = await service.switch_exchange("okx")
        assert result["success"] is False
        assert "未初始化" in result["message"]

    @pytest.mark.asyncio
    async def test_switch_exchange_unsupported(self) -> None:
        """测试切换不支持的交易所。"""
        service = ExchangeService()
        result = await service.switch_exchange("unsupported")
        assert result["success"] is False
        assert "不支持" in result["message"]

    @pytest.mark.asyncio
    async def test_close_exchange_not_exists(self) -> None:
        """测试关闭不存在的交易所。"""
        service = ExchangeService()
        result = await service.close_exchange("nonexistent")
        assert result["success"] is False

    def test_get_exchange_config_not_exists(self) -> None:
        """测试获取不存在的配置。"""
        service = ExchangeService()
        config = service.get_exchange_config("nonexistent")
        assert config is None

    def test_update_exchange_config_not_exists(self) -> None:
        """测试更新不存在的配置。"""
        service = ExchangeService()
        result = service.update_exchange_config("nonexistent", api_key="new")
        assert result["success"] is False


class TestExchangeRoutes:
    """测试交易所路由（模拟 API）。"""

    def test_exchange_list_route_import(self) -> None:
        """测试交易所路由导入。"""
        from services.api.app.routes.exchange import router
        assert router.prefix == "/api/v1/exchange"

    def test_exchange_list_response_format(self) -> None:
        """测试交易所列表响应格式。"""
        from services.api.app.routes.exchange import _success, _error

        success = _success({"items": []}, {"action": "test"})
        assert success["data"] is not None
        assert success["error"] is None

        error = _error("test_code", "test message", {"action": "test"})
        assert error["data"] is None
        assert error["error"]["code"] == "test_code"