"""P7-2 动态止损机制测试。

测试ATR计算、动态止损计算、止损调整等功能。
"""

from __future__ import annotations

import sys
import unittest
from decimal import Decimal
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.api.app.services.dynamic_stoploss_service import (
    DynamicStoplossService,
    StoplossConfig,
    PositionStoplossState,
    StoplossAdjustmentResult,
)
from services.api.app.services.volatility_service import VolatilityService, VolatilityResult


class StoplossConfigTests(unittest.TestCase):
    """止损配置测试。"""

    def test_stoploss_config_defaults(self) -> None:
        """测试默认配置值。"""
        config = StoplossConfig()
        self.assertEqual(config.base_stoploss, Decimal("-0.10"))
        self.assertEqual(config.min_stoploss, Decimal("-0.05"))
        self.assertEqual(config.max_stoploss, Decimal("-0.15"))

    def test_stoploss_config_from_env(self) -> None:
        """测试从环境变量读取配置。"""
        config = StoplossConfig.from_env()
        self.assertIsInstance(config.base_stoploss, Decimal)
        self.assertIsInstance(config.min_stoploss, Decimal)
        self.assertIsInstance(config.max_stoploss, Decimal)


class DynamicStoplossTests(unittest.TestCase):
    """动态止损计算测试。"""

    def test_calculate_stoploss_normal_volatility(self) -> None:
        """测试正常波动率止损计算。"""
        service = DynamicStoplossService(config=StoplossConfig())
        stoploss = service.calculate_stoploss("BTCUSDT", volatility_factor=Decimal("1.0"))
        # 正常波动率应返回基础止损
        self.assertEqual(stoploss, Decimal("-0.10"))

    def test_calculate_stoploss_high_volatility(self) -> None:
        """测试高波动率放宽止损。"""
        config = StoplossConfig(
            base_stoploss=Decimal("-0.10"),
            max_stoploss=Decimal("-0.15"),
            high_volatility_threshold=Decimal("1.5"),
        )
        service = DynamicStoplossService(config=config)
        # 高波动率应放宽止损空间
        stoploss = service.calculate_stoploss("BTCUSDT", volatility_factor=Decimal("2.0"))
        self.assertLessEqual(stoploss, Decimal("-0.10"))
        self.assertGreaterEqual(stoploss, config.max_stoploss)

    def test_calculate_stoploss_low_volatility(self) -> None:
        """测试低波动率收紧止损。"""
        config = StoplossConfig(
            base_stoploss=Decimal("-0.10"),
            min_stoploss=Decimal("-0.05"),
            low_volatility_threshold=Decimal("0.7"),
        )
        service = DynamicStoplossService(config=config)
        # 低波动率应收紧止损
        stoploss = service.calculate_stoploss("BTCUSDT", volatility_factor=Decimal("0.5"))
        self.assertGreaterEqual(stoploss, Decimal("-0.10"))
        self.assertLessEqual(stoploss, config.min_stoploss)

    def test_calculate_stoploss_clamping(self) -> None:
        """测试止损范围限制。"""
        config = StoplossConfig(
            base_stoploss=Decimal("-0.10"),
            min_stoploss=Decimal("-0.05"),
            max_stoploss=Decimal("-0.15"),
        )
        service = DynamicStoplossService(config=config)
        # 极端波动率也应被限制在范围内
        stoploss = service.calculate_stoploss("BTCUSDT", volatility_factor=Decimal("5.0"))
        self.assertGreaterEqual(stoploss, config.max_stoploss)
        self.assertLessEqual(stoploss, config.min_stoploss)


