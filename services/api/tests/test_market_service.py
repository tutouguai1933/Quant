from __future__ import annotations

import os
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.api.app.main import app  # noqa: E402
from services.api.app.routes import market as market_route  # noqa: E402
from services.api.app.services.indicator_service import build_indicator_summary  # noqa: E402
from services.api.app.services.market_service import MarketService  # noqa: E402
from services.api.app.services.market_service import (  # noqa: E402
    _build_chart_cache_key,
    normalize_kline_series,
    normalize_market_snapshot,
)


class FakeMarketClient:
    def __init__(
        self,
        tickers: list[dict[str, object]] | None = None,
        klines: list[list[object]] | None = None,
        klines_by_request: dict[tuple[str, str], list[list[object]]] | None = None,
    ) -> None:
        self.tickers = tickers or []
        self.klines = klines or []
        self.klines_by_request = klines_by_request or {}
        self.last_symbol: str | None = None
        self.last_interval: str | None = None
        self.last_limit: int | None = None
        self.requests: list[tuple[str, str, int]] = []

    def get_tickers(self) -> list[dict[str, object]]:
        return list(self.tickers)

    def get_klines(self, symbol: str, interval: str = "4h", limit: int = 200) -> list[list[object]]:
        self.last_symbol = symbol
        self.last_interval = interval
        self.last_limit = limit
        self.requests.append((symbol, interval, limit))
        requested_rows = self.klines_by_request.get((symbol, interval))
        if requested_rows is not None:
            return list(requested_rows)
        return list(self.klines)


class FakeStrategyCatalogService:
    def __init__(self, whitelist: list[str] | None = None) -> None:
        self.whitelist = whitelist or ["BTCUSDT", "ETHUSDT"]

    def get_whitelist(self) -> list[str]:
        return list(self.whitelist)

    def get_catalog(self) -> dict[str, object]:
        return {
            "whitelist": self.get_whitelist(),
            "strategies": [
                {
                    "key": "trend_breakout",
                    "display_name": "趋势突破",
                    "default_params": {
                        "timeframe": "1h",
                        "lookback_bars": 2,
                        "breakout_buffer_pct": 0.5,
                    },
                },
                {
                    "key": "trend_pullback",
                    "display_name": "趋势回调",
                    "default_params": {
                        "timeframe": "1h",
                        "lookback_bars": 2,
                        "pullback_depth_pct": 5.0,
                    },
                },
            ],
        }


class FakeResearchService:
    def __init__(self, symbols: dict[str, dict[str, object]] | None = None) -> None:
        self.symbols = symbols or {
            "BTCUSDT": {
                "symbol": "BTCUSDT",
                "score": "0.7100",
                "signal": "long",
                "model_version": "qlib-minimal-20260402120000",
                "explanation": "trend_gap=2.1%",
                "generated_at": "2026-04-02T12:00:00+00:00",
            }
        }

    def get_symbol_research(self, symbol: str) -> dict[str, object] | None:
        return self.symbols.get(symbol.strip().upper())


