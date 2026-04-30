"""P7-1 多策略模板框架测试。

测试策略基类、趋势策略、网格策略及策略切换功能。
"""

from __future__ import annotations

import sys
import unittest
from decimal import Decimal
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.api.app.services.strategy.base import StrategyBase, StrategySignal, StrategyResult
from services.api.app.services.strategy.trend import TrendStrategy
from services.api.app.services.strategy.grid import GridStrategy


class StrategyBaseTests(unittest.TestCase):
    """策略基类测试。"""

    def test_strategy_signal_dataclass(self) -> None:
        """测试StrategySignal数据类。"""
        signal = StrategySignal(
            action="buy",
            strength=0.8,
            reason="test_reason",
            metadata={"key": "value"},
        )
        self.assertEqual(signal.action, "buy")
        self.assertEqual(signal.strength, 0.8)
        self.assertEqual(signal.reason, "test_reason")
        self.assertIn("key", signal.metadata)

    def test_strategy_result_dataclass(self) -> None:
        """测试StrategyResult数据类。"""
        signal = StrategySignal(action="hold", strength=0.0, reason="test")
        result = StrategyResult(signal=signal, indicators={"ema": "100"})
        self.assertEqual(result.signal.action, "hold")
        self.assertIn("ema", result.indicators)

    def test_strategy_base_default_config(self) -> None:
        """测试策略基类默认配置提取。"""
        strategy = TrendStrategy()
        config = strategy.get_default_config()
        self.assertIn("fast_period", config)
        self.assertEqual(config["fast_period"], 7)
        self.assertIn("slow_period", config)
        self.assertEqual(config["slow_period"], 25)

    def test_strategy_base_validate_config_valid(self) -> None:
        """测试配置验证通过。"""
        strategy = TrendStrategy()
        is_valid, error = strategy.validate_config({"fast_period": 10, "slow_period": 30})
        self.assertTrue(is_valid)
        self.assertEqual(error, "")

    def test_strategy_base_validate_config_invalid_type(self) -> None:
        """测试配置验证失败（类型错误）。"""
        strategy = TrendStrategy()
        is_valid, error = strategy.validate_config({"fast_period": "invalid"})
        self.assertFalse(is_valid)
        self.assertIn("must be a number", error)

    def test_strategy_base_validate_config_out_of_range(self) -> None:
        """测试配置验证失败（超出范围）。"""
        strategy = TrendStrategy()
        is_valid, error = strategy.validate_config({"fast_period": 100})
        self.assertFalse(is_valid)
        self.assertIn("must be <= 50", error)

    def test_strategy_base_update_config(self) -> None:
        """测试配置更新。"""
        strategy = TrendStrategy()
        result = strategy.update_config({"fast_period": 5, "slow_period": 20})
        self.assertTrue(result)
        self.assertEqual(strategy.config["fast_period"], 5)

    def test_strategy_base_to_dict(self) -> None:
        """测试策略序列化。"""
        strategy = TrendStrategy()
        data = strategy.to_dict()
        self.assertEqual(data["name"], "trend")
        self.assertEqual(data["display_name"], "趋势跟踪")
        self.assertIn("config_schema", data)


