"""评分系统单元测试。

测试因子计算、评分服务和策略集成。
"""

from __future__ import annotations

import pytest
from decimal import Decimal

from services.api.app.services.scoring.factors import (
    RSIFactor,
    MACDFactor,
    VolumeFactor,
    VolatilityFactor,
    TrendFactor,
    MomentumFactor,
    create_factor,
)
from services.api.app.services.scoring.scoring_service import (
    scoring_service,
    ScoringConfig,
)


class TestRSIFactor:
    """RSI因子测试。"""

    def test_oversold_zone_high_score(self) -> None:
        """超卖区应该返回高分。"""
        factor = RSIFactor()
        # RSI=25，超卖区，预期高分
        score = factor.calculate({"rsi": 25})
        assert score > 0.8
        assert 0 <= score <= 1

    def test_overbought_zone_low_score(self) -> None:
        """超买区应该返回低分。"""
        factor = RSIFactor()
        # RSI=75，超买区，预期低分
        score = factor.calculate({"rsi": 75})
        assert score < 0.3
        assert 0 <= score <= 1

    def test_neutral_zone_medium_score(self) -> None:
        """中性区应该返回中等分。"""
        factor = RSIFactor()
        # RSI=50，中性
        score = factor.calculate({"rsi": 50})
        assert 0.4 <= score <= 0.6

    def test_missing_data_returns_neutral(self) -> None:
        """缺少数据时返回中性值。"""
        factor = RSIFactor()
        score = factor.calculate({})
        assert score == 0.5

    def test_invalid_rsi_returns_neutral(self) -> None:
        """无效RSI值返回中性值。"""
        factor = RSIFactor()
        score = factor.calculate({"rsi": -10})
        assert score == 0.5
        score = factor.calculate({"rsi": 150})
        assert score == 0.5


class TestMACDFactor:
    """MACD因子测试。"""

    def test_golden_cross_high_score(self) -> None:
        """金叉状态应该返回高分。"""
        factor = MACDFactor()
        # MACD线高于信号线，柱状图为正
        score = factor.calculate({
            "macd": {
                "macd": 0.5,
                "signal": 0.3,
                "histogram": 0.2,
            }
        })
        assert score > 0.7

    def test_death_cross_low_score(self) -> None:
        """死叉状态应该返回低分。"""
        factor = MACDFactor()
        # MACD线低于信号线，柱状图为负
        score = factor.calculate({
            "macd": {
                "macd": -0.5,
                "signal": 0.3,
                "histogram": -0.8,
            }
        })
        assert score < 0.3

    def test_missing_data_returns_neutral(self) -> None:
        """缺少数据时返回中性值。"""
        factor = MACDFactor()
        score = factor.calculate({})
        assert score == 0.5


class TestVolumeFactor:
    """成交量因子测试。"""

    def test_high_volume_high_score(self) -> None:
        """放量应该返回高分。"""
        factor = VolumeFactor()
        # 当前成交量是平均的2.5倍
        score = factor.calculate({
            "volume": {
                "current": 2500,
                "average": 1000,
            }
        })
        assert score > 0.7

    def test_low_volume_low_score(self) -> None:
        """缩量应该返回低分。"""
        factor = VolumeFactor()
        # 当前成交量是平均的0.3倍
        score = factor.calculate({
            "volume": {
                "current": 300,
                "average": 1000,
            }
        })
        assert score < 0.3

    def test_normal_volume_medium_score(self) -> None:
        """正常成交量返回中等分。"""
        factor = VolumeFactor()
        score = factor.calculate({
            "volume": {
                "current": 1000,
                "average": 1000,
            }
        })
        assert 0.4 <= score <= 0.6


class TestVolatilityFactor:
    """波动率因子测试。"""

    def test_optimal_volatility_high_score(self) -> None:
        """适中波动率应该返回高分。"""
        factor = VolatilityFactor()
        # 波动率在最优区间中心
        score = factor.calculate({"volatility": 0.05})
        assert score > 0.8

    def test_low_volatility_low_score(self) -> None:
        """过低波动率返回低分。"""
        factor = VolatilityFactor()
        score = factor.calculate({"volatility": 0.005})
        assert score < 0.4

    def test_high_volatility_low_score(self) -> None:
        """过高波动率返回低分。"""
        factor = VolatilityFactor()
        score = factor.calculate({"volatility": 0.15})
        assert score < 0.5


