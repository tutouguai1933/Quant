from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.api.app.services.market_timeframe_service import (  # noqa: E402
    build_multi_timeframe_summary,
    get_supported_market_intervals,
    normalize_market_interval,
)


class MarketTimeframeServiceTests(unittest.TestCase):
    def test_normalize_market_interval_supports_binance_style_choices(self) -> None:
        self.assertEqual(normalize_market_interval("15m"), "15m")
        self.assertEqual(normalize_market_interval("1d"), "1d")
        self.assertEqual(normalize_market_interval("weird"), "4h")
        self.assertEqual(
            get_supported_market_intervals(),
            ("1m", "3m", "5m", "15m", "30m", "1h", "4h", "1d", "1w"),
        )

    def test_build_multi_timeframe_summary_keeps_interval_order_and_symbol(self) -> None:
        summary = build_multi_timeframe_summary(
            symbol="btcusdt",
            intervals=("1d", "4h"),
            evaluate_interval=lambda interval: {"decision": f"seen:{interval}"},
        )

        self.assertEqual(
            summary,
            [
                {"symbol": "BTCUSDT", "interval": "1d", "decision": "seen:1d"},
                {"symbol": "BTCUSDT", "interval": "4h", "decision": "seen:4h"},
            ],
        )


if __name__ == "__main__":
    unittest.main()
