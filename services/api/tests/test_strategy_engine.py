from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import services.api.app.routes.signals as signals_route  # noqa: E402
from services.api.app.routes.signals import run_strategy  # noqa: E402
from services.api.app.services.strategy_engine import apply_research_soft_gate  # noqa: E402
from services.api.app.services.strategy_engine import evaluate_trend_breakout  # noqa: E402
from services.api.app.services.strategy_engine import evaluate_trend_pullback  # noqa: E402
import services.api.app.services.strategy_catalog as strategy_catalog_module  # noqa: E402


class StrategyEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self._market_service_backup = signals_route.market_service
        self._strategy_catalog_route_backup = signals_route.strategy_catalog_service
        self._strategy_catalog_backup = strategy_catalog_module.strategy_catalog_service
        self._research_service_backup = signals_route.research_service
        self.market_service = _FakeMarketService()
        signals_route.market_service = self.market_service
        self.strategy_catalog_service = _FakeStrategyCatalogService()
        strategy_catalog_module.strategy_catalog_service = self.strategy_catalog_service
        signals_route.strategy_catalog_service = self.strategy_catalog_service
        signals_route.research_service = _FakeNeutralResearchService()

    def tearDown(self) -> None:
        signals_route.market_service = self._market_service_backup
        signals_route.strategy_catalog_service = self._strategy_catalog_route_backup
        strategy_catalog_module.strategy_catalog_service = self._strategy_catalog_backup
        signals_route.research_service = self._research_service_backup

    def test_evaluate_trend_breakout_breaks_above_recent_high(self) -> None:
        result = evaluate_trend_breakout(
            "BTCUSDT",
            _candles(
                [
                    (100, 101, 99, 100),
                    (100, 102, 99, 101),
                    (101, 106, 100, 105),
                ]
            ),
            timeframe="1h",
            lookback_bars=2,
            breakout_buffer_pct=0.5,
        )

        self.assertEqual(result["decision"], "signal")
        self.assertEqual(result["strategy_id"], "trend_breakout")
        self.assertEqual(result["timeframe"], "1h")
        self.assertEqual(result["lookback_bars"], 2)
        self.assertEqual(result["overlays"]["history_bars_used"], 2)

    def test_evaluate_trend_breakout_breaks_below_recent_low(self) -> None:
        result = evaluate_trend_breakout(
            "BTCUSDT",
            _candles(
                [
                    (100, 101, 99, 100),
                    (100, 102, 99, 101),
                    (98, 99, 95, 96),
                ]
            ),
            timeframe="1h",
            lookback_bars=2,
            breakout_buffer_pct=0.5,
        )

        self.assertEqual(result["decision"], "block")
        self.assertEqual(result["strategy_id"], "trend_breakout")

    def test_evaluate_trend_breakout_stays_in_range(self) -> None:
        result = evaluate_trend_breakout(
            "BTCUSDT",
            _candles(
                [
                    (100, 105, 99, 101),
                    (101, 106, 100, 104),
                    (102, 105, 101, 103),
                ]
            ),
            timeframe="1h",
            lookback_bars=2,
            breakout_buffer_pct=2.0,
        )

        self.assertEqual(result["decision"], "watch")
        self.assertEqual(result["reason"], "close_stays_inside_recent_range")
        self.assertEqual(result["overlays"]["history_bars_used"], 2)

    def test_research_soft_gate_downgrades_breakout_signal_when_score_is_bearish(self) -> None:
        base_result = evaluate_trend_breakout(
            "BTCUSDT",
            _candles(
                [
                    (100, 101, 99, 100),
                    (100, 102, 99, 101),
                    (101, 106, 100, 105),
                ]
            ),
            timeframe="1h",
            lookback_bars=2,
            breakout_buffer_pct=0.5,
        )

        gated_result = apply_research_soft_gate(
            base_result,
            {
                "score": "0.3200",
                "signal": "short",
                "model_version": "qlib-minimal-test",
                "explanation": "bearish",
            },
        )

        self.assertEqual(gated_result["decision"], "watch")
        self.assertEqual(gated_result["reason"], "close_breaks_recent_high_soft_blocked_by_research")
        self.assertEqual(gated_result["confidence"], "low")
        self.assertEqual(gated_result["research_gate"]["status"], "suppressed_by_research")

    def test_evaluate_trend_pullback_signals_after_reclaiming_pullback_level(self) -> None:
        result = evaluate_trend_pullback(
            "BTCUSDT",
            _candles(
                [
                    (100, 104, 99, 103),
                    (103, 108, 102, 107),
                    (107, 110, 106, 109),
                    (108, 109, 104, 106),
                ]
            ),
            timeframe="1h",
            lookback_bars=2,
            pullback_depth_pct=5.0,
        )

        self.assertEqual(result["strategy_id"], "trend_pullback")
        self.assertEqual(result["decision"], "signal")
        self.assertEqual(result["reason"], "close_reclaims_pullback_level")
        self.assertEqual(result["lookback_bars"], 2)
        self.assertEqual(result["overlays"]["history_bars_used"], 2)

    def test_research_soft_gate_confirms_pullback_signal_when_score_is_supportive(self) -> None:
        base_result = evaluate_trend_pullback(
            "BTCUSDT",
            _candles(
                [
                    (100, 104, 99, 103),
                    (103, 108, 102, 107),
                    (107, 110, 106, 109),
                    (108, 109, 104, 106),
                ]
            ),
            timeframe="1h",
            lookback_bars=2,
            pullback_depth_pct=5.0,
        )

        gated_result = apply_research_soft_gate(
            base_result,
            {
                "score": "0.7100",
                "signal": "long",
                "model_version": "qlib-minimal-test",
                "explanation": "bullish",
            },
        )

        self.assertEqual(gated_result["decision"], "signal")
        self.assertEqual(gated_result["reason"], "close_reclaims_pullback_level_research_confirmed")
        self.assertEqual(gated_result["confidence"], "high")
        self.assertEqual(gated_result["research_gate"]["status"], "confirmed_by_research")

    def test_research_soft_gate_treats_nan_score_as_invalid(self) -> None:
        base_result = evaluate_trend_breakout(
            "BTCUSDT",
            _candles(
                [
                    (100, 101, 99, 100),
                    (100, 102, 99, 101),
                    (101, 106, 100, 105),
                ]
            ),
            timeframe="1h",
            lookback_bars=2,
            breakout_buffer_pct=0.5,
        )

        gated_result = apply_research_soft_gate(
            base_result,
            {
                "score": "NaN",
                "signal": "long",
                "model_version": "qlib-minimal-test",
                "explanation": "bad score",
            },
        )

        self.assertEqual(gated_result["decision"], "signal")
        self.assertEqual(gated_result["confidence"], "medium")
        self.assertEqual(gated_result["research_gate"]["status"], "invalid_score")

    def test_evaluate_trend_pullback_blocks_when_trend_is_lost(self) -> None:
        result = evaluate_trend_pullback(
            "BTCUSDT",
            _candles(
                [
                    (100, 104, 99, 103),
                    (103, 108, 102, 107),
                    (107, 110, 106, 109),
                    (104, 105, 94, 95),
                ]
            ),
            timeframe="1h",
            lookback_bars=2,
            pullback_depth_pct=5.0,
        )

        self.assertEqual(result["decision"], "block")
        self.assertEqual(result["reason"], "structure_low_broken")

    def test_evaluate_trend_pullback_watches_when_pullback_has_not_completed(self) -> None:
        result = evaluate_trend_pullback(
            "BTCUSDT",
            _candles(
                [
                    (100, 104, 99, 103),
                    (103, 108, 102, 107),
                    (107, 110, 106, 109),
                    (108, 109, 105, 106),
                ]
            ),
            timeframe="1h",
            lookback_bars=2,
            pullback_depth_pct=5.0,
        )

        self.assertEqual(result["decision"], "watch")
        self.assertEqual(result["reason"], "pullback_pending")

    def test_evaluate_trend_pullback_returns_unavailable_when_history_is_shorter_than_lookback_plus_one(self) -> None:
        result = evaluate_trend_pullback(
            "BTCUSDT",
            _candles(
                [
                    (100, 104, 99, 103),
                    (103, 108, 102, 107),
                    (107, 110, 106, 109),
                    (108, 109, 101, 106),
                ]
            ),
            timeframe="1h",
            lookback_bars=4,
            pullback_depth_pct=5.0,
        )

        self.assertEqual(result["decision"], "evaluation_unavailable")
        self.assertEqual(result["reason"], "insufficient_history_for_lookback")

    def test_evaluate_trend_pullback_blocks_when_structure_low_is_broken(self) -> None:
        result = evaluate_trend_pullback(
            "BTCUSDT",
            _candles(
                [
                    (100, 104, 99, 103),
                    (103, 108, 102, 107),
                    (107, 110, 106, 109),
                    (108, 109, 101, 106),
                    (106, 107, 97, 98),
                ]
            ),
            timeframe="1h",
            lookback_bars=4,
            pullback_depth_pct=5.0,
        )

        self.assertEqual(result["decision"], "block")
        self.assertEqual(result["reason"], "structure_low_broken")

    def test_strategy_run_route_returns_uniform_envelope(self) -> None:
        response = run_strategy({"strategy_id": "trend_breakout", "symbol": "BTCUSDT"})

        self.assertEqual(set(response.keys()), {"data", "error", "meta"})
        self.assertIsNone(response["error"])
        self.assertEqual(response["data"]["item"]["strategy_id"], "trend_breakout")
        self.assertEqual(response["data"]["item"]["symbol"], "BTCUSDT")
        self.assertEqual(response["data"]["item"]["timeframe"], "15m")
        self.assertEqual(response["data"]["item"]["lookback_bars"], 3)
        self.assertEqual(response["data"]["item"]["decision"], "watch")
        self.assertEqual(response["data"]["item"]["overlays"]["history_bars_used"], 3)
        self.assertEqual(self.market_service.calls[-1]["interval"], "15m")
        self.assertEqual(self.market_service.calls[-1]["limit"], 4)

    def test_strategy_run_route_marks_symbol_outside_whitelist_as_unavailable(self) -> None:
        response = run_strategy({"strategy_id": "trend_breakout", "symbol": "XRPUSDT"})

        self.assertEqual(response["data"]["item"]["decision"], "evaluation_unavailable")
        self.assertNotEqual(response["data"]["item"]["decision"], "watch")
        self.assertEqual(response["data"]["item"]["reason"], "symbol_not_in_market_whitelist")

    def test_strategy_run_route_marks_empty_chart_as_unavailable(self) -> None:
        response = run_strategy({"strategy_id": "trend_breakout", "symbol": "EMPTYUSDT"})

        self.assertEqual(response["data"]["item"]["decision"], "evaluation_unavailable")
        self.assertEqual(response["data"]["item"]["reason"], "empty_chart")

    def test_strategy_run_route_rejects_missing_symbol(self) -> None:
        response = run_strategy({"strategy_id": "trend_breakout"})

        self.assertEqual(response["error"]["code"], "invalid_request")
        self.assertIn("symbol", response["error"]["message"])

    def test_strategy_run_route_rejects_none_symbol(self) -> None:
        response = run_strategy({"strategy_id": "trend_breakout", "symbol": None})

        self.assertEqual(response["error"]["code"], "invalid_request")
        self.assertIn("symbol", response["error"]["message"])

    def test_strategy_run_route_rejects_unknown_strategy_id(self) -> None:
        response = run_strategy({"strategy_id": "mean_reversion", "symbol": "BTCUSDT"})

        self.assertEqual(set(response.keys()), {"data", "error", "meta"})
        self.assertIsNone(response["data"])
        self.assertEqual(response["error"]["code"], "unsupported_strategy")

    def test_strategy_run_route_supports_trend_pullback(self) -> None:
        response = run_strategy({"strategy_id": "trend_pullback", "symbol": "BTCUSDT"})

        self.assertIsNone(response["error"])
        self.assertEqual(response["data"]["item"]["strategy_id"], "trend_pullback")
        self.assertEqual(response["data"]["item"]["timeframe"], "30m")
        self.assertEqual(response["data"]["item"]["lookback_bars"], 4)
        self.assertEqual(response["data"]["item"]["decision"], "signal")
        self.assertEqual(self.market_service.calls[-1]["interval"], "30m")
        self.assertEqual(self.market_service.calls[-1]["limit"], 5)

    def test_strategy_run_route_returns_unavailable_when_pullback_strategy_is_missing_from_catalog(self) -> None:
        missing_strategy_catalog_service = _FakeMissingPullbackStrategyCatalogService()
        strategy_catalog_module.strategy_catalog_service = missing_strategy_catalog_service
        signals_route.strategy_catalog_service = missing_strategy_catalog_service

        response = run_strategy({"strategy_id": "trend_pullback", "symbol": "BTCUSDT"})

        self.assertEqual(response["data"]["item"]["decision"], "evaluation_unavailable")
        self.assertEqual(response["data"]["item"]["reason"], "strategy_not_in_catalog")
        self.assertEqual(self.market_service.calls, [])

    def test_strategy_run_route_returns_unavailable_when_pullback_default_params_missing(self) -> None:
        missing_params_catalog_service = _FakeMissingPullbackDefaultParamsCatalogService()
        strategy_catalog_module.strategy_catalog_service = missing_params_catalog_service
        signals_route.strategy_catalog_service = missing_params_catalog_service

        response = run_strategy({"strategy_id": "trend_pullback", "symbol": "BTCUSDT"})

        self.assertEqual(response["data"]["item"]["decision"], "evaluation_unavailable")
        self.assertEqual(response["data"]["item"]["reason"], "missing_default_params")
        self.assertEqual(self.market_service.calls, [])

    def test_strategy_run_route_returns_unavailable_when_pullback_parameter_is_not_numeric(self) -> None:
        invalid_params_catalog_service = _FakeInvalidPullbackParamsCatalogService()
        strategy_catalog_module.strategy_catalog_service = invalid_params_catalog_service
        signals_route.strategy_catalog_service = invalid_params_catalog_service

        response = run_strategy({"strategy_id": "trend_pullback", "symbol": "BTCUSDT"})

        self.assertEqual(response["data"]["item"]["decision"], "evaluation_unavailable")
        self.assertEqual(response["data"]["item"]["reason"], "invalid_pullback_depth_pct")
        self.assertEqual(self.market_service.calls, [])

    def test_strategy_run_route_uses_catalog_timeframe_and_lookback(self) -> None:
        response = run_strategy({"strategy_id": "trend_breakout", "symbol": "BTCUSDT"})

        self.assertEqual(response["data"]["item"]["timeframe"], "15m")
        self.assertEqual(response["data"]["item"]["lookback_bars"], 3)

    def test_strategy_run_route_applies_research_soft_gate(self) -> None:
        signals_route.research_service = _FakeBearishResearchService()
        signals_route.market_service = _FakeSignalMarketService()

        response = run_strategy({"strategy_id": "trend_breakout", "symbol": "BTCUSDT"})

        self.assertEqual(response["data"]["item"]["decision"], "watch")
        self.assertEqual(response["data"]["item"]["confidence"], "low")
        self.assertEqual(response["data"]["item"]["research_gate"]["status"], "suppressed_by_research")

    def test_strategy_run_route_rejects_invalid_lookback_bars(self) -> None:
        invalid_catalog_service = _FakeInvalidLookbackCatalogService()
        strategy_catalog_module.strategy_catalog_service = invalid_catalog_service
        signals_route.strategy_catalog_service = invalid_catalog_service

        response = run_strategy({"strategy_id": "trend_breakout", "symbol": "BTCUSDT"})

        self.assertEqual(response["data"]["item"]["decision"], "evaluation_unavailable")
        self.assertEqual(response["data"]["item"]["reason"], "invalid_lookback_bars")
        self.assertEqual(response["meta"]["lookback_bars"], 0)
        self.assertEqual(self.market_service.calls, [])