class PositionStoplossStateTests(unittest.TestCase):
    """持仓止损状态测试。"""

    def test_position_state_creation(self) -> None:
        """测试持仓状态创建。"""
        state = PositionStoplossState(
            symbol="BTCUSDT",
            position_id="test-123",
            current_stoploss=Decimal("-0.10"),
            entry_price=Decimal("100000"),
            current_price=Decimal("105000"),
            volatility_factor=Decimal("1.0"),
            last_adjusted_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        )
        self.assertEqual(state.symbol, "BTCUSDT")
        self.assertEqual(state.position_id, "test-123")
        self.assertEqual(state.adjustment_count, 0)

    def test_position_state_to_dict(self) -> None:
        """测试持仓状态序列化。"""
        state = PositionStoplossState(
            symbol="BTCUSDT",
            position_id="test-123",
            current_stoploss=Decimal("-0.10"),
            entry_price=Decimal("100000"),
            current_price=Decimal("105000"),
            volatility_factor=Decimal("1.0"),
            last_adjusted_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        )
        data = state.to_dict()
        self.assertEqual(data["symbol"], "BTCUSDT")
        self.assertIn("current_stoploss", data)


class StoplossServiceTests(unittest.TestCase):
    """止损服务测试。"""

    def test_register_position(self) -> None:
        """测试注册持仓。"""
        service = DynamicStoplossService(config=StoplossConfig())
        state = service.register_position(
            symbol="BTCUSDT",
            position_id="test-123",
            entry_price=Decimal("100000"),
            current_price=Decimal("100000"),
        )
        self.assertEqual(state.symbol, "BTCUSDT")
        self.assertEqual(state.position_id, "test-123")

    def test_unregister_position(self) -> None:
        """测试移除持仓。"""
        service = DynamicStoplossService(config=StoplossConfig())
        service.register_position(
            symbol="BTCUSDT",
            position_id="test-123",
            entry_price=Decimal("100000"),
            current_price=Decimal("100000"),
        )
        removed = service.unregister_position("test-123")
        self.assertTrue(removed)

    def test_get_position_state(self) -> None:
        """测试获取持仓状态。"""
        service = DynamicStoplossService(config=StoplossConfig())
        service.register_position(
            symbol="BTCUSDT",
            position_id="test-123",
            entry_price=Decimal("100000"),
            current_price=Decimal("100000"),
        )
        state = service.get_position_state("test-123")
        self.assertIsNotNone(state)
        self.assertEqual(state.symbol, "BTCUSDT")

    def test_get_config(self) -> None:
        """测试获取配置。"""
        service = DynamicStoplossService(config=StoplossConfig())
        config = service.get_config()
        self.assertIn("base_stoploss", config)
        self.assertIn("min_stoploss", config)
        self.assertIn("max_stoploss", config)


class VolatilityServiceTests(unittest.TestCase):
    """波动率服务测试。"""

    def test_calculate_atr_basic(self) -> None:
        """测试ATR基本计算。"""
        service = VolatilityService()
        ohlcv = _create_ohlcv_data()
        atr = service.calculate_atr(ohlcv, period=5)
        self.assertIsInstance(atr, Decimal)
        self.assertGreater(atr, Decimal("0"))

    def test_calculate_std_basic(self) -> None:
        """测试标准差基本计算。"""
        service = VolatilityService()
        prices = [Decimal(str(100 + i)) for i in range(20)]
        std = service.calculate_std(prices, period=10)
        self.assertIsInstance(std, Decimal)

    def test_calculate_atr_insufficient_data(self) -> None:
        """测试数据不足时ATR返回0。"""
        service = VolatilityService()
        atr = service.calculate_atr([{"high": "100", "low": "99", "close": "100"}], period=14)
        self.assertEqual(atr, Decimal("0"))


def _create_ohlcv_data(count: int = 30) -> list[dict[str, object]]:
    """创建测试OHLCV数据。"""
    ohlcv: list[dict[str, object]] = []
    base = Decimal("100")
    for i in range(count):
        variation = Decimal(str((i % 5 - 2) * 2))
        ohlcv.append({
            "high": base + variation + Decimal("3"),
            "low": base + variation - Decimal("3"),
            "close": base + variation,
        })
    return ohlcv


if __name__ == "__main__":
    unittest.main()