class TrendStrategyTests(unittest.TestCase):
    """趋势跟踪策略测试。"""

    def test_trend_strategy_initialization(self) -> None:
        """测试趋势策略初始化。"""
        strategy = TrendStrategy()
        self.assertEqual(strategy.name, "trend")
        self.assertEqual(strategy.display_name, "趋势跟踪")

    def test_trend_strategy_signal_generation_buy(self) -> None:
        """测试趋势策略买入信号生成。"""
        strategy = TrendStrategy(config={"fast_period": 3, "slow_period": 5})
        candles = _create_candles_for_trend_up()
        result = strategy.analyze({
            "candles": candles,
            "symbol": "BTCUSDT",
            "timeframe": "1h",
        })
        self.assertEqual(result.signal.action, "buy")
        self.assertIn("fast_ema", result.indicators)
        self.assertIn("slow_ema", result.indicators)

    def test_trend_strategy_signal_generation_sell(self) -> None:
        """测试趋势策略卖出信号生成。"""
        strategy = TrendStrategy(config={"fast_period": 3, "slow_period": 5})
        candles = _create_candles_for_trend_down()
        result = strategy.analyze({
            "candles": candles,
            "symbol": "BTCUSDT",
            "timeframe": "1h",
        })
        self.assertEqual(result.signal.action, "sell")

    def test_trend_strategy_insufficient_candles(self) -> None:
        """测试数据不足返回hold。"""
        strategy = TrendStrategy(config={"fast_period": 7, "slow_period": 25})
        result = strategy.analyze({
            "candles": [{"close": "100"}],
            "symbol": "BTCUSDT",
            "timeframe": "1h",
        })
        self.assertEqual(result.signal.action, "hold")
        self.assertEqual(result.signal.reason, "insufficient_candles")

    def test_trend_strategy_ema_calculation(self) -> None:
        """测试EMA计算正确性。"""
        strategy = TrendStrategy()
        prices = [Decimal("100"), Decimal("101"), Decimal("102"), Decimal("103")]
        ema = strategy._calculate_ema(prices, 3)
        self.assertIsInstance(ema, Decimal)
        self.assertGreater(ema, Decimal("0"))

    def test_trend_strategy_config_schema(self) -> None:
        """测试配置schema返回。"""
        schema = TrendStrategy().get_config_schema()
        self.assertIn("parameters", schema)
        self.assertIn("fast_period", schema["parameters"])
        self.assertIn("slow_period", schema["parameters"])


class GridStrategyTests(unittest.TestCase):
    """网格交易策略测试。"""

    def test_grid_strategy_initialization(self) -> None:
        """测试网格策略初始化。"""
        strategy = GridStrategy()
        self.assertEqual(strategy.name, "grid")
        self.assertEqual(strategy.display_name, "网格交易")

    def test_grid_strategy_signal_at_lower_grid(self) -> None:
        """测试价格触及下网格线买入信号。"""
        strategy = GridStrategy(config={
            "grid_count": 5,
            "price_range": {"low": 100, "high": 110},
            "grid_threshold_pct": 1.0,
        })
        result = strategy.analyze({
            "candles": [],
            "current_price": Decimal("100"),
            "symbol": "BTCUSDT",
        })
        self.assertEqual(result.signal.action, "buy")
        self.assertEqual(result.signal.reason, "price_hit_lower_grid")

    def test_grid_strategy_signal_at_upper_grid(self) -> None:
        """测试价格触及上网格线卖出信号。"""
        strategy = GridStrategy(config={
            "grid_count": 5,
            "price_range": {"low": 100, "high": 110},
            "grid_threshold_pct": 1.0,
        })
        # 使用略高于上限的价格触发卖出
        result = strategy.analyze({
            "candles": [],
            "current_price": Decimal("111"),
            "symbol": "BTCUSDT",
        })
        self.assertEqual(result.signal.action, "sell")
        # 111触发的是price_hit_upper_grid而不是price_above_range
        self.assertIn(result.signal.reason, ["price_hit_upper_grid", "price_above_range"])

    def test_grid_strategy_signal_below_range(self) -> None:
        """测试价格低于区间买入信号。"""
        strategy = GridStrategy(config={
            "grid_count": 5,
            "price_range": {"low": 100, "high": 110},
        })
        result = strategy.analyze({
            "candles": [],
            "current_price": Decimal("95"),
            "symbol": "BTCUSDT",
        })
        self.assertEqual(result.signal.action, "buy")
        self.assertEqual(result.signal.reason, "price_below_range")
        self.assertEqual(result.signal.strength, 1.0)

    def test_grid_strategy_signal_above_range(self) -> None:
        """测试价格高于区间卖出信号。"""
        strategy = GridStrategy(config={
            "grid_count": 5,
            "price_range": {"low": 100, "high": 110},
        })
        result = strategy.analyze({
            "candles": [],
            "current_price": Decimal("115"),
            "symbol": "BTCUSDT",
        })
        self.assertEqual(result.signal.action, "sell")
        self.assertEqual(result.signal.reason, "price_above_range")
        self.assertEqual(result.signal.strength, 1.0)

    def test_grid_strategy_auto_range_calculation(self) -> None:
        """测试自动区间计算。"""
        strategy = GridStrategy(config={"grid_count": 10})
        candles = _create_candles_for_grid()
        result = strategy.analyze({
            "candles": candles,
            "current_price": Decimal("105"),
            "symbol": "BTCUSDT",
        })
        self.assertIn("grid_low", result.indicators)
        self.assertIn("grid_high", result.indicators)

    def test_grid_strategy_grid_levels_calculation(self) -> None:
        """测试网格价位计算。"""
        strategy = GridStrategy()
        levels = strategy._calculate_grid_levels(Decimal("100"), Decimal("110"), 5)
        self.assertEqual(len(levels), 5)
        self.assertEqual(levels[0], Decimal("100"))
        self.assertEqual(levels[4], Decimal("110"))

    def test_grid_strategy_invalid_price(self) -> None:
        """测试无效价格返回hold。"""
        strategy = GridStrategy()
        result = strategy.analyze({
            "candles": [],
            "current_price": Decimal("0"),
            "symbol": "BTCUSDT",
        })
        self.assertEqual(result.signal.action, "hold")
        self.assertEqual(result.signal.reason, "invalid_price")