class _FakeMarketService:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def get_symbol_chart(
        self,
        symbol: str,
        interval: str = "4h",
        limit: int = 200,
        allowed_symbols: tuple[str, ...] | None = None,
    ) -> dict[str, object]:
        self.calls.append(
            {
                "symbol": symbol,
                "interval": interval,
                "limit": limit,
                "allowed_symbols": allowed_symbols,
            }
        )
        if symbol == "XRPUSDT":
            return {"items": [], "overlays": {}, "markers": {}}
        if symbol == "EMPTYUSDT":
            return {"items": [], "overlays": {}, "markers": {}}
        return {
            "items": [
                {"open": "100", "high": "101", "low": "99", "close": "100", "volume": "10"},
                {"open": "101", "high": "103", "low": "100", "close": "102", "volume": "11"},
                {"open": "102", "high": "104", "low": "101", "close": "103", "volume": "12"},
                {"open": "103", "high": "105", "low": "102", "close": "104", "volume": "13"},
                {"open": "104", "high": "110", "low": "101", "close": "103", "volume": "14"},
            ],
            "overlays": {},
            "markers": {},
        }


def _candles(rows: list[tuple[int, int, int, int]]) -> list[dict[str, object]]:
    candles: list[dict[str, object]] = []
    for index, (open_price, high, low, close) in enumerate(rows, start=1):
        candles.append(
            {
                "open_time": index * 2 - 1,
                "open": str(open_price),
                "high": str(high),
                "low": str(low),
                "close": str(close),
                "volume": "10",
                "close_time": index * 2,
            }
        )
    return candles


