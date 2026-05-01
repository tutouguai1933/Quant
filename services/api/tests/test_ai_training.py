"""AI训练数据收集API测试。

测试训练数据收集服务的API端点。
"""

from __future__ import annotations

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.api.app.routes.ai_training import (
    router,
    _success,
    _error,
    _unauthorized,
)
from services.api.app.services.ai.training_data_service import (
    TrainingDataService,
    TrainingSample,
    State,
    MarketState,
    IndicatorState,
    PositionState,
    TimeState,
    ActionType,
    Action,
    ActionLabel,
    Outcome,
    SampleMetadata,
)


class HelperFunctionsTests(unittest.TestCase):
    """辅助函数测试。"""

    def test_success_response(self) -> None:
        """测试成功响应格式。"""
        result = _success({"key": "value"}, {"source": "test"})
        self.assertEqual(result["data"]["key"], "value")
        self.assertIsNone(result["error"])
        self.assertEqual(result["meta"]["source"], "test")

    def test_error_response(self) -> None:
        """测试错误响应格式。"""
        result = _error("test_error", "测试错误消息", {"detail": "info"})
        self.assertIsNone(result["data"])
        self.assertEqual(result["error"]["code"], "test_error")
        self.assertEqual(result["error"]["message"], "测试错误消息")
        self.assertEqual(result["meta"]["detail"], "info")

    def test_unauthorized_response(self) -> None:
        """测试未授权响应格式。"""
        result = _unauthorized()
        self.assertIsNone(result["data"])
        self.assertEqual(result["error"]["code"], "unauthorized")
        self.assertIn("登录", result["error"]["message"])


