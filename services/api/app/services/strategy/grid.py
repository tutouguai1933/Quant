"""Grid trading strategy for price range-based trading.

Signal logic:
- Buy when price touches lower grid line
- Sell when price touches upper grid line
- Grid lines evenly distributed within price range
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from services.api.app.services.strategy.base import StrategyBase, StrategyResult, StrategySignal


class GridStrategy(StrategyBase):
    """Grid trading strategy for range-bound markets.

    Divides price range into grid levels and triggers trades
    when price crosses grid lines.
    """

    name = "grid"
    display_name = "网格交易"
    description = "价格区间网格交易策略"

    def analyze(self, data: dict[str, Any]) -> StrategyResult:
        """Analyze price data for grid trading signals.

        Args:
            data: Must contain "candles" list and optionally "current_price"

        Returns:
            StrategyResult with grid-based buy/sell signal
        """
        candles = data.get("candles", [])
        symbol = data.get("symbol", "UNKNOWN")

        # Get current price from data or latest candle
        current_price = data.get("current_price")
        if current_price is None and candles:
            try:
                current_price = Decimal(str(candles[-1].get("close", 0)))
            except (InvalidOperation, TypeError):
                current_price = None

        if current_price is None:
            return StrategyResult(
                signal=StrategySignal(
                    action="hold",
                    strength=0.0,
                    reason="no_current_price",
                ),
                indicators={"error": "no_price_data"},
            )

        current_price = Decimal(str(current_price))
        if current_price <= 0:
            return StrategyResult(
                signal=StrategySignal(
                    action="hold",
                    strength=0.0,
                    reason="invalid_price",
                ),
                indicators={"error": "price_must_be_positive"},
            )

        # Get grid configuration
        grid_count = self.config.get("grid_count", 10)
        price_range = self.config.get("price_range", {})
        low = price_range.get("low")
        high = price_range.get("high")

        # Auto-calculate range from candles if not configured
        if low is None or high is None:
            if len(candles) < 10:
                return StrategyResult(
                    signal=StrategySignal(
                        action="hold",
                        strength=0.0,
                        reason="insufficient_candles_for_range",
                        metadata={"required": 10, "actual": len(candles)},
                    ),
                    indicators={"error": "insufficient_data_for_range_calculation"},
                )

            # Use recent candle highs/low to determine range
            recent_candles = candles[-20:] if len(candles) >= 20 else candles
            highs = []
            lows = []
            for c in recent_candles:
                try:
                    h = Decimal(str(c.get("high", 0)))
                    l = Decimal(str(c.get("low", 0)))
                    if h > 0 and l > 0:
                        highs.append(h)
                        lows.append(l)
                except (InvalidOperation, TypeError):
                    continue

            if not highs or not lows:
                return StrategyResult(
                    signal=StrategySignal(
                        action="hold",
                        strength=0.0,
                        reason="invalid_candle_data",
                    ),
                    indicators={"error": "no_valid_high_low"},
                )

            high = max(highs)
            low = min(lows)

            # Add buffer to range (5% on each side)
            buffer = (high - low) * Decimal("0.05")
            low = low - buffer
            high = high + buffer

        low = Decimal(str(low))
        high = Decimal(str(high))

        if high <= low:
            return StrategyResult(
                signal=StrategySignal(
                    action="hold",
                    strength=0.0,
                    reason="invalid_range",
                ),
                indicators={"error": "high_must_be_greater_than_low"},
            )

        # Calculate grid levels
        grid_levels = self._calculate_grid_levels(low, high, grid_count)

        # Find nearest grid levels
        lower_grid, upper_grid = self._find_nearest_grids(current_price, grid_levels)

        # Calculate position within grid
        grid_position = self._calculate_grid_position(current_price, lower_grid, upper_grid)

        # Determine signal
        grid_threshold = Decimal(str(self.config.get("grid_threshold_pct", 0.5))) / Decimal("100")
        distance_to_lower = abs(current_price - lower_grid) / lower_grid if lower_grid > 0 else Decimal("0")
        distance_to_upper = abs(current_price - upper_grid) / upper_grid if upper_grid > 0 else Decimal("0")

        action = "hold"
        reason = "price_within_grid"
        strength = 0.0

        # Price above range -> strong sell
        if current_price > high:
            action = "sell"
            reason = "price_above_range"
            strength = 1.0

        # Price at high (highest grid level) -> sell signal
        elif current_price == high:
            action = "sell"
            reason = "price_hit_upper_grid"
            strength = 1.0

        # Price below range -> strong buy
        elif current_price < low:
            action = "buy"
            reason = "price_below_range"
            strength = 1.0

        # Price at low (lowest grid level) -> buy signal
        elif current_price == low:
            action = "buy"
            reason = "price_hit_lower_grid"
            strength = 1.0

        # Near upper grid line -> sell signal
        elif distance_to_upper <= grid_threshold:
            action = "sell"
            reason = "price_hit_upper_grid"
            strength = float(min(distance_to_upper / grid_threshold, 1.0))

        # Near lower grid line -> buy signal
        elif distance_to_lower <= grid_threshold:
            action = "buy"
            reason = "price_hit_lower_grid"
            strength = float(min(distance_to_lower / grid_threshold, 1.0))

        return StrategyResult(
            signal=StrategySignal(
                action=action,
                strength=strength,
                reason=reason,
                metadata={
                    "symbol": symbol,
                    "grid_position": float(grid_position),
                    "distance_to_lower_pct": float(distance_to_lower * 100),
                    "distance_to_upper_pct": float(distance_to_upper * 100),
                },
            ),
            indicators={
                "current_price": str(current_price.normalize()),
                "grid_low": str(low.normalize()),
                "grid_high": str(high.normalize()),
                "grid_count": grid_count,
                "lower_grid_level": str(lower_grid.normalize()),
                "upper_grid_level": str(upper_grid.normalize()),
                "grid_position_pct": str((grid_position * 100).normalize()),
            },
        )

    def _calculate_grid_levels(self, low: Decimal, high: Decimal, count: int) -> list[Decimal]:
        """Calculate evenly distributed grid levels."""
        if count <= 1:
            return [low, high]

        step = (high - low) / Decimal(count - 1)
        levels = []
        for i in range(count):
            level = low + step * Decimal(i)
            levels.append(level)

        return levels

    def _find_nearest_grids(self, price: Decimal, levels: list[Decimal]) -> tuple[Decimal, Decimal]:
        """Find the grid levels surrounding current price."""
        if not levels:
            return price, price

        # Sort levels
        sorted_levels = sorted(levels)

        # Find surrounding levels
        lower = sorted_levels[0]
        upper = sorted_levels[-1]

        for i, level in enumerate(sorted_levels):
            if level <= price:
                lower = level
                if i + 1 < len(sorted_levels):
                    upper = sorted_levels[i + 1]
            else:
                upper = level
                break

        return lower, upper

    def _calculate_grid_position(self, price: Decimal, lower: Decimal, upper: Decimal) -> Decimal:
        """Calculate position within grid cell (0 to 1)."""
        if upper <= lower:
            return Decimal("0.5")

        position = (price - lower) / (upper - lower)
        return max(Decimal("0"), min(Decimal("1"), position))

    def get_config_schema(self) -> dict[str, Any]:
        """Return configuration schema for grid strategy."""
        return {
            "parameters": {
                "grid_count": {
                    "type": "number",
                    "default": 10,
                    "min": 2,
                    "max": 50,
                    "description": "网格数量",
                },
                "price_range": {
                    "type": "object",
                    "default": {"low": None, "high": None},
                    "description": "价格区间（可选，自动计算）",
                    "properties": {
                        "low": {"type": "number", "description": "区间下限"},
                        "high": {"type": "number", "description": "区间上限"},
                    },
                },
                "grid_threshold_pct": {
                    "type": "number",
                    "default": 0.5,
                    "min": 0.1,
                    "max": 2.0,
                    "description": "触发信号的网格阈值百分比",
                },
                "timeframe": {
                    "type": "string",
                    "default": "1h",
                    "options": ["1m", "5m", "15m", "30m", "1h", "4h", "1d"],
                    "description": "分析时间周期",
                },
            },
        }