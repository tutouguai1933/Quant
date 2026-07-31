"""Unit tests for SlippageModel."""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import unittest

from services.api.app.services.slippage_model import SlippageConfig, SlippageModel


class SlippageModelTests(unittest.TestCase):

    def test_depth_cost_zero_when_order_book_empty(self):
        model = SlippageModel()
        est = model.estimate(
            symbol="BTCUSDT",
            side="buy",
            stake_amount=Decimal("500"),
            order_book={"bids": [], "asks": []},
            candles_4h=[],
        )
        self.assertEqual(est.expected_bps, Decimal("0"))

    def test_depth_cost_positive_for_asymmetric_book(self):
        order_book = {
            "bids": [["50000", "1"], ["49900", "2"], ["49800", "3"]],
            "asks": [["50100", "1"], ["50200", "2"], ["50300", "3"]],
        }
        model = SlippageModel()
        est = model.estimate(
            symbol="BTCUSDT",
            side="buy",
            stake_amount=Decimal("500"),
            order_book=order_book,
            candles_4h=[],
        )
        self.assertGreater(est.expected_bps, Decimal("0"))

    def test_volatility_zero_with_no_candles(self):
        model = SlippageModel()
        est = model.estimate(
            symbol="BTCUSDT",
            side="buy",
            stake_amount=Decimal("500"),
            order_book={"bids": [["50000", "10"]], "asks": [["50100", "10"]]},
            candles_4h=[],
        )
        self.assertEqual(est.worst_case_bps, est.expected_bps * 2)

    def test_volatility_computed_from_candles(self):
        candles = [
            {"close": "50000"}, {"close": "50100"}, {"close": "50200"},
            {"close": "50300"}, {"close": "50400"}, {"close": "50500"},
            {"close": "50600"}, {"close": "50700"}, {"close": "50800"},
            {"close": "50900"}, {"close": "51000"}, {"close": "51100"},
            {"close": "51200"}, {"close": "51300"}, {"close": "51400"},
            {"close": "51500"}, {"close": "51600"}, {"close": "51700"},
            {"close": "51800"}, {"close": "51900"}, {"close": "52000"},
        ]
        model = SlippageModel()
        est = model.estimate(
            symbol="BTCUSDT",
            side="buy",
            stake_amount=Decimal("500"),
            order_book={"bids": [["50000", "10"]], "asks": [["50100", "10"]]},
            candles_4h=candles,
        )
        self.assertGreater(est.worst_case_bps, Decimal("0"))

    def test_depth_coverage_pct_bounded_at_100(self):
        order_book = {
            "bids": [["50000", "100"]],
            "asks": [["50100", "100"]],
        }
        model = SlippageModel()
        est = model.estimate(
            symbol="BTCUSDT",
            side="buy",
            stake_amount=Decimal("1"),
            order_book=order_book,
            candles_4h=[],
        )
        self.assertEqual(est.depth_coverage_pct, Decimal("100"))

    def test_depth_coverage_low_when_thin_book(self):
        order_book = {
            "bids": [["50000", "0.001"]],
            "asks": [["50100", "0.001"]],
        }
        model = SlippageModel()
        est = model.estimate(
            symbol="BTCUSDT",
            side="buy",
            stake_amount=Decimal("50000"),
            order_book=order_book,
            candles_4h=[],
        )
        self.assertLess(est.depth_coverage_pct, Decimal("100"))
        self.assertGreater(est.depth_coverage_pct, Decimal("0"))

    def test_sell_side_uses_bids(self):
        order_book = {
            "bids": [["50000", "1"], ["49000", "2"]],
            "asks": [["51000", "1"], ["52000", "2"]],
        }
        model = SlippageModel()
        est_buy = model.estimate(
            symbol="BTCUSDT",
            side="buy",
            stake_amount=Decimal("500"),
            order_book=order_book,
            candles_4h=[],
        )
        est_sell = model.estimate(
            symbol="BTCUSDT",
            side="sell",
            stake_amount=Decimal("500"),
            order_book=order_book,
            candles_4h=[],
        )
        self.assertIsNotNone(est_buy.expected_bps)
        self.assertIsNotNone(est_sell.expected_bps)


if __name__ == "__main__":
    unittest.main()
