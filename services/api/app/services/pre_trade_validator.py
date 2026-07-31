"""Pre-trade validation service: exchange-side checks before order submission."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal


@dataclass
class PreTradeCheck:
    name: str
    passed: bool
    detail: str | None
    severity: Literal["block", "warn"]


@dataclass
class PreTradeReport:
    symbol: str
    side: Literal["buy", "sell"]
    stake_amount: Decimal
    reference_price: Decimal
    checks: list[PreTradeCheck] = field(default_factory=list)
    blocked: bool = False
    warnings: list[str] = field(default_factory=list)
    slippage: "SlippageEstimate | None" = None


@dataclass
class PreTradeConfig:
    enabled: bool = True
    min_depth_coverage: int = 3
    max_spread_bps: int = 20
    max_deviation_bps: int = 100
    max_slippage_bps: int = 30


class PreTradeValidator:

    def __init__(self, market_client, account_client, config: PreTradeConfig | None = None) -> None:
        self._market_client = market_client
        self._account_client = account_client
        self._config = config or PreTradeConfig()

    def validate(
        self,
        symbol: str,
        side: str,
        stake_amount: Decimal,
        reference_price: Decimal,
        candles_4h: list[dict] | None = None,
    ) -> PreTradeReport:
        report = PreTradeReport(
            symbol=symbol,
            side=side,
            stake_amount=stake_amount,
            reference_price=reference_price,
        )

        report.checks.append(self._check_symbol_status(symbol))
        report.checks.append(self._check_price_precision(symbol, reference_price))
        order_book = self._fetch_order_book(symbol)
        report.checks.append(self._check_liquidity(symbol, side, stake_amount, reference_price, order_book))
        report.checks.append(self._check_spread(order_book))
        report.checks.append(self._check_balance(symbol, side, stake_amount, reference_price))
        report.checks.append(self._check_price_deviation(symbol, reference_price))

        report.blocked = any(check.severity == "block" and not check.passed for check in report.checks)
        report.warnings = [check.detail for check in report.checks if check.severity == "warn" and not check.passed]

        return report

    def _check_symbol_status(self, symbol: str) -> PreTradeCheck:
        try:
            info = self._market_client.get_exchange_info((symbol,))
        except Exception:
            return PreTradeCheck(
                name="symbol_status",
                passed=False,
                detail="无法获取交易所信息",
                severity="block",
            )
        symbols = info.get("symbols", []) if isinstance(info, dict) else []
        for item in symbols:
            if str(item.get("symbol", "")).upper() != symbol:
                continue
            status = str(item.get("status", "")).upper()
            if status != "TRADING":
                return PreTradeCheck(
                    name="symbol_status",
                    passed=False,
                    detail=f"交易对状态={status}，不是 TRADING",
                    severity="block",
                )
            filters = item.get("filters")
            if not isinstance(filters, list) or not filters:
                return PreTradeCheck(
                    name="symbol_status",
                    passed=False,
                    detail="缺少交易规则 filters",
                    severity="block",
                )
            return PreTradeCheck(name="symbol_status", passed=True, detail=None, severity="block")
        return PreTradeCheck(
            name="symbol_status",
            passed=False,
            detail=f"交易对 {symbol} 未在交易所信息中找到",
            severity="block",
        )

    def _check_price_precision(self, symbol: str, reference_price: Decimal) -> PreTradeCheck:
        try:
            info = self._market_client.get_exchange_info((symbol,))
        except Exception:
            return PreTradeCheck(
                name="price_precision",
                passed=True,
                detail="无法获取交易规则，跳过精度检查",
                severity="warn",
            )
        tick_size = self._extract_tick_size(info, symbol)
        if tick_size is None or tick_size <= 0:
            return PreTradeCheck(
                name="price_precision",
                passed=True,
                detail="无法获取 tickSize，跳过精度检查",
                severity="warn",
            )
        rounded = (reference_price / tick_size).to_integral_value() * tick_size
        deviation = abs(reference_price - rounded)
        if deviation > tick_size * Decimal("0.5"):
            return PreTradeCheck(
                name="price_precision",
                passed=False,
                detail=f"参考价 {reference_price} 按 tickSize={tick_size} 取整后偏离 {deviation}",
                severity="warn",
            )
        return PreTradeCheck(name="price_precision", passed=True, detail=None, severity="warn")

    def _check_liquidity(
        self,
        symbol: str,
        side: str,
        stake_amount: Decimal,
        reference_price: Decimal,
        order_book: dict | None,
    ) -> PreTradeCheck:
        if order_book is None:
            return PreTradeCheck(
                name="liquidity",
                passed=True,
                detail="无法获取订单簿，跳过流动性检查",
                severity="warn",
            )
        target_qty = stake_amount / reference_price
        side_key = "asks" if side == "buy" else "bids"
        orders = order_book.get(side_key, [])
        cumulative = Decimal("0")
        for entry in orders:
            if not isinstance(entry, list) or len(entry) < 2:
                continue
            try:
                cumulative += Decimal(str(entry[1]))
            except Exception:
                continue
        coverage = cumulative / target_qty if target_qty > 0 else Decimal("0")
        min_coverage = Decimal(str(self._config.min_depth_coverage))
        if coverage < min_coverage:
            return PreTradeCheck(
                name="liquidity",
                passed=False,
                detail=f"可见深度 {cumulative} < 目标量 {target_qty} × {min_coverage}",
                severity="block",
            )
        return PreTradeCheck(name="liquidity", passed=True, detail=None, severity="block")

    def _check_spread(self, order_book: dict | None) -> PreTradeCheck:
        if order_book is None:
            return PreTradeCheck(
                name="spread",
                passed=True,
                detail="无法获取订单簿，跳过价差检查",
                severity="warn",
            )
        bids = order_book.get("bids", [])
        asks = order_book.get("asks", [])
        if not bids or not asks:
            return PreTradeCheck(
                name="spread",
                passed=True,
                detail="订单簿为空，跳过价差检查",
                severity="warn",
            )
        try:
            best_bid = Decimal(str(bids[0][0]))
            best_ask = Decimal(str(asks[0][0]))
        except (IndexError, KeyError, ValueError):
            return PreTradeCheck(
                name="spread",
                passed=True,
                detail="无法解析订单簿价格",
                severity="warn",
            )
        if best_bid <= 0 or best_ask <= 0:
            return PreTradeCheck(name="spread", passed=True, detail=None, severity="warn")
        spread_bps = (best_ask - best_bid) / best_bid * 10000
        max_spread = Decimal(str(self._config.max_spread_bps))
        if spread_bps > max_spread:
            return PreTradeCheck(
                name="spread",
                passed=False,
                detail=f"买卖价差 {spread_bps:.1f} bps > {max_spread} bps",
                severity="block",
            )
        return PreTradeCheck(name="spread", passed=True, detail=None, severity="block")

    def _check_balance(
        self,
        symbol: str,
        side: str,
        stake_amount: Decimal,
        reference_price: Decimal,
    ) -> PreTradeCheck:
        try:
            balances = self._account_client.get_balances()
        except Exception:
            return PreTradeCheck(
                name="balance",
                passed=True,
                detail="无法获取余额，跳过余额检查",
                severity="warn",
            )
        if side == "buy":
            for item in balances:
                asset = str(item.get("asset", "")).strip().upper()
                if asset != "USDT":
                    continue
                free = Decimal(str(item.get("free", "0") or "0"))
                if free < stake_amount:
                    return PreTradeCheck(
                        name="balance",
                        passed=False,
                        detail=f"可用 USDT={free} < 下单金额 {stake_amount}",
                        severity="block",
                    )
                return PreTradeCheck(name="balance", passed=True, detail=None, severity="block")
            return PreTradeCheck(
                name="balance",
                passed=False,
                detail="账户中未找到 USDT 余额",
                severity="block",
            )
        else:
            base_asset = symbol.replace("USDT", "")
            for item in balances:
                asset = str(item.get("asset", "")).strip().upper()
                if asset != base_asset:
                    continue
                free = Decimal(str(item.get("free", "0") or "0"))
                required = stake_amount / reference_price
                if free < required:
                    return PreTradeCheck(
                        name="balance",
                        passed=False,
                        detail=f"可用 {base_asset}={free} < 需要 {required}",
                        severity="block",
                    )
                return PreTradeCheck(name="balance", passed=True, detail=None, severity="block")
            return PreTradeCheck(
                name="balance",
                passed=False,
                detail=f"账户中未找到 {base_asset} 余额",
                severity="block",
            )

    def _check_price_deviation(self, symbol: str, reference_price: Decimal) -> PreTradeCheck:
        try:
            tickers = self._market_client.get_tickers((symbol,))
        except Exception:
            return PreTradeCheck(
                name="price_deviation",
                passed=True,
                detail="无法获取行情，跳过价格偏离检查",
                severity="warn",
            )
        last_price = None
        for item in tickers:
            if str(item.get("symbol", "")).upper() == symbol:
                raw = item.get("lastPrice") or item.get("last_price") or item.get("price")
                if raw not in (None, ""):
                    last_price = Decimal(str(raw))
                break
        if last_price is None or last_price <= 0:
            return PreTradeCheck(
                name="price_deviation",
                passed=True,
                detail="无法获取最新价",
                severity="warn",
            )
        deviation_bps = abs(last_price - reference_price) / reference_price * 10000
        max_dev = Decimal(str(self._config.max_deviation_bps))
        if deviation_bps > max_dev:
            return PreTradeCheck(
                name="price_deviation",
                passed=False,
                detail=f"最新价 {last_price} vs 参考价 {reference_price} 偏离 {deviation_bps:.1f} bps > {max_dev}",
                severity="block",
            )
        return PreTradeCheck(name="price_deviation", passed=True, detail=None, severity="block")

    def _fetch_order_book(self, symbol: str) -> dict | None:
        try:
            return self._market_client.get_order_book(symbol)
        except Exception:
            return None

    @staticmethod
    def _extract_tick_size(info: dict, symbol: str) -> Decimal | None:
        for item in info.get("symbols", []):
            if str(item.get("symbol", "")).upper() != symbol:
                continue
            for raw_filter in item.get("filters", []):
                if str(raw_filter.get("filterType", "")).upper() == "PRICE_FILTER":
                    value = raw_filter.get("tickSize")
                    if value not in (None, ""):
                        return Decimal(str(value))
        return None
