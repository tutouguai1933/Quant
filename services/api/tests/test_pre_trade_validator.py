"""Unit tests for PreTradeValidator."""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import unittest

from services.api.app.services.pre_trade_validator import (
    PreTradeCheck,
    PreTradeConfig,
    PreTradeReport,
    PreTradeValidator,
)


class _FakeMarketClient:
    def __init__(
        self,
        *,
        exchange_info: dict | None = None,
        order_book: dict | None = None,
        tickers: list[dict] | None = None,
    ):
        self._exchange_info = exchange_info or {"symbols": []}
        self._order_book = order_book or {"bids": [], "asks": []}
        self._tickers = tickers or []

    def get_exchange_info(self, symbols=None):
        return self._exchange_info

    def get_order_book(self, symbol, limit=20):
        return self._order_book

    def get_tickers(self, symbols=None):
        return self._tickers


class _FakeAccountClient:
    def __init__(self, balances: list[dict] | None = None):
        self._balances = balances or []

    def get_balances(self):
        return self._balances


def _make_exchange_info(symbol="BTCUSDT", status="TRADING", tick_size="0.01"):
    return {
        "symbols": [
            {
                "symbol": symbol,
                "status": status,
                "filters": [
                    {"filterType": "PRICE_FILTER", "tickSize": tick_size},
                    {"filterType": "LOT_SIZE", "stepSize": "0.00001"},
                ],
            }
        ]
    }


