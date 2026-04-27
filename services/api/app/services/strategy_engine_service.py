"""真实交易策略引擎服务。

这个文件负责实现核心策略逻辑：
- 入场评分计算（基于研究score、趋势确认）
- 仓位大小计算（基于score和波动率）
- 动态止损追踪
- 退出条件检查（盈亏比、时间、反向信号）
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Callable

from services.api.app.adapters.freqtrade.client import freqtrade_client
from services.api.app.core.settings import Settings
from services.api.app.services.market_service import MarketService
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


# 策略配置常量
MIN_ENTRY_SCORE = _read_env_decimal("QUANT_STRATEGY_MIN_ENTRY_SCORE", Decimal("0.70"))
TRAILING_STOP_TRIGGER = _read_env_decimal("QUANT_STRATEGY_TRAILING_STOP_TRIGGER", Decimal("0.02"))
TRAILING_STOP_DISTANCE = _read_env_decimal("QUANT_STRATEGY_TRAILING_STOP_DISTANCE", Decimal("0.01"))
PROFIT_EXIT_RATIO = _read_env_decimal("QUANT_STRATEGY_PROFIT_EXIT_RATIO", Decimal("0.05"))
MAX_HOLDING_HOURS = _read_env_int("QUANT_STRATEGY_MAX_HOLDING_HOURS", 48)
BASE_POSITION_RATIO = _read_env_decimal("QUANT_STRATEGY_BASE_POSITION_RATIO", Decimal("0.25"))
MAX_POSITION_RATIO = _read_env_decimal("QUANT_STRATEGY_MAX_POSITION_RATIO", Decimal("0.50"))
VOLATILITY_SCALE_FACTOR = _read_env_decimal("QUANT_STRATEGY_VOLATILITY_SCALE_FACTOR", Decimal("0.5"))


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
        2. 趋势确认（EMA状态）
        3. 波动率评估
        """
        normalized_symbol = symbol.strip().upper()
        normalized_side = signal_side.strip().lower()

        # 读取研究评分
        research_summary = self._research_reader(normalized_symbol)
        research_score = self._parse_research_score(research_summary)
        research_signal = self._parse_research_signal(research_summary)

        # 如果传入信号评分，使用它；否则使用研究评分
        effective_score = signal_score if signal_score is not None else research_score

        # 检查趋势确认
        trend_confirmed = self._check_trend_confirmation(
            symbol=normalized_symbol,
            side=normalized_side,
        )

        # 检查研究信号是否与交易方向一致
        research_aligned = self._check_research_alignment(
            research_signal=research_signal,
            trade_side=normalized_side,
            research_score=research_score,
        )

        # 计算综合评分
        combined_score = self._calculate_combined_score(
            research_score=effective_score,
            trend_confirmed=trend_confirmed,
            research_aligned=research_aligned,
        )

        # 计算建议仓位比例
        volatility = self._estimate_volatility(symbol=normalized_symbol)
        suggested_position = self._calculate_position_size(
            score=combined_score,
            volatility=volatility,
        )

        # 判断是否允许入场
        allowed = combined_score >= MIN_ENTRY_SCORE
        if not allowed:
            reason = f"综合评分 {combined_score:.4f} 未达到入场阈值 {MIN_ENTRY_SCORE:.4f}"
            confidence = "low"
        elif not trend_confirmed:
            reason = "趋势未确认，建议观望"
            confidence = "medium"
            allowed = False
        elif not research_aligned:
            reason = "研究信号与交易方向不一致"
            confidence = "low"
        else:
            reason = "入场条件满足"
            confidence = "high"

        return EntryDecision(
            allowed=allowed,
            score=combined_score,
            reason=reason,
            confidence=confidence,
            trend_confirmed=trend_confirmed,
            research_aligned=research_aligned,
            suggested_position_ratio=suggested_position,
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
        """
        if volatility is None:
            volatility = self._estimate_volatility(symbol=symbol.strip().upper())

        return self._calculate_position_size(score=score, volatility=volatility)

    def _calculate_position_size(
        self,
        *,
        score: Decimal,
        volatility: Decimal,
    ) -> Decimal:
        """内部仓位计算逻辑。"""
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
        if volatility > Decimal("0.05"):  # 5%以上波动率
            volatility_multiplier = Decimal("0.6")
        elif volatility > Decimal("0.03"):  # 3-5%波动率
            volatility_multiplier = Decimal("0.8")
        elif volatility < Decimal("0.01"):  # 1%以下波动率
            volatility_multiplier = Decimal("1.2")
        else:
            volatility_multiplier = Decimal("1.0")

        # 最终仓位
        final_position = base_position * score_multiplier * volatility_multiplier
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
        """
        normalized_symbol = symbol.strip().upper()

        if score is None:
            research_summary = self._research_reader(normalized_symbol)
            score = self._parse_research_score(research_summary)

        if volatility is None:
            volatility = self._estimate_volatility(symbol=normalized_symbol)

        # 基础止损比例
        base_stop = self._stop_loss_pct

        # 高评分允许更宽止损（更有信心）
        if score >= Decimal("0.80"):
            stop_multiplier = Decimal("1.2")  # 放宽止损
        elif score >= Decimal("0.70"):
            stop_multiplier = Decimal("1.0")  # 标准止损
        else:
            stop_multiplier = Decimal("0.8")  # 收紧止损

        # 高波动需要更宽止损
        if volatility > Decimal("0.05"):
            volatility_multiplier = Decimal("1.3")
        elif volatility > Decimal("0.03"):
            volatility_multiplier = Decimal("1.1")
        else:
            volatility_multiplier = Decimal("1.0")

        final_stop = base_stop * stop_multiplier * volatility_multiplier
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
        # 研究评分权重 70%，趋势确认权重 30%
        base_score = research_score * Decimal("0.70")

        # 趋势确认加成
        trend_bonus = Decimal("0.30") if trend_confirmed else Decimal("0")

        # 研究一致加成
        alignment_bonus = Decimal("0.10") if research_aligned else Decimal("0")

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


# 单例实例
strategy_engine_service = StrategyEngineService()