class _FakeStrategyCatalogService:
    def get_whitelist(self) -> list[str]:
        return ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "EMPTYUSDT"]

    def get_catalog(self) -> dict[str, object]:
        return {
            "whitelist": self.get_whitelist(),
            "strategies": [
                {
                    "key": "trend_breakout",
                    "display_name": "趋势突破",
                    "description": "test override",
                    "default_params": {
                        "timeframe": "15m",
                        "lookback_bars": 3,
                        "breakout_buffer_pct": 2.0,
                    },
                },
                {
                    "key": "trend_pullback",
                    "display_name": "趋势回调",
                    "description": "test override",
                    "default_params": {
                        "timeframe": "30m",
                        "lookback_bars": 4,
                        "pullback_depth_pct": 3.0,
                    },
                }
            ],
        }


class _FakeSignalMarketService(_FakeMarketService):
    def get_symbol_chart(
        self,
        symbol: str,
        interval: str = "4h",
        limit: int = 200,
        allowed_symbols: tuple[str, ...] | None = None,
    ) -> dict[str, object]:
        self.calls.append(
            {
                "symbol": symbol,
                "interval": interval,
                "limit": limit,
                "allowed_symbols": allowed_symbols,
            }
        )
        return {
            "items": [
                {"open": "100", "high": "101", "low": "99", "close": "100", "volume": "10"},
                {"open": "100", "high": "102", "low": "99", "close": "101", "volume": "11"},
                {"open": "101", "high": "106", "low": "100", "close": "105", "volume": "12"},
            ],
            "overlays": {},
            "markers": {},
        }


