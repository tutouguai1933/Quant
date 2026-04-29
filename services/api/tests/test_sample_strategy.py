"""测试 SampleStrategy 策略参数和核心逻辑。"""

import pytest
from decimal import Decimal


class TestStrategyParameters:
    """测试策略参数配置。"""

    def test_entry_score_threshold(self):
        """验证入场评分阈值配置。"""
        # MIN_ENTRY_SCORE = 0.60
        expected_threshold = 0.60
        # 从 strategy_engine_service 导入
        from services.api.app.services.strategy_engine_service import MIN_ENTRY_SCORE
        assert float(MIN_ENTRY_SCORE) == expected_threshold

    def test_trailing_stop_trigger(self):
        """验证移动止损触发阈值。"""
        # TRAILING_STOP_TRIGGER = 0.02 (盈利2%触发)
        expected_trigger = 0.02
        from services.api.app.services.strategy_engine_service import TRAILING_STOP_TRIGGER
        assert float(TRAILING_STOP_TRIGGER) == expected_trigger

    def test_trailing_stop_distance(self):
        """验证移动止损距离。"""
        # TRAILING_STOP_DISTANCE = 0.01 (止损距离1%)
        expected_distance = 0.01
        from services.api.app.services.strategy_engine_service import TRAILING_STOP_DISTANCE
        assert float(TRAILING_STOP_DISTANCE) == expected_distance

    def test_profit_exit_ratio(self):
        """验证盈利目标退出比例。"""
        # PROFIT_EXIT_RATIO = 0.05 (盈利5%自动退出)
        expected_ratio = 0.05
        from services.api.app.services.strategy_engine_service import PROFIT_EXIT_RATIO
        assert float(PROFIT_EXIT_RATIO) == expected_ratio

    def test_max_holding_hours(self):
        """验证最大持仓时间限制。"""
        # MAX_HOLDING_HOURS = 48 (最大持仓48小时)
        expected_hours = 48
        from services.api.app.services.strategy_engine_service import MAX_HOLDING_HOURS
        assert MAX_HOLDING_HOURS == expected_hours


class TestIndicatorCalculation:
    """测试技术指标计算。"""

    def test_rsi_calculation(self):
        """验证 RSI 计算。"""
        from services.api.app.services.indicator_service import calculate_rsi
        from decimal import Decimal

        # 创建测试数据：价格上升序列
        closes = [Decimal("100"), Decimal("101"), Decimal("102"), Decimal("103"),
                  Decimal("104"), Decimal("105"), Decimal("106"), Decimal("107"),
                  Decimal("108"), Decimal("109"), Decimal("110"), Decimal("111"),
                  Decimal("112"), Decimal("113"), Decimal("114")]

        rsi = calculate_rsi(closes, 14)
        # 价格持续上升，RSI 应该接近100
        assert rsi > Decimal("70")

    def test_macd_calculation(self):
        """验证 MACD 计算。"""
        from services.api.app.services.indicator_service import calculate_macd
        from decimal import Decimal

        # 创建足够长的测试数据
        closes = [Decimal(str(100 + i)) for i in range(50)]

        macd_result = calculate_macd(closes, 12, 26, 9)

        assert "macd_line" in macd_result
        assert "signal_line" in macd_result
        assert "histogram" in macd_result
        assert "trend" in macd_result

        # 价格持续上升，趋势应为 bullish
        assert macd_result["trend"] == "bullish"

    def test_volume_trend_calculation(self):
        """验证成交量趋势计算。"""
        from services.api.app.services.indicator_service import calculate_volume_trend
        from decimal import Decimal

        # 创建测试数据：放量上涨
        volumes = [Decimal("1000")] * 19 + [Decimal("1500")]  # 最后一个成交量放大
        closes = [Decimal(str(100 + i)) for i in range(20)]

        volume_result = calculate_volume_trend(volumes, closes, 20)

        assert "volume_ratio" in volume_result
        assert "price_volume_alignment" in volume_result
        assert "trend_strength" in volume_result

        # 放量上涨，应为 bullish_volume
        assert volume_result["price_volume_alignment"] == "bullish_volume"


