"""仓位管理服务。

实现动态仓位分配、最大回撤限制机制和仓位计算算法。
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    """风险等级。"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class PositionStatus(Enum):
    """仓位状态。"""

    NORMAL = "normal"
    WARNING = "warning"
    DRAWDOWN_LIMIT = "drawdown_limit"
    TRADING_PAUSED = "trading_paused"


@dataclass(slots=True)
class PositionConfig:
    """仓位管理配置。"""

    max_drawdown_pct: Decimal = Decimal("15")
    position_risk_pct: Decimal = Decimal("2")
    max_position_count: int = 4
    base_capital: Decimal = Decimal("10000")
    kelly_enabled: bool = False
    kelly_fraction: Decimal = Decimal("0.5")
    trading_paused_on_drawdown: bool = True
    drawdown_alert_threshold: Decimal = Decimal("10")
    risk_levels: dict[str, dict[str, Any]] = field(default_factory=dict)

    @classmethod
    def from_json(cls, path: str | Path | None = None) -> "PositionConfig":
        """从JSON配置文件读取配置。"""
        if path is None:
            path = Path(__file__).parent.parent.parent.parent.parent / "data" / "config" / "position_config.json"

        path = Path(path)
        if not path.exists():
            logger.warning("Position config file not found at %s, using defaults", path)
            return cls()

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to load position config: %s, using defaults", exc)
            return cls()

        risk_levels = data.get("risk_levels", {})

        return cls(
            max_drawdown_pct=_parse_decimal(data.get("max_drawdown_pct"), Decimal("15")),
            position_risk_pct=_parse_decimal(data.get("position_risk_pct"), Decimal("2")),
            max_position_count=int(data.get("max_position_count", 4)),
            base_capital=_parse_decimal(data.get("base_capital"), Decimal("10000")),
            kelly_enabled=bool(data.get("kelly_enabled", False)),
            kelly_fraction=_parse_decimal(data.get("kelly_fraction"), Decimal("0.5")),
            trading_paused_on_drawdown=bool(data.get("trading_paused_on_drawdown", True)),
            drawdown_alert_threshold=_parse_decimal(data.get("drawdown_alert_threshold"), Decimal("10")),
            risk_levels=risk_levels,
        )


