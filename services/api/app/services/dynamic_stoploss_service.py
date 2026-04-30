"""动态止损服务，根据市场波动率调整止损比例。"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from services.api.app.adapters.freqtrade.client import freqtrade_client
from services.api.app.services.volatility_service import volatility_service, VolatilityService


@dataclass(slots=True)
class StoplossConfig:
    """动态止损配置。"""

    base_stoploss: Decimal = Decimal("-0.10")
    min_stoploss: Decimal = Decimal("-0.05")
    max_stoploss: Decimal = Decimal("-0.15")
    high_volatility_threshold: Decimal = Decimal("1.5")
    low_volatility_threshold: Decimal = Decimal("0.7")
    adjustment_interval_minutes: int = 30
    throttle_min_change_pct: Decimal = Decimal("0.02")

    @classmethod
    def from_env(cls) -> "StoplossConfig":
        """从环境变量读取止损配置。"""

        def parse_decimal(key: str, default: str) -> Decimal:
            raw = os.getenv(key, default).strip()
            try:
                return Decimal(raw)
            except InvalidOperation:
                return Decimal(default)

        base_stoploss = parse_decimal("QUANT_STOPLOSS_BASE", "-0.10")
        min_stoploss = parse_decimal("QUANT_STOPLOSS_MIN", "-0.05")
        max_stoploss = parse_decimal("QUANT_STOPLOSS_MAX", "-0.15")
        high_vol_threshold = parse_decimal("QUANT_STOPLOSS_HIGH_VOL_THRESHOLD", "1.5")
        low_vol_threshold = parse_decimal("QUANT_STOPLOSS_LOW_VOL_THRESHOLD", "0.7")
        interval_minutes = int(os.getenv("QUANT_STOPLOSS_INTERVAL_MINUTES", "30") or "30")
        throttle_pct = parse_decimal("QUANT_STOPLOSS_THROTTLE_PCT", "0.02")

        return cls(
            base_stoploss=base_stoploss,
            min_stoploss=min_stoploss,
            max_stoploss=max_stoploss,
            high_volatility_threshold=high_vol_threshold,
            low_volatility_threshold=low_vol_threshold,
            adjustment_interval_minutes=interval_minutes,
            throttle_min_change_pct=throttle_pct,
        )


@dataclass(slots=True)
class PositionStoplossState:
    """持仓止损状态。"""

    symbol: str
    position_id: str
    current_stoploss: Decimal
    entry_price: Decimal
    current_price: Decimal
    volatility_factor: Decimal
    last_adjusted_at: datetime
    adjustment_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "position_id": self.position_id,
            "current_stoploss": str(self.current_stoploss),
            "entry_price": str(self.entry_price),
            "current_price": str(self.current_price),
            "volatility_factor": str(self.volatility_factor),
            "last_adjusted_at": self.last_adjusted_at.isoformat(),
            "adjustment_count": self.adjustment_count,
        }


@dataclass(slots=True)
class StoplossAdjustmentResult:
    """止损调整结果。"""

    symbol: str
    previous_stoploss: Decimal
    new_stoploss: Decimal
    volatility_factor: Decimal
    reason: str
    adjusted_at: datetime
    success: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "previous_stoploss": str(self.previous_stoploss),
            "new_stoploss": str(self.new_stoploss),
            "volatility_factor": str(self.volatility_factor),
            "reason": self.reason,
            "adjusted_at": self.adjusted_at.isoformat(),
            "success": self.success,
        }


class DynamicStoplossService:
    """动态止损服务，根据市场波动率动态调整止损比例。"""

    def __init__(
        self,
        config: StoplossConfig | None = None,
        volatility_svc: VolatilityService | None = None,
    ) -> None:
        self._config = config or StoplossConfig.from_env()
        self._volatility_svc = volatility_svc or volatility_service
        self._position_states: dict[str, PositionStoplossState] = {}
        self._adjustment_history: dict[str, list[StoplossAdjustmentResult]] = {}

    def calculate_stoploss(self, symbol: str, volatility_factor: Decimal | None = None) -> Decimal:
        """计算动态止损比例。

        核心逻辑：
        - 高波动率(>1.5) = 更大止损空间，避免过早止损
        - 低波动率(<0.7) = 更小止损空间，保护利润
        - 正常波动率 = 使用基础止损
        """
        if volatility_factor is None:
            volatility_factor = self._volatility_svc.get_volatility_factor(symbol)

        base = self._config.base_stoploss

        if volatility_factor >= self._config.high_volatility_threshold:
            high_vol_adjustment = Decimal("0.03") * (volatility_factor - Decimal("1"))
            dynamic_stoploss = base - high_vol_adjustment
        elif volatility_factor <= self._config.low_volatility_threshold:
            low_vol_adjustment = Decimal("0.02") * (Decimal("1") - volatility_factor)
            dynamic_stoploss = base + low_vol_adjustment
        else:
            dynamic_stoploss = base

        if dynamic_stoploss < self._config.max_stoploss:
            dynamic_stoploss = self._config.max_stoploss
        if dynamic_stoploss > self._config.min_stoploss:
            dynamic_stoploss = self._config.min_stoploss

        return dynamic_stoploss.quantize(Decimal("0.01"))

    def adjust_trade_stoploss(self, trade_id: str, force: bool = False) -> StoplossAdjustmentResult:
        """调整单个交易的止损。"""
        now = datetime.now(timezone.utc)

        position_state = self._position_states.get(trade_id)
        if not position_state:
            return self._create_failed_result(trade_id, "position_not_found", now)

        if not force:
            last_adjusted = position_state.last_adjusted_at
            interval = timedelta(minutes=self._config.adjustment_interval_minutes)
            if now - last_adjusted < interval:
                return self._create_failed_result(
                    trade_id,
                    "throttled: adjustment_interval_not_elapsed",
                    now,
                )

        volatility_factor = self._volatility_svc.get_volatility_factor(position_state.symbol)
        new_stoploss = self.calculate_stoploss(position_state.symbol, volatility_factor)

        change_pct = abs(new_stoploss - position_state.current_stoploss)
        if not force and change_pct < self._config.throttle_min_change_pct:
            return self._create_failed_result(
                trade_id,
                "throttled: change_below_threshold",
                now,
            )

        previous_stoploss = position_state.current_stoploss
        position_state.current_stoploss = new_stoploss
        position_state.volatility_factor = volatility_factor
        position_state.last_adjusted_at = now
        position_state.adjustment_count += 1

        result = StoplossAdjustmentResult(
            symbol=position_state.symbol,
            previous_stoploss=previous_stoploss,
            new_stoploss=new_stoploss,
            volatility_factor=volatility_factor,
            reason=self._build_reason(volatility_factor),
            adjusted_at=now,
            success=True,
        )

        history = self._adjustment_history.get(trade_id, [])
        history.append(result)
        self._adjustment_history[trade_id] = history[-50:]

        return result

    def adjust_all_positions(self, force: bool = False) -> list[StoplossAdjustmentResult]:
        """调整所有持仓的止损。"""
        results: list[StoplossAdjustmentResult] = []

        for trade_id in list(self._position_states.keys()):
            result = self.adjust_trade_stoploss(trade_id, force=force)
            results.append(result)

        return results

    def register_position(
        self,
        symbol: str,
        position_id: str,
        entry_price: Decimal,
        current_price: Decimal,
        initial_stoploss: Decimal | None = None,
    ) -> PositionStoplossState:
        """注册新持仓并初始化止损状态。"""
        now = datetime.now(timezone.utc)
        volatility_factor = self._volatility_svc.get_volatility_factor(symbol)

        if initial_stoploss is None:
            initial_stoploss = self.calculate_stoploss(symbol, volatility_factor)

        state = PositionStoplossState(
            symbol=symbol.upper(),
            position_id=position_id,
            current_stoploss=initial_stoploss,
            entry_price=entry_price,
            current_price=current_price,
            volatility_factor=volatility_factor,
            last_adjusted_at=now,
            adjustment_count=0,
        )

        self._position_states[position_id] = state
        return state

    def unregister_position(self, position_id: str) -> bool:
        """移除持仓止损状态。"""
        if position_id in self._position_states:
            del self._position_states[position_id]
            return True
        return False

    def get_position_state(self, position_id: str) -> PositionStoplossState | None:
        """获取持仓止损状态。"""
        return self._position_states.get(position_id)

    def get_all_position_states(self) -> list[PositionStoplossState]:
        """获取所有持仓止损状态。"""
        return list(self._position_states.values())

    def sync_with_freqtrade(self) -> dict[str, Any]:
        """从Freqtrade同步持仓状态。"""
        try:
            snapshot = freqtrade_client.get_snapshot()
            positions = list(snapshot.positions)
        except Exception:
            return {"synced": 0, "errors": ["failed_to_get_snapshot"]}

        synced_count = 0
        errors: list[str] = []

        for position in positions:
            try:
                symbol = str(position.get("symbol") or "")
                position_id = str(position.get("id") or symbol)
                entry_price = Decimal(str(position.get("entryPrice") or "0"))
                current_price = Decimal(str(position.get("markPrice") or entry_price))

                if symbol and entry_price > 0:
                    self.register_position(
                        symbol=symbol,
                        position_id=position_id,
                        entry_price=entry_price,
                        current_price=current_price,
                    )
                    synced_count += 1
            except Exception as exc:
                errors.append(f"position_sync_error: {exc}")

        return {"synced": synced_count, "errors": errors, "total_positions": len(positions)}

    def get_config(self) -> dict[str, Any]:
        """获取当前配置。"""
        return {
            "base_stoploss": str(self._config.base_stoploss),
            "min_stoploss": str(self._config.min_stoploss),
            "max_stoploss": str(self._config.max_stoploss),
            "high_volatility_threshold": str(self._config.high_volatility_threshold),
            "low_volatility_threshold": str(self._config.low_volatility_threshold),
            "adjustment_interval_minutes": self._config.adjustment_interval_minutes,
            "throttle_min_change_pct": str(self._config.throttle_min_change_pct),
        }

    def update_config(self, updates: dict[str, Any]) -> dict[str, Any]:
        """更新配置。"""
        if "base_stoploss" in updates:
            self._config.base_stoploss = Decimal(str(updates["base_stoploss"]))
        if "min_stoploss" in updates:
            self._config.min_stoploss = Decimal(str(updates["min_stoploss"]))
        if "max_stoploss" in updates:
            self._config.max_stoploss = Decimal(str(updates["max_stoploss"]))
        if "high_volatility_threshold" in updates:
            self._config.high_volatility_threshold = Decimal(str(updates["high_volatility_threshold"]))
        if "low_volatility_threshold" in updates:
            self._config.low_volatility_threshold = Decimal(str(updates["low_volatility_threshold"]))
        if "adjustment_interval_minutes" in updates:
            self._config.adjustment_interval_minutes = int(updates["adjustment_interval_minutes"])
        if "throttle_min_change_pct" in updates:
            self._config.throttle_min_change_pct = Decimal(str(updates["throttle_min_change_pct"]))

        return self.get_config()

    def _build_reason(self, volatility_factor: Decimal) -> str:
        """构建调整原因描述。"""
        if volatility_factor >= self._config.high_volatility_threshold:
            return f"high_volatility_adjustment (factor={volatility_factor:.2f})"
        elif volatility_factor <= self._config.low_volatility_threshold:
            return f"low_volatility_adjustment (factor={volatility_factor:.2f})"
        else:
            return f"normal_volatility (factor={volatility_factor:.2f})"

    def _create_failed_result(
        self,
        trade_id: str,
        reason: str,
        now: datetime,
    ) -> StoplossAdjustmentResult:
        """创建失败结果。"""
        state = self._position_states.get(trade_id)
        symbol = state.symbol if state else trade_id
        current_stoploss = state.current_stoploss if state else Decimal("0")
        volatility_factor = state.volatility_factor if state else Decimal("1")

        return StoplossAdjustmentResult(
            symbol=symbol,
            previous_stoploss=current_stoploss,
            new_stoploss=current_stoploss,
            volatility_factor=volatility_factor,
            reason=reason,
            adjusted_at=now,
            success=False,
        )


dynamic_stoploss_service = DynamicStoplossService()