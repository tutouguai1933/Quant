"""强化学习策略模板。

定义RL策略的基类接口，支持状态提取、动作选择、奖励计算和策略更新。
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any

from services.api.app.services.ai.adaptive_params import (
    AdaptiveParamsService,
    MarketRegime,
    RegimeParams,
)
from services.api.app.services.ai.training_data_service import (
    Action,
    ActionType,
    State,
    TrainingSample,
)

logger = logging.getLogger(__name__)


@dataclass
class Experience:
    """RL经验数据结构（用于策略更新）。"""

    state: State
    action: Action
    reward: float
    next_state: State
    done: bool = False
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state.to_dict(),
            "action": self.action.to_dict(),
            "reward": self.reward,
            "next_state": self.next_state.to_dict(),
            "done": self.done,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class PolicyConfig:
    """策略配置。"""

    exploration_rate: float = 0.1           # 推索率
    exploration_decay: float = 0.995        # 推索衰减
    min_exploration_rate: float = 0.01      # 最小推索率
    learning_rate: float = 0.001            # 学习率
    discount_factor: float = 0.95           # 折扣因子
    batch_size: int = 32                    # 批次大小

    # 奖励权重
    pnl_weight: float = 0.40
    risk_weight: float = 0.30
    execution_weight: float = 0.20
    consistency_weight: float = 0.10

    def to_dict(self) -> dict[str, Any]:
        return {
            "exploration_rate": self.exploration_rate,
            "exploration_decay": self.exploration_decay,
            "min_exploration_rate": self.min_exploration_rate,
            "learning_rate": self.learning_rate,
            "discount_factor": self.discount_factor,
            "batch_size": self.batch_size,
            "pnl_weight": self.pnl_weight,
            "risk_weight": self.risk_weight,
            "execution_weight": self.execution_weight,
            "consistency_weight": self.consistency_weight,
        }


@dataclass
class RLStrategyResult:
    """RL策略执行结果。"""

    action: Action
    state: State
    market_regime: MarketRegime
    adaptive_params: RegimeParams
    confidence: float = 0.0
    reasoning: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action.to_dict(),
            "state": self.state.to_dict(),
            "market_regime": self.market_regime.value,
            "adaptive_params": self.adaptive_params.to_dict(),
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "timestamp": self.timestamp.isoformat(),
        }


class RLStrategyBase(ABC):
    """强化学习策略基类。

    所有RL策略必须继承此基类并实现核心方法。
    """

    name: str = "rl_base"
    display_name: str = "RL策略基类"
    description: str = "强化学习策略模板基类"
    version: str = "1.0.0"

    def __init__(
        self,
        config: dict[str, Any] | None = None,
        adaptive_params_service: AdaptiveParamsService | None = None,
    ) -> None:
        self._config = PolicyConfig()
        if config:
            self._apply_config(config)

        self._adaptive_params = adaptive_params_service or AdaptiveParamsService()
        self._experience_buffer: list[Experience] = []
        self._buffer_size = 10000
        self._current_exploration_rate = self._config.exploration_rate
        self._training_mode = False

    def _apply_config(self, config: dict[str, Any]) -> None:
        """应用配置。"""
        self._config = PolicyConfig(
            exploration_rate=float(config.get("exploration_rate", 0.1)),
            exploration_decay=float(config.get("exploration_decay", 0.995)),
            min_exploration_rate=float(config.get("min_exploration_rate", 0.01)),
            learning_rate=float(config.get("learning_rate", 0.001)),
            discount_factor=float(config.get("discount_factor", 0.95)),
            batch_size=int(config.get("batch_size", 32)),
            pnl_weight=float(config.get("pnl_weight", 0.40)),
            risk_weight=float(config.get("risk_weight", 0.30)),
            execution_weight=float(config.get("execution_weight", 0.20)),
            consistency_weight=float(config.get("consistency_weight", 0.10)),
        )

    @abstractmethod
    def get_state(
        self,
        market_data: dict[str, Any],
        indicators: dict[str, Any] | None = None,
        position_info: dict[str, Any] | None = None,
    ) -> State:
        """提取状态向量。

        Args:
            market_data: 市场数据（包含K线等）
            indicators: 技术指标数据
            position_info: 持仓信息

        Returns:
            State: 状态向量
        """
        raise NotImplementedError

    @abstractmethod
    def select_action(self, state: State, explore: bool = True) -> Action:
        """选择动作。

        Args:
            state: 当前状态
            explore: 是否启用探索

        Returns:
            Action: 选择执行的动作
        """
        raise NotImplementedError

    @abstractmethod
    def calculate_reward(
        self,
        action: Action,
        outcome: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> float:
        """计算奖励。

        Args:
            action: 执行的动作
            outcome: 动作结果（包含盈亏等）
            context: 额外上下文信息

        Returns:
            float: 奖励值
        """
        raise NotImplementedError

    @abstractmethod
    def update_policy(self, experience: Experience) -> None:
        """更新策略。

        Args:
            experience: RL经验数据
        """
        raise NotImplementedError

    def set_training_mode(self, enabled: bool) -> None:
        """设置训练模式。"""
        self._training_mode = enabled

    def get_adaptive_params(self, market_regime: MarketRegime) -> RegimeParams:
        """获取自适应参数。"""
        return self._adaptive_params.get_params(market_regime)

    def analyze(
        self,
        market_data: dict[str, Any],
        indicators: dict[str, Any] | None = None,
        position_info: dict[str, Any] | None = None,
    ) -> RLStrategyResult:
        """分析市场并返回策略结果。

        Args:
            market_data: 市场数据
            indicators: 技术指标
            position_info: 持仓信息

        Returns:
            RLStrategyResult: 策略执行结果
        """
        # 提取状态
        state = self.get_state(market_data, indicators, position_info)

        # 检测市场状态
        candles = market_data.get("candles", [])
        market_regime = self._adaptive_params.detect_market_regime(candles)

        # 获取自适应参数
        adaptive_params = self.get_adaptive_params(market_regime)

        # 选择动作
        explore = self._training_mode and self._should_explore()
        action = self.select_action(state, explore=explore)

        # 计算置信度
        confidence = self._calculate_confidence(state, action, market_regime)

        # 生成推理说明
        reasoning = self._generate_reasoning(state, action, market_regime)

        return RLStrategyResult(
            action=action,
            state=state,
            market_regime=market_regime,
            adaptive_params=adaptive_params,
            confidence=confidence,
            reasoning=reasoning,
        )

    def _should_explore(self) -> bool:
        """决定是否探索。"""
        import random
        return random.random() < self._current_exploration_rate

    def _decay_exploration(self) -> None:
        """衰减探索率。"""
        self._current_exploration_rate *= self._config.exploration_decay
        self._current_exploration_rate = max(
            self._current_exploration_rate,
            self._config.min_exploration_rate
        )

    def _calculate_confidence(
        self,
        state: State,
        action: Action,
        regime: MarketRegime,
    ) -> float:
        """计算置信度（简化版本）。"""
        # 基于动作类型的置信度
        action_confidence = {
            ActionType.HOLD: 0.5,
            ActionType.OPEN_LONG: 0.6,
            ActionType.OPEN_SHORT: 0.6,
            ActionType.CLOSE_POSITION: 0.7,
            ActionType.ADJUST_PARAMS: 0.4,
        }.get(action.type, 0.5)

        # 根据市场状态调整
        regime_adjustment = {
            MarketRegime.TRENDING_UP: 0.1,
            MarketRegime.TRENDING_DOWN: 0.1,
            MarketRegime.RANGING: -0.1,
            MarketRegime.VOLATILE: -0.2,
            MarketRegime.QUIET: 0.05,
            MarketRegime.TRANSITION: -0.05,
        }.get(regime, 0.0)

        confidence = action_confidence + regime_adjustment
        return max(0.0, min(1.0, confidence))

    def _generate_reasoning(
        self,
        state: State,
        action: Action,
        regime: MarketRegime,
    ) -> str:
        """生成推理说明。"""
        regime_desc = {
            MarketRegime.TRENDING_UP: "上升趋势",
            MarketRegime.TRENDING_DOWN: "下降趋势",
            MarketRegime.RANGING: "震荡区间",
            MarketRegime.VOLATILE: "高波动",
            MarketRegime.QUIET: "低波动",
            MarketRegime.TRANSITION: "状态转换",
        }.get(regime, "未知")

        action_desc = {
            ActionType.HOLD: "观望",
            ActionType.OPEN_LONG: "开多",
            ActionType.OPEN_SHORT: "开空",
            ActionType.CLOSE_POSITION: "平仓",
            ActionType.ADJUST_PARAMS: "调整参数",
        }.get(action.type, "未知")

        trend_str = "强" if state.market.trend_strength > 0.5 else "弱"
        vol_str = "高" if state.market.volatility_regime > 0.5 else "低"

        return f"市场状态: {regime_desc} ({trend_str}趋势, {vol_str}波动) -> 动作: {action_desc}"

    def record_experience(
        self,
        state: State,
        action: Action,
        outcome: dict[str, Any],
        next_state: State,
        context: dict[str, Any] | None = None,
    ) -> Experience:
        """记录经验并更新策略。

        Args:
            state: 前状态
            action: 执行的动作
            outcome: 动作结果
            next_state: 后状态
            context: 额外上下文

        Returns:
            Experience: 记录的经验数据
        """
        # 计算奖励
        reward = self.calculate_reward(action, outcome, context)

        # 创建经验
        experience = Experience(
            state=state,
            action=action,
            reward=reward,
            next_state=next_state,
            done=outcome.get("done", False),
        )

        # 加入缓冲区
        self._experience_buffer.append(experience)
        if len(self._experience_buffer) > self._buffer_size:
            self._experience_buffer = self._experience_buffer[-self._buffer_size:]

        # 更新策略（如果缓冲区足够）
        if len(self._experience_buffer) >= self._config.batch_size:
            self._update_from_buffer()

        # 衰减探索率
        if self._training_mode:
            self._decay_exploration()

        return experience

    def _update_from_buffer(self) -> None:
        """从缓冲区更新策略。"""
        # 取最近一批经验
        recent_experiences = self._experience_buffer[-self._config.batch_size:]

        for exp in recent_experiences:
            try:
                self.update_policy(exp)
            except Exception as e:
                logger.warning("策略更新失败: %s", e)

    def get_experience_count(self) -> int:
        """获取经验数量。"""
        return len(self._experience_buffer)

    def get_exploration_rate(self) -> float:
        """获取当前探索率。"""
        return self._current_exploration_rate

    def get_config(self) -> dict[str, Any]:
        """获取策略配置。"""
        return self._config.to_dict()

    def to_dict(self) -> dict[str, Any]:
        """序列化策略信息。"""
        return {
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "version": self.version,
            "config": self.get_config(),
            "exploration_rate": self._current_exploration_rate,
            "experience_count": self.get_experience_count(),
            "training_mode": self._training_mode,
        }


class SimpleRLStrategy(RLStrategyBase):
    """简单RL策略示例实现。

    使用简单的规则近似RL策略，用于演示和测试。
    """

    name = "simple_rl"
    display_name = "简单RL策略"
    description = "基于规则的简单RL策略实现"
    version = "1.0.0"

    def get_state(
        self,
        market_data: dict[str, Any],
        indicators: dict[str, Any] | None = None,
        position_info: dict[str, Any] | None = None,
    ) -> State:
        """提取状态向量。"""
        from services.api.app.services.ai.training_data_service import (
            MarketState,
            IndicatorState,
            PositionState,
            TimeState,
            TrainingDataService,
        )

        candles = market_data.get("candles", [])
        service = TrainingDataService()

        return service.extract_state(candles, indicators, position_info)

    def select_action(self, state: State, explore: bool = True) -> Action:
        """选择动作（简化规则版本）。"""
        import random

        # 探索模式：随机动作
        if explore:
            action_types = list(ActionType)
            random_action = random.choice(action_types)
            return Action(
                type=random_action,
                size_pct=random.uniform(0.1, 0.8),
                stop_loss_pct=random.uniform(0.02, 0.04),
                take_profit_pct=random.uniform(0.03, 0.08),
            )

        # 利用模式：基于规则的决策
        # 趋势强度 + 价格位置决定动作
        trend = state.market.trend_strength
        price_pos = state.market.price_position
        rsi = state.indicators.rsi

        # 有持仓时的决策
        if state.position.has_position:
            # 盈亏较大时平仓
            if state.position.unrealized_pnl_pct > 0.05:
                return Action(type=ActionType.CLOSE_POSITION)
            # 回撤较大时平仓
            if state.position.unrealized_pnl_pct < -0.03:
                return Action(type=ActionType.CLOSE_POSITION)
            # 否则持有
            return Action(type=ActionType.HOLD)

        # 无持仓时的决策
        # 强上升趋势 + 价格在高位区间 + RSI不过热 -> 开多
        if trend > 0.5 and price_pos > 0.6 and rsi < 70:
            return Action(
                type=ActionType.OPEN_LONG,
                size_pct=0.6,
                stop_loss_pct=0.03,
                take_profit_pct=0.06,
            )

        # 弱趋势或震荡 -> 观望
        if trend < 0.3 or price_pos < 0.3 or price_pos > 0.7:
            return Action(type=ActionType.HOLD)

        # 中等趋势 -> 轻仓试探
        return Action(
            type=ActionType.OPEN_LONG,
            size_pct=0.3,
            stop_loss_pct=0.02,
            take_profit_pct=0.03,
        )

    def calculate_reward(
        self,
        action: Action,
        outcome: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> float:
        """计算奖励。"""
        # 收益贡献
        pnl = outcome.get("pnl", 0.0)
        pnl_reward = self._normalize_pnl(pnl) * self._config.pnl_weight

        # 风险贡献
        max_dd = outcome.get("max_drawdown", 0.0)
        risk_penalty = -max_dd * self._config.risk_weight

        # 执行质量
        slippage = outcome.get("slippage", 0.0)
        execution_penalty = -slippage * self._config.execution_weight

        # 策略一致性（动作与市场状态匹配度）
        consistency = outcome.get("consistency", 0.5)
        consistency_reward = consistency * self._config.consistency_weight

        return pnl_reward + risk_penalty + execution_penalty + consistency_reward

    def _normalize_pnl(self, pnl: float) -> float:
        """归一化收益。"""
        # 收益范围假设为 -0.1 到 0.1
        normalized = pnl / 0.1
        return max(-1.0, min(1.0, normalized))

    def update_policy(self, experience: Experience) -> None:
        """更新策略（简化版本：仅更新内部参数）。"""
        # 简化版本：不实现实际的模型更新
        # 在真实实现中，这里会更新神经网络权重等

        # 根据奖励反馈调整探索率
        if experience.reward > 0.5:
            # 好结果，略微降低探索率（增加利用）
            self._current_exploration_rate *= 0.99
        elif experience.reward < -0.5:
            # 坏结果，略微提高探索率（增加探索）
            self._current_exploration_rate *= 1.01

        # 保持在范围内
        self._current_exploration_rate = max(
            self._config.min_exploration_rate,
            min(0.5, self._current_exploration_rate)
        )


# 创建默认实例
simple_rl_strategy = SimpleRLStrategy()