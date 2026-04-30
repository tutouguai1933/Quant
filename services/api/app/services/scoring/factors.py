"""多因子加权评分模型，用于优化入场决策。

每个因子独立计算评分（0-1范围），然后通过加权平均得到综合评分。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any


@dataclass(slots=True)
class FactorBase(ABC):
    """因子基类：定义因子计算接口和通用属性。"""

    name: str
    weight: float = 1.0
    description: str = ""

    @abstractmethod
    def calculate(self, data: dict[str, Any]) -> float:
        """计算因子值（0-1范围）。

        Args:
            data: 包含市场数据的字典，如K线、指标等

        Returns:
            float: 0-1范围的评分值
        """
        pass

    def to_dict(self) -> dict[str, Any]:
        """返回因子配置信息。"""
        return {
            "name": self.name,
            "weight": self.weight,
            "description": self.description,
        }


@dataclass(slots=True)
class RSIFactor(FactorBase):
    """RSI因子：超卖区(30以下)得高分，超买区(70以上)得低分。

    评分逻辑：
    - RSI <= 30: 评分接近1（强烈超卖，买入信号）
    - RSI >= 70: 评分接近0（强烈超买，不建议买入）
    - RSI在50附近: 评分中等
    """

    name: str = "rsi"
    weight: float = 1.0
    description: str = "RSI超卖因子：RSI<=30时高分"
    oversold_threshold: float = 30.0
    overbought_threshold: float = 70.0

    def calculate(self, data: dict[str, Any]) -> float:
        rsi_value = self._parse_rsi(data.get("rsi"))
        if rsi_value is None:
            return 0.5  # 无数据时返回中性值

        if rsi_value <= self.oversold_threshold:
            # 超卖区：线性映射30->1, 0->1
            return 1.0 - (rsi_value / self.oversold_threshold) * 0.2
        elif rsi_value >= self.overbought_threshold:
            # 超买区：线性映射70->0.3, 100->0
            # 超买不应买入，得分应低
            excess = rsi_value - self.overbought_threshold
            return max(0.0, 0.3 - (excess / 30.0) * 0.3)
        else:
            # 中性区：50为中心，线性映射
            deviation = abs(rsi_value - 50.0) / 20.0
            if rsi_value < 50:
                return 0.5 + deviation * 0.5
            else:
                return 0.5 - deviation * 0.3

    def _parse_rsi(self, value: Any) -> float | None:
        try:
            parsed = float(Decimal(str(value)))
            return parsed if 0 <= parsed <= 100 else None
        except (TypeError, ValueError, InvalidOperation):
            return None

    def to_dict(self) -> dict[str, Any]:
        base_dict = FactorBase.to_dict(self)
        return {
            **base_dict,
            "oversold_threshold": self.oversold_threshold,
            "overbought_threshold": self.overbought_threshold,
        }


@dataclass(slots=True)
class MACDFactor(FactorBase):
    """MACD因子：金叉状态得高分，死叉状态得低分。

    评分逻辑：
    - MACD线上穿信号线（金叉）: 高分
    - MACD线下穿信号线（死叉）: 低分
    - MACD柱状图为正且增长: 中高分
    - MACD柱状图为负且增长: 中低分
    """

    name: str = "macd"
    weight: float = 1.0
    description: str = "MACD因子：金叉状态得高分"

    def calculate(self, data: dict[str, Any]) -> float:
        macd_data = data.get("macd", {})
        if not isinstance(macd_data, dict):
            return 0.5

        macd_line = self._parse_decimal(macd_data.get("macd"))
        signal_line = self._parse_decimal(macd_data.get("signal"))
        histogram = self._parse_decimal(macd_data.get("histogram"))

        if macd_line is None or signal_line is None:
            return 0.5

        diff = macd_line - signal_line

        # 金叉/死叉判断
        if diff > 0:
            # MACD线在信号线上方
            if histogram is not None and histogram > 0:
                # 金叉并柱状图增长
                return min(1.0, 0.7 + float(abs(histogram)) * 0.3)
            else:
                # 保持在上方但可能减弱
                return 0.6
        elif diff < 0:
            # MACD线在信号线下方
            if histogram is not None and histogram < 0:
                # 死叉并柱状图下降
                return max(0.0, 0.3 - float(abs(histogram)) * 0.3)
            else:
                # 保持在下方但可能反转
                return 0.4
        else:
            return 0.5

    def _parse_decimal(self, value: Any) -> Decimal | None:
        try:
            return Decimal(str(value))
        except (TypeError, ValueError, InvalidOperation):
            return None


@dataclass(slots=True)
class VolumeFactor(FactorBase):
    """成交量因子：放量突破得高分，缩量得低分。

    评分逻辑：
    - 当前成交量显著高于平均（放量）: 高分
    - 当前成交量显著低于平均（缩量）: 低分
    - 放量突破往往预示趋势启动
    """

    name: str = "volume"
    weight: float = 0.8
    description: str = "成交量因子：放量突破得高分"
    volume_ratio_high: float = 2.0
    volume_ratio_low: float = 0.5

    def calculate(self, data: dict[str, Any]) -> float:
        volume_data = data.get("volume", {})
        if not isinstance(volume_data, dict):
            return 0.5

        current_volume = self._parse_float(volume_data.get("current"))
        avg_volume = self._parse_float(volume_data.get("average"))

        if current_volume is None or avg_volume is None or avg_volume <= 0:
            return 0.5

        volume_ratio = current_volume / avg_volume

        if volume_ratio >= self.volume_ratio_high:
            # 显著放量
            return min(1.0, 0.7 + (volume_ratio - self.volume_ratio_high) * 0.1)
        elif volume_ratio <= self.volume_ratio_low:
            # 显著缩量
            return max(0.0, 0.3 - (self.volume_ratio_low - volume_ratio) * 0.2)
        else:
            # 正常区间
            if volume_ratio > 1.0:
                return 0.5 + (volume_ratio - 1.0) * 0.2
            else:
                return 0.5 - (1.0 - volume_ratio) * 0.2

    def _parse_float(self, value: Any) -> float | None:
        try:
            parsed = float(Decimal(str(value)))
            return parsed if parsed > 0 else None
        except (TypeError, ValueError, InvalidOperation):
            return None

    def to_dict(self) -> dict[str, Any]:
        base_dict = FactorBase.to_dict(self)
        return {
            **base_dict,
            "volume_ratio_high": self.volume_ratio_high,
            "volume_ratio_low": self.volume_ratio_low,
        }


@dataclass(slots=True)
class VolatilityFactor(FactorBase):
    """波动率因子：适中波动得高分，极端波动得低分。

    评分逻辑：
    - 波动率适中（既不过于平稳也不过于剧烈）: 高分
    - 波动率过低（市场缺乏动力）: 低分
    - 波动率过高（风险过大）: 低分
    """

    name: str = "volatility"
    weight: float = 0.6
    description: str = "波动率因子：适中波动得高分"
    optimal_range_low: float = 0.02
    optimal_range_high: float = 0.08

    def calculate(self, data: dict[str, Any]) -> float:
        volatility = self._parse_float(data.get("volatility"))
        if volatility is None:
            return 0.5

        # 波动率在最优区间内
        if self.optimal_range_low <= volatility <= self.optimal_range_high:
            # 在最优区间中心得最高分
            center = (self.optimal_range_low + self.optimal_range_high) / 2
            deviation = abs(volatility - center) / (self.optimal_range_high - center)
            return 1.0 - deviation * 0.3

        # 波动率过低
        if volatility < self.optimal_range_low:
            return max(0.0, volatility / self.optimal_range_low * 0.4)

        # 波动率过高
        excess_ratio = (volatility - self.optimal_range_high) / self.optimal_range_high
        return max(0.0, 0.7 - excess_ratio * 0.5)

    def _parse_float(self, value: Any) -> float | None:
        try:
            parsed = float(Decimal(str(value)))
            return parsed if parsed >= 0 else None
        except (TypeError, ValueError, InvalidOperation):
            return None

    def to_dict(self) -> dict[str, Any]:
        base_dict = FactorBase.to_dict(self)
        return {
            **base_dict,
            "optimal_range_low": self.optimal_range_low,
            "optimal_range_high": self.optimal_range_high,
        }


@dataclass(slots=True)
class TrendFactor(FactorBase):
    """趋势因子：上升趋势得高分，下降趋势得低分。

    评分逻辑：
    - 价格位于趋势线上方: 高分
    - 价格位于趋势线下方: 低分
    - 趋势斜率正: 加分
    - 趋势斜率负: 减分
    """

    name: str = "trend"
    weight: float = 1.2
    description: str = "趋势因子：上升趋势得高分"

    def calculate(self, data: dict[str, Any]) -> float:
        trend_data = data.get("trend", {})
        if not isinstance(trend_data, dict):
            return 0.5

        price_vs_trend = self._parse_float(trend_data.get("price_vs_trend"))
        slope = self._parse_float(trend_data.get("slope"))

        base_score = 0.5

        if price_vs_trend is not None:
            if price_vs_trend > 0:
                base_score += min(0.3, price_vs_trend * 0.1)
            else:
                base_score -= min(0.3, abs(price_vs_trend) * 0.1)

        if slope is not None:
            if slope > 0:
                base_score += min(0.2, slope * 0.1)
            else:
                base_score -= min(0.2, abs(slope) * 0.1)

        return max(0.0, min(1.0, base_score))

    def _parse_float(self, value: Any) -> float | None:
        try:
            return float(Decimal(str(value)))
        except (TypeError, ValueError, InvalidOperation):
            return None


@dataclass(slots=True)
class MomentumFactor(FactorBase):
    """动量因子：正动量得高分，负动量得低分。

    评分逻辑：
    - 价格变化率（ROC）为正: 高分
    - 价格变化率为负: 低分
    - 动量加速: 加分
    """

    name: str = "momentum"
    weight: float = 0.8
    description: str = "动量因子：正动量得高分"

    def calculate(self, data: dict[str, Any]) -> float:
        momentum = self._parse_float(data.get("momentum"))
        roc = self._parse_float(data.get("roc"))

        if momentum is None and roc is None:
            return 0.5

        base_score = 0.5

        if momentum is not None:
            # 动量值映射到评分
            normalized_momentum = momentum / 100.0
            base_score += min(0.3, normalized_momentum)

        if roc is not None:
            # ROC值映射到评分（ROC通常在±10%范围）
            normalized_roc = roc / 20.0
            base_score += min(0.2, max(-0.2, normalized_roc))

        return max(0.0, min(1.0, base_score))

    def _parse_float(self, value: Any) -> float | None:
        try:
            return float(Decimal(str(value)))
        except (TypeError, ValueError, InvalidOperation):
            return None


# 默认因子列表
DEFAULT_FACTORS: list[FactorBase] = [
    RSIFactor(weight=1.0),
    MACDFactor(weight=1.0),
    VolumeFactor(weight=0.8),
    VolatilityFactor(weight=0.6),
    TrendFactor(weight=1.2),
    MomentumFactor(weight=0.8),
]


def create_factor(factor_type: str, weight: float = 1.0, **kwargs) -> FactorBase | None:
    """根据类型创建因子实例。

    Args:
        factor_type: 因子类型名称
        weight: 因子权重
        **kwargs: 因子配置参数

    Returns:
        FactorBase: 因子实例，如果类型不支持则返回None
    """
    factor_map = {
        "rsi": RSIFactor,
        "macd": MACDFactor,
        "volume": VolumeFactor,
        "volatility": VolatilityFactor,
        "trend": TrendFactor,
        "momentum": MomentumFactor,
    }

    factor_class = factor_map.get(factor_type.lower())
    if factor_class is None:
        return None

    return factor_class(weight=weight, **kwargs)