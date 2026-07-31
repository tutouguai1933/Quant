"""Slippage estimation: depth-cost method + volatility method."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass
class SlippageEstimate:
    expected_bps: Decimal
    worst_case_bps: Decimal
    depth_coverage_pct: Decimal


@dataclass
class SlippageConfig:
    max_slippage_bps: int = 30
    volatility_window: int = 20


class SlippageModel:

    def __init__(self, config: SlippageConfig | None = None) -> None:
        self._config = config or SlippageConfig()

    def estimate(
        self,
        symbol: str,
        side: str,
        stake_amount: Decimal,
        order_book: dict,
        candles_4h: list[dict],
    ) -> SlippageEstimate:
        expected_bps = self._depth_cost(
            side=side,
            target_notional=stake_amount,
            order_book=order_book,
        )
        volatility_bps = self._volatility_method(candles_4h)
        depth_coverage_pct = self._depth_coverage(
            side=side,
            target_notional=stake_amount,
            order_book=order_book,
        )
        worst_case_bps = max(expected_bps * 2, volatility_bps * 2)
        return SlippageEstimate(
            expected_bps=expected_bps,
            worst_case_bps=worst_case_bps,
            depth_coverage_pct=depth_coverage_pct,
        )

    def _depth_cost(
        self,
        side: str,
        target_notional: Decimal,
        order_book: dict,
    ) -> Decimal:
        side_key = "asks" if side == "buy" else "bids"
        orders = order_book.get(side_key, [])
        if not orders:
            return Decimal("0")
        best_price = None
        cumulative_notional = Decimal("0")
        cumulative_qty = Decimal("0")
        for entry in orders:
            if not isinstance(entry, list) or len(entry) < 2:
                continue
            try:
                price = Decimal(str(entry[0]))
                qty = Decimal(str(entry[1]))
            except Exception:
                continue
            if best_price is None:
                best_price = price
            notional = price * qty
            cumulative_notional += notional
            cumulative_qty += qty
        if best_price is None or cumulative_qty <= 0:
            return Decimal("0")
        avg_price = cumulative_notional / cumulative_qty
        if side == "buy":
            deviation = abs(avg_price - best_price) / best_price
        else:
            deviation = abs(best_price - avg_price) / best_price
        return (deviation * 10000).quantize(Decimal("0.01"))

    def _volatility_method(self, candles_4h: list[dict]) -> Decimal:
        window = self._config.volatility_window
        closes: list[Decimal] = []
        for candle in candles_4h[-window:]:
            close = candle.get("close") or candle.get("Close")
            if close is None:
                continue
            try:
                closes.append(Decimal(str(close)))
            except Exception:
                continue
        if len(closes) < 2:
            return Decimal("0")
        returns: list[Decimal] = []
        for i in range(1, len(closes)):
            if closes[i - 1] == 0:
                continue
            ret = (closes[i] - closes[i - 1]) / closes[i - 1]
            returns.append(ret)
        if not returns:
            return Decimal("0")
        mean = sum(returns, Decimal("0")) / len(returns)
        variance = sum((r - mean) ** 2 for r in returns) / len(returns)
        std = variance.sqrt()
        return (std * 10000 * 2).quantize(Decimal("0.01"))

    def _depth_coverage(
        self,
        side: str,
        target_notional: Decimal,
        order_book: dict,
    ) -> Decimal:
        side_key = "asks" if side == "buy" else "bids"
        orders = order_book.get(side_key, [])
        if target_notional <= 0:
            return Decimal("100")
        cumulative = Decimal("0")
        for entry in orders:
            if not isinstance(entry, list) or len(entry) < 2:
                continue
            try:
                price = Decimal(str(entry[0]))
                qty = Decimal(str(entry[1]))
            except Exception:
                continue
            cumulative += price * qty
        coverage = (cumulative / target_notional * 100).quantize(Decimal("0.01"))
        return min(coverage, Decimal("100"))