@dataclass(slots=True)
class PositionSuggestion:
    """仓位建议。"""

    symbol: str
    suggested_size: Decimal
    risk_amount: Decimal
    position_pct: Decimal
    method: str
    reason: str
    stop_loss_price: Decimal | None = None
    entry_price: Decimal | None = None
    calculated_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "suggested_size": str(self.suggested_size.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)),
            "risk_amount": str(self.risk_amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
            "position_pct": str(self.position_pct.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
            "method": self.method,
            "reason": self.reason,
            "stop_loss_price": str(self.stop_loss_price) if self.stop_loss_price else None,
            "entry_price": str(self.entry_price) if self.entry_price else None,
            "calculated_at": self.calculated_at.isoformat() if self.calculated_at else None,
        }


@dataclass(slots=True)
class DrawdownState:
    """回撤状态。"""

    current_drawdown_pct: Decimal = Decimal("0")
    peak_capital: Decimal = Decimal("0")
    current_capital: Decimal = Decimal("0")
    triggered: bool = False
    triggered_at: datetime | None = None
    trading_paused: bool = False
    alert_sent: bool = False
    resolved_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "current_drawdown_pct": str(self.current_drawdown_pct.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
            "peak_capital": str(self.peak_capital.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
            "current_capital": str(self.current_capital.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
            "triggered": self.triggered,
            "triggered_at": self.triggered_at.isoformat() if self.triggered_at else None,
            "trading_paused": self.trading_paused,
            "alert_sent": self.alert_sent,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }


@dataclass(slots=True)
class PositionSummary:
    """仓位状态汇总。"""

    status: PositionStatus
    current_positions: int
    max_positions: int
    available_slots: int
    total_capital: Decimal
    used_capital: Decimal
    available_capital: Decimal
    drawdown_state: DrawdownState
    risk_level: RiskLevel
    can_open_new: bool
    reason: str
    evaluated_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "current_positions": self.current_positions,
            "max_positions": self.max_positions,
            "available_slots": self.available_slots,
            "total_capital": str(self.total_capital.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
            "used_capital": str(self.used_capital.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
            "available_capital": str(self.available_capital.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
            "drawdown_state": self.drawdown_state.to_dict(),
            "risk_level": self.risk_level.value,
            "can_open_new": self.can_open_new,
            "reason": self.reason,
            "evaluated_at": self.evaluated_at.isoformat() if self.evaluated_at else None,
        }


def _parse_decimal(value: Any, default: Decimal) -> Decimal:
    """解析Decimal值。"""
    if value is None:
        return default
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return default


class PositionManagementService:
    """仓位管理服务，实现动态仓位分配和回撤限制。"""

    def __init__(self, config: PositionConfig | None = None) -> None:
        self._config = config or PositionConfig.from_json()
        self._drawdown_state = DrawdownState(
            peak_capital=self._config.base_capital,
            current_capital=self._config.base_capital,
        )
        self._current_positions: dict[str, dict[str, Any]] = {}
        self._trade_history: list[dict[str, Any]] = []
        self._win_count: int = 0
        self._loss_count: int = 0
        self._total_win_amount: Decimal = Decimal("0")
        self._total_loss_amount: Decimal = Decimal("0")

    def get_position_status(self) -> PositionSummary:
        """获取当前仓位状态。"""
        now = datetime.now(timezone.utc)

        # 更新回撤状态
        self._update_drawdown_state()

        # 确定风险等级
        risk_level = self._determine_risk_level()

        # 根据风险等级调整最大仓位数
        max_positions = self._get_max_positions_for_risk(risk_level)

        current_count = len(self._current_positions)
        available_slots = max(0, max_positions - current_count)

        # 计算已用和可用资金
        used_capital = self._calculate_used_capital()
        available_capital = self._drawdown_state.current_capital - used_capital

        # 确定状态
        status, reason, can_open = self._determine_status_and_permission(
            available_slots, available_capital, risk_level
        )

        return PositionSummary(
            status=status,
            current_positions=current_count,
            max_positions=max_positions,
            available_slots=available_slots,
            total_capital=self._drawdown_state.current_capital,
            used_capital=used_capital,
            available_capital=available_capital,
            drawdown_state=self._drawdown_state,
            risk_level=risk_level,
            can_open_new=can_open,
            reason=reason,
            evaluated_at=now,
        )

    def calculate_position(
        self,
        symbol: str,
        entry_price: Decimal | None = None,
        stop_loss_price: Decimal | None = None,
        risk_level: RiskLevel | None = None,
        method: str = "fixed_ratio",
    ) -> PositionSuggestion:
        """计算建议仓位大小。

        Args:
            symbol: 交易标的
            entry_price: 入场价格
            stop_loss_price: 止损价格
            risk_level: 风险等级
            method: 计算方法 (fixed_ratio, kelly)

        Returns:
            PositionSuggestion: 仓位建议
        """
        now = datetime.now(timezone.utc)
        effective_risk_level = risk_level or self._determine_risk_level()

        # 获取风险百分比和乘数
        base_risk_pct = self._config.position_risk_pct
        risk_multiplier = self._get_risk_multiplier(effective_risk_level)
        effective_risk_pct = base_risk_pct * risk_multiplier

        # 计算风险金额
        capital = self._drawdown_state.current_capital
        risk_amount = capital * effective_risk_pct / Decimal("100")

        # 根据方法计算仓位
        if method == "kelly" and self._config.kelly_enabled:
            suggested_size, position_pct, calc_reason = self._calculate_kelly_position(
                symbol, capital, risk_amount, entry_price, stop_loss_price
            )
        else:
            suggested_size, position_pct, calc_reason = self._calculate_fixed_ratio_position(
                symbol, capital, risk_amount, entry_price, stop_loss_price
            )

        return PositionSuggestion(
            symbol=symbol,
            suggested_size=suggested_size,
            risk_amount=risk_amount,
            position_pct=position_pct,
            method=method if method == "kelly" and self._config.kelly_enabled else "fixed_ratio",
            reason=calc_reason,
            stop_loss_price=stop_loss_price,
            entry_price=entry_price,
            calculated_at=now,
        )

    def get_drawdown_status(self) -> DrawdownState:
        """获取回撤状态。"""
        self._update_drawdown_state()
        return self._drawdown_state

    def update_capital(self, new_capital: Decimal) -> dict[str, Any]:
        """更新账户资金。"""
        now = datetime.now(timezone.utc)

        # 更新峰值
        if new_capital > self._drawdown_state.peak_capital:
            self._drawdown_state.peak_capital = new_capital
            logger.info("New peak capital: %s", new_capital)

        self._drawdown_state.current_capital = new_capital

        # 计算回撤
        self._update_drawdown_state()

        return {
            "updated_at": now.isoformat(),
            "peak_capital": str(self._drawdown_state.peak_capital),
            "current_capital": str(self._drawdown_state.current_capital),
            "drawdown_pct": str(self._drawdown_state.current_drawdown_pct),
            "drawdown_triggered": self._drawdown_state.triggered,
        }

    def record_trade_result(
        self,
        symbol: str,
        pnl: Decimal,
        position_size: Decimal | None = None,
    ) -> dict[str, Any]:
        """记录交易结果，用于Kelly Criterion计算。"""
        now = datetime.now(timezone.utc)

        self._trade_history.append({
            "symbol": symbol,
            "pnl": str(pnl),
            "position_size": str(position_size) if position_size else None,
            "recorded_at": now.isoformat(),
        })

        if pnl > Decimal("0"):
            self._win_count += 1
            self._total_win_amount += pnl
        else:
            self._loss_count += 1
            self._total_loss_amount += pnl.copy_abs()

        # 更新资金
        new_capital = self._drawdown_state.current_capital + pnl
        self.update_capital(new_capital)

        return {
            "recorded_at": now.isoformat(),
            "pnl": str(pnl),
            "win_count": self._win_count,
            "loss_count": self._loss_count,
            "win_rate": self._calculate_win_rate(),
            "avg_win": str(self._calculate_avg_win()),
            "avg_loss": str(self._calculate_avg_loss()),
        }

    def add_position(
        self,
        symbol: str,
        size: Decimal,
        entry_price: Decimal,
        stop_loss: Decimal | None = None,
    ) -> dict[str, Any]:
        """添加仓位。"""
        now = datetime.now(timezone.utc)

        # 检查是否可以开仓
        status = self.get_position_status()
        if not status.can_open_new:
            return {
                "success": False,
                "reason": status.reason,
                "status": status.to_dict(),
            }

        self._current_positions[symbol] = {
            "symbol": symbol,
            "size": str(size),
            "entry_price": str(entry_price),
            "stop_loss": str(stop_loss) if stop_loss else None,
            "opened_at": now.isoformat(),
        }

        return {
            "success": True,
            "symbol": symbol,
            "size": str(size),
            "opened_at": now.isoformat(),
            "current_positions": len(self._current_positions),
            "available_slots": status.max_positions - len(self._current_positions),
        }

    def remove_position(self, symbol: str) -> dict[str, Any]:
        """移除仓位。"""
        now = datetime.now(timezone.utc)

        if symbol not in self._current_positions:
            return {
                "success": False,
                "reason": f"Position {symbol} not found",
            }

        position = self._current_positions.pop(symbol)

        return {
            "success": True,
            "symbol": symbol,
            "removed_at": now.isoformat(),
            "position": position,
            "remaining_positions": len(self._current_positions),
        }

    def reset_drawdown_trigger(self) -> dict[str, Any]:
        """重置回撤触发状态，恢复交易。"""
        now = datetime.now(timezone.utc)

        if not self._drawdown_state.triggered:
            return {
                "success": False,
                "reason": "Drawdown not triggered",
                "drawdown_state": self._drawdown_state.to_dict(),
            }

        self._drawdown_state.resolved_at = now
        self._drawdown_state.triggered = False
        self._drawdown_state.trading_paused = False
        self._drawdown_state.alert_sent = False

        # 重置峰值（可选）
        self._drawdown_state.peak_capital = self._drawdown_state.current_capital
        self._drawdown_state.current_drawdown_pct = Decimal("0")

        logger.info("Drawdown trigger reset at %s", now.isoformat())

        return {
            "success": True,
            "resolved_at": now.isoformat(),
            "drawdown_state": self._drawdown_state.to_dict(),
            "message": "Trading resumed, drawdown limit reset",
        }

    def set_risk_level(self, level: RiskLevel) -> dict[str, Any]:
        """手动设置风险等级。"""
        now = datetime.now(timezone.utc)
        self._manual_risk_level = level

        return {
            "success": True,
            "risk_level": level.value,
            "set_at": now.isoformat(),
            "max_positions": self._get_max_positions_for_risk(level),
            "risk_multiplier": self._get_risk_multiplier(level),
        }

    def _update_drawdown_state(self) -> None:
        """更新回撤状态。"""
        if self._drawdown_state.peak_capital <= Decimal("0"):
            return

        current = self._drawdown_state.current_capital
        peak = self._drawdown_state.peak_capital

        # 计算回撤百分比
        drawdown_pct = ((peak - current) / peak) * Decimal("100")
        self._drawdown_state.current_drawdown_pct = drawdown_pct

        # 检查是否触发回撤限制
        if drawdown_pct >= self._config.max_drawdown_pct:
            if not self._drawdown_state.triggered:
                now = datetime.now(timezone.utc)
                self._drawdown_state.triggered = True
                self._drawdown_state.triggered_at = now
                logger.warning(
                    "Drawdown limit triggered: %.2f%% >= %.2f%%",
                    drawdown_pct,
                    self._config.max_drawdown_pct,
                )

            if self._config.trading_paused_on_drawdown:
                self._drawdown_state.trading_paused = True

        # 检查是否需要发送预警
        if drawdown_pct >= self._config.drawdown_alert_threshold and not self._drawdown_state.alert_sent:
            self._drawdown_state.alert_sent = True
            logger.warning(
                "Drawdown alert: %.2f%% >= %.2f%%",
                drawdown_pct,
                self._config.drawdown_alert_threshold,
            )

    def _determine_risk_level(self) -> RiskLevel:
        """根据回撤状态确定风险等级。"""
        if hasattr(self, "_manual_risk_level"):
            return self._manual_risk_level

        drawdown_pct = self._drawdown_state.current_drawdown_pct

        if drawdown_pct >= Decimal("10"):
            return RiskLevel.HIGH
        elif drawdown_pct >= Decimal("5"):
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW

    def _get_max_positions_for_risk(self, level: RiskLevel) -> int:
        """获取风险等级对应的最大仓位数。"""
        level_config = self._config.risk_levels.get(level.value, {})
        return int(level_config.get("max_positions", self._config.max_position_count))

    def _get_risk_multiplier(self, level: RiskLevel) -> Decimal:
        """获取风险等级对应的风险乘数。"""
        level_config = self._config.risk_levels.get(level.value, {})
        return _parse_decimal(level_config.get("multiplier"), Decimal("1.0"))

    def _calculate_used_capital(self) -> Decimal:
        """计算已用资金。"""
        total = Decimal("0")
        for pos in self._current_positions.values():
            try:
                size = Decimal(str(pos.get("size", "0")))
                entry = Decimal(str(pos.get("entry_price", "0")))
                total += size * entry
            except (InvalidOperation, ValueError):
                continue
        return total

    def _determine_status_and_permission(
        self,
        available_slots: int,
        available_capital: Decimal,
        risk_level: RiskLevel,
    ) -> tuple[PositionStatus, str, bool]:
        """确定仓位状态和是否可以开新仓。"""
        if self._drawdown_state.triggered:
            if self._drawdown_state.trading_paused:
                return (
                    PositionStatus.TRADING_PAUSED,
                    f"Drawdown limit triggered ({self._drawdown_state.current_drawdown_pct:.2f}%), trading paused",
                    False,
                )
            return (
                PositionStatus.DRAWDOWN_LIMIT,
                f"Drawdown limit triggered ({self._drawdown_state.current_drawdown_pct:.2f}%)",
                False,
            )

        if self._drawdown_state.current_drawdown_pct >= self._config.drawdown_alert_threshold:
            return (
                PositionStatus.WARNING,
                f"Drawdown warning ({self._drawdown_state.current_drawdown_pct:.2f}%), reduce position size",
                available_slots > 0 and available_capital > Decimal("0"),
            )

        if available_slots <= 0:
            return (
                PositionStatus.NORMAL,
                "Maximum position count reached",
                False,
            )

        if available_capital <= Decimal("0"):
            return (
                PositionStatus.WARNING,
                "Insufficient available capital",
                False,
            )

        return (
            PositionStatus.NORMAL,
            f"Normal operation, {available_slots} slots available",
            True,
        )

    def _calculate_fixed_ratio_position(
        self,
        symbol: str,
        capital: Decimal,
        risk_amount: Decimal,
        entry_price: Decimal | None,
        stop_loss_price: Decimal | None,
    ) -> tuple[Decimal, Decimal, str]:
        """固定比例法计算仓位。"""
        if entry_price is None or entry_price <= Decimal("0"):
            # 无法计算具体数量，返回百分比
            position_pct = risk_amount / capital * Decimal("100")
            return Decimal("0"), position_pct, "Entry price not provided, only position_pct calculated"

        if stop_loss_price is None or stop_loss_price <= Decimal("0"):
            # 无止损价格，使用默认风险比例
            position_pct = self._config.position_risk_pct
            suggested_size = (capital * position_pct / Decimal("100")) / entry_price
            return suggested_size, position_pct, f"Fixed ratio {position_pct}% without stop loss"

        # 计算每单位风险
        risk_per_unit = entry_price - stop_loss_price
        if risk_per_unit <= Decimal("0"):
            # 止损价格高于入场价格，不合理
            position_pct = self._config.position_risk_pct
            suggested_size = (capital * position_pct / Decimal("100")) / entry_price
            return suggested_size, position_pct, "Invalid stop loss (above entry), using default ratio"

        # 计算仓位大小 = 风险金额 / 每单位风险
        suggested_size = risk_amount / risk_per_unit
        position_pct = (suggested_size * entry_price / capital) * Decimal("100")

        reason = f"Fixed ratio: risk {self._config.position_risk_pct}% of capital, stop loss at {stop_loss_price}"
        return suggested_size, position_pct, reason

    def _calculate_kelly_position(
        self,
        symbol: str,
        capital: Decimal,
        risk_amount: Decimal,
        entry_price: Decimal | None,
        stop_loss_price: Decimal | None,
    ) -> tuple[Decimal, Decimal, str]:
        """Kelly Criterion计算仓位。"""
        win_rate = self._calculate_win_rate()
        avg_win = self._calculate_avg_win()
        avg_loss = self._calculate_avg_loss()

        if avg_loss <= Decimal("0") or win_rate <= Decimal("0"):
            # 无足够历史数据，使用固定比例
            return self._calculate_fixed_ratio_position(
                symbol, capital, risk_amount, entry_price, stop_loss_price
            )

        # Kelly百分比 = W - (1-W)/R，其中W是胜率，R是盈亏比
        win_loss_ratio = avg_win / avg_loss
        kelly_pct = win_rate - (Decimal("1") - win_rate) / win_loss_ratio

        # 使用半Kelly（更保守）
        effective_kelly_pct = kelly_pct * self._config.kelly_fraction

        # Kelly值不能为负或过大
        if effective_kelly_pct <= Decimal("0"):
            return self._calculate_fixed_ratio_position(
                symbol, capital, risk_amount, entry_price, stop_loss_price
            )

        # 限制最大仓位百分比
        max_pct = Decimal("25")
        effective_kelly_pct = min(effective_kelly_pct, max_pct)

        position_pct = effective_kelly_pct
        suggested_size = Decimal("0")

        if entry_price and entry_price > Decimal("0"):
            suggested_size = (capital * position_pct / Decimal("100")) / entry_price

        reason = f"Kelly Criterion: win_rate={win_rate:.2%}, ratio={win_loss_ratio:.2f}, kelly={kelly_pct:.2%}, using {effective_kelly_pct:.2%}"
        return suggested_size, position_pct, reason

    def _calculate_win_rate(self) -> Decimal:
        """计算胜率。"""
        total = self._win_count + self._loss_count
        if total <= 0:
            return Decimal("0.5")  # 默认50%胜率
        return Decimal(self._win_count) / Decimal(total)

    def _calculate_avg_win(self) -> Decimal:
        """计算平均盈利。"""
        if self._win_count <= 0:
            return Decimal("0")
        return self._total_win_amount / Decimal(self._win_count)

    def _calculate_avg_loss(self) -> Decimal:
        """计算平均亏损。"""
        if self._loss_count <= 0:
            return Decimal("0")
        return self._total_loss_amount / Decimal(self._loss_count)

    def get_trade_statistics(self) -> dict[str, Any]:
        """获取交易统计数据。"""
        return {
            "total_trades": self._win_count + self._loss_count,
            "win_count": self._win_count,
            "loss_count": self._loss_count,
            "win_rate": str(self._calculate_win_rate().quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)),
            "avg_win": str(self._calculate_avg_win().quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
            "avg_loss": str(self._calculate_avg_loss().quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
            "total_profit": str(self._total_win_amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
            "total_loss": str(self._total_loss_amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
            "net_pnl": str((self._total_win_amount - self._total_loss_amount).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
        }


position_management_service = PositionManagementService()