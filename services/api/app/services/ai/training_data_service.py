"""训练数据收集服务。

收集K线、指标、交易结果用于强化学习策略训练。
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, date
from decimal import Decimal, InvalidOperation
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ActionType(Enum):
    """动作类型枚举。"""
    HOLD = "hold"
    OPEN_LONG = "open_long"
    OPEN_SHORT = "open_short"
    CLOSE_POSITION = "close_position"
    ADJUST_PARAMS = "adjust_params"


class MarketRegime(Enum):
    """市场状态枚举。"""
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    VOLATILE = "volatile"
    QUIET = "quiet"
    TRANSITION = "transition"


@dataclass(slots=True)
class MarketState:
    """市场状态数据结构。"""

    volatility_regime: float = 0.0
    trend_strength: float = 0.0
    volume_profile: float = 0.0
    price_position: float = 0.0

    def to_dict(self) -> dict[str, float]:
        return {
            "volatility_regime": self.volatility_regime,
            "trend_strength": self.trend_strength,
            "volume_profile": self.volume_profile,
            "price_position": self.price_position,
        }

    def to_array(self) -> list[float]:
        return [
            self.volatility_regime,
            self.trend_strength,
            self.volume_profile,
            self.price_position,
        ]


@dataclass(slots=True)
class IndicatorState:
    """技术指标状态数据结构。"""

    rsi: float = 50.0
    macd_signal: float = 0.0
    bb_position: float = 0.5
    ma_distance: float = 0.0

    def to_dict(self) -> dict[str, float]:
        return {
            "rsi": self.rsi,
            "macd_signal": self.macd_signal,
            "bb_position": self.bb_position,
            "ma_distance": self.ma_distance,
        }

    def to_array(self) -> list[float]:
        return [
            self.rsi / 100.0,  # 归一化到0-1
            self.macd_signal,
            self.bb_position,
            self.ma_distance,
        ]


@dataclass(slots=True)
class PositionState:
    """持仓状态数据结构。"""

    has_position: bool = False
    position_duration: int = 0
    unrealized_pnl_pct: float = 0.0
    entry_distance_pct: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "has_position": self.has_position,
            "position_duration": self.position_duration,
            "unrealized_pnl_pct": self.unrealized_pnl_pct,
            "entry_distance_pct": self.entry_distance_pct,
        }

    def to_array(self) -> list[float]:
        return [
            float(self.has_position),
            min(self.position_duration / 100.0, 1.0),  # 归一化
            self.unrealized_pnl_pct,
            self.entry_distance_pct,
        ]


@dataclass(slots=True)
class TimeState:
    """时间特征数据结构。"""

    hour_of_day: int = 0
    day_of_week: int = 0
    is_trading_hours: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "hour_of_day": self.hour_of_day,
            "day_of_week": self.day_of_week,
            "is_trading_hours": self.is_trading_hours,
        }

    def to_array(self) -> list[float]:
        return [
            self.hour_of_day / 24.0,  # 归一化到0-1
            self.day_of_week / 7.0,   # 归一化到0-1
            float(self.is_trading_hours),
        ]


@dataclass
class State:
    """完整状态向量。"""

    market: MarketState
    indicators: IndicatorState
    position: PositionState
    time: TimeState

    def to_dict(self) -> dict[str, Any]:
        return {
            "market": self.market.to_dict(),
            "indicators": self.indicators.to_dict(),
            "position": self.position.to_dict(),
            "time": self.time.to_dict(),
        }

    def to_array(self) -> list[float]:
        """转换为可用于模型输入的数组。"""
        return (
            self.market.to_array()
            + self.indicators.to_array()
            + self.position.to_array()
            + self.time.to_array()
        )


@dataclass
class Action:
    """动作数据结构。"""

    type: ActionType
    size_pct: float = 0.0
    stop_loss_pct: float = 0.0
    take_profit_pct: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type.value,
            "params": {
                "size_pct": self.size_pct,
                "stop_loss_pct": self.stop_loss_pct,
                "take_profit_pct": self.take_profit_pct,
            },
        }


@dataclass
class ActionLabel:
    """动作标签(最优动作)。"""

    optimal_action: Action
    action_confidence: float = 0.0
    alternative_actions: list[Action] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "optimal_action": self.optimal_action.to_dict(),
            "action_confidence": self.action_confidence,
            "alternative_actions": [a.to_dict() for a in self.alternative_actions],
        }


@dataclass
class Outcome:
    """事后评估结果。"""

    actual_pnl: float = 0.0
    holding_period: int = 0
    max_drawdown: float = 0.0
    market_context: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "actual_pnl": self.actual_pnl,
            "holding_period": self.holding_period,
            "max_drawdown": self.max_drawdown,
            "market_context": self.market_context,
        }


@dataclass
class SampleMetadata:
    """样本元数据。"""

    source_strategy: str = ""
    data_quality: float = 1.0
    noise_level: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_strategy": self.source_strategy,
            "data_quality": self.data_quality,
            "noise_level": self.noise_level,
        }


@dataclass
class TrainingSample:
    """完整训练样本。"""

    timestamp: datetime
    symbol: str
    state: State
    label: ActionLabel | None = None
    outcome: Outcome | None = None
    metadata: SampleMetadata = field(default_factory=SampleMetadata)

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "symbol": self.symbol,
            "state": self.state.to_dict(),
            "label": self.label.to_dict() if self.label else None,
            "outcome": self.outcome.to_dict() if self.outcome else None,
            "metadata": self.metadata.to_dict(),
        }


class TrainingDataService:
    """训练数据收集服务。

    功能：
    1. 从市场数据提取状态向量
    2. 从交易结果生成标签
    3. 存储和导出训练数据集
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self._config = config or {}
        self._samples: dict[str, list[TrainingSample]] = {}  # symbol -> samples
        self._sample_buffer: list[TrainingSample] = []
        self._buffer_size = self._config.get("buffer_size", 1000)
        self._storage_path: Path | None = None

    def set_storage_path(self, path: str | Path) -> None:
        """设置数据存储路径。"""
        self._storage_path = Path(path)
        self._storage_path.mkdir(parents=True, exist_ok=True)

    def extract_state(
        self,
        candles: list[dict[str, Any]],
        indicators: dict[str, Any] | None = None,
        position_info: dict[str, Any] | None = None,
    ) -> State:
        """从市场数据提取状态向量。

        Args:
            candles: K线数据列表
            indicators: 技术指标数据
            position_info: 持仓信息

        Returns:
            State: 完整状态向量
        """
        if not candles:
            return State(
                market=MarketState(),
                indicators=IndicatorState(),
                position=PositionState(),
                time=TimeState(),
            )

        # 提取市场状态
        market_state = self._extract_market_state(candles)

        # 提取指标状态
        indicator_state = self._extract_indicator_state(indicators or {})

        # 提取持仓状态
        position_state = self._extract_position_state(position_info or {})

        # 提取时间状态
        time_state = self._extract_time_state(candles[-1] if candles else {})

        return State(
            market=market_state,
            indicators=indicator_state,
            position=position_state,
            time=time_state,
        )

    def _extract_market_state(self, candles: list[dict[str, Any]]) -> MarketState:
        """提取市场状态特征。"""
        if len(candles) < 20:
            return MarketState()

        recent_candles = candles[-20:]

        # 计算波动率状态
        highs = [self._to_decimal(c.get("high", 0)) for c in recent_candles]
        lows = [self._to_decimal(c.get("low", 0)) for c in recent_candles]
        closes = [self._to_decimal(c.get("close", 0)) for c in recent_candles]

        if not closes or closes[-1] == 0:
            return MarketState()

        price_range = float(max(highs) - min(lows)) / float(closes[-1])
        volatility_regime = min(price_range * 5, 1.0)  # 归一化

        # 计算趋势强度
        if len(closes) >= 10:
            first_close = float(closes[-10])
            last_close = float(closes[-1])
            trend_strength = abs(last_close - first_close) / first_close
            trend_strength = min(trend_strength * 10, 1.0)  # 归一化
        else:
            trend_strength = 0.0

        # 计算成交量特征
        volumes = [c.get("volume", 0) for c in recent_candles]
        if volumes and sum(volumes) > 0:
            avg_volume = sum(volumes[:-1]) / len(volumes[:-1]) if len(volumes) > 1 else volumes[0]
            current_volume = volumes[-1]
            volume_profile = min(current_volume / avg_volume / 2, 1.0) if avg_volume > 0 else 0.5
        else:
            volume_profile = 0.5

        # 计算价格相对位置
        if highs and lows and closes:
            range_size = float(max(highs) - min(lows))
            if range_size > 0:
                price_position = (float(closes[-1]) - float(min(lows))) / range_size
            else:
                price_position = 0.5
        else:
            price_position = 0.5

        return MarketState(
            volatility_regime=volatility_regime,
            trend_strength=trend_strength,
            volume_profile=volume_profile,
            price_position=price_position,
        )

    def _extract_indicator_state(self, indicators: dict[str, Any]) -> IndicatorState:
        """提取技术指标状态。"""
        rsi = indicators.get("rsi", 50.0)
        if isinstance(rsi, dict):
            rsi = rsi.get("value", 50.0)

        macd_signal = indicators.get("macd", {}).get("signal", 0.0)
        if isinstance(macd_signal, dict):
            macd_signal = macd_signal.get("value", 0.0)

        bb_position = indicators.get("bb_position", 0.5)
        if isinstance(bb_position, dict):
            bb_position = bb_position.get("value", 0.5)

        ma_distance = indicators.get("ma_distance", 0.0)
        if isinstance(ma_distance, dict):
            ma_distance = ma_distance.get("value", 0.0)

        return IndicatorState(
            rsi=float(rsi) if rsi is not None else 50.0,
            macd_signal=float(macd_signal) if macd_signal is not None else 0.0,
            bb_position=float(bb_position) if bb_position is not None else 0.5,
            ma_distance=float(ma_distance) if ma_distance is not None else 0.0,
        )

    def _extract_position_state(self, position_info: dict[str, Any]) -> PositionState:
        """提取持仓状态。"""
        has_position = position_info.get("has_position", False)
        position_duration = position_info.get("position_duration", 0)
        unrealized_pnl_pct = position_info.get("unrealized_pnl_pct", 0.0)
        entry_distance_pct = position_info.get("entry_distance_pct", 0.0)

        return PositionState(
            has_position=bool(has_position),
            position_duration=int(position_duration) if position_duration else 0,
            unrealized_pnl_pct=float(unrealized_pnl_pct) if unrealized_pnl_pct else 0.0,
            entry_distance_pct=float(entry_distance_pct) if entry_distance_pct else 0.0,
        )

    def _extract_time_state(self, candle: dict[str, Any]) -> TimeState:
        """提取时间状态。"""
        timestamp = candle.get("timestamp")
        if timestamp:
            if isinstance(timestamp, str):
                try:
                    dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                except ValueError:
                    dt = datetime.now(timezone.utc)
            elif isinstance(timestamp, datetime):
                dt = timestamp
            else:
                dt = datetime.now(timezone.utc)

            hour_of_day = dt.hour
            day_of_week = dt.weekday()
            # 简化判断：9:00-15:00为交易时段
            is_trading_hours = 9 <= hour_of_day < 15
        else:
            hour_of_day = 0
            day_of_week = 0
            is_trading_hours = True

        return TimeState(
            hour_of_day=hour_of_day,
            day_of_week=day_of_week,
            is_trading_hours=is_trading_hours,
        )

    def collect_sample(
        self,
        symbol: str,
        candles: list[dict[str, Any]],
        indicators: dict[str, Any] | None = None,
        position_info: dict[str, Any] | None = None,
        source_strategy: str = "",
    ) -> TrainingSample:
        """收集单个训练样本。

        Args:
            symbol: 交易标的符号
            candles: K线数据
            indicators: 技术指标
            position_info: 持仓信息
            source_strategy: 来源策略名称

        Returns:
            TrainingSample: 训练样本
        """
        timestamp = datetime.now(timezone.utc)
        if candles and candles[-1].get("timestamp"):
            ts = candles[-1].get("timestamp")
            if isinstance(ts, datetime):
                timestamp = ts
            elif isinstance(ts, str):
                try:
                    timestamp = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                except ValueError:
                    pass

        state = self.extract_state(candles, indicators, position_info)
        metadata = SampleMetadata(
            source_strategy=source_strategy,
            data_quality=self._estimate_data_quality(candles),
            noise_level=self._estimate_noise_level(candles),
        )

        sample = TrainingSample(
            timestamp=timestamp,
            symbol=symbol.strip().upper(),
            state=state,
            metadata=metadata,
        )

        # 缓存样本
        self._sample_buffer.append(sample)
        if len(self._sample_buffer) >= self._buffer_size:
            self._flush_buffer()

        # 添加到符号特定列表
        symbol_samples = self._samples.setdefault(sample.symbol, [])
        symbol_samples.append(sample)

        return sample

    def _estimate_data_quality(self, candles: list[dict[str, Any]]) -> float:
        """估计数据质量评分。"""
        if not candles:
            return 0.0

        # 检查完整性
        required_fields = ["open", "high", "low", "close"]
        complete_count = 0
        for candle in candles:
            if all(f in candle and candle[f] is not None for f in required_fields):
                complete_count += 1

        completeness = complete_count / len(candles)

        # 检查一致性（无异常值）
        closes = [c.get("close", 0) for c in candles]
        if closes:
            avg_close = sum(closes) / len(closes)
            outliers = sum(1 for c in closes if abs(c - avg_close) > avg_close * 0.5)
            consistency = 1.0 - outliers / len(closes)
        else:
            consistency = 0.0

        return (completeness * 0.6 + consistency * 0.4)

    def _estimate_noise_level(self, candles: list[dict[str, Any]]) -> float:
        """估计噪声水平。"""
        if len(candles) < 5:
            return 0.0

        # 计算价格变化的方差
        closes = [float(c.get("close", 0)) for c in candles if c.get("close")]
        if len(closes) < 5:
            return 0.0

        changes = [closes[i] - closes[i-1] for i in range(1, len(closes))]
        if not changes:
            return 0.0

        avg_change = sum(changes) / len(changes)
        variance = sum((c - avg_change) ** 2 for c in changes) / len(changes)
        avg_close = sum(closes) / len(closes)

        # 归一化噪声水平
        noise_level = min(variance / (avg_close ** 2) * 100, 1.0)
        return noise_level

    def generate_labels(
        self,
        samples: list[TrainingSample],
        future_candles: list[dict[str, Any]],
        lookahead_bars: int = 20,
    ) -> list[TrainingSample]:
        """生成训练标签(最优动作)。

        Args:
            samples: 无标签样本列表
            future_candles: 未来K线数据（用于事后评估）
            lookahead_bars: 前瞻周期

        Returns:
            list[TrainingSample]: 带标签的样本列表
        """
        labeled_samples = []

        for sample in samples:
            # 计算未来收益
            outcome = self._calculate_outcome(sample, future_candles, lookahead_bars)

            # 根据收益确定最优动作
            label = self._determine_optimal_action(outcome)

            labeled_sample = TrainingSample(
                timestamp=sample.timestamp,
                symbol=sample.symbol,
                state=sample.state,
                label=label,
                outcome=outcome,
                metadata=sample.metadata,
            )
            labeled_samples.append(labeled_sample)

        return labeled_samples

    def _calculate_outcome(
        self,
        sample: TrainingSample,
        future_candles: list[dict[str, Any]],
        lookahead_bars: int,
    ) -> Outcome:
        """计算事后评估结果。"""
        if not future_candles:
            return Outcome()

        relevant_candles = future_candles[:lookahead_bars]
        if not relevant_candles:
            return Outcome()

        closes = [float(c.get("close", 0)) for c in relevant_candles if c.get("close")]
        if not closes:
            return Outcome()

        entry_price = closes[0]
        max_price = max(closes)
        min_price = min(closes)
        final_price = closes[-1]

        # 计算做多收益
        long_pnl = (final_price - entry_price) / entry_price if entry_price > 0 else 0
        long_max_dd = (entry_price - min_price) / entry_price if entry_price > 0 else 0

        # 计算做空收益（如果支持）
        short_pnl = (entry_price - final_price) / entry_price if entry_price > 0 else 0
        short_max_dd = (max_price - entry_price) / entry_price if entry_price > 0 else 0

        # 确定最佳策略
        if long_pnl > short_pnl:
            actual_pnl = long_pnl
            max_drawdown = long_max_dd
            market_context = "bullish"
        else:
            actual_pnl = short_pnl
            max_drawdown = short_max_dd
            market_context = "bearish"

        return Outcome(
            actual_pnl=actual_pnl,
            holding_period=len(closes),
            max_drawdown=max_drawdown,
            market_context=market_context,
        )

    def _determine_optimal_action(self, outcome: Outcome) -> ActionLabel:
        """根据事后结果确定最优动作。"""
        # 简化逻辑：根据收益确定动作
        pnl = outcome.actual_pnl
        dd = outcome.max_drawdown

        # 根据收益和回撤决定动作
        if pnl > 0.02 and dd < 0.05:
            # 高收益低回撤 -> 开多
            optimal_action = Action(
                type=ActionType.OPEN_LONG,
                size_pct=0.8,
                stop_loss_pct=dd * 1.5,
                take_profit_pct=pnl * 0.8,
            )
            confidence = 0.8
        elif pnl < -0.02:
            # 负收益 -> 不开仓
            optimal_action = Action(type=ActionType.HOLD)
            confidence = 0.6
        elif pnl > 0:
            # 小正收益 -> 轻仓试探
            optimal_action = Action(
                type=ActionType.OPEN_LONG,
                size_pct=0.3,
                stop_loss_pct=0.02,
                take_profit_pct=0.03,
            )
            confidence = 0.4
        else:
            # 中性 -> 观望
            optimal_action = Action(type=ActionType.HOLD)
            confidence = 0.5

        return ActionLabel(
            optimal_action=optimal_action,
            action_confidence=confidence,
        )

    def _flush_buffer(self) -> None:
        """将缓冲区数据写入存储。"""
        if not self._storage_path or not self._sample_buffer:
            return

        try:
            filename = f"training_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            filepath = self._storage_path / filename

            data = [sample.to_dict() for sample in self._sample_buffer]
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

            logger.info("训练数据已保存: %s (%d samples)", filepath, len(self._sample_buffer))
            self._sample_buffer.clear()
        except Exception as e:
            logger.warning("保存训练数据失败: %s", e)

    def export_dataset(
        self,
        symbols: list[str] | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        format: str = "json",
    ) -> str:
        """导出训练数据集。

        Args:
            symbols: 要导出的符号列表（None表示全部）
            start_date: 开始日期
            end_date: 结束日期
            format: 导出格式（json/parquet）

        Returns:
            str: 导出文件路径
        """
        if not self._storage_path:
            self._storage_path = Path("/tmp/training_data")
            self._storage_path.mkdir(parents=True, exist_ok=True)

        # 收集要导出的样本
        export_samples = []
        for symbol, samples in self._samples.items():
            if symbols and symbol not in symbols:
                continue

            for sample in samples:
                # 日期过滤
                sample_date = sample.timestamp.date()
                if start_date and sample_date < start_date:
                    continue
                if end_date and sample_date > end_date:
                    continue
                export_samples.append(sample)

        if not export_samples:
            logger.warning("没有可导出的训练样本")
            return ""

        # 导出
        filename = f"dataset_{datetime.now().strftime('%Y%m%d')}.{format}"
        filepath = self._storage_path / filename

        if format == "json":
            data = [sample.to_dict() for sample in export_samples]
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        else:
            # 其他格式暂不支持，回退到JSON
            data = [sample.to_dict() for sample in export_samples]
            with open(filepath.with_suffix(".json"), "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            filepath = filepath.with_suffix(".json")

        logger.info("训练数据集已导出: %s (%d samples)", filepath, len(export_samples))
        return str(filepath)

    def get_sample_count(self, symbol: str | None = None) -> int:
        """获取样本数量。"""
        if symbol:
            return len(self._samples.get(symbol.strip().upper(), []))
        return sum(len(samples) for samples in self._samples.values())

    def get_statistics(self) -> dict[str, Any]:
        """获取数据统计信息。"""
        total_samples = self.get_sample_count()
        symbols = list(self._samples.keys())

        # 计算状态分布统计
        all_states = []
        for samples in self._samples.values():
            for sample in samples:
                all_states.append(sample.state.to_array())

        if all_states:
            # 简化统计：计算各维度的均值
            state_means = []
            for i in range(len(all_states[0])):
                values = [s[i] for s in all_states]
                state_means.append(sum(values) / len(values))
        else:
            state_means = []

        return {
            "total_samples": total_samples,
            "symbols": symbols,
            "buffer_size": len(self._sample_buffer),
            "state_dimension_means": state_means,
        }

    def clear_samples(self, symbol: str | None = None) -> int:
        """清除样本数据。"""
        if symbol:
            key = symbol.strip().upper()
            count = len(self._samples.get(key, []))
            if key in self._samples:
                del self._samples[key]
            return count

        total = self.get_sample_count()
        self._samples.clear()
        self._sample_buffer.clear()
        return total

    def _to_decimal(self, value: Any) -> Decimal:
        """转换为Decimal。"""
        try:
            return Decimal(str(value))
        except (TypeError, ValueError, InvalidOperation):
            return Decimal("0")


# 全局训练数据服务实例
training_data_service = TrainingDataService()