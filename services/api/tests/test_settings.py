from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.api.app.core.settings import DEFAULT_MARKET_SYMBOLS, Settings  # noqa: E402


class SettingsTests(unittest.TestCase):
    def setUp(self) -> None:
        self._env_backup = os.environ.copy()

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._env_backup)

    def test_default_mode_is_demo(self) -> None:
        self._clear_runtime_env()

        settings = Settings.from_env()

        self.assertEqual(settings.runtime_mode, "demo")
        self.assertEqual(settings.market_symbols, DEFAULT_MARKET_SYMBOLS)

    def test_settings_repr_hides_binance_credentials(self) -> None:
        os.environ["QUANT_RUNTIME_MODE"] = "demo"
        os.environ["BINANCE_API_KEY"] = "test-key"
        os.environ["BINANCE_API_SECRET"] = "test-secret"

        settings = Settings.from_env()
        rendered = repr(settings)

        self.assertNotIn("test-key", rendered)
        self.assertNotIn("test-secret", rendered)
        self.assertIn("runtime_mode='demo'", rendered)
        self.assertIn("market_symbols", rendered)

    def test_live_mode_requires_binance_credentials(self) -> None:
        self._clear_runtime_env()
        os.environ["QUANT_RUNTIME_MODE"] = "live"

        with self.assertRaises(ValueError):
            Settings.from_env()

    def test_invalid_runtime_mode_rejects_value(self) -> None:
        self._clear_runtime_env()
        os.environ["QUANT_RUNTIME_MODE"] = "paper"

        with self.assertRaises(ValueError):
            Settings.from_env()

    def test_blank_market_symbols_rejects_value(self) -> None:
        self._clear_runtime_env()
        os.environ["QUANT_MARKET_SYMBOLS"] = " , , "

        with self.assertRaises(ValueError):
            Settings.from_env()

    def test_live_mode_loads_with_credentials(self) -> None:
        self._clear_runtime_env()
        os.environ["QUANT_RUNTIME_MODE"] = "live"
        os.environ["BINANCE_API_KEY"] = "test-key"
        os.environ["BINANCE_API_SECRET"] = "test-secret"

        settings = Settings.from_env()

        self.assertEqual(settings.runtime_mode, "live")
        self.assertEqual(settings.binance_api_key, "test-key")
        self.assertEqual(settings.binance_api_secret, "test-secret")

    def test_dry_run_mode_loads_without_credentials(self) -> None:
        self._clear_runtime_env()
        os.environ["QUANT_RUNTIME_MODE"] = "dry-run"

        settings = Settings.from_env()

        self.assertEqual(settings.runtime_mode, "dry-run")
        self.assertEqual(settings.binance_api_key, "")
        self.assertEqual(settings.binance_api_secret, "")

    def test_explicit_market_symbols_are_normalized_and_deduplicated(self) -> None:
        self._clear_runtime_env()
        os.environ["QUANT_MARKET_SYMBOLS"] = " btcusdt,ETHUSDT,ethusdt , solusdt "

        settings = Settings.from_env()

        self.assertEqual(settings.market_symbols, ("BTCUSDT", "ETHUSDT", "SOLUSDT"))
        self.assertEqual(settings.market_symbols.count("ETHUSDT"), 1)

    def test_invalid_market_symbol_rejects_value(self) -> None:
        self._clear_runtime_env()
        os.environ["QUANT_MARKET_SYMBOLS"] = "BTC-USDT"

        with self.assertRaises(ValueError):
            Settings.from_env()

    def _clear_runtime_env(self) -> None:
        os.environ.pop("QUANT_RUNTIME_MODE", None)
        os.environ.pop("BINANCE_API_KEY", None)
        os.environ.pop("BINANCE_API_SECRET", None)
        os.environ.pop("QUANT_MARKET_SYMBOLS", None)


if __name__ == "__main__":
    unittest.main()