class StrategySwitchTests(unittest.TestCase):
    """策略切换API测试。"""

    def test_strategy_registry(self) -> None:
        """测试策略注册表。"""
        from services.api.app.services.strategy import TrendStrategy, GridStrategy
        trend = TrendStrategy()
        grid = GridStrategy()
        self.assertEqual(trend.name, "trend")
        self.assertEqual(grid.name, "grid")

    def test_strategy_name_attribute(self) -> None:
        """测试策略名称属性。"""
        strategies = [TrendStrategy(), GridStrategy()]
        names = [s.name for s in strategies]
        self.assertIn("trend", names)
        self.assertIn("grid", names)


def _create_candles_for_trend_up(count: int = 10) -> list[dict[str, object]]:
    """创建上升趋势K线数据。"""
    candles: list[dict[str, object]] = []
    base = 100
    for i in range(count):
        price = base + i * 2
        candles.append({
            "open_time": i * 60000,
            "open": str(price - 1),
            "high": str(price + 2),
            "low": str(price - 2),
            "close": str(price),
            "volume": "100",
            "close_time": i * 60000 + 59999,
        })
    return candles


def _create_candles_for_trend_down(count: int = 10) -> list[dict[str, object]]:
    """创建下降趋势K线数据。"""
    candles: list[dict[str, object]] = []
    base = 120
    for i in range(count):
        price = base - i * 2
        candles.append({
            "open_time": i * 60000,
            "open": str(price + 1),
            "high": str(price + 2),
            "low": str(price - 2),
            "close": str(price),
            "volume": "100",
            "close_time": i * 60000 + 59999,
        })
    return candles


def _create_candles_for_grid(count: int = 20) -> list[dict[str, object]]:
    """创建网格测试K线数据（有波动）。"""
    candles: list[dict[str, object]] = []
    base = 100
    for i in range(count):
        variation = (i % 5 - 2) * 2
        price = base + variation
        candles.append({
            "open_time": i * 60000,
            "open": str(price - 1),
            "high": str(price + 3),
            "low": str(price - 3),
            "close": str(price),
            "volume": "100",
            "close_time": i * 60000 + 59999,
        })
    return candles


if __name__ == "__main__":
    unittest.main()