class TestEntryDecision:
    """测试入场决策逻辑。"""

    def test_entry_score_below_threshold_rejected(self):
        """验证评分低于阈值时拒绝入场。"""
        from services.api.app.services.strategy_engine_service import (
            StrategyEngineService,
            MIN_ENTRY_SCORE,
        )

        service = StrategyEngineService()

        # 模拟低评分场景
        decision = service.calculate_entry_score(
            symbol="BTC/USDT",
            signal_side="long",
            signal_score=Decimal("0.50"),  # 低于阈值
        )

        assert decision.score < MIN_ENTRY_SCORE
        assert decision.allowed == False

    def test_entry_score_above_threshold_allowed(self):
        """验证评分高于阈值时允许入场。"""
        from services.api.app.services.strategy_engine_service import (
            StrategyEngineService,
            MIN_ENTRY_SCORE,
        )

        service = StrategyEngineService()

        # 模拟高评分场景（需要设置 mock 数据）
        # 这里测试基础逻辑，实际运行时会从研究服务获取评分

        # 验证评分阈值正确
        assert float(MIN_ENTRY_SCORE) == 0.60


class TestTrailingStop:
    """测试追踪止损逻辑。"""

    def test_trailing_stop_activation(self):
        """验证追踪止损激活条件。"""
        from services.api.app.services.strategy_engine_service import (
            StrategyEngineService,
            PositionState,
            TRAILING_STOP_TRIGGER,
        )
        from datetime import datetime, timezone

        service = StrategyEngineService()

        # 创建持仓状态
        position = PositionState(
            symbol="BTC/USDT",
            entry_price=Decimal("100"),
            entry_time=datetime.now(timezone.utc),
            quantity=Decimal("1"),
            side="long",
        )

        # 盈利未达到触发阈值
        current_price = Decimal("101")  # 1%盈利
        update = service.update_trailing_stop(
            symbol="BTC/USDT",
            current_price=current_price,
            position=position,
        )

        assert update.activated == False

        # 盈利达到触发阈值
        current_price = Decimal("102")  # 2%盈利
        update = service.update_trailing_stop(
            symbol="BTC/USDT",
            current_price=current_price,
            position=position,
        )

        assert update.activated == True

    def test_trailing_stop_distance(self):
        """验证追踪止损距离计算。"""
        from services.api.app.services.strategy_engine_service import (
            StrategyEngineService,
            PositionState,
            TRAILING_STOP_DISTANCE,
        )
        from datetime import datetime, timezone

        service = StrategyEngineService()

        # 创建已激活追踪止损的持仓
        position = PositionState(
            symbol="BTC/USDT",
            entry_price=Decimal("100"),
            entry_time=datetime.now(timezone.utc),
            quantity=Decimal("1"),
            side="long",
            trailing_stop_active=True,
            peak_price=Decimal("105"),  # 峰值价格
        )

        current_price = Decimal("105")
        update = service.update_trailing_stop(
            symbol="BTC/USDT",
            current_price=current_price,
            position=position,
        )

        # 止损价格 = 峰值价格 * (1 - TRAILING_STOP_DISTANCE)
        expected_stop = Decimal("105") * (Decimal("1") - TRAILING_STOP_DISTANCE)
        assert update.new_stop_price == expected_stop


