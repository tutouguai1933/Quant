"""真实交易策略引擎服务。

这个文件负责实现核心策略逻辑：
- 入场评分计算（基于研究score、趋势确认）
- 仓位大小计算（基于score和波动率）
- 动态止损追踪
- 退出条件检查（盈亏比、时间、反向信号）

支持多币种交易：
- 不同币种有不同的波动率参数配置
- 从配置中心获取交易对白名单
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Callable

from services.api.app.adapters.freqtrade.client import freqtrade_client
from services.api.app.core.settings import Settings
from services.api.app.services.indicator_service import calculate_macd, calculate_rsi, calculate_volume_trend
from services.api.app.services.market_service import MarketService
from services.api.app.services.model_suggestion_service import model_suggestion_service
from services.api.app.services.research_service import research_service

logger = logging.getLogger(__name__)


def _read_env_decimal(key: str, default: Decimal) -> Decimal:
    """从环境变量读取 Decimal 配置。"""
    raw = os.environ.get(key)
    if raw is None or raw.strip() == "":
        return default
    try:
        return Decimal(raw.strip())
    except (InvalidOperation, ValueError):
        logger.warning("配置 %s=%s 解析失败，使用默认值 %s", key, raw, default)
        return default


def _read_env_int(key: str, default: int) -> int:
    """从环境变量读取整数配置。"""
    raw = os.environ.get(key)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw.strip())
    except ValueError:
        logger.warning("配置 %s=%s 解析失败，使用默认值 %s", key, raw, default)
        return default


# 币种波动率参数配置（用于多币种差异化策略）
PAIR_VOLATILITY_PARAMS: dict[str, dict[str, Decimal]] = {
    "BTC/USDT": {
        "volatility_multiplier": Decimal("0.8"),  # BTC 波动相对较小
        "stop_loss_multiplier": Decimal("1.0"),
        "position_multiplier": Decimal("1.2"),  # 允许更大仓位
    },
    "ETH/USDT": {
        "volatility_multiplier": Decimal("0.9"),
        "stop_loss_multiplier": Decimal("1.0"),
        "position_multiplier": Decimal("1.1"),
    },
    "DOGE/USDT": {
        "volatility_multiplier": Decimal("1.3"),  # DOGE 波动较大
        "stop_loss_multiplier": Decimal("1.2"),
        "position_multiplier": Decimal("0.8"),  # 减小仓位
    },
    "SOL/USDT": {
        "volatility_multiplier": Decimal("1.1"),
        "stop_loss_multiplier": Decimal("1.1"),
        "position_multiplier": Decimal("0.9"),
    },
}


def get_pair_volatility_params(pair: str) -> dict[str, Decimal]:
    """获取特定交易对的波动率参数。

    Args:
        pair: 交易对名称

    Returns:
        该交易对的波动率参数配置
    """
    normalized_pair = pair.strip().upper()
    if "/" not in normalized_pair:
        if normalized_pair.endswith("USDT"):
            base = normalized_pair[:-4]
            normalized_pair = f"{base}/USDT"

    return PAIR_VOLATILITY_PARAMS.get(normalized_pair, {
        "volatility_multiplier": Decimal("1.0"),
        "stop_loss_multiplier": Decimal("1.0"),
        "position_multiplier": Decimal("1.0"),
    })


# 策略配置常量
MIN_ENTRY_SCORE = _read_env_decimal("QUANT_STRATEGY_MIN_ENTRY_SCORE", Decimal("0.60"))
TRAILING_STOP_TRIGGER = _read_env_decimal("QUANT_STRATEGY_TRAILING_STOP_TRIGGER", Decimal("0.02"))
TRAILING_STOP_DISTANCE = _read_env_decimal("QUANT_STRATEGY_TRAILING_STOP_DISTANCE", Decimal("0.01"))
PROFIT_EXIT_RATIO = _read_env_decimal("QUANT_STRATEGY_PROFIT_EXIT_RATIO", Decimal("0.05"))
MAX_HOLDING_HOURS = _read_env_int("QUANT_STRATEGY_MAX_HOLDING_HOURS", 48)
BASE_POSITION_RATIO = _read_env_decimal("QUANT_STRATEGY_BASE_POSITION_RATIO", Decimal("0.25"))
MAX_POSITION_RATIO = _read_env_decimal("QUANT_STRATEGY_MAX_POSITION_RATIO", Decimal("0.50"))
VOLATILITY_SCALE_FACTOR = _read_env_decimal("QUANT_STRATEGY_VOLATILITY_SCALE_FACTOR", Decimal("0.5"))

# 技术指标配置常量
RSI_OVERBUY_THRESHOLD = _read_env_decimal("QUANT_RSI_OVERBUY_THRESHOLD", Decimal("70"))
RSI_OVERSELL_THRESHOLD = _read_env_decimal("QUANT_RSI_OVERSELL_THRESHOLD", Decimal("30"))
RSI_PERIOD = _read_env_int("QUANT_RSI_PERIOD", 14)
MACD_FAST_PERIOD = _read_env_int("QUANT_MACD_FAST_PERIOD", 12)
MACD_SLOW_PERIOD = _read_env_int("QUANT_MACD_SLOW_PERIOD", 26)
MACD_SIGNAL_PERIOD = _read_env_int("QUANT_MACD_SIGNAL_PERIOD", 9)
VOLUME_TREND_PERIOD = _read_env_int("QUANT_VOLUME_TREND_PERIOD", 20)


@dataclass(slots=True)
class PositionState:
    """持仓状态追踪。"""
    symbol: str
    entry_price: Decimal
    entry_time: datetime
    quantity: Decimal
    side: str
    strategy_id: int | None = None
    signal_id: int | None = None
    initial_stop_price: Decimal = Decimal("0")
    trailing_stop_price: Decimal = Decimal("0")
    trailing_stop_active: bool = False
    peak_price: Decimal = Decimal("0")
    research_score: Decimal = Decimal("0")

    def to_dict(self) -> dict[str, object]:
        """把持仓状态转成字典。"""
        return {
            "symbol": self.symbol,
            "entry_price": str(self.entry_price),
            "entry_time": self.entry_time.isoformat(),
            "quantity": str(self.quantity),
            "side": self.side,
            "strategy_id": self.strategy_id,
            "signal_id": self.signal_id,
            "initial_stop_price": str(self.initial_stop_price),
            "trailing_stop_price": str(self.trailing_stop_price),
            "trailing_stop_active": self.trailing_stop_active,
            "peak_price": str(self.peak_price),
            "research_score": str(self.research_score),
        }


@dataclass(slots=True)
class EntryDecision:
    """入场决策结果。"""
    allowed: bool
    score: Decimal
    reason: str
    confidence: str
    trend_confirmed: bool
    research_aligned: bool
    suggested_position_ratio: Decimal
    rsi_value: Decimal | None = None
    rsi_signal: str = "neutral"
    macd_trend: str = "neutral"
    volume_signal: str = "neutral"
    edge_case_detected: bool = False
    model_suggestion_id: str | None = None
    model_suggestion_action: str | None = None
    model_suggestion_reasoning: str | None = None

    def to_dict(self) -> dict[str, object]:
        """把入场决策转成字典。"""
        return {
            "allowed": self.allowed,
            "score": str(self.score),
            "reason": self.reason,
            "confidence": self.confidence,
            "trend_confirmed": self.trend_confirmed,
            "research_aligned": self.research_aligned,
            "suggested_position_ratio": str(self.suggested_position_ratio),
            "rsi_value": str(self.rsi_value) if self.rsi_value is not None else None,
            "rsi_signal": self.rsi_signal,
            "macd_trend": self.macd_trend,
            "volume_signal": self.volume_signal,
            "edge_case_detected": self.edge_case_detected,
            "model_suggestion_id": self.model_suggestion_id,
            "model_suggestion_action": self.model_suggestion_action,
            "model_suggestion_reasoning": self.model_suggestion_reasoning,
        }


@dataclass(slots=True)
class ExitDecision:
    """退出决策结果。"""
    should_exit: bool
    reason: str
    current_pnl_pct: Decimal
    holding_hours: int
    trailing_stop_triggered: bool
    profit_target_reached: bool
    time_limit_reached: bool
    reverse_signal_detected: bool

    def to_dict(self) -> dict[str, object]:
        """把退出决策转成字典。"""
        return {
            "should_exit": self.should_exit,
            "reason": self.reason,
            "current_pnl_pct": str(self.current_pnl_pct),
            "holding_hours": self.holding_hours,
            "trailing_stop_triggered": self.trailing_stop_triggered,
            "profit_target_reached": self.profit_target_reached,
            "time_limit_reached": self.time_limit_reached,
            "reverse_signal_detected": self.reverse_signal_detected,
        }


@dataclass(slots=True)
class TrailingStopUpdate:
    """止损更新结果。"""
    new_stop_price: Decimal
    activated: bool
    peak_updated: bool
    previous_stop: Decimal

    def to_dict(self) -> dict[str, object]:
        """把止损更新转成字典。"""
        return {
            "new_stop_price": str(self.new_stop_price),
            "activated": self.activated,
            "peak_updated": self.peak_updated,
            "previous_stop": str(self.previous_stop),
        }


class StrategyEngineService:
    """真实交易策略引擎。"""

    def __init__(
        self,
        *,
        market_reader: MarketService | None = None,
        research_reader: Callable[[str], dict[str, object] | None] | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._market_reader = market_reader or MarketService()
        self._research_reader = research_reader or research_service.get_symbol_research
        self._settings = settings or Settings.from_env()
        self._position_states: dict[str, PositionState] = {}
        self._stop_loss_pct = Decimal("0.10")  # 默认10%止损

    def calculate_entry_score(
        self,
        symbol: str,
        *,
        signal_side: str = "long",
        signal_score: Decimal | None = None,
    ) -> EntryDecision:
        """计算入场评分。

        综合考虑：
        1. 研究层 score（主要依据）
        2. 趋势确认（EMA状态 + RSI/MACD/成交量）
        3. 波动率评估
        4. 技术指标信号（RSI、MACD、成交量）
        """
        normalized_symbol = symbol.strip().upper()
        normalized_side = signal_side.strip().lower()

        # 读取研究评分
        research_summary = self._research_reader(normalized_symbol)
        research_score = self._parse_research_score(research_summary)
        research_signal = self._parse_research_signal(research_summary)

        # 如果传入信号评分，使用它；否则使用研究评分
        effective_score = signal_score if signal_score is not None else research_score

        # 计算技术指标
        indicators = self._calculate_technical_indicators(
            symbol=normalized_symbol,
            side=normalized_side,
        )
        rsi_value = indicators.get("rsi_value")
        rsi_signal = str(indicators.get("rsi_signal", "neutral"))
        macd_trend = str(indicators.get("macd_trend", "neutral"))
        volume_signal = str(indicators.get("volume_signal", "neutral"))

        # 检查趋势确认（结合EMA、RSI、MACD、成交量）
        trend_confirmed = self._check_trend_confirmation_with_indicators(
            symbol=normalized_symbol,
            side=normalized_side,
            rsi_value=rsi_value,
            rsi_signal=rsi_signal,
            macd_trend=macd_trend,
            volume_signal=volume_signal,
        )

        # 检查研究信号是否与交易方向一致
        research_aligned = self._check_research_alignment(
            research_signal=research_signal,
            trade_side=normalized_side,
            research_score=research_score,
        )

        # 计算综合评分（加入技术指标权重）
        combined_score = self._calculate_combined_score_with_indicators(
            research_score=effective_score,
            trend_confirmed=trend_confirmed,
            research_aligned=research_aligned,
            rsi_signal=rsi_signal,
            macd_trend=macd_trend,
            volume_signal=volume_signal,
        )

        # 计算建议仓位比例
        volatility = self._estimate_volatility(symbol=normalized_symbol)
        suggested_position = self._calculate_position_size(
            score=combined_score,
            volatility=volatility,
        )

        # 边界场景检测和模型建议
        edge_case_detected = False
        model_suggestion_id = None
        model_suggestion_action = None
        model_suggestion_reasoning = None

        # 检测边界场景：评分在阈值附近或信号矛盾
        edge_analysis = model_suggestion_service.analyze_edge_case(
            score=combined_score,
            threshold=MIN_ENTRY_SCORE,
        )

        if edge_analysis.is_edge_case or (not trend_confirmed and research_aligned):
            edge_case_detected = True
            logger.info(
                "检测到边界场景: %s, score=%.4f, threshold=%.4f, trend_confirmed=%s, rsi=%s, macd=%s, vol=%s",
                normalized_symbol,
                float(combined_score),
                float(MIN_ENTRY_SCORE),
                trend_confirmed,
                rsi_signal,
                macd_trend,
                volume_signal,
            )

            # 准备上下文数据
            context_data = {
                "symbol": normalized_symbol,
                "score": float(combined_score),
                "threshold": float(MIN_ENTRY_SCORE),
                "action_type": "entry",
                "side": normalized_side,
                "trend_confirmed": trend_confirmed,
                "research_aligned": research_aligned,
                "volatility": float(volatility),
                "market_signals": {
                    "research_score": float(effective_score),
                    "research_signal": research_signal,
                    "rsi_value": float(rsi_value) if rsi_value is not None else None,
                    "rsi_signal": rsi_signal,
                    "macd_trend": macd_trend,
                    "volume_signal": volume_signal,
                },
                "conflicting_signals": [],
            }

            if not trend_confirmed:
                context_data["conflicting_signals"].append({
                    "type": "trend_mismatch",
                    "description": f"价格趋势未确认 (RSI={rsi_signal}, MACD={macd_trend}, VOL={volume_signal})",
                })

            # 获取模型建议
            suggestion = model_suggestion_service.get_model_suggestion(context_data)
            if suggestion is not None:
                model_suggestion_id = suggestion.suggestion_id
                model_suggestion_action = suggestion.action
                model_suggestion_reasoning = suggestion.reasoning

                logger.info(
                    "模型建议: id=%s, action=%s, confidence=%s, reasoning=%s",
                    suggestion.suggestion_id,
                    suggestion.action,
                    suggestion.confidence,
                    suggestion.reasoning,
                )

        # 判断是否允许入场
        allowed = combined_score >= MIN_ENTRY_SCORE
        if not allowed:
            reason = f"综合评分 {combined_score:.4f} 未达到入场阈值 {MIN_ENTRY_SCORE:.4f}"
            confidence = "low"
        elif not trend_confirmed:
            reason = f"趋势未确认 (RSI={rsi_signal}, MACD={macd_trend}, VOL={volume_signal})"
            confidence = "medium"
            allowed = False
        elif not research_aligned:
            reason = "研究信号与交易方向不一致"
            confidence = "low"
        else:
            reason = f"入场条件满足 (RSI={rsi_signal}, MACD={macd_trend}, VOL={volume_signal})"
            confidence = "high"

        return EntryDecision(
            allowed=allowed,
            score=combined_score,
            reason=reason,
            confidence=confidence,
            trend_confirmed=trend_confirmed,
            research_aligned=research_aligned,
            suggested_position_ratio=suggested_position,
            rsi_value=rsi_value,
            rsi_signal=rsi_signal,
            macd_trend=macd_trend,
            volume_signal=volume_signal,
            edge_case_detected=edge_case_detected,
            model_suggestion_id=model_suggestion_id,
            model_suggestion_action=model_suggestion_action,
            model_suggestion_reasoning=model_suggestion_reasoning,
        )

    def calculate_position_size(
        self,
        symbol: str,
        *,
        score: Decimal,
        volatility: Decimal | None = None,
    ) -> Decimal:
        """计算仓位大小。

        基于评分和波动率动态调整仓位。
        支持不同币种的差异化参数配置。
        """
        normalized_symbol = symbol.strip().upper()
        if volatility is None:
            volatility = self._estimate_volatility(symbol=normalized_symbol)

        # 获取币种特定的波动率参数
        pair_params = get_pair_volatility_params(normalized_symbol)
        pair_position_multiplier = pair_params["position_multiplier"]
        pair_volatility_multiplier = pair_params["volatility_multiplier"]

        return self._calculate_position_size(
            score=score,
            volatility=volatility,
            pair_position_multiplier=pair_position_multiplier,
            pair_volatility_multiplier=pair_volatility_multiplier,
        )

    def _calculate_position_size(
        self,
        *,
        score: Decimal,
        volatility: Decimal,
        pair_position_multiplier: Decimal = Decimal("1.0"),
        pair_volatility_multiplier: Decimal = Decimal("1.0"),
    ) -> Decimal:
        """内部仓位计算逻辑。

        Args:
            score: 评分
            volatility: 波动率
            pair_position_multiplier: 币种特定的仓位乘数
            pair_volatility_multiplier: 币种特定的波动率乘数
        """
        # 基础仓位比例
        base_position = BASE_POSITION_RATIO

        # 根据评分调整仓位（0.7以下不入场，0.7-0.8标准仓位，0.8+加仓）
        if score < MIN_ENTRY_SCORE:
            return Decimal("0")
        elif score < Decimal("0.80"):
            score_multiplier = Decimal("1.0")
        elif score < Decimal("0.90"):
            score_multiplier = Decimal("1.2")
        else:
            score_multiplier = Decimal("1.5")

        # 根据波动率调整仓位（高波动降仓，低波动加仓）
        # 应用币种特定的波动率乘数
        adjusted_volatility = volatility * pair_volatility_multiplier

        if adjusted_volatility > Decimal("0.05"):  # 5%以上波动率
            volatility_multiplier = Decimal("0.6")
        elif adjusted_volatility > Decimal("0.03"):  # 3-5%波动率
            volatility_multiplier = Decimal("0.8")
        elif adjusted_volatility < Decimal("0.01"):  # 1%以下波动率
            volatility_multiplier = Decimal("1.2")
        else:
            volatility_multiplier = Decimal("1.0")

        # 最终仓位（应用币种特定的仓位乘数）
        final_position = base_position * score_multiplier * volatility_multiplier * pair_position_multiplier
        final_position = min(final_position, MAX_POSITION_RATIO)
        final_position = max(final_position, Decimal("0"))

        return final_position.quantize(Decimal("0.01"))

    def update_trailing_stop(
        self,
        symbol: str,
        current_price: Decimal,
        *,
        position: PositionState | None = None,
    ) -> TrailingStopUpdate:
        """更新追踪止损。

        当盈利超过触发阈值后，启用追踪止损。
        """
        normalized_symbol = symbol.strip().upper()

        if position is None:
            position = self._position_states.get(normalized_symbol)
        if position is None:
            return TrailingStopUpdate(
                new_stop_price=Decimal("0"),
                activated=False,
                peak_updated=False,
                previous_stop=Decimal("0"),
            )

        entry_price = position.entry_price
        previous_stop = position.trailing_stop_price

        # 计算当前盈亏比例
        pnl_pct = (current_price - entry_price) / entry_price

        # 更新峰值价格
        peak_updated = False
        if current_price > position.peak_price:
            position.peak_price = current_price
            peak_updated = True

        # 检查是否触发追踪止损
        if not position.trailing_stop_active:
            if pnl_pct >= TRAILING_STOP_TRIGGER:
                position.trailing_stop_active = True
                logger.info(
                    "追踪止损已激活: %s, 盈利 %.2f%% >= 触发阈值 %.2f%%",
                    normalized_symbol,
                    float(pnl_pct * 100),
                    float(TRAILING_STOP_TRIGGER * 100),
                )

        # 计算新的止损价格
        new_stop_price = previous_stop
        activated = position.trailing_stop_active

        if activated:
            # 追踪止损：峰值价格 - 追踪距离
            new_stop_price = position.peak_price * (Decimal("1") - TRAILING_STOP_DISTANCE)
            position.trailing_stop_price = new_stop_price

        return TrailingStopUpdate(
            new_stop_price=new_stop_price,
            activated=activated,
            peak_updated=peak_updated,
            previous_stop=previous_stop,
        )

    def check_exit_conditions(
        self,
        symbol: str,
        current_price: Decimal,
        *,
        position: PositionState | None = None,
        current_time: datetime | None = None,
    ) -> ExitDecision:
        """检查退出条件。

        检查：
        1. 追踪止损触发
        2. 盈利目标达成
        3. 持仓时间限制
        4. 反向信号检测
        """
        normalized_symbol = symbol.strip().upper()

        if position is None:
            position = self._position_states.get(normalized_symbol)
        if position is None:
            return ExitDecision(
                should_exit=False,
                reason="无持仓",
                current_pnl_pct=Decimal("0"),
                holding_hours=0,
                trailing_stop_triggered=False,
                profit_target_reached=False,
                time_limit_reached=False,
                reverse_signal_detected=False,
            )

        if current_time is None:
            current_time = datetime.now(timezone.utc)

        entry_price = position.entry_price
        entry_time = position.entry_time

        # 计算当前盈亏比例
        pnl_pct = (current_price - entry_price) / entry_price

        # 计算持仓时间（小时）
        holding_duration = current_time - entry_time
        holding_hours = int(holding_duration.total_seconds() / 3600)

        # 检查追踪止损
        trailing_stop_triggered = False
        stop_price = position.trailing_stop_price if position.trailing_stop_active else position.initial_stop_price
        if stop_price > Decimal("0") and current_price <= stop_price:
            trailing_stop_triggered = True

        # 检查盈利目标
        profit_target_reached = pnl_pct >= PROFIT_EXIT_RATIO

        # 检查时间限制
        time_limit_reached = holding_hours >= MAX_HOLDING_HOURS

        # 检查反向信号
        reverse_signal_detected = self._detect_reverse_signal(
            symbol=normalized_symbol,
            position_side=position.side,
        )

        # 决定是否退出
        should_exit = False
        reason = "继续持有"

        if trailing_stop_triggered:
            should_exit = True
            reason = f"追踪止损触发: 当前价格 {current_price:.4f} <= 止损价格 {stop_price:.4f}"
        elif profit_target_reached:
            should_exit = True
            reason = f"盈利目标达成: 盈利 {pnl_pct:.2%} >= 目标 {PROFIT_EXIT_RATIO:.2%}"
        elif time_limit_reached:
            should_exit = True
            reason = f"持仓时间超限: {holding_hours} 小时 >= 上限 {MAX_HOLDING_HOURS} 小时"
        elif reverse_signal_detected:
            should_exit = True
            reason = "检测到反向信号"

        return ExitDecision(
            should_exit=should_exit,
            reason=reason,
            current_pnl_pct=pnl_pct,
            holding_hours=holding_hours,
            trailing_stop_triggered=trailing_stop_triggered,
            profit_target_reached=profit_target_reached,
            time_limit_reached=time_limit_reached,
            reverse_signal_detected=reverse_signal_detected,
        )

    def register_position(
        self,
        symbol: str,
        entry_price: Decimal,
        quantity: Decimal,
        side: str,
        *,
        strategy_id: int | None = None,
        signal_id: int | None = None,
        research_score: Decimal | None = None,
        initial_stop_pct: Decimal | None = None,
    ) -> PositionState:
        """注册新持仓并设置初始止损。"""
        normalized_symbol = symbol.strip().upper()
        normalized_side = side.strip().lower()

        # 计算初始止损价格
        if initial_stop_pct is None:
            initial_stop_pct = self._stop_loss_pct
        if normalized_side == "long":
            initial_stop_price = entry_price * (Decimal("1") - initial_stop_pct)
        else:
            initial_stop_price = entry_price * (Decimal("1") + initial_stop_pct)

        # 获取研究评分
        if research_score is None:
            research_summary = self._research_reader(normalized_symbol)
            research_score = self._parse_research_score(research_summary)

        position = PositionState(
            symbol=normalized_symbol,
            entry_price=entry_price,
            entry_time=datetime.now(timezone.utc),
            quantity=quantity,
            side=normalized_side,
            strategy_id=strategy_id,
            signal_id=signal_id,
            initial_stop_price=initial_stop_price,
            trailing_stop_price=initial_stop_price,
            trailing_stop_active=False,
            peak_price=entry_price,
            research_score=research_score or Decimal("0"),
        )

        self._position_states[normalized_symbol] = position
        logger.info(
            "注册持仓: %s %s @ %s, 初始止损 %s",
            normalized_side,
            normalized_symbol,
            str(entry_price),
            str(initial_stop_price),
        )

        return position

    def remove_position(self, symbol: str) -> PositionState | None:
        """移除持仓记录。"""
        normalized_symbol = symbol.strip().upper()
        position = self._position_states.pop(normalized_symbol, None)
        if position is not None:
            logger.info("移除持仓记录: %s", normalized_symbol)
        return position

    def get_position(self, symbol: str) -> PositionState | None:
        """获取持仓状态。"""
        return self._position_states.get(symbol.strip().upper())

    def get_all_positions(self) -> list[PositionState]:
        """获取所有持仓。"""
        return list(self._position_states.values())

    def sync_positions_from_freqtrade(self) -> list[PositionState]:
        """从 Freqtrade 同步持仓状态。"""
        snapshot = freqtrade_client.get_snapshot()
        positions = list(snapshot.positions or [])

        synced_positions: list[PositionState] = []
        for pos in positions:
            symbol = str(pos.get("symbol", "")).strip().upper()
            if not symbol:
                continue

            entry_price = self._parse_decimal(pos.get("entryPrice"))
            quantity = self._parse_decimal(pos.get("quantity"))
            side = str(pos.get("side", "long")).strip().lower()

            if entry_price is None or quantity is None:
                continue

            # 如果已存在记录，更新；否则创建新记录
            existing = self._position_states.get(symbol)
            if existing is not None:
                existing.quantity = quantity
                synced_positions.append(existing)
            else:
                new_position = self.register_position(
                    symbol=symbol,
                    entry_price=entry_price,
                    quantity=quantity,
                    side=side,
                )
                synced_positions.append(new_position)

        return synced_positions

    def calculate_dynamic_stop_loss(
        self,
        symbol: str,
        *,
        score: Decimal | None = None,
        volatility: Decimal | None = None,
    ) -> Decimal:
        """计算动态止损比例。

        根据评分和波动率调整止损距离。
        支持不同币种的差异化参数配置。
        """
        normalized_symbol = symbol.strip().upper()

        if score is None:
            research_summary = self._research_reader(normalized_symbol)
            score = self._parse_research_score(research_summary)

        if volatility is None:
            volatility = self._estimate_volatility(symbol=normalized_symbol)

        # 获取币种特定的波动率参数
        pair_params = get_pair_volatility_params(normalized_symbol)
        pair_stop_loss_multiplier = pair_params["stop_loss_multiplier"]
        pair_volatility_multiplier = pair_params["volatility_multiplier"]

        # 基础止损比例
        base_stop = self._stop_loss_pct

        # 高评分允许更宽止损（更有信心）
        if score >= Decimal("0.80"):
            stop_multiplier = Decimal("1.2")  # 放宽止损
        elif score >= Decimal("0.70"):
            stop_multiplier = Decimal("1.0")  # 标准止损
        else:
            stop_multiplier = Decimal("0.8")  # 收紧止损

        # 高波动需要更宽止损（应用币种特定的波动率乘数）
        adjusted_volatility = volatility * pair_volatility_multiplier
        if adjusted_volatility > Decimal("0.05"):
            volatility_multiplier = Decimal("1.3")
        elif adjusted_volatility > Decimal("0.03"):
            volatility_multiplier = Decimal("1.1")
        else:
            volatility_multiplier = Decimal("1.0")

        # 最终止损（应用币种特定的止损乘数）
        final_stop = base_stop * stop_multiplier * volatility_multiplier * pair_stop_loss_multiplier
        final_stop = min(final_stop, Decimal("0.20"))  # 最大20%止损
        final_stop = max(final_stop, Decimal("0.05"))  # 最小5%止损

        return final_stop.quantize(Decimal("0.01"))

    def monitor_all_positions(self) -> list[dict[str, object]]:
        """监控所有持仓，检查退出条件。"""
        results: list[dict[str, object]] = []
        current_time = datetime.now(timezone.utc)

        for position in self._position_states.values():
            # 获取当前价格
            current_price = self._get_current_price(position.symbol)
            if current_price is None:
                continue

            # 更新追踪止损
            stop_update = self.update_trailing_stop(
                symbol=position.symbol,
                current_price=current_price,
                position=position,
            )

            # 检查退出条件
            exit_decision = self.check_exit_conditions(
                symbol=position.symbol,
                current_price=current_price,
                position=position,
                current_time=current_time,
            )

            results.append({
                "symbol": position.symbol,
                "position": position.to_dict(),
                "current_price": str(current_price),
                "stop_update": stop_update.to_dict(),
                "exit_decision": exit_decision.to_dict(),
            })

        return results

    def _parse_research_score(self, research_summary: dict[str, object] | None) -> Decimal:
        """解析研究评分。"""
        if research_summary is None:
            return Decimal("0")
        raw_score = research_summary.get("score")
        if raw_score is None:
            return Decimal("0")
        try:
            score = Decimal(str(raw_score))
            if not score.is_finite():
                return Decimal("0")
            return score
        except (InvalidOperation, ValueError):
            return Decimal("0")

    def _parse_research_signal(self, research_summary: dict[str, object] | None) -> str:
        """解析研究信号方向。"""
        if research_summary is None:
            return ""
        return str(research_summary.get("signal", "")).strip().lower()

    def _check_trend_confirmation(
        self,
        *,
        symbol: str,
        side: str,
    ) -> bool:
        """检查趋势确认（基于 EMA）。"""
        try:
            chart = self._market_reader.get_symbol_chart(
                symbol=symbol,
                interval="4h",
                limit=50,
            )
            candles = list(chart.get("items", []))
            if len(candles) < 20:
                return False

            # 计算 EMA20 和 EMA55
            closes = [self._parse_decimal(c.get("close")) for c in candles[-20:]]
            if any(c is None for c in closes):
                return False

            ema20 = self._calculate_ema([c for c in closes if c is not None], 20)
            if ema20 is None:
                return False

            current_close = closes[-1]
            if current_close is None:
                return False

            # 趋势确认逻辑
            if side == "long":
                # 做多需要价格在 EMA20 之上
                return current_close > ema20
            else:
                # 做空需要价格在 EMA20 之下
                return current_close < ema20
        except Exception as exc:
            logger.warning("趋势确认检查失败: %s", exc)
            return False

    def _check_research_alignment(
        self,
        *,
        research_signal: str,
        trade_side: str,
        research_score: Decimal,
    ) -> bool:
        """检查研究信号是否与交易方向一致。"""
        if research_score < MIN_ENTRY_SCORE:
            return False

        if not research_signal:
            # 无研究信号时，仅看评分
            return research_score >= MIN_ENTRY_SCORE

        return research_signal == trade_side

    def _calculate_combined_score(
        self,
        *,
        research_score: Decimal,
        trend_confirmed: bool,
        research_aligned: bool,
    ) -> Decimal:
        """计算综合评分。"""
        # 研究评分权重 80%，趋势确认权重 20%
        base_score = research_score * Decimal("0.80")

        # 趋势确认加成
        trend_bonus = Decimal("0.20") if trend_confirmed else Decimal("0")

        # 研究一致加成
        alignment_bonus = Decimal("0.05") if research_aligned else Decimal("0")

        combined = base_score + trend_bonus + alignment_bonus
        return min(combined, Decimal("1.0"))

    def _estimate_volatility(self, symbol: str) -> Decimal:
        """估算波动率。"""
        try:
            chart = self._market_reader.get_symbol_chart(
                symbol=symbol,
                interval="1h",
                limit=24,
            )
            candles = list(chart.get("items", []))
            if len(candles) < 12:
                return Decimal("0.03")  # 默认3%波动率

            # 计算最近12小时的波动率
            closes = []
            for c in candles[-12:]:
                close = self._parse_decimal(c.get("close"))
                if close is not None:
                    closes.append(close)

            if len(closes) < 2:
                return Decimal("0.03")

            # 计算价格变动范围
            min_close = min(closes)
            max_close = max(closes)
            avg_close = sum(closes) / len(closes)

            volatility = (max_close - min_close) / avg_close
            return volatility.quantize(Decimal("0.0001"))
        except Exception as exc:
            logger.warning("波动率估算失败: %s", exc)
            return Decimal("0.03")

    def _detect_reverse_signal(
        self,
        *,
        symbol: str,
        position_side: str,
    ) -> bool:
        """检测反向信号。"""
        research_summary = self._research_reader(symbol)
        if research_summary is None:
            return False

        research_signal = self._parse_research_signal(research_summary)
        research_score = self._parse_research_score(research_summary)

        if not research_signal:
            return False

        # 强反向信号检测
        if position_side == "long":
            # 做多持仓时，检测到做空信号且评分低于40%
            return research_signal == "short" and research_score < Decimal("0.40")
        else:
            # 做空持仓时，检测到做多信号且评分高于60%
            return research_signal == "long" and research_score > Decimal("0.60")

    def _get_current_price(self, symbol: str) -> Decimal | None:
        """获取当前价格。"""
        try:
            chart = self._market_reader.get_symbol_chart(
                symbol=symbol,
                interval="1m",
                limit=1,
            )
            candles = list(chart.get("items", []))
            if not candles:
                return None

            return self._parse_decimal(candles[0].get("close"))
        except Exception as exc:
            logger.warning("获取当前价格失败: %s", exc)
            return None

    def _parse_decimal(self, value: object) -> Decimal | None:
        """解析 Decimal。"""
        if value is None:
            return None
        try:
            parsed = Decimal(str(value))
            if not parsed.is_finite():
                return None
            return parsed
        except (InvalidOperation, ValueError):
            return None

    def _calculate_ema(self, values: list[Decimal], period: int) -> Decimal | None:
        """计算 EMA。"""
        if len(values) < period:
            return None

        k = Decimal("2") / Decimal(period + 1)
        ema = values[0]

        for value in values[1:]:
            ema = value * k + ema * (Decimal("1") - k)

        return ema

    def _calculate_technical_indicators(
        self,
        *,
        symbol: str,
        side: str,
    ) -> dict[str, Decimal | str | None]:
        """计算技术指标（RSI、MACD、成交量趋势）。"""
        result: dict[str, Decimal | str | None] = {
            "rsi_value": None,
            "rsi_signal": "neutral",
            "macd_trend": "neutral",
            "volume_signal": "neutral",
        }

        try:
            # 获取足够的K线数据用于计算技术指标
            chart = self._market_reader.get_symbol_chart(
                symbol=symbol,
                interval="4h",
                limit=100,  # 需要足够的数据来计算MACD
            )
            candles = list(chart.get("items", []))

            if len(candles) < 35:  # MACD需要至少26+9的数据
                logger.warning("技术指标计算: %s 数据不足 (%d根)", symbol, len(candles))
                return result

            # 解析收盘价和成交量
            closes: list[Decimal] = []
            volumes: list[Decimal] = []
            for c in candles:
                close = self._parse_decimal(c.get("close"))
                volume = self._parse_decimal(c.get("volume"))
                if close is not None:
                    closes.append(close)
                if volume is not None:
                    volumes.append(volume)

            if len(closes) < 35:
                return result

            # 计算RSI
            rsi_value = calculate_rsi(closes, RSI_PERIOD)
            result["rsi_value"] = rsi_value

            # RSI信号判断
            if side == "long":
                # 做多时，RSI在超卖区域为买入信号，超买区域为风险
                if rsi_value < RSI_OVERSELL_THRESHOLD:
                    result["rsi_signal"] = "oversold_buy"  # 超卖，买入机会
                elif rsi_value > RSI_OVERBUY_THRESHOLD:
                    result["rsi_signal"] = "overbought_risk"  # 超买，风险警告
                else:
                    result["rsi_signal"] = "neutral"
            else:
                # 做空时，RSI在超买区域为卖出信号，超卖区域为风险
                if rsi_value > RSI_OVERBUY_THRESHOLD:
                    result["rsi_signal"] = "overbought_sell"  # 超买，卖出机会
                elif rsi_value < RSI_OVERSELL_THRESHOLD:
                    result["rsi_signal"] = "oversold_risk"  # 超卖，风险警告
                else:
                    result["rsi_signal"] = "neutral"

            # 计算MACD
            macd_result = calculate_macd(
                closes,
                MACD_FAST_PERIOD,
                MACD_SLOW_PERIOD,
                MACD_SIGNAL_PERIOD,
            )
            result["macd_trend"] = str(macd_result.get("trend", "neutral"))

            # 计算成交量趋势
            if len(volumes) >= VOLUME_TREND_PERIOD:
                volume_result = calculate_volume_trend(
                    volumes,
                    closes,
                    VOLUME_TREND_PERIOD,
                )
                result["volume_signal"] = str(volume_result.get("price_volume_alignment", "neutral"))
            else:
                result["volume_signal"] = "neutral"

            logger.debug(
                "技术指标: %s RSI=%.2f(%s) MACD=%s VOL=%s",
                symbol,
                float(rsi_value),
                result["rsi_signal"],
                result["macd_trend"],
                result["volume_signal"],
            )

            return result

        except Exception as exc:
            logger.warning("技术指标计算失败: %s - %s", symbol, exc)
            return result

    def _check_trend_confirmation_with_indicators(
        self,
        *,
        symbol: str,
        side: str,
        rsi_value: Decimal | None,
        rsi_signal: str,
        macd_trend: str,
        volume_signal: str,
    ) -> bool:
        """结合技术指标检查趋势确认。

        综合考虑：
        1. EMA趋势（基础）
        2. RSI是否在合理区间
        3. MACD趋势方向
        4. 成交量是否配合

        Returns:
            True 如果趋势确认
        """
        # 首先检查基础EMA趋势
        ema_confirmed = self._check_trend_confirmation(symbol=symbol, side=side)

        # 如果EMA趋势未确认，直接返回False
        if not ema_confirmed:
            return False

        # 计算技术指标得分
        indicator_score = 0
        total_indicators = 3

        # RSI信号检查
        if rsi_value is not None:
            if side == "long":
                # 做多时，RSI不在超买区域（>70）为正面信号
                if rsi_signal in ("oversold_buy", "neutral"):
                    indicator_score += 1
                elif rsi_signal == "overbought_risk":
                    # RSI超买时，趋势可能不稳固
                    indicator_score += 0
            else:
                # 做空时，RSI不在超卖区域（<30）为正面信号
                if rsi_signal in ("overbought_sell", "neutral"):
                    indicator_score += 1
                elif rsi_signal == "oversold_risk":
                    indicator_score += 0
        else:
            indicator_score += 0.5  # 数据不足，给中性分

        # MACD趋势检查
        if side == "long":
            if macd_trend == "bullish":
                indicator_score += 1
            elif macd_trend == "neutral":
                indicator_score += 0.5
            else:
                indicator_score += 0
        else:
            if macd_trend == "bearish":
                indicator_score += 1
            elif macd_trend == "neutral":
                indicator_score += 0.5
            else:
                indicator_score += 0

        # 成交量检查
        if volume_signal in ("bullish_volume", "bearish_volume"):
            # 量价配合
            if side == "long" and volume_signal == "bullish_volume":
                indicator_score += 1
            elif side == "short" and volume_signal == "bearish_volume":
                indicator_score += 1
            else:
                # 量价背离
                indicator_score += 0.3
        elif volume_signal == "normal_volume":
            indicator_score += 0.5
        else:
            indicator_score += 0.5

        # 计算综合指标得分比例
        indicator_ratio = indicator_score / total_indicators

        # 需要至少2/3的指标支持才能确认趋势
        # 即 indicator_ratio >= 0.67
        return indicator_ratio >= Decimal("0.67")

    def _calculate_combined_score_with_indicators(
        self,
        *,
        research_score: Decimal,
        trend_confirmed: bool,
        research_aligned: bool,
        rsi_signal: str,
        macd_trend: str,
        volume_signal: str,
    ) -> Decimal:
        """计算综合评分，加入技术指标权重。"""
        # 研究评分权重 60%
        base_score = research_score * Decimal("0.60")

        # 趋势确认权重 20%
        trend_bonus = Decimal("0.20") if trend_confirmed else Decimal("0")

        # 研究一致权重 5%
        alignment_bonus = Decimal("0.05") if research_aligned else Decimal("0")

        # 技术指标权重 15%（分散到RSI、MACD、成交量各5%）
        indicator_bonus = Decimal("0")

        # RSI加分（5%）
        if rsi_signal in ("oversold_buy", "overbought_sell"):
            indicator_bonus += Decimal("0.05")
        elif rsi_signal == "neutral":
            indicator_bonus += Decimal("0.02")

        # MACD加分（5%）
        if macd_trend == "bullish" or macd_trend == "bearish":
            indicator_bonus += Decimal("0.05")
        elif macd_trend == "neutral":
            indicator_bonus += Decimal("0.02")

        # 成交量加分（5%）
        if volume_signal in ("bullish_volume", "bearish_volume"):
            indicator_bonus += Decimal("0.05")
        elif volume_signal in ("normal_volume", "neutral"):
            indicator_bonus += Decimal("0.02")

        combined = base_score + trend_bonus + alignment_bonus + indicator_bonus
        return min(combined, Decimal("1.0"))


# 单例实例
strategy_engine_service = StrategyEngineService()