class DataClassTests(unittest.TestCase):
    """数据类测试。"""

    def test_market_state_to_dict(self) -> None:
        """测试市场状态序列化。"""
        state = MarketState(
            volatility_regime=0.5,
            trend_strength=0.8,
            volume_profile=0.3,
            price_position=0.7,
        )
        d = state.to_dict()
        self.assertEqual(d["volatility_regime"], 0.5)
        self.assertEqual(d["trend_strength"], 0.8)
        self.assertEqual(d["volume_profile"], 0.3)
        self.assertEqual(d["price_position"], 0.7)

    def test_market_state_to_array(self) -> None:
        """测试市场状态数组转换。"""
        state = MarketState(
            volatility_regime=0.5,
            trend_strength=0.8,
            volume_profile=0.3,
            price_position=0.7,
        )
        arr = state.to_array()
        self.assertEqual(len(arr), 4)
        self.assertEqual(arr, [0.5, 0.8, 0.3, 0.7])

    def test_indicator_state_to_dict(self) -> None:
        """测试指标状态序列化。"""
        state = IndicatorState(
            rsi=70.0,
            macd_signal=0.5,
            bb_position=0.8,
            ma_distance=0.1,
        )
        d = state.to_dict()
        self.assertEqual(d["rsi"], 70.0)
        self.assertEqual(d["macd_signal"], 0.5)
        self.assertEqual(d["bb_position"], 0.8)
        self.assertEqual(d["ma_distance"], 0.1)

    def test_indicator_state_to_array(self) -> None:
        """测试指标状态数组转换（RSI应归一化）。"""
        state = IndicatorState(
            rsi=50.0,
            macd_signal=0.25,
            bb_position=0.75,
            ma_distance=0.1,
        )
        arr = state.to_array()
        self.assertEqual(len(arr), 4)
        self.assertEqual(arr[0], 0.5)  # RSI归一化
        self.assertEqual(arr[1], 0.25)
        self.assertEqual(arr[2], 0.75)
        self.assertEqual(arr[3], 0.1)

    def test_position_state_to_dict(self) -> None:
        """测试持仓状态序列化。"""
        state = PositionState(
            has_position=True,
            position_duration=10,
            unrealized_pnl_pct=0.05,
            entry_distance_pct=0.02,
        )
        d = state.to_dict()
        self.assertTrue(d["has_position"])
        self.assertEqual(d["position_duration"], 10)
        self.assertEqual(d["unrealized_pnl_pct"], 0.05)
        self.assertEqual(d["entry_distance_pct"], 0.02)

    def test_position_state_to_array(self) -> None:
        """测试持仓状态数组转换。"""
        state = PositionState(
            has_position=True,
            position_duration=50,
            unrealized_pnl_pct=0.05,
            entry_distance_pct=0.02,
        )
        arr = state.to_array()
        self.assertEqual(len(arr), 4)
        self.assertEqual(arr[0], 1.0)  # has_position
        self.assertEqual(arr[1], 0.5)  # 归一化的duration
        self.assertEqual(arr[2], 0.05)
        self.assertEqual(arr[3], 0.02)

    def test_time_state_to_dict(self) -> None:
        """测试时间状态序列化。"""
        state = TimeState(
            hour_of_day=14,
            day_of_week=2,
            is_trading_hours=True,
        )
        d = state.to_dict()
        self.assertEqual(d["hour_of_day"], 14)
        self.assertEqual(d["day_of_week"], 2)
        self.assertTrue(d["is_trading_hours"])

    def test_time_state_to_array(self) -> None:
        """测试时间状态数组转换（归一化）。"""
        state = TimeState(
            hour_of_day=12,
            day_of_week=3,
            is_trading_hours=True,
        )
        arr = state.to_array()
        self.assertEqual(len(arr), 3)
        self.assertEqual(arr[0], 12 / 24.0)  # hour归一化
        self.assertEqual(arr[1], 3 / 7.0)    # day归一化
        self.assertEqual(arr[2], 1.0)        # is_trading_hours

    def test_state_to_dict(self) -> None:
        """测试完整状态序列化。"""
        state = State(
            market=MarketState(volatility_regime=0.5),
            indicators=IndicatorState(rsi=60.0),
            position=PositionState(has_position=True),
            time=TimeState(hour_of_day=10),
        )
        d = state.to_dict()
        self.assertIn("market", d)
        self.assertIn("indicators", d)
        self.assertIn("position", d)
        self.assertIn("time", d)

    def test_state_to_array(self) -> None:
        """测试完整状态数组转换。"""
        state = State(
            market=MarketState(volatility_regime=0.5, trend_strength=0.3, volume_profile=0.2, price_position=0.8),
            indicators=IndicatorState(rsi=50.0, macd_signal=0.0, bb_position=0.5, ma_distance=0.0),
            position=PositionState(has_position=False, position_duration=0, unrealized_pnl_pct=0.0, entry_distance_pct=0.0),
            time=TimeState(hour_of_day=0, day_of_week=0, is_trading_hours=True),
        )
        arr = state.to_array()
        self.assertEqual(len(arr), 4 + 4 + 4 + 3)  # 15维

    def test_action_to_dict(self) -> None:
        """测试动作序列化。"""
        action = Action(
            type=ActionType.OPEN_LONG,
            size_pct=0.8,
            stop_loss_pct=0.02,
            take_profit_pct=0.05,
        )
        d = action.to_dict()
        self.assertEqual(d["type"], "open_long")
        self.assertEqual(d["params"]["size_pct"], 0.8)
        self.assertEqual(d["params"]["stop_loss_pct"], 0.02)
        self.assertEqual(d["params"]["take_profit_pct"], 0.05)

    def test_action_label_to_dict(self) -> None:
        """测试动作标签序列化。"""
        label = ActionLabel(
            optimal_action=Action(type=ActionType.HOLD),
            action_confidence=0.8,
            alternative_actions=[Action(type=ActionType.OPEN_LONG)],
        )
        d = label.to_dict()
        self.assertEqual(d["optimal_action"]["type"], "hold")
        self.assertEqual(d["action_confidence"], 0.8)
        self.assertEqual(len(d["alternative_actions"]), 1)

    def test_outcome_to_dict(self) -> None:
        """测试结果序列化。"""
        outcome = Outcome(
            actual_pnl=0.05,
            holding_period=10,
            max_drawdown=0.02,
            market_context="bullish",
        )
        d = outcome.to_dict()
        self.assertEqual(d["actual_pnl"], 0.05)
        self.assertEqual(d["holding_period"], 10)
        self.assertEqual(d["max_drawdown"], 0.02)
        self.assertEqual(d["market_context"], "bullish")

    def test_sample_metadata_to_dict(self) -> None:
        """测试样本元数据序列化。"""
        metadata = SampleMetadata(
            source_strategy="trend",
            data_quality=0.9,
            noise_level=0.1,
        )
        d = metadata.to_dict()
        self.assertEqual(d["source_strategy"], "trend")
        self.assertEqual(d["data_quality"], 0.9)
        self.assertEqual(d["noise_level"], 0.1)

    def test_training_sample_to_dict(self) -> None:
        """测试训练样本序列化。"""
        sample = TrainingSample(
            timestamp=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            symbol="BTCUSDT",
            state=State(
                market=MarketState(),
                indicators=IndicatorState(),
                position=PositionState(),
                time=TimeState(),
            ),
            metadata=SampleMetadata(source_strategy="test"),
        )
        d = sample.to_dict()
        self.assertIn("timestamp", d)
        self.assertEqual(d["symbol"], "BTCUSDT")
        self.assertIn("state", d)
        self.assertIsNone(d["label"])
        self.assertIsNone(d["outcome"])


