"""波动率服务和动态止损服务单元测试。"""

from __future__ import annotations

import unittest
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

from services.api.app.services.volatility_service import (
    VolatilityService,
    VolatilityConfig,
    VolatilityResult,
)
from services.api.app.services.dynamic_stoploss_service import (
    DynamicStoplossService,
    StoplossConfig,
    PositionStoplossState,
    StoplossAdjustmentResult,
)


class TestVolatilityService(unittest.TestCase):
    """波动率服务测试。"""

    def setUp(self):
        self.mock_market_client = MagicMock()
        self.config = VolatilityConfig(atr_period=14, std_period=20, cache_ttl_seconds=300)
        self.service = VolatilityService(
            config=self.config,
            market_client=self.mock_market_client,
        )

    def test_calculate_atr_basic(self):
        """测试ATR基本计算。"""
        ohlcv = [
            {"high": Decimal("100"), "low": Decimal("90"), "close": Decimal("95")},
            {"high": Decimal("105"), "low": Decimal("92"), "close": Decimal("100")},
            {"high": Decimal("110"), "low": Decimal("98"), "close": Decimal("105")},
            {"high": Decimal("108"), "low": Decimal("100"), "close": Decimal("104")},
            {"high": Decimal("112"), "low": Decimal("102"), "close": Decimal("108")},
        ]
        atr = self.service.calculate_atr(ohlcv, period=3)
        self.assertIsInstance(atr, Decimal)
        self.assertGreater(atr, Decimal("0"))

    def test_calculate_atr_insufficient_data(self):
        """测试数据不足时ATR返回0。"""
        ohlcv = [{"high": 100, "low": 90, "close": 95}]
        atr = self.service.calculate_atr(ohlcv, period=14)
        self.assertEqual(atr, Decimal("0"))

    def test_calculate_std_basic(self):
        """测试标准差基本计算。"""
        prices = [Decimal("100"), Decimal("102"), Decimal("98"), Decimal("101"), Decimal("99")]
        std = self.service.calculate_std(prices, period=5)
        self.assertIsInstance(std, Decimal)
        self.assertGreater(std, Decimal("0"))

    def test_calculate_std_insufficient_data(self):
        """测试数据不足时标准差返回0。"""
        prices = [Decimal("100")]
        std = self.service.calculate_std(prices, period=20)
        self.assertEqual(std, Decimal("0"))

    def test_calculate_stoploss_normal_volatility(self):
        """测试正常波动率时止损计算。"""
        stoploss_service = DynamicStoplossService()
        result = stoploss_service.calculate_stoploss("BTCUSDT", Decimal("1.0"))
        base_stoploss = Decimal("-0.10")
        self.assertEqual(result, base_stoploss)

    def test_calculate_stoploss_high_volatility(self):
        """测试高波动率时止损放宽。"""
        stoploss_service = DynamicStoplossService()
        result = stoploss_service.calculate_stoploss("BTCUSDT", Decimal("2.0"))
        base_stoploss = Decimal("-0.10")
        self.assertLess(result, base_stoploss)

    def test_calculate_stoploss_low_volatility(self):
        """测试低波动率时止损收紧。"""
        stoploss_service = DynamicStoplossService()
        result = stoploss_service.calculate_stoploss("BTCUSDT", Decimal("0.5"))
        base_stoploss = Decimal("-0.10")
        self.assertGreater(result, base_stoploss)

    def test_calculate_stoploss_respects_bounds(self):
        """测试止损计算遵守边界限制。"""
        config = StoplossConfig(
            base_stoploss=Decimal("-0.10"),
            min_stoploss=Decimal("-0.05"),
            max_stoploss=Decimal("-0.15"),
        )
        stoploss_service = DynamicStoplossService(config=config)

        # 高波动率测试 - 应该触发max_stoploss边界
        # factor=3.0时调整约 0.03*(3.0-1)=0.06, 结果约-0.16, 应被clamp到-0.15
        result_high = stoploss_service.calculate_stoploss("BTCUSDT", Decimal("3.0"))
        self.assertEqual(result_high, config.max_stoploss)

        # 正常波动率 - 应返回基础止损
        result_normal = stoploss_service.calculate_stoploss("BTCUSDT", Decimal("1.0"))
        self.assertEqual(result_normal, config.base_stoploss)

    def test_empty_result_structure(self):
        """测试空结果数据结构。"""
        now = datetime.now(timezone.utc)
        result = self.service._empty_result("TEST", now)
        self.assertEqual(result.symbol, "TEST")
        self.assertEqual(result.atr, Decimal("0"))
        self.assertEqual(result.volatility_factor, Decimal("1.0"))


