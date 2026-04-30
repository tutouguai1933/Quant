"""自适应参数调整服务。

根据市场状态动态调整策略参数。
"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class MarketRegime(Enum):
    """市场状态枚举。"""
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    VOLATILE = "volatile"
    QUIET = "quiet"
    TRANSITION = "transition"


# 各市场状态的默认参数
DEFAULT_REGIME_PARAMS = {
    MarketRegime.TRENDING_UP: {
        "stop_loss_pct": 0.03,
        "take_profit_pct": 0.08,
        "entry_threshold": 0.65,
        "position_size_pct": 0.8,
        "lookback_bars": 30,
        "breakout_buffer_pct": 0.5,
    },
    MarketRegime.TRENDING_DOWN: {
        "stop_loss_pct": 0.03,
        "take_profit_pct": 0.08,
        "entry_threshold": 0.65,
        "position_size_pct": 0.6,  # 下跌趋势仓位更保守
        "lookback_bars": 30,
        "breakout_buffer_pct": 0.5,
    },
    MarketRegime.RANGING: {
        "stop_loss_pct": 0.02,
        "take_profit_pct": 0.03,
        "entry_threshold": 0.70,
        "position_size_pct": 0.5,
        "lookback_bars": 20,
        "breakout_buffer_pct": 1.0,  # 震荡需要更大突破缓冲
    },
    MarketRegime.VOLATILE: {
        "stop_loss_pct": 0.04,
        "take_profit_pct": 0.06,
        "entry_threshold": 0.75,
        "position_size_pct": 0.3,
        "lookback_bars": 15,  # 高波动使用更短周期
        "breakout_buffer_pct": 1.5,
    },
    MarketRegime.QUIET: {
        "stop_loss_pct": 0.02,
        "take_profit_pct": 0.04,
        "entry_threshold": 0.60,
        "position_size_pct": 0.6,
        "lookback_bars": 40,
        "breakout_buffer_pct": 0.3,
    },
    MarketRegime.TRANSITION: {
        "stop_loss_pct": 0.03,
        "take_profit_pct": 0.05,
        "entry_threshold": 0.70,
        "position_size_pct": 0.4,
        "lookback_bars": 25,
        "breakout_buffer_pct": 0.8,
    },
}

# 状态检测阈值
HIGH_VOL_THRESHOLD = 0.02      # 高波动阈值
TREND_THRESHOLD = 0.01         # 趋势强度阈值
RANGE_THRESHOLD = 0.005        # 区间判定阈值


@dataclass
class RegimeParams:
    """市场状态参数。"""

    stop_loss_pct: float = 0.03
    take_profit_pct: float = 0.05
    entry_threshold: float = 0.65
    position_size_pct: float = 0.5
    lookback_bars: int = 20
    breakout_buffer_pct: float = 0.5

    def to_dict(self) -> dict[str, Any]:
        return {
            "stop_loss_pct": self.stop_loss_pct,
            "take_profit_pct": self.take_profit_pct,
            "entry_threshold": self.entry_threshold,
            "position_size_pct": self.position_size_pct,
            "lookback_bars": self.lookback_bars,
            "breakout_buffer_pct": self.breakout_buffer_pct,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RegimeParams":
        return cls(
            stop_loss_pct=float(data.get("stop_loss_pct", 0.03)),
            take_profit_pct=float(data.get("take_profit_pct", 0.05)),
            entry_threshold=float(data.get("entry_threshold", 0.65)),
            position_size_pct=float(data.get("position_size_pct", 0.5)),
            lookback_bars=int(data.get("lookback_bars", 20)),
            breakout_buffer_pct=float(data.get("breakout_buffer_pct", 0.5)),
        )


@dataclass
class RegimeConfig:
    """自适应参数配置。"""

    transition_speed: float = 0.1           # 参数过渡速度
    min_observation_bars: int = 20          # 最小观察周期
    regime_detection_window: int = 50       # 状态检测窗口
    custom_params: dict[str, dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "transition_speed": self.transition_speed,
            "min_observation_bars": self.min_observation_bars,
            "regime_detection_window": self.regime_detection_window,
            "custom_params": dict(self.custom_params),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RegimeConfig":
        return cls(
            transition_speed=float(data.get("transition_speed", 0.1)),
            min_observation_bars=int(data.get("min_observation_bars", 20)),
            regime_detection_window=int(data.get("regime_detection_window", 50)),
            custom_params=dict(data.get("custom_params", {})),
        )


class AdaptiveParamsService:
    """自适应参数调整服务。

    功能：
    1. 识别市场状态
    2. 根据状态调整策略参数
    3. 参数平滑过渡
    4. 参数持久化
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self._config = RegimeConfig()
        if config:
            self._config = RegimeConfig.from_dict(config)

        self._regime_params: dict[MarketRegime, RegimeParams] = {}
        self._load_default_params()

        self._current_regime: MarketRegime = MarketRegime.TRANSITION
        self._current_params: RegimeParams = RegimeParams()
        self._regime_history: list[tuple[datetime, MarketRegime]] = []
        self._params_history: list[tuple[datetime, RegimeParams]] = []

        self._config_lock = threading.Lock()
        self._config_path: Path | None = None

    def set_config_path(self, path: str | Path) -> None:
        """设置配置持久化路径。"""
        self._config_path = Path(path)
        self._load_config()

    def _load_default_params(self) -> None:
        """加载默认参数。"""
        for regime, params in DEFAULT_REGIME_PARAMS.items():
            self._regime_params[regime] = RegimeParams.from_dict(params)

        # 加载自定义参数
        for regime_str, params in self._config.custom_params.items():
            try:
                regime = MarketRegime(regime_str)
                self._regime_params[regime] = RegimeParams.from_dict(params)
            except ValueError:
                logger.warning("未知的市场状态: %s", regime_str)

    def _load_config(self) -> None:
        """从文件加载配置。"""
        if self._config_path is None or not self._config_path.exists():
            return

        try:
            with open(self._config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            with self._config_lock:
                self._config = RegimeConfig.from_dict(data.get("adaptive_params", {}))
                # 加载自定义状态参数
                for regime_str, params in data.get("regime_params", {}).items():
                    try:
                        regime = MarketRegime(regime_str)
                        self._regime_params[regime] = RegimeParams.from_dict(params)
                    except ValueError:
                        pass
            logger.info("自适应参数配置已加载: %s", self._config_path)
        except Exception as e:
            logger.warning("加载自适应参数配置失败: %s", e)

    def _save_config(self) -> None:
        """保存配置到文件。"""
        if self._config_path is None:
            return

        try:
            data = {
                "adaptive_params": self._config.to_dict(),
                "regime_params": {
                    regime.value: params.to_dict()
                    for regime, params in self._regime_params.items()
                },
            }
            with open(self._config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            logger.info("自适应参数配置已保存: %s", self._config_path)
        except Exception as e:
            logger.warning("保存自适应参数配置失败: %s", e)

    def detect_market_regime(
        self,
        candles: list[dict[str, Any]],
        window: int | None = None,
    ) -> MarketRegime:
        """检测市场状态。

        Args:
            candles: K线数据列表
            window: 检测窗口大小

        Returns:
            MarketRegime: 当前市场状态
        """
        if window is None:
            window = self._config.regime_detection_window

        if len(candles) < self._config.min_observation_bars:
            return MarketRegime.TRANSITION

        recent_candles = candles[-window:] if len(candles) >= window else candles

        # 计算关键指标
        volatility = self._calculate_volatility(recent_candles)
        trend_strength, trend_direction = self._calculate_trend_strength(recent_candles)
        range_bound = self._calculate_range_bound(recent_candles)

        # 状态判定逻辑
        regime = self._classify_regime(volatility, trend_strength, trend_direction, range_bound)

        # 更新当前状态
        self._current_regime = regime
        self._regime_history.append((datetime.now(timezone.utc), regime))
        # 限制历史长度
        if len(self._regime_history) > 1000:
            self._regime_history = self._regime_history[-1000:]

        return regime

    def _calculate_volatility(self, candles: list[dict[str, Any]]) -> float:
        """计算波动率。"""
        if len(candles) < 2:
            return 0.0

        closes = []
        for c in candles:
            close = c.get("close")
            if close is not None:
                try:
                    closes.append(float(Decimal(str(close))))
                except (TypeError, ValueError, InvalidOperation):
                    pass

        if len(closes) < 2:
            return 0.0

        # 计算收益率
        returns = []
        for i in range(1, len(closes)):
            if closes[i-1] > 0:
                returns.append((closes[i] - closes[i-1]) / closes[i-1])

        if not returns:
            return 0.0

        # 计算标准差
        mean_return = sum(returns) / len(returns)
        variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
        volatility = variance ** 0.5

        return volatility

    def _calculate_trend_strength(
        self,
        candles: list[dict[str, Any]]
    ) -> tuple[float, float]:
        """计算趋势强度和方向。

        Returns:
            tuple[float, float]: (强度, 方向) 方向正值表示上升，负值表示下降
        """
        if len(candles) < 5:
            return (0.0, 0.0)

        closes = []
        for c in candles:
            close = c.get("close")
            if close is not None:
                try:
                    closes.append(float(Decimal(str(close))))
                except (TypeError, ValueError, InvalidOperation):
                    pass

        if len(closes) < 5:
            return (0.0, 0.0)

        # 计算线性回归斜率
        n = len(closes)
        x_mean = (n - 1) / 2
        y_mean = sum(closes) / n

        numerator = 0.0
        denominator = 0.0

        for i, y in enumerate(closes):
            numerator += (i - x_mean) * (y - y_mean)
            denominator += (i - x_mean) ** 2

        if denominator == 0:
            return (0.0, 0.0)

        slope = numerator / denominator

        # 计算趋势强度（归一化）
        avg_close = y_mean
        if avg_close > 0:
            strength = abs(slope) * n / avg_close
            strength = min(strength, 1.0)  # 限制到1
        else:
            strength = 0.0

        # 方向
        direction = 1.0 if slope > 0 else -1.0

        return (strength, direction)

    def _calculate_range_bound(self, candles: list[dict[str, Any]]) -> float:
        """计算区间约束程度。

        Returns:
            float: 区间约束值，越小表示越接近区间震荡
        """
        if len(candles) < 10:
            return 1.0

        highs = []
        lows = []
        closes = []

        for c in candles:
            high = c.get("high")
            low = c.get("low")
            close = c.get("close")

            if high is not None and low is not None and close is not None:
                try:
                    highs.append(float(Decimal(str(high))))
                    lows.append(float(Decimal(str(low))))
                    closes.append(float(Decimal(str(close))))
                except (TypeError, ValueError, InvalidOperation):
                    pass

        if len(highs) < 10:
            return 1.0

        # 计算价格范围
        total_range = max(highs) - min(lows)
        avg_close = sum(closes) / len(closes)

        if avg_close <= 0:
            return 1.0

        # 区间约束比例
        range_pct = total_range / avg_close

        # 计算价格穿越区间次数
        range_high = max(highs)
        range_low = min(lows)
        crossings = 0

        for close in closes:
            if close >= range_high or close <= range_low:
                crossings += 1

        crossing_ratio = crossings / len(closes)

        # 区间约束 = 区间大小因子 * 穿越比例因子
        # 小值表示震荡，大值表示趋势
        bound = range_pct * 5 + crossing_ratio

        return bound

    def _classify_regime(
        self,
        volatility: float,
        trend_strength: float,
        trend_direction: float,
        range_bound: float,
    ) -> MarketRegime:
        """根据指标判定市场状态。"""
        # 高波动状态
        if volatility > HIGH_VOL_THRESHOLD:
            return MarketRegime.VOLATILE

        # 趋势状态
        if trend_strength > TREND_THRESHOLD:
            if trend_direction > 0:
                return MarketRegime.TRENDING_UP
            else:
                return MarketRegime.TRENDING_DOWN

        # 区间震荡
        if range_bound < RANGE_THRESHOLD * 5:
            return MarketRegime.RANGING

        # 低波动
        if volatility < HIGH_VOL_THRESHOLD / 2:
            return MarketRegime.QUIET

        # 默认：状态转换
        return MarketRegime.TRANSITION

    def get_params(self, regime: MarketRegime | None = None) -> RegimeParams:
        """获取指定状态的参数。

        Args:
            regime: 市场状态（None表示当前状态）

        Returns:
            RegimeParams: 参数配置
        """
        if regime is None:
            regime = self._current_regime

        return self._regime_params.get(regime, RegimeParams())

    def get_current_params(self) -> RegimeParams:
        """获取当前参数（考虑平滑过渡）。"""
        return self._current_params

    def update_params(
        self,
        candles: list[dict[str, Any]],
        force: bool = False,
    ) -> RegimeParams:
        """根据市场数据更新参数。

        Args:
            candles: K线数据
            force: 是否强制更新（不考虑平滑过渡）

        Returns:
            RegimeParams: 更新后的参数
        """
        # 检测市场状态
        regime = self.detect_market_regime(candles)
        target_params = self._regime_params.get(regime, RegimeParams())

        if force:
            self._current_params = target_params
        else:
            # 平滑过渡
            self._current_params = self._smooth_transition(
                self._current_params,
                target_params,
                self._config.transition_speed
            )

        # 记录历史
        self._params_history.append((datetime.now(timezone.utc), self._current_params))
        if len(self._params_history) > 1000:
            self._params_history = self._params_history[-1000:]

        return self._current_params

    def _smooth_transition(
        self,
        current: RegimeParams,
        target: RegimeParams,
        speed: float,
    ) -> RegimeParams:
        """参数平滑过渡。"""
        return RegimeParams(
            stop_loss_pct=current.stop_loss_pct + (target.stop_loss_pct - current.stop_loss_pct) * speed,
            take_profit_pct=current.take_profit_pct + (target.take_profit_pct - current.take_profit_pct) * speed,
            entry_threshold=current.entry_threshold + (target.entry_threshold - current.entry_threshold) * speed,
            position_size_pct=current.position_size_pct + (target.position_size_pct - current.position_size_pct) * speed,
            lookback_bars=int(current.lookback_bars + (target.lookback_bars - current.lookback_bars) * speed),
            breakout_buffer_pct=current.breakout_buffer_pct + (target.breakout_buffer_pct - current.breakout_buffer_pct) * speed,
        )

    def set_regime_params(
        self,
        regime: MarketRegime,
        params: dict[str, Any],
    ) -> bool:
        """设置指定状态的参数。

        Args:
            regime: 市场状态
            params: 参数字典

        Returns:
            bool: 设置是否成功
        """
        # 验证参数
        for key, value in params.items():
            if key in ["stop_loss_pct", "take_profit_pct", "entry_threshold", "position_size_pct", "breakout_buffer_pct"]:
                if not isinstance(value, (int, float)):
                    return False
                if value < 0:
                    return False
                if key == "entry_threshold" and value > 1.0:
                    return False
                if key == "position_size_pct" and value > 1.0:
                    return False
            elif key == "lookback_bars":
                if not isinstance(value, int):
                    return False
                if value < 1:
                    return False

        self._regime_params[regime] = RegimeParams.from_dict(params)
        self._save_config()
        return True

    def set_transition_speed(self, speed: float) -> bool:
        """设置参数过渡速度。

        Args:
            speed: 过渡速度 (0-1)

        Returns:
            bool: 设置是否成功
        """
        if not isinstance(speed, (int, float)):
            return False
        if speed < 0 or speed > 1:
            return False

        with self._config_lock:
            self._config.transition_speed = float(speed)

        self._save_config()
        return True

    def get_regime_history(self, limit: int = 100) -> list[dict[str, Any]]:
        """获取状态变化历史。"""
        history = self._regime_history[-limit:]
        return [
            {"timestamp": ts.isoformat(), "regime": regime.value}
            for ts, regime in history
        ]

    def get_params_history(self, limit: int = 100) -> list[dict[str, Any]]:
        """获取参数变化历史。"""
        history = self._params_history[-limit:]
        return [
            {"timestamp": ts.isoformat(), "params": params.to_dict()}
            for ts, params in history
        ]

    def get_current_regime(self) -> MarketRegime:
        """获取当前市场状态。"""
        return self._current_regime

    def get_all_regime_params(self) -> dict[str, dict[str, Any]]:
        """获取所有状态的参数配置。"""
        return {
            regime.value: params.to_dict()
            for regime, params in self._regime_params.items()
        }

    def get_config(self) -> dict[str, Any]:
        """获取完整配置。"""
        with self._config_lock:
            return self._config.to_dict()


# 全局自适应参数服务实例
adaptive_params_service = AdaptiveParamsService()