class TrainingDataServiceTests(unittest.TestCase):
    """训练数据服务测试。"""

    def setUp(self) -> None:
        """每个测试前重置服务状态。"""
        self.service = TrainingDataService()
        self.service.clear_samples()

    def test_extract_state_empty_candles(self) -> None:
        """测试空K线数据提取状态。"""
        state = self.service.extract_state([])
        self.assertIsInstance(state, State)
        self.assertIsInstance(state.market, MarketState)
        self.assertIsInstance(state.indicators, IndicatorState)

    def test_extract_state_with_candles(self) -> None:
        """测试有K线数据时提取状态。"""
        candles = _create_candles(count=30)
        state = self.service.extract_state(candles)
        self.assertIsInstance(state, State)
        self.assertGreater(state.market.volatility_regime, 0)

    def test_extract_state_with_indicators(self) -> None:
        """测试带指标的状态提取。"""
        candles = _create_candles(count=30)
        indicators = {
            "rsi": 70.0,
            "macd": {"signal": 0.5},
            "bb_position": 0.8,
            "ma_distance": 0.02,
        }
        state = self.service.extract_state(candles, indicators=indicators)
        self.assertEqual(state.indicators.rsi, 70.0)
        self.assertEqual(state.indicators.macd_signal, 0.5)
        self.assertEqual(state.indicators.bb_position, 0.8)
        self.assertEqual(state.indicators.ma_distance, 0.02)

    def test_extract_state_with_position_info(self) -> None:
        """测试带持仓信息的状态提取。"""
        candles = _create_candles(count=30)
        position_info = {
            "has_position": True,
            "position_duration": 10,
            "unrealized_pnl_pct": 0.05,
            "entry_distance_pct": 0.02,
        }
        state = self.service.extract_state(candles, position_info=position_info)
        self.assertTrue(state.position.has_position)
        self.assertEqual(state.position.position_duration, 10)
        self.assertEqual(state.position.unrealized_pnl_pct, 0.05)

    def test_collect_sample(self) -> None:
        """测试样本收集。"""
        candles = _create_candles(count=30)
        sample = self.service.collect_sample(
            symbol="BTCUSDT",
            candles=candles,
            source_strategy="test_strategy",
        )
        self.assertEqual(sample.symbol, "BTCUSDT")
        self.assertEqual(sample.metadata.source_strategy, "test_strategy")
        self.assertEqual(self.service.get_sample_count(), 1)
        self.assertEqual(self.service.get_sample_count("BTCUSDT"), 1)

    def test_collect_sample_normalizes_symbol(self) -> None:
        """测试样本收集时符号标准化。"""
        candles = _create_candles(count=30)
        sample = self.service.collect_sample(
            symbol="  btcusdt  ",
            candles=candles,
        )
        self.assertEqual(sample.symbol, "BTCUSDT")

    def test_get_statistics(self) -> None:
        """测试获取统计信息。"""
        candles = _create_candles(count=30)
        self.service.collect_sample(symbol="BTCUSDT", candles=candles)
        self.service.collect_sample(symbol="ETHUSDT", candles=candles)

        stats = self.service.get_statistics()
        self.assertEqual(stats["total_samples"], 2)
        self.assertIn("BTCUSDT", stats["symbols"])
        self.assertIn("ETHUSDT", stats["symbols"])

    def test_clear_samples_all(self) -> None:
        """测试清空所有样本。"""
        candles = _create_candles(count=30)
        self.service.collect_sample(symbol="BTCUSDT", candles=candles)
        self.service.collect_sample(symbol="ETHUSDT", candles=candles)

        cleared = self.service.clear_samples()
        self.assertEqual(cleared, 2)
        self.assertEqual(self.service.get_sample_count(), 0)

    def test_clear_samples_by_symbol(self) -> None:
        """测试按符号清空样本。"""
        candles = _create_candles(count=30)
        self.service.collect_sample(symbol="BTCUSDT", candles=candles)
        self.service.collect_sample(symbol="ETHUSDT", candles=candles)

        cleared = self.service.clear_samples("BTCUSDT")
        self.assertEqual(cleared, 1)
        self.assertEqual(self.service.get_sample_count(), 1)
        self.assertEqual(self.service.get_sample_count("BTCUSDT"), 0)
        self.assertEqual(self.service.get_sample_count("ETHUSDT"), 1)

    def test_export_dataset(self) -> None:
        """测试导出数据集。"""
        candles = _create_candles(count=30)
        self.service.collect_sample(symbol="BTCUSDT", candles=candles)

        filepath = self.service.export_dataset()
        self.assertTrue(filepath.endswith(".json"))

    def test_estimate_data_quality(self) -> None:
        """测试数据质量估计。"""
        candles = _create_candles(count=30)
        quality = self.service._estimate_data_quality(candles)
        self.assertGreater(quality, 0.8)  # 完整数据应高质量

    def test_estimate_data_quality_empty(self) -> None:
        """测试空数据质量估计。"""
        quality = self.service._estimate_data_quality([])
        self.assertEqual(quality, 0.0)

    def test_estimate_noise_level(self) -> None:
        """测试噪声水平估计。"""
        candles = _create_candles(count=30)
        noise = self.service._estimate_noise_level(candles)
        self.assertGreaterEqual(noise, 0.0)
        self.assertLessEqual(noise, 1.0)

    def test_estimate_noise_level_insufficient(self) -> None:
        """测试数据不足时噪声估计。"""
        candles = _create_candles(count=3)
        noise = self.service._estimate_noise_level(candles)
        self.assertEqual(noise, 0.0)


class RouterDefinitionTests(unittest.TestCase):
    """路由定义测试。"""

    def test_router_prefix(self) -> None:
        """测试路由前缀。"""
        self.assertEqual(router.prefix, "/api/v1/ai/training")

    def test_router_tags(self) -> None:
        """测试路由标签。"""
        self.assertIn("ai-training", router.tags)


def _create_candles(count: int = 30, base_price: float = 100.0) -> list[dict[str, object]]:
    """创建测试K线数据。"""
    candles: list[dict[str, object]] = []
    for i in range(count):
        price = base_price + i * 0.5
        candles.append({
            "open_time": i * 60000,
            "open": price - 1,  # 使用数值类型
            "high": price + 2,
            "low": price - 2,
            "close": price,
            "volume": 100,
            "close_time": i * 60000 + 59999,
            "timestamp": datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        })
    return candles


if __name__ == "__main__":
    unittest.main()