class TestDynamicStoplossService(unittest.TestCase):
    """动态止损服务测试。"""

    def setUp(self):
        self.config = StoplossConfig(
            base_stoploss=Decimal("-0.10"),
            min_stoploss=Decimal("-0.05"),
            max_stoploss=Decimal("-0.15"),
            high_volatility_threshold=Decimal("1.5"),
            low_volatility_threshold=Decimal("0.7"),
            adjustment_interval_minutes=30,
            throttle_min_change_pct=Decimal("0.02"),
        )
        self.mock_volatility_svc = MagicMock()
        self.mock_volatility_svc.get_volatility_factor.return_value = Decimal("1.0")
        self.service = DynamicStoplossService(
            config=self.config,
            volatility_svc=self.mock_volatility_svc,
        )

    def test_register_position(self):
        """测试持仓注册。"""
        state = self.service.register_position(
            symbol="BTCUSDT",
            position_id="pos-1",
            entry_price=Decimal("50000"),
            current_price=Decimal("51000"),
        )
        self.assertEqual(state.symbol, "BTCUSDT")
        self.assertEqual(state.position_id, "pos-1")
        self.assertEqual(state.entry_price, Decimal("50000"))

    def test_unregister_position(self):
        """测试持仓移除。"""
        self.service.register_position(
            symbol="BTCUSDT",
            position_id="pos-1",
            entry_price=Decimal("50000"),
            current_price=Decimal("51000"),
        )
        removed = self.service.unregister_position("pos-1")
        self.assertTrue(removed)
        removed_again = self.service.unregister_position("pos-1")
        self.assertFalse(removed_again)

    def test_get_position_state(self):
        """测试获取持仓状态。"""
        self.service.register_position(
            symbol="BTCUSDT",
            position_id="pos-1",
            entry_price=Decimal("50000"),
            current_price=Decimal("51000"),
        )
        state = self.service.get_position_state("pos-1")
        self.assertIsNotNone(state)
        self.assertEqual(state.symbol, "BTCUSDT")

    def test_adjust_trade_stoploss_position_not_found(self):
        """测试调整不存在持仓的止损。"""
        result = self.service.adjust_trade_stoploss("nonexistent")
        self.assertFalse(result.success)
        self.assertIn("position_not_found", result.reason)

    def test_adjust_trade_stoploss_throttled_by_interval(self):
        """测试调整间隔节流。"""
        now = datetime.now(timezone.utc)
        state = PositionStoplossState(
            symbol="BTCUSDT",
            position_id="pos-1",
            current_stoploss=Decimal("-0.10"),
            entry_price=Decimal("50000"),
            current_price=Decimal("51000"),
            volatility_factor=Decimal("1.0"),
            last_adjusted_at=now,
            adjustment_count=0,
        )
        self.service._position_states["pos-1"] = state

        result = self.service.adjust_trade_stoploss("pos-1", force=False)
        self.assertFalse(result.success)
        self.assertIn("throttled", result.reason)

    def test_adjust_trade_stoploss_forced(self):
        """测试强制调整止损。"""
        now = datetime.now(timezone.utc) - timedelta(minutes=60)
        state = PositionStoplossState(
            symbol="BTCUSDT",
            position_id="pos-1",
            current_stoploss=Decimal("-0.10"),
            entry_price=Decimal("50000"),
            current_price=Decimal("51000"),
            volatility_factor=Decimal("1.0"),
            last_adjusted_at=now,
            adjustment_count=0,
        )
        self.service._position_states["pos-1"] = state
        self.mock_volatility_svc.get_volatility_factor.return_value = Decimal("2.0")

        result = self.service.adjust_trade_stoploss("pos-1", force=True)
        self.assertTrue(result.success)
        self.assertEqual(state.adjustment_count, 1)

    def test_get_config(self):
        """测试获取配置。"""
        config = self.service.get_config()
        self.assertEqual(config["base_stoploss"], "-0.10")
        self.assertEqual(config["min_stoploss"], "-0.05")
        self.assertEqual(config["max_stoploss"], "-0.15")

    def test_update_config(self):
        """测试更新配置。"""
        updates = {"base_stoploss": "-0.08", "adjustment_interval_minutes": 60}
        updated = self.service.update_config(updates)
        self.assertEqual(updated["base_stoploss"], "-0.08")
        self.assertEqual(updated["adjustment_interval_minutes"], 60)

    def test_adjust_all_positions(self):
        """测试批量调整所有持仓。"""
        self.service.register_position(
            symbol="BTCUSDT",
            position_id="pos-1",
            entry_price=Decimal("50000"),
            current_price=Decimal("51000"),
        )
        self.service.register_position(
            symbol="ETHUSDT",
            position_id="pos-2",
            entry_price=Decimal("3000"),
            current_price=Decimal("3100"),
        )

        results = self.service.adjust_all_positions(force=True)
        self.assertEqual(len(results), 2)


class TestVolatilityResult(unittest.TestCase):
    """波动率结果数据结构测试。"""

    def test_to_dict(self):
        """测试转换为字典。"""
        now = datetime.now(timezone.utc)
        result = VolatilityResult(
            symbol="BTCUSDT",
            atr=Decimal("500"),
            atr_percent=Decimal("1.0"),
            std=Decimal("300"),
            std_percent=Decimal("0.6"),
            volatility_factor=Decimal("1.2"),
            calculated_at=now,
            period_atr=14,
            period_std=20,
            data_points=100,
        )
        d = result.to_dict()
        self.assertEqual(d["symbol"], "BTCUSDT")
        self.assertEqual(d["atr"], "500")
        self.assertEqual(d["volatility_factor"], "1.2")


class TestPositionStoplossState(unittest.TestCase):
    """持仓止损状态数据结构测试。"""

    def test_to_dict(self):
        """测试转换为字典。"""
        now = datetime.now(timezone.utc)
        state = PositionStoplossState(
            symbol="BTCUSDT",
            position_id="pos-1",
            current_stoploss=Decimal("-0.10"),
            entry_price=Decimal("50000"),
            current_price=Decimal("51000"),
            volatility_factor=Decimal("1.0"),
            last_adjusted_at=now,
            adjustment_count=5,
        )
        d = state.to_dict()
        self.assertEqual(d["symbol"], "BTCUSDT")
        self.assertEqual(d["current_stoploss"], "-0.10")
        self.assertEqual(d["adjustment_count"], 5)


if __name__ == "__main__":
    unittest.main()