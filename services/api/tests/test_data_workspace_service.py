from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.api.app.services.data_workspace_service import DataWorkspaceService  # noqa: E402


class DataWorkspaceServiceTests(unittest.TestCase):
    def test_workspace_returns_snapshot_states_and_filters(self) -> None:
        service = DataWorkspaceService(
            research_reader=_FakeResearchService(),
            market_reader=_FakeMarketService(),
            whitelist_provider=lambda: ["BTCUSDT", "ETHUSDT"],
            controls_builder=_fake_controls,
        )

        item = service.get_workspace(symbol="ETHUSDT", interval="4h", limit=120)

        self.assertEqual(item["status"], "ready")
        self.assertEqual(item["config_alignment"]["status"], "aligned")
        self.assertEqual(item["filters"]["selected_symbol"], "ETHUSDT")
        self.assertEqual(item["filters"]["selected_interval"], "4h")
        self.assertEqual(item["filters"]["limit"], 120)
        self.assertEqual(item["controls"]["lookback_days"], 30)
        self.assertEqual(item["controls"]["window_mode"], "fixed")
        self.assertEqual(item["controls"]["start_date"], "2026-01-01")
        self.assertEqual(item["controls"]["end_date"], "2026-02-01")
        self.assertIn("fixed", item["controls"]["available_window_modes"])
        self.assertEqual(item["snapshot"]["snapshot_id"], "dataset-abc123")
        self.assertEqual(item["snapshot"]["data_states"]["current"], "feature-ready")
        self.assertEqual(item["preview"]["symbol"], "ETHUSDT")
        self.assertEqual(item["preview"]["total_rows"], 3)
        self.assertIn("first_open_time", item["preview"])
        self.assertIn("last_close_time", item["preview"])
        self.assertEqual(item["symbols"][0]["symbol"], "BTCUSDT")
        self.assertIn("controls", item)

    def test_workspace_degrades_cleanly_when_research_is_unavailable(self) -> None:
        service = DataWorkspaceService(
            research_reader=_UnavailableResearchService(),
            market_reader=_FakeMarketService(),
            whitelist_provider=lambda: ["BTCUSDT"],
            controls_builder=_fake_controls,
        )

        item = service.get_workspace(symbol="BTCUSDT", interval="1h", limit=50)

        self.assertEqual(item["status"], "unavailable")
        self.assertEqual(item["snapshot"]["snapshot_id"], "")
        self.assertEqual(item["preview"]["total_rows"], 3)

    def test_workspace_marks_preview_failure_as_degraded_when_research_is_ready(self) -> None:
        service = DataWorkspaceService(
            research_reader=_FakeResearchService(),
            market_reader=_BrokenMarketService(),
            whitelist_provider=lambda: ["BTCUSDT"],
            controls_builder=_fake_controls,
        )

        item = service.get_workspace(symbol="BTCUSDT", interval="4h", limit=80)

        self.assertEqual(item["status"], "degraded")
        self.assertEqual(item["preview"]["status"], "unavailable")
        self.assertEqual(item["preview"]["total_rows"], 0)
        self.assertIn("preview unavailable", item["preview"]["detail"])

    def test_workspace_normalizes_invalid_symbol_and_interval(self) -> None:
        service = DataWorkspaceService(
            research_reader=_FakeResearchService(),
            market_reader=_FakeMarketService(),
            whitelist_provider=lambda: ["BTCUSDT", "ETHUSDT"],
            controls_builder=_fake_controls,
        )

        item = service.get_workspace(symbol="DOGEUSDT", interval="12h", limit=10)

        self.assertEqual(item["filters"]["selected_symbol"], "BTCUSDT")
        self.assertEqual(item["filters"]["selected_interval"], "4h")
        self.assertEqual(item["preview"]["symbol"], "BTCUSDT")
        self.assertEqual(item["preview"]["interval"], "4h")
        self.assertEqual(item["filters"]["available_intervals"][0], "1m")
        self.assertIn("4h", item["filters"]["available_intervals"])


class _FakeResearchService:
    def get_factory_report(self) -> dict[str, object]:
        return {
            "status": "ready",
            "backend": "qlib-fallback",
            "config_alignment": {
                "status": "aligned",
                "stale_fields": [],
                "note": "当前页面配置和最近一次研究结果已经对齐。",
            },
            "snapshots": {
                "training": {
                    "snapshot_id": "dataset-abc123",
                    "cache_signature": "abc123",
                    "active_data_state": "feature-ready",
                    "data_states": {
                        "raw": {"symbol_count": 2, "row_count": 240},
                        "cleaned": {"symbol_count": 2, "row_count": 220},
                        "feature-ready": {"symbol_count": 2, "row_count": 200},
                        "current": "feature-ready",
                    },
                }
            },
            "latest_training": {
                "training_context": {
                    "holding_window": "1-3d",
                    "sample_window": {
                        "training": {"start": 1, "end": 10, "count": 100},
                        "validation": {"start": 11, "end": 15, "count": 40},
                        "backtest": {"start": 16, "end": 20, "count": 30},
                    },
                }
            },
        }


class _UnavailableResearchService:
    def get_factory_report(self) -> dict[str, object]:
        return {"status": "unavailable", "backend": "qlib-fallback"}


class _FakeMarketService:
    def get_symbol_chart(self, symbol: str, interval: str, limit: int, allowed_symbols: tuple[str, ...]) -> dict[str, object]:
        return {
            "items": [
                {
                    "open_time": 1712016000000,
                    "open": "100.0",
                    "high": "101.0",
                    "low": "99.0",
                    "close": "100.5",
                    "volume": "1000.0",
                    "close_time": 1712030399999,
                },
                {
                    "open_time": 1712030400000,
                    "open": "100.5",
                    "high": "102.0",
                    "low": "100.0",
                    "close": "101.8",
                    "volume": "1200.0",
                    "close_time": 1712044799999,
                },
                {
                    "open_time": 1712044800000,
                    "open": "101.8",
                    "high": "103.0",
                    "low": "101.2",
                    "close": "102.6",
                    "volume": "1300.0",
                    "close_time": 1712059199999,
                },
            ]
        }


class _BrokenMarketService:
    def get_symbol_chart(self, symbol: str, interval: str, limit: int, allowed_symbols: tuple[str, ...]) -> dict[str, object]:
        raise RuntimeError("preview unavailable")


def _fake_controls() -> dict[str, object]:
    return {
        "config": {
            "data": {
                "selected_symbols": ["BTCUSDT", "ETHUSDT"],
                "primary_symbol": "BTCUSDT",
                "timeframes": ["4h", "1h"],
                "sample_limit": 120,
                "lookback_days": 30,
                "window_mode": "fixed",
                "start_date": "2026-01-01",
                "end_date": "2026-02-01",
            }
        },
        "options": {"window_modes": ["rolling", "fixed"]},
    }


if __name__ == "__main__":
    unittest.main()