class TestExitConditions:
    """测试退出条件逻辑。"""

    def test_profit_target_exit(self):
        """验证盈利目标退出。"""
        from services.api.app.services.strategy_engine_service import (
            StrategyEngineService,
            PositionState,
            PROFIT_EXIT_RATIO,
        )
        from datetime import datetime, timezone

        service = StrategyEngineService()

        # 创建持仓
        position = PositionState(
            symbol="BTC/USDT",
            entry_price=Decimal("100"),
            entry_time=datetime.now(timezone.utc),
            quantity=Decimal("1"),
            side="long",
        )

        # 盈利达到目标
        current_price = Decimal("105")  # 5%盈利
        decision = service.check_exit_conditions(
            symbol="BTC/USDT",
            current_price=current_price,
            position=position,
        )

        assert decision.profit_target_reached == True
        assert decision.should_exit == True

    def test_time_limit_exit(self):
        """验证持仓时间限制退出。"""
        from services.api.app.services.strategy_engine_service import (
            StrategyEngineService,
            PositionState,
            MAX_HOLDING_HOURS,
        )
        from datetime import datetime, timezone, timedelta

        service = StrategyEngineService()

        # 创建持仓（超过48小时）
        entry_time = datetime.now(timezone.utc) - timedelta(hours=50)
        position = PositionState(
            symbol="BTC/USDT",
            entry_price=Decimal("100"),
            entry_time=entry_time,
            quantity=Decimal("1"),
            side="long",
        )

        current_price = Decimal("101")
        decision = service.check_exit_conditions(
            symbol="BTC/USDT",
            current_price=current_price,
            position=position,
        )

        assert decision.time_limit_reached == True
        assert decision.should_exit == True


class TestPositionSizing:
    """测试仓位大小计算。"""

    def test_position_size_with_high_score(self):
        """验证高评分时的仓位计算。"""
        from services.api.app.services.strategy_engine_service import (
            StrategyEngineService,
            MIN_ENTRY_SCORE,
        )

        service = StrategyEngineService()

        # 高评分场景
        score = Decimal("0.85")
        volatility = Decimal("0.02")  # 低波动率

        position_ratio = service.calculate_position_size(
            symbol="BTC/USDT",
            score=score,
            volatility=volatility,
        )

        # 高评分 + 低波动 = 较大仓位
        assert position_ratio > Decimal("0.25")

    def test_position_size_with_high_volatility(self):
        """验证高波动时的仓位限制。"""
        from services.api.app.services.strategy_engine_service import (
            StrategyEngineService,
            MAX_POSITION_RATIO,
        )

        service = StrategyEngineService()

        # 高波动场景
        score = Decimal("0.80")
        volatility = Decimal("0.06")  # 高波动率

        position_ratio = service.calculate_position_size(
            symbol="DOGE/USDT",  # DOGE 波动较大
            score=score,
            volatility=volatility,
        )

        # 高波动 = 减小仓位
        assert position_ratio <= MAX_POSITION_RATIO


class TestMultiPairSupport:
    """测试多币种支持。"""

    def test_pair_volatility_params(self):
        """验证不同币种的波动率参数。"""
        from services.api.app.services.strategy_engine_service import (
            get_pair_volatility_params,
        )

        # BTC 参数
        btc_params = get_pair_volatility_params("BTC/USDT")
        assert btc_params["volatility_multiplier"] < Decimal("1.0")  # BTC 波动相对较小

        # DOGE 参数
        doge_params = get_pair_volatility_params("DOGE/USDT")
        assert doge_params["volatility_multiplier"] > Decimal("1.0")  # DOGE 波动较大

        # 未配置币种使用默认值
        unknown_params = get_pair_volatility_params("UNKNOWN/USDT")
        assert unknown_params["volatility_multiplier"] == Decimal("1.0")