class PreTradeValidatorTests(unittest.TestCase):

    def test_all_checks_pass_for_valid_setup(self):
        market = _FakeMarketClient(
            exchange_info=_make_exchange_info(),
            order_book={
                "bids": [["50000", "10"], ["49900", "20"]],
                "asks": [["50100", "10"], ["50200", "20"]],
            },
            tickers=[{"symbol": "BTCUSDT", "lastPrice": "50050"}],
        )
        account = _FakeAccountClient(
            balances=[{"asset": "USDT", "free": "10000"}]
        )
        config = PreTradeConfig(
            min_depth_coverage=1,
            max_spread_bps=500,
            max_deviation_bps=1000,
        )
        validator = PreTradeValidator(market, account, config=config)
        report = validator.validate(
            symbol="BTCUSDT",
            side="buy",
            stake_amount=Decimal("500"),
            reference_price=Decimal("50000"),
        )
        self.assertFalse(report.blocked)
        self.assertTrue(all(c.passed for c in report.checks))

    def test_blocked_when_symbol_status_not_trading(self):
        market = _FakeMarketClient(
            exchange_info=_make_exchange_info(status="BREAK"),
        )
        account = _FakeAccountClient()
        validator = PreTradeValidator(market, account)
        report = validator.validate(
            symbol="BTCUSDT",
            side="buy",
            stake_amount=Decimal("500"),
            reference_price=Decimal("50000"),
        )
        self.assertTrue(report.blocked)
        status_checks = [c for c in report.checks if c.name == "symbol_status"]
        self.assertFalse(status_checks[0].passed)

    def test_blocked_when_liquidity_insufficient(self):
        market = _FakeMarketClient(
            exchange_info=_make_exchange_info(),
            order_book={
                "bids": [["50000", "0.001"]],
                "asks": [["50100", "0.001"]],
            },
        )
        account = _FakeAccountClient(
            balances=[{"asset": "USDT", "free": "10000"}]
        )
        validator = PreTradeValidator(market, account)
        report = validator.validate(
            symbol="BTCUSDT",
            side="buy",
            stake_amount=Decimal("500"),
            reference_price=Decimal("50000"),
        )
        self.assertTrue(report.blocked)
        liq_checks = [c for c in report.checks if c.name == "liquidity"]
        self.assertFalse(liq_checks[0].passed)

    def test_blocked_when_spread_too_wide(self):
        market = _FakeMarketClient(
            exchange_info=_make_exchange_info(),
            order_book={
                "bids": [["50000", "10"]],
                "asks": [["51000", "10"]],
            },
        )
        account = _FakeAccountClient(
            balances=[{"asset": "USDT", "free": "10000"}]
        )
        config = PreTradeConfig(max_spread_bps=10)
        validator = PreTradeValidator(market, account, config=config)
        report = validator.validate(
            symbol="BTCUSDT",
            side="buy",
            stake_amount=Decimal("500"),
            reference_price=Decimal("50000"),
        )
        self.assertTrue(report.blocked)
        spread_checks = [c for c in report.checks if c.name == "spread"]
        self.assertFalse(spread_checks[0].passed)

    def test_blocked_when_balance_insufficient(self):
        market = _FakeMarketClient(
            exchange_info=_make_exchange_info(),
            order_book={
                "bids": [["50000", "10"]],
                "asks": [["50100", "10"]],
            },
        )
        account = _FakeAccountClient(
            balances=[{"asset": "USDT", "free": "10"}]
        )
        validator = PreTradeValidator(market, account)
        report = validator.validate(
            symbol="BTCUSDT",
            side="buy",
            stake_amount=Decimal("500"),
            reference_price=Decimal("50000"),
        )
        self.assertTrue(report.blocked)
        bal_checks = [c for c in report.checks if c.name == "balance"]
        self.assertFalse(bal_checks[0].passed)

    def test_blocked_when_price_deviation_too_large(self):
        market = _FakeMarketClient(
            exchange_info=_make_exchange_info(),
            order_book={
                "bids": [["50000", "10"]],
                "asks": [["50100", "10"]],
            },
            tickers=[{"symbol": "BTCUSDT", "lastPrice": "51000"}],
        )
        account = _FakeAccountClient(
            balances=[{"asset": "USDT", "free": "10000"}]
        )
        config = PreTradeConfig(max_deviation_bps=10)
        validator = PreTradeValidator(market, account, config=config)
        report = validator.validate(
            symbol="BTCUSDT",
            side="buy",
            stake_amount=Decimal("500"),
            reference_price=Decimal("50000"),
        )
        self.assertTrue(report.blocked)
        dev_checks = [c for c in report.checks if c.name == "price_deviation"]
        self.assertFalse(dev_checks[0].passed)

    def test_price_precision_passes_for_tick_aligned_price(self):
        market = _FakeMarketClient(
            exchange_info=_make_exchange_info(tick_size="0.01"),
            order_book={
                "bids": [["50000", "10"]],
                "asks": [["50100", "10"]],
            },
        )
        account = _FakeAccountClient(
            balances=[{"asset": "USDT", "free": "10000"}]
        )
        validator = PreTradeValidator(market, account)
        report = validator.validate(
            symbol="BTCUSDT",
            side="buy",
            stake_amount=Decimal("500"),
            reference_price=Decimal("50000.01"),
        )
        precision_checks = [c for c in report.checks if c.name == "price_precision"]
        self.assertTrue(precision_checks[0].passed)

    def test_price_precision_warns_when_no_tick_size(self):
        info_no_price_filter = {
            "symbols": [{
                "symbol": "BTCUSDT",
                "status": "TRADING",
                "filters": [{"filterType": "LOT_SIZE", "stepSize": "0.00001"}],
            }]
        }
        market = _FakeMarketClient(
            exchange_info=info_no_price_filter,
            order_book={
                "bids": [["50000", "10"]],
                "asks": [["50100", "10"]],
            },
        )
        account = _FakeAccountClient(
            balances=[{"asset": "USDT", "free": "10000"}]
        )
        validator = PreTradeValidator(market, account)
        report = validator.validate(
            symbol="BTCUSDT",
            side="buy",
            stake_amount=Decimal("500"),
            reference_price=Decimal("50000"),
        )
        precision_checks = [c for c in report.checks if c.name == "price_precision"]
        self.assertTrue(precision_checks[0].passed)
        self.assertEqual(precision_checks[0].severity, "warn")

    def test_graceful_when_order_book_fails(self):
        market = _FakeMarketClient(
            exchange_info=_make_exchange_info(),
            order_book=None,
            tickers=[{"symbol": "BTCUSDT", "lastPrice": "50000"}],
        )
        account = _FakeAccountClient(
            balances=[{"asset": "USDT", "free": "10000"}]
        )

        class FailingMarketClient:
            def get_exchange_info(self, symbols=None):
                return _make_exchange_info()
            def get_order_book(self, symbol, limit=20):
                raise RuntimeError("network error")
            def get_tickers(self, symbols=None):
                return [{"symbol": "BTCUSDT", "lastPrice": "50000"}]

        validator = PreTradeValidator(FailingMarketClient(), account)
        report = validator.validate(
            symbol="BTCUSDT",
            side="buy",
            stake_amount=Decimal("500"),
            reference_price=Decimal("50000"),
        )
        self.assertFalse(report.blocked)
        liq = [c for c in report.checks if c.name == "liquidity"]
        self.assertTrue(liq[0].passed)
        self.assertEqual(liq[0].severity, "warn")


if __name__ == "__main__":
    unittest.main()