class _FakeInvalidLookbackCatalogService(_FakeStrategyCatalogService):
    def get_catalog(self) -> dict[str, object]:
        catalog = super().get_catalog()
        catalog["strategies"][0]["default_params"]["lookback_bars"] = 0
        return catalog


class _FakeMissingPullbackStrategyCatalogService(_FakeStrategyCatalogService):
    def get_catalog(self) -> dict[str, object]:
        catalog = super().get_catalog()
        catalog["strategies"] = [catalog["strategies"][0]]
        return catalog


class _FakeMissingPullbackDefaultParamsCatalogService(_FakeStrategyCatalogService):
    def get_catalog(self) -> dict[str, object]:
        catalog = super().get_catalog()
        del catalog["strategies"][1]["default_params"]
        return catalog


class _FakeInvalidPullbackParamsCatalogService(_FakeStrategyCatalogService):
    def get_catalog(self) -> dict[str, object]:
        catalog = super().get_catalog()
        catalog["strategies"][1]["default_params"]["pullback_depth_pct"] = "oops"
        return catalog


class _FakeNeutralResearchService:
    def get_symbol_research(self, symbol: str) -> dict[str, object] | None:
        return None


class _FakeBearishResearchService:
    def get_symbol_research(self, symbol: str) -> dict[str, object] | None:
        return {
            "symbol": symbol,
            "score": "0.3200",
            "signal": "short",
            "model_version": "qlib-minimal-test",
            "explanation": "bearish",
        }


if __name__ == "__main__":
    unittest.main()
