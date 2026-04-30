"""Trend following strategy using EMA crossover.

Signal logic:
- Fast EMA > Slow EMA: Buy signal
- Fast EMA < Slow EMA: Sell signal
- Strength based on crossover distance
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from services.api.app.services.strategy.base import StrategyBase, StrategyResult, StrategySignal


class TrendStrategy(StrategyBase):
    """EMA crossover trend following strategy.

    Uses fast and slow EMA periods to identify trend direction.
    Buy when fast EMA crosses above slow EMA, sell when crosses below.
    """

    name = "trend"
    display_name = "趋势跟踪"
    description = "基于EMA均线交叉的趋势跟踪策略"

    def analyze(self, data: dict[str, Any]) -> StrategyResult:
        """Analyze candle data for EMA crossover signals.

        Args:
            data: Must contain "candles" list with OHLCV data

        Returns:
            StrategyResult with buy/sell/hold signal
        """
        candles = data.get("candles", [])
        symbol = data.get("symbol", "UNKNOWN")
        timeframe = data.get("timeframe", "1h")

        if len(candles) < max(self.config.get("slow_period", 25), self.config.get("fast_period", 7)) + 1:
            return StrategyResult(
                signal=StrategySignal(
                    action="hold",
                    strength=0.0,
                    reason="insufficient_candles",
                    metadata={"required_candles": max(self.config.get("slow_period", 25), self.config.get("fast_period", 7)) + 1, "actual": len(candles)},
                ),
                indicators={"error": "insufficient_data"},
            )

        # Calculate EMAs
        fast_period = self.config.get("fast_period", 7)
        slow_period = self.config.get("slow_period", 25)

        closes = []
        for candle in candles:
            try:
                close = Decimal(str(candle.get("close", 0)))
                if close > 0:
                    closes.append(close)
            except (InvalidOperation, TypeError):
                continue

        if len(closes) < slow_period + 1:
            return StrategyResult(
                signal=StrategySignal(
                    action="hold",
                    strength=0.0,
                    reason="insufficient_valid_closes",
                ),
                indicators={"error": "insufficient_valid_data"},
            )

        fast_ema = self._calculate_ema(closes, fast_period)
        slow_ema = self._calculate_ema(closes, slow_period)

        # Previous EMAs for crossover detection
        prev_fast_ema = self._calculate_ema(closes[:-1], fast_period) if len(closes) > fast_period else fast_ema
        prev_slow_ema = self._calculate_ema(closes[:-1], slow_period) if len(closes) > slow_period else slow_ema

        # Determine signal
        current_close = closes[-1]

        # Crossover detection
        crossover_up = prev_fast_ema <= prev_slow_ema and fast_ema > slow_ema
        crossover_down = prev_fast_ema >= prev_slow_ema and fast_ema < slow_ema

        # Trend strength based on distance between EMAs
        ema_distance = abs(fast_ema - slow_ema) / slow_ema
        strength = float(min(ema_distance * 10, 1.0))  # Scale to 0-1

        if crossover_up:
            action = "buy"
            reason = "fast_ema_crossed_above_slow_ema"
        elif crossover_down:
            action = "sell"
            reason = "fast_ema_crossed_below_slow_ema"
        elif fast_ema > slow_ema:
            action = "buy"
            reason = "fast_ema_above_slow_ema_trend_up"
            strength = strength * 0.5  # Reduce strength for non-crossover signals
        elif fast_ema < slow_ema:
            action = "sell"
            reason = "fast_ema_below_slow_ema_trend_down"
            strength = strength * 0.5
        else:
            action = "hold"
            reason = "ema_neutral"
            strength = 0.0

        return StrategyResult(
            signal=StrategySignal(
                action=action,
                strength=strength,
                reason=reason,
                metadata={
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "crossover_up": crossover_up,
                    "crossover_down": crossover_down,
                },
            ),
            indicators={
                "fast_ema": str(fast_ema.normalize()),
                "slow_ema": str(slow_ema.normalize()),
                "prev_fast_ema": str(prev_fast_ema.normalize()),
                "prev_slow_ema": str(prev_slow_ema.normalize()),
                "close": str(current_close.normalize()),
                "ema_distance_pct": str((ema_distance * 100).normalize()),
            },
        )

    def _calculate_ema(self, prices: list[Decimal], period: int) -> Decimal:
        """Calculate Exponential Moving Average.

        Uses smoothing factor: alpha = 2 / (period + 1)
        """
        if len(prices) < period:
            # Not enough data, use simple average of available prices
            return sum(prices) / len(prices) if prices else Decimal("0")

        # Start with SMA for first period values
        sma = sum(prices[:period]) / period
        alpha = Decimal("2") / Decimal(period + 1)

        ema = sma
        for price in prices[period:]:
            ema = alpha * price + (Decimal("1") - alpha) * ema

        return ema

    def get_config_schema(self) -> dict[str, Any]:
        """Return configuration schema for trend strategy."""
        return {
            "parameters": {
                "fast_period": {
                    "type": "number",
                    "default": 7,
                    "min": 1,
                    "max": 50,
                    "description": "快线EMA周期",
                },
                "slow_period": {
                    "type": "number",
                    "default": 25,
                    "min": 1,
                    "max": 100,
                    "description": "慢线EMA周期",
                },
                "timeframe": {
                    "type": "string",
                    "default": "1h",
                    "options": ["1m", "5m", "15m", "30m", "1h", "4h", "1d"],
                    "description": "分析时间周期",
                },
            },
        }