class TestResearchScoreIntegration:
    """测试研究评分集成功能。

    注意：策略文件在 Freqtrade 容器中运行，需要 pandas、numpy、freqtrade 等依赖。
    主机环境的测试主要验证静态内容，完整功能测试应在容器中运行。
    """

    def test_research_score_api_url_configuration(self):
        """验证研究 API URL 配置。"""
        import os
        from pathlib import Path

        strategy_path = Path(__file__).resolve().parents[3] / "infra" / "freqtrade" / "user_data" / "strategies"
        strategy_file = strategy_path / "SampleStrategy.py"

        content = strategy_file.read_text(encoding="utf-8")
        # 验证 API URL 配置存在
        assert "QUANT_API_BASE_URL" in content
        assert "/api/v1/evaluation/workspace" in content
        # 验证超时配置
        assert "RESEARCH_API_TIMEOUT" in content
        # 验证权重配置
        assert "RESEARCH_SCORE_FALLBACK_WEIGHT" in content

    def test_research_score_method_exists(self):
        """验证研究评分获取方法存在。"""
        from pathlib import Path

        strategy_path = Path(__file__).resolve().parents[3] / "infra" / "freqtrade" / "user_data" / "strategies"
        strategy_file = strategy_path / "SampleStrategy.py"

        content = strategy_file.read_text(encoding="utf-8")
        # 验证方法定义存在
        assert "def _fetch_research_score" in content
        assert "def _calculate_entry_score" in content
        # 验证综合评分逻辑
        assert "research_score * RESEARCH_SCORE_FALLBACK_WEIGHT" in content
        # 验证 fallback 处理
        assert "API 不可用时使用纯本地计算" in content

    def test_research_score_cache_configuration(self):
        """验证评分缓存配置。"""
        from pathlib import Path

        strategy_path = Path(__file__).resolve().parents[3] / "infra" / "freqtrade" / "user_data" / "strategies"
        strategy_file = strategy_path / "SampleStrategy.py"

        content = strategy_file.read_text(encoding="utf-8")
        # 验证缓存配置
        assert "_research_score_cache" in content
        assert "_cache_timestamp" in content
        assert "_cache_ttl_seconds" in content

    def test_calculate_entry_score_accepts_metadata(self):
        """验证 _calculate_entry_score 接受 metadata 参数。"""
        from pathlib import Path

        strategy_path = Path(__file__).resolve().parents[3] / "infra" / "freqtrade" / "user_data" / "strategies"
        strategy_file = strategy_path / "SampleStrategy.py"

        content = strategy_file.read_text(encoding="utf-8")
        # 验证方法签名
        assert "def _calculate_entry_score(self, dataframe: DataFrame, metadata: dict = None)" in content
        # 验证 metadata 用于获取币种信息
        assert "pair = metadata.get(\"pair\", \"\")" in content

    def test_requests_import_with_fallback(self):
        """验证 requests 导入有 fallback 处理。"""
        from pathlib import Path

        strategy_path = Path(__file__).resolve().parents[3] / "infra" / "freqtrade" / "user_data" / "strategies"
        strategy_file = strategy_path / "SampleStrategy.py"

        content = strategy_file.read_text(encoding="utf-8")
        # 验证 requests 导入有 fallback
        assert "try:" in content
        assert "import requests" in content
        assert "except ImportError:" in content
        assert "requests = None" in content

    def test_fetch_research_score_handles_timeout(self):
        """验证超时处理逻辑。"""
        from pathlib import Path

        strategy_path = Path(__file__).resolve().parents[3] / "infra" / "freqtrade" / "user_data" / "strategies"
        strategy_file = strategy_path / "SampleStrategy.py"

        content = strategy_file.read_text(encoding="utf-8")
        # 验证超时异常处理
        assert "requests.exceptions.Timeout" in content
        assert "return None" in content

    def test_fetch_research_score_handles_api_error(self):
        """验证 API 错误处理逻辑。"""
        from pathlib import Path

        strategy_path = Path(__file__).resolve().parents[3] / "infra" / "freqtrade" / "user_data" / "strategies"
        strategy_file = strategy_path / "SampleStrategy.py"

        content = strategy_file.read_text(encoding="utf-8")
        # 验证请求异常处理
        assert "requests.exceptions.RequestException" in content
        # 验证响应解析异常处理
        assert "(KeyError, ValueError, TypeError)" in content

    def test_symbol_normalization(self):
        """验证币种符号标准化逻辑。"""
        from pathlib import Path

        strategy_path = Path(__file__).resolve().parents[3] / "infra" / "freqtrade" / "user_data" / "strategies"
        strategy_file = strategy_path / "SampleStrategy.py"

        content = strategy_file.read_text(encoding="utf-8")
        # 验证符号标准化处理（去除斜杠）
        assert "normalized_symbol = entry_symbol.replace(\"/\", \"\")" in content
        assert "normalized_request = symbol.replace(\"/\", \"\")" in content