class MarketServiceTests(unittest.TestCase):
    @staticmethod
    def _make_candle_row(
        open_time: int,
        open_price: str,
        high: str,
        low: str,
        close: str,
        volume: str,
        close_time: int | None = None,
    ) -> dict[str, object]:
        return {
            "open_time": open_time,
            "open": open_price,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
            "close_time": close_time if close_time is not None else open_time + 3599999,
        }

    def test_normalize_market_snapshot(self) -> None:
        raw = {
            "symbol": "BTCUSDT",
            "lastPrice": "68000.00",
            "priceChangePercent": "3.10",
            "quoteVolume": "182000000.0",
        }

        item = normalize_market_snapshot(raw)

        self.assertEqual(item["symbol"], "BTCUSDT")
        self.assertEqual(item["last_price"], "68000.00")
        self.assertEqual(item["change_percent"], "3.10")
        self.assertEqual(item["quote_volume"], "182000000.0")

    def test_normalize_kline_series(self) -> None:
        raw = [
            [1710000000000, "67000", "68500", "66500", "68000", "1200", 1710003599999],
            [1710003600000, "bad"],
        ]

        data = normalize_kline_series(raw)

        self.assertEqual(data[0]["open_time"], 1710000000000)
        self.assertEqual(data[0]["open"], "67000")
        self.assertEqual(data[0]["high"], "68500")
        self.assertEqual(data[0]["low"], "66500")
        self.assertEqual(data[0]["close"], "68000")
        self.assertEqual(data[0]["volume"], "1200")
        self.assertEqual(data[0]["close_time"], 1710003599999)
        self.assertEqual(len(data), 1)

    def test_list_market_snapshots_filters_allowed_symbols(self) -> None:
        client = FakeMarketClient(
            tickers=[
                {
                    "symbol": "BTCUSDT",
                    "lastPrice": "68000.00",
                    "priceChangePercent": "3.10",
                    "quoteVolume": "182000000.0",
                },
                {
                    "symbol": "DOGEUSDT",
                    "lastPrice": "0.20",
                    "priceChangePercent": "1.25",
                    "quoteVolume": "35000000.0",
                },
            ]
        )

        service = MarketService(client=client, catalog_service=FakeStrategyCatalogService())
        items = service.list_market_snapshots(("BTCUSDT", "ETHUSDT"))

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["symbol"], "BTCUSDT")
        self.assertEqual(items[0]["last_price"], "68000.00")

    def test_list_market_snapshots_returns_strategy_view_for_whitelist_symbols(self) -> None:
        client = FakeMarketClient(
            tickers=[
                {
                    "symbol": "BTCUSDT",
                    "lastPrice": "68000.00",
                    "priceChangePercent": "3.10",
                    "quoteVolume": "182000000.0",
                },
                {
                    "symbol": "ETHUSDT",
                    "lastPrice": "3200.00",
                    "priceChangePercent": "-1.25",
                    "quoteVolume": "98000000.0",
                },
                {
                    "symbol": "DOGEUSDT",
                    "lastPrice": "0.20",
                    "priceChangePercent": "1.25",
                    "quoteVolume": "35000000.0",
                },
            ],
            klines_by_request={
                ("BTCUSDT", "1h"): [
                    [1710000000000, "100", "101", "99", "100", "10", 1710003599999],
                    [1710003600000, "100", "102", "99", "101", "11", 1710007199999],
                    [1710007200000, "101", "106", "100", "105", "12", 1710010799999],
                ],
                ("ETHUSDT", "1h"): [
                    [1710000000000, "100", "104", "99", "103", "10", 1710003599999],
                    [1710003600000, "103", "108", "102", "107", "11", 1710007199999],
                    [1710007200000, "107", "110", "106", "109", "12", 1710010799999],
                    [1710010800000, "108", "109", "104", "106", "13", 1710014399999],
                ],
            },
        )
        service = MarketService(client=client, catalog_service=FakeStrategyCatalogService())

        items = service.list_market_snapshots(("BTCUSDT", "ETHUSDT"))

        self.assertEqual([item["symbol"] for item in items], ["BTCUSDT", "ETHUSDT"])
        self.assertTrue(items[0]["is_whitelisted"])
        self.assertEqual(items[0]["recommended_strategy"], "trend_breakout")
        self.assertEqual(items[0]["trend_state"], "uptrend")
        self.assertTrue(items[1]["is_whitelisted"])
        self.assertEqual(items[1]["recommended_strategy"], "trend_pullback")
        self.assertEqual(items[1]["trend_state"], "pullback")

    def test_list_market_snapshots_limits_strategy_and_trend_values_to_known_set(self) -> None:
        client = FakeMarketClient(
            tickers=[
                {
                    "symbol": "BTCUSDT",
                    "lastPrice": "68000.00",
                    "priceChangePercent": "3.10",
                    "quoteVolume": "182000000.0",
                }
            ],
            klines_by_request={
                ("BTCUSDT", "1h"): [
                    [1710000000000, "100", "101", "99", "100", "10", 1710003599999],
                    [1710003600000, "100", "101", "99", "100", "11", 1710007199999],
                    [1710007200000, "100", "101", "99", "100", "12", 1710010799999],
                    [1710010800000, "100", "101", "99", "100", "13", 1710014399999],
                ],
            },
        )
        service = MarketService(client=client)

        items = service.list_market_snapshots(("BTCUSDT",))

        self.assertEqual(len(items), 1)
        self.assertIn(items[0]["recommended_strategy"], {"trend_breakout", "trend_pullback", "none"})
        self.assertIn(items[0]["trend_state"], {"uptrend", "pullback", "neutral"})

    def test_list_market_snapshots_returns_research_brief(self) -> None:
        client = FakeMarketClient(
            tickers=[
                {
                    "symbol": "BTCUSDT",
                    "lastPrice": "68000.00",
                    "priceChangePercent": "3.10",
                    "quoteVolume": "182000000.0",
                }
            ],
            klines_by_request={
                ("BTCUSDT", "1h"): [
                    [1710000000000, "100", "101", "99", "100", "10", 1710003599999],
                    [1710003600000, "100", "102", "99", "101", "11", 1710007199999],
                    [1710007200000, "101", "103", "100", "102", "12", 1710010799999],
                    [1710010800000, "102", "106", "101", "105", "13", 1710014399999],
                ],
            },
        )
        service = MarketService(
            client=client,
            catalog_service=FakeStrategyCatalogService(["BTCUSDT"]),
            research_reader=FakeResearchService(),
        )

        items = service.list_market_snapshots(("BTCUSDT",))
        brief = items[0]["research_brief"]

        self.assertEqual(brief["research_bias"], "bullish")
        self.assertEqual(brief["recommended_strategy"], "trend_breakout")
        self.assertEqual(brief["confidence"], "high")
        self.assertEqual(brief["research_gate"]["status"], "confirmed_by_research")
        self.assertEqual(brief["model_version"], "qlib-minimal-20260402120000")

    def test_get_symbol_chart_normalizes_kline_rows(self) -> None:
        client = FakeMarketClient(
            klines=[
                [1710000000000, "67000", "68500", "66500", "68000", "1200", 1710003599999],
                [1710003600000, "bad"],
            ]
        )

        service = MarketService(client=client)
        chart = service.get_symbol_chart("BTCUSDT", interval="1h", limit=50)

        self.assertEqual(client.last_symbol, "BTCUSDT")
        self.assertIn(("BTCUSDT", "1h", 50), client.requests)
        self.assertEqual(len(chart["items"]), 1)
        self.assertEqual(chart["items"][0]["close"], "68000")
        self.assertEqual(chart["overlays"]["ema_fast"]["sample_size"], 1)
        self.assertFalse(chart["overlays"]["ema_fast"]["ready"])
        self.assertTrue(chart["overlays"]["ema_fast"]["warnings"])
        self.assertEqual(chart["markers"]["signals"], [])

    def test_get_symbol_chart_returns_research_cockpit(self) -> None:
        client = FakeMarketClient(
            klines_by_request={
                ("BTCUSDT", "1h"): [
                    [1710000000000, "100", "101", "99", "100", "10", 1710003599999],
                    [1710003600000, "100", "102", "99", "101", "11", 1710007199999],
                    [1710007200000, "101", "103", "100", "102", "12", 1710010799999],
                    [1710010800000, "102", "106", "101", "105", "13", 1710014399999],
                ],
            }
        )
        service = MarketService(
            client=client,
            catalog_service=FakeStrategyCatalogService(["BTCUSDT"]),
            research_reader=FakeResearchService(),
        )

        chart = service.get_symbol_chart("BTCUSDT", interval="1h", limit=50, allowed_symbols=("BTCUSDT",))
        cockpit = chart["research_cockpit"]

        self.assertEqual(cockpit["research_bias"], "bullish")
        self.assertEqual(cockpit["research_gate"]["status"], "confirmed_by_research")
        self.assertEqual(cockpit["signal_count"], 1)
        self.assertEqual(cockpit["entry_hint"], "103.515")
        self.assertEqual(cockpit["stop_hint"], "99")

    def test_get_symbol_chart_returns_interval_metadata_and_multi_timeframe_summary(self) -> None:
        client = FakeMarketClient(
            klines_by_request={
                ("BTCUSDT", "1h"): [
                    [1710000000000, "100", "101", "99", "100", "10", 1710003599999],
                    [1710003600000, "100", "102", "99", "101", "11", 1710007199999],
                    [1710007200000, "101", "103", "100", "102", "12", 1710010799999],
                    [1710010800000, "102", "106", "101", "105", "13", 1710014399999],
                ],
                ("BTCUSDT", "15m"): [
                    [1710000000000, "100", "101", "99", "100", "10", 1710000899999],
                    [1710000900000, "100", "102", "99", "101", "11", 1710001799999],
                    [1710001800000, "101", "103", "100", "102", "12", 1710002699999],
                    [1710002700000, "102", "106", "101", "105", "13", 1710003599999],
                ],
                ("BTCUSDT", "4h"): [
                    [1710000000000, "100", "101", "99", "100", "10", 1710014399999],
                    [1710014400000, "100", "102", "99", "101", "11", 1710028799999],
                    [1710028800000, "101", "103", "100", "102", "12", 1710043199999],
                    [1710043200000, "102", "106", "101", "105", "13", 1710057599999],
                ],
                ("BTCUSDT", "1d"): [
                    [1710000000000, "100", "101", "99", "100", "10", 1710086399999],
                    [1710086400000, "100", "102", "99", "101", "11", 1710172799999],
                    [1710172800000, "101", "103", "100", "102", "12", 1710259199999],
                    [1710259200000, "102", "106", "101", "105", "13", 1710345599999],
                ],
            }
        )
        service = MarketService(
            client=client,
            catalog_service=FakeStrategyCatalogService(["BTCUSDT"]),
            research_reader=FakeResearchService(),
        )

        chart = service.get_symbol_chart("BTCUSDT", interval="15m", limit=50)

        self.assertEqual(chart["active_interval"], "15m")
        self.assertEqual(chart["supported_intervals"][0], "1m")
        self.assertEqual(chart["supported_intervals"][-1], "1w")
        self.assertEqual(
            [item["interval"] for item in chart["multi_timeframe_summary"]],
            ["1d", "4h", "1h", "15m"],
        )

    def test_get_symbol_chart_falls_back_to_default_interval_when_interval_is_invalid(self) -> None:
        client = FakeMarketClient(
            klines_by_request={
                ("BTCUSDT", "4h"): [
                    [1710000000000, "100", "101", "99", "100", "10", 1710014399999],
                    [1710014400000, "100", "102", "99", "101", "11", 1710028799999],
                    [1710028800000, "101", "103", "100", "102", "12", 1710043199999],
                    [1710043200000, "102", "106", "101", "105", "13", 1710057599999],
                ],
                ("BTCUSDT", "1h"): [
                    [1710000000000, "100", "101", "99", "100", "10", 1710003599999],
                    [1710003600000, "100", "102", "99", "101", "11", 1710007199999],
                    [1710007200000, "101", "103", "100", "102", "12", 1710010799999],
                    [1710010800000, "102", "106", "101", "105", "13", 1710014399999],
                ],
                ("BTCUSDT", "1d"): [
                    [1710000000000, "100", "101", "99", "100", "10", 1710086399999],
                    [1710086400000, "100", "102", "99", "101", "11", 1710172799999],
                    [1710172800000, "101", "103", "100", "102", "12", 1710259199999],
                    [1710259200000, "102", "106", "101", "105", "13", 1710345599999],
                ],
                ("BTCUSDT", "15m"): [
                    [1710000000000, "100", "101", "99", "100", "10", 1710000899999],
                    [1710000900000, "100", "102", "99", "101", "11", 1710001799999],
                    [1710001800000, "101", "103", "100", "102", "12", 1710002699999],
                    [1710002700000, "102", "106", "101", "105", "13", 1710003599999],
                ],
            }
        )
        service = MarketService(
            client=client,
            catalog_service=FakeStrategyCatalogService(["BTCUSDT"]),
            research_reader=FakeResearchService(),
        )

        chart = service.get_symbol_chart("BTCUSDT", interval="weird", limit=50)

        self.assertEqual(chart["active_interval"], "4h")
        self.assertIn(("BTCUSDT", "4h", 50), client.requests)

    def test_get_symbol_chart_does_not_leak_multi_timeframe_summary_outside_whitelist(self) -> None:
        client = FakeMarketClient(
            klines_by_request={
                ("BTCUSDT", "15m"): [
                    [1710000000000, "100", "101", "99", "100", "10", 1710000899999],
                    [1710000900000, "100", "102", "99", "101", "11", 1710001799999],
                    [1710001800000, "101", "103", "100", "102", "12", 1710002699999],
                    [1710002700000, "102", "106", "101", "105", "13", 1710003599999],
                ],
            }
        )
        service = MarketService(
            client=client,
            catalog_service=FakeStrategyCatalogService(["BTCUSDT"]),
            research_reader=FakeResearchService(),
        )

        chart = service.get_symbol_chart("BTCUSDT", interval="15m", limit=50, allowed_symbols=("ETHUSDT",))

        self.assertEqual(chart["items"], [])
        self.assertEqual(chart["active_interval"], "15m")
        self.assertEqual(chart["supported_intervals"][0], "1m")
        self.assertEqual(chart["supported_intervals"][-1], "1w")
        self.assertEqual(chart["multi_timeframe_summary"], [])
        self.assertEqual(client.requests, [])
        self.assertEqual(chart["research_cockpit"]["research_bias"], "unavailable")
        self.assertEqual(chart["research_cockpit"]["research_gate"]["status"], "unavailable")
        self.assertEqual(chart["research_cockpit"]["research_explanation"], "该币种暂无研究结论")
        self.assertEqual(chart["research_cockpit"]["model_version"], "")
        self.assertEqual(chart["research_cockpit"]["generated_at"], "")

    def test_get_symbol_chart_avoids_duplicate_reads_for_same_interval(self) -> None:
        client = FakeMarketClient(
            klines_by_request={
                ("BTCUSDT", "1h"): [
                    [1710000000000, "100", "101", "99", "100", "10", 1710003599999],
                    [1710003600000, "100", "102", "99", "101", "11", 1710007199999],
                    [1710007200000, "101", "103", "100", "102", "12", 1710010799999],
                    [1710010800000, "102", "106", "101", "105", "13", 1710014399999],
                ],
                ("BTCUSDT", "15m"): [
                    [1710000000000, "100", "101", "99", "100", "10", 1710000899999],
                    [1710000900000, "100", "102", "99", "101", "11", 1710001799999],
                    [1710001800000, "101", "103", "100", "102", "12", 1710002699999],
                    [1710002700000, "102", "106", "101", "105", "13", 1710003599999],
                ],
                ("BTCUSDT", "4h"): [
                    [1710000000000, "100", "101", "99", "100", "10", 1710014399999],
                    [1710014400000, "100", "102", "99", "101", "11", 1710028799999],
                    [1710028800000, "101", "103", "100", "102", "12", 1710043199999],
                    [1710043200000, "102", "106", "101", "105", "13", 1710057599999],
                ],
                ("BTCUSDT", "1d"): [
                    [1710000000000, "100", "101", "99", "100", "10", 1710086399999],
                    [1710086400000, "100", "102", "99", "101", "11", 1710172799999],
                    [1710172800000, "101", "103", "100", "102", "12", 1710259199999],
                    [1710259200000, "102", "106", "101", "105", "13", 1710345599999],
                ],
            }
        )
        service = MarketService(
            client=client,
            catalog_service=FakeStrategyCatalogService(["BTCUSDT"]),
            research_reader=FakeResearchService(),
        )

        service.get_symbol_chart("BTCUSDT", interval="15m", limit=50)

        interval_counts = {
            interval: len([request for request in client.requests if request[1] == interval])
            for interval in ("1d", "4h", "1h", "15m")
        }
        self.assertEqual(interval_counts, {"1d": 1, "4h": 1, "1h": 1, "15m": 1})

    def test_build_chart_cache_key_ignores_allowed_symbol_order(self) -> None:
        self.assertEqual(
            _build_chart_cache_key("15m", ("BTCUSDT", "ETHUSDT")),
            _build_chart_cache_key("15m", ("ETHUSDT", "BTCUSDT")),
        )

    def test_build_indicator_summary_marks_insufficient_samples_not_ready(self) -> None:
        items = [
            self._make_candle_row(1710000000000, "10", "11", "9", "10", "100"),
            self._make_candle_row(1710003600000, "11", "12", "10", "11", "110"),
            self._make_candle_row(1710007200000, "12", "13", "11", "12", "120"),
        ]

        summary = build_indicator_summary(items, now=datetime(2026, 4, 1, 7, 0, tzinfo=timezone.utc))

        self.assertEqual(set(summary.keys()), {"ema_fast", "ema_slow", "atr", "rsi", "volume_sma"})
        self.assertFalse(summary["ema_fast"]["ready"])
        self.assertIsNone(summary["ema_fast"]["value"])
        self.assertEqual(summary["ema_fast"]["sample_size"], 3)
        self.assertIn("insufficient_samples", " ".join(summary["ema_fast"]["warnings"]))
        self.assertTrue(summary["ema_fast"]["last_candle_closed"])

    def test_build_indicator_summary_marks_last_candle_open_when_close_time_is_future(self) -> None:
        future_close_time = int(datetime(2026, 4, 1, 1, 0, tzinfo=timezone.utc).timestamp() * 1000)
        items = [
            self._make_candle_row(
                1710000000000 + index * 3600000,
                str(100 + index),
                str(101 + index),
                str(99 + index),
                str(100 + index),
                str(1000 + index * 10),
                close_time=future_close_time if index == 29 else None,
            )
            for index in range(30)
        ]

        summary = build_indicator_summary(items, now=datetime(2026, 4, 1, 0, 0, tzinfo=timezone.utc))

        self.assertTrue(summary["ema_fast"]["ready"])
        self.assertFalse(summary["ema_fast"]["last_candle_closed"])

    def test_build_indicator_summary_marks_empty_sample_state_clearly(self) -> None:
        summary = build_indicator_summary([], now=datetime(2026, 4, 1, 0, 0, tzinfo=timezone.utc))

        self.assertEqual(summary["ema_fast"]["sample_size"], 0)
        self.assertFalse(summary["ema_fast"]["ready"])
        self.assertIn("insufficient_samples:0/12", summary["ema_fast"]["warnings"])
        self.assertFalse(summary["ema_fast"]["last_candle_closed"])

    def test_build_indicator_summary_marks_all_bad_rows_clearly(self) -> None:
        items = [
            {"open_time": 1, "close_time": 2, "open": "bad", "high": "bad", "low": "bad", "close": "bad", "volume": "bad"},
            {"open_time": 3, "close_time": 4, "open": "bad", "high": "bad", "low": "bad", "close": "bad", "volume": "bad"},
        ]

        summary = build_indicator_summary(items, now=datetime(2026, 4, 1, 0, 0, tzinfo=timezone.utc))

        self.assertEqual(summary["ema_fast"]["sample_size"], 0)
        self.assertFalse(summary["ema_fast"]["ready"])
        self.assertIn("invalid_candle_rows:2", summary["ema_fast"]["warnings"])
        self.assertIn("insufficient_samples:0/12", summary["ema_fast"]["warnings"])
        self.assertFalse(summary["ema_fast"]["last_candle_closed"])

    def test_build_indicator_summary_propagates_bad_row_warning(self) -> None:
        items = [
            self._make_candle_row(1710000000000 + index * 3600000, str(100 + index), str(101 + index), str(99 + index), str(100 + index), str(1000 + index * 10))
            for index in range(29)
        ]
        items.insert(10, {"open_time": 1710036000000, "close_time": 1710039599999, "close": "bad"})

        summary = build_indicator_summary(items, now=datetime(2026, 4, 1, 7, 0, tzinfo=timezone.utc))

        self.assertEqual(summary["ema_fast"]["sample_size"], 29)
        self.assertTrue(summary["ema_fast"]["ready"])
        self.assertIn("invalid_candle_rows:1", summary["ema_fast"]["warnings"])
        self.assertTrue(summary["ema_fast"]["last_candle_closed"])

    def test_build_indicator_summary_marks_ready_for_long_valid_series(self) -> None:
        items = [
            self._make_candle_row(1710000000000 + index * 3600000, str(100 + index), str(101 + index), str(99 + index), str(100 + index), str(1000 + index * 10))
            for index in range(30)
        ]

        summary = build_indicator_summary(items, now=datetime(2026, 4, 1, 7, 0, tzinfo=timezone.utc))

        self.assertTrue(summary["ema_fast"]["ready"])
        self.assertIsInstance(summary["ema_fast"]["value"], str)
        self.assertEqual(summary["ema_fast"]["sample_size"], 30)
        self.assertFalse(summary["ema_fast"]["warnings"])

    def test_market_route_returns_success_envelope(self) -> None:
        fake_service = FakeMarketClient(
            tickers=[
                {
                    "symbol": "BTCUSDT",
                    "lastPrice": "68000.00",
                    "priceChangePercent": "3.10",
                    "quoteVolume": "182000000.0",
                }
            ],
            klines=[
                [1710000000000, "67000", "68500", "66500", "68000", "1200", 1710003599999],
                [1710003600000, "bad"],
            ],
        )
        original_service = market_route.service

        with patch.dict(os.environ, {"QUANT_MARKET_SYMBOLS": "BTCUSDT"}, clear=False):
            market_route.service = MarketService(
                client=fake_service,
                catalog_service=FakeStrategyCatalogService(["BTCUSDT"]),
            )
            try:
                response = market_route.list_market()
                chart_response = market_route.get_market_chart("btcusdt", interval="1h", limit=50)
            finally:
                market_route.service = original_service

        self.assertEqual(set(response.keys()), {"data", "error", "meta"})
        self.assertIsNone(response["error"])
        self.assertEqual(response["data"]["items"][0]["symbol"], "BTCUSDT")
        self.assertIn("recommended_strategy", response["data"]["items"][0])
        self.assertIn("trend_state", response["data"]["items"][0])
        self.assertIn(response["data"]["items"][0]["recommended_strategy"], {"trend_breakout", "trend_pullback", "none"})
        self.assertIn(response["data"]["items"][0]["trend_state"], {"uptrend", "pullback", "neutral"})

        self.assertEqual(set(chart_response.keys()), {"data", "error", "meta"})
        self.assertIsNone(chart_response["error"])
        self.assertEqual(chart_response["data"]["items"][0]["close"], "68000")
        self.assertIn("overlays", chart_response["data"])
        self.assertIn("markers", chart_response["data"])
        self.assertEqual(chart_response["data"]["overlays"]["ema_fast"]["sample_size"], 1)
        self.assertEqual(
            set(chart_response["data"]["overlays"].keys()),
            {"ema_fast", "ema_slow", "atr", "rsi", "volume_sma"},
        )
        self.assertEqual(
            set(chart_response["data"]["markers"].keys()),
            {"signals", "entries", "stops"},
        )
        self.assertEqual(chart_response["data"]["markers"]["signals"], [])
        self.assertEqual(chart_response["data"]["markers"]["entries"], [])
        self.assertEqual(chart_response["data"]["markers"]["stops"], [])
        self.assertIn("strategy_context", chart_response["data"])
        self.assertIn("research_brief", response["data"]["items"][0])
        self.assertIn("research_cockpit", chart_response["data"])
        self.assertIn("freqtrade_readiness", chart_response["data"])

    def test_market_chart_returns_strategy_context_and_marker_hints(self) -> None:
        fake_service = FakeMarketClient(
            klines_by_request={
                ("BTCUSDT", "1h"): [
                    [1710000000000, "100", "101", "99", "100", "10", 1710003599999],
                    [1710003600000, "100", "102", "99", "101", "11", 1710007199999],
                    [1710007200000, "101", "103", "100", "102", "12", 1710010799999],
                    [1710010800000, "102", "106", "101", "105", "13", 1710014399999],
                ],
            }
        )
        original_service = market_route.service

        with patch.dict(os.environ, {"QUANT_MARKET_SYMBOLS": "BTCUSDT"}, clear=False):
            market_route.service = MarketService(
                client=fake_service,
                catalog_service=FakeStrategyCatalogService(["BTCUSDT"]),
            )
            try:
                response = market_route.get_market_chart("btcusdt", interval="1h", limit=50)
            finally:
                market_route.service = original_service

        self.assertEqual(response["data"]["strategy_context"]["recommended_strategy"], "trend_breakout")
        self.assertEqual(response["data"]["strategy_context"]["trend_state"], "uptrend")
        self.assertIn("trend_breakout", response["data"]["strategy_context"]["evaluations"])
        self.assertIn("trend_pullback", response["data"]["strategy_context"]["evaluations"])
        self.assertTrue(response["data"]["markers"]["entries"])
        self.assertTrue(response["data"]["markers"]["stops"])
        self.assertEqual(response["data"]["freqtrade_readiness"]["backend"], "memory")
        self.assertFalse(response["data"]["freqtrade_readiness"]["ready_for_real_freqtrade"])

    def test_market_chart_respects_symbol_whitelist_boundary(self) -> None:
        fake_service = FakeMarketClient(
            klines=[[1710000000000, "67000", "68500", "66500", "68000", "1200", 1710003599999]]
        )
        original_service = market_route.service

        with patch.dict(os.environ, {"QUANT_MARKET_SYMBOLS": "ETHUSDT"}, clear=False):
            market_route.service = MarketService(client=fake_service)
            try:
                response = market_route.get_market_chart("btcusdt", interval="1h", limit=50)
            finally:
                market_route.service = original_service

        self.assertEqual(response["data"]["items"], [])
        self.assertFalse(response["data"]["overlays"]["ema_fast"]["ready"])
        self.assertIn("symbol_not_in_market_whitelist", " ".join(response["data"]["overlays"]["ema_fast"]["warnings"]))

    def test_main_app_includes_market_router(self) -> None:
        router_prefixes = []
        for router in getattr(app, "routers", []):
            prefix = getattr(router, "prefix", None)
            if prefix is None:
                prefix = getattr(router, "kwargs", {}).get("prefix")
            router_prefixes.append(prefix)

        self.assertIn("/api/v1/market", router_prefixes)


if __name__ == "__main__":
    unittest.main()