class TestScoringService:
    """评分服务测试。"""

    def test_calculate_score_basic(self) -> None:
        """基本评分计算。"""
        result = scoring_service.calculate_score(
            "BTC/USDT",
            {
                "rsi": 30,
                "macd": {"macd": 0.5, "signal": 0.3, "histogram": 0.2},
                "volume": {"current": 2000, "average": 1000},
                "volatility": 0.05,
                "momentum": 5,
            }
        )
        assert result.symbol == "BTC/USDT"
        assert 0 <= result.total_score <= 1
        assert len(result.factors) > 0
        assert result.threshold > 0

    def test_threshold_check(self) -> None:
        """阈值检查。"""
        # 设置阈值为0.7
        scoring_service.set_min_entry_score(0.7)

        # 低评分应该不通过阈值
        result = scoring_service.calculate_score("TEST/USDT", {"rsi": 70})
        assert not result.passed_threshold

        # 检查阈值设置生效
        result = scoring_service.calculate_score("TEST2/USDT", {"rsi": 20, "momentum": 10})
        assert result.threshold == 0.7

    def test_factor_weights_update(self) -> None:
        """因子权重更新。"""
        success = scoring_service.set_factor_weights({"rsi": 2.0, "macd": 0.5})
        assert success

        weights = scoring_service.get_factor_weights()
        assert weights["weights"]["rsi"] == 2.0
        assert weights["weights"]["macd"] == 0.5

    def test_enable_disable_factor(self) -> None:
        """启用/禁用因子。"""
        # 禁用因子
        scoring_service.disable_factor("momentum")
        weights = scoring_service.get_factor_weights()
        assert "momentum" not in weights["enabled_factors"]

        # 启用因子
        scoring_service.enable_factor("momentum")
        weights = scoring_service.get_factor_weights()
        assert "momentum" in weights["enabled_factors"]

    def test_score_history(self) -> None:
        """评分历史记录。"""
        symbol = "HIST/USDT"
        # 计算多次评分
        for i in range(5):
            scoring_service.calculate_score(symbol, {"rsi": 30 + i * 5})

        history = scoring_service.get_score_history(symbol, limit=3)
        assert len(history) <= 3


class TestCreateFactor:
    """因子创建工厂测试。"""

    def test_create_rsi_factor(self) -> None:
        """创建RSI因子。"""
        factor = create_factor("rsi", weight=2.0)
        assert factor is not None
        assert factor.name == "rsi"
        assert factor.weight == 2.0

    def test_create_unknown_factor(self) -> None:
        """创建未知因子返回None。"""
        factor = create_factor("unknown")
        assert factor is None

    def test_create_all_factor_types(self) -> None:
        """创建所有支持的因子类型。"""
        types = ["rsi", "macd", "volume", "volatility", "trend", "momentum"]
        for t in types:
            factor = create_factor(t)
            assert factor is not None
            assert factor.name == t


class TestScoringConfig:
    """评分配置测试。"""

    def test_config_to_dict(self) -> None:
        """配置序列化。"""
        config = ScoringConfig(
            min_entry_score=0.65,
            factor_weights={"rsi": 1.5, "macd": 1.0},
            enabled_factors=["rsi", "macd"],
        )
        data = config.to_dict()
        assert data["min_entry_score"] == 0.65
        assert "rsi" in data["factor_weights"]
        assert "rsi" in data["enabled_factors"]

    def test_config_from_dict(self) -> None:
        """配置反序列化。"""
        data = {
            "min_entry_score": 0.70,
            "factor_weights": {"rsi": 2.0},
            "enabled_factors": ["rsi", "volume"],
        }
        config = ScoringConfig.from_dict(data)
        assert config.min_entry_score == 0.70
        assert config.factor_weights["rsi"] == 2.0
        assert len(config.enabled_factors) == 2
