from __future__ import annotations

import os
import sys
import unittest
from decimal import Decimal
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

    def test_live_mode_normalizes_live_guardrails(self) -> None:
        self._clear_runtime_env()
        os.environ["QUANT_RUNTIME_MODE"] = "live"
        os.environ["BINANCE_API_KEY"] = "test-key"
        os.environ["BINANCE_API_SECRET"] = "test-secret"
        os.environ["QUANT_FREQTRADE_API_URL"] = "http://127.0.0.1:8080"
        os.environ["QUANT_FREQTRADE_API_USERNAME"] = "bot"
        os.environ["QUANT_FREQTRADE_API_PASSWORD"] = "secret"
        os.environ["QUANT_ALLOW_LIVE_EXECUTION"] = "true"
        os.environ["QUANT_LIVE_ALLOWED_SYMBOLS"] = " dogeusdt , dogeusdt "
        os.environ["QUANT_LIVE_MAX_STAKE_USDT"] = "1"
        os.environ["QUANT_LIVE_MAX_OPEN_TRADES"] = "1"

        settings = Settings.from_env()

        self.assertTrue(settings.allow_live_execution)
        self.assertEqual(settings.live_allowed_symbols, ("DOGEUSDT",))
        self.assertEqual(settings.live_max_stake_usdt, Decimal("1"))
        self.assertEqual(settings.live_max_open_trades, 1)
        self.assertTrue(settings.should_use_freqtrade_rest())

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

    def test_live_max_stake_requires_positive_number(self) -> None:
        self._clear_runtime_env()
        os.environ["QUANT_RUNTIME_MODE"] = "live"
        os.environ["BINANCE_API_KEY"] = "test-key"
        os.environ["BINANCE_API_SECRET"] = "test-secret"
        os.environ["QUANT_LIVE_MAX_STAKE_USDT"] = "0"

        with self.assertRaises(ValueError):
            Settings.from_env()

    def test_live_max_open_trades_requires_positive_integer(self) -> None:
        self._clear_runtime_env()
        os.environ["QUANT_RUNTIME_MODE"] = "live"
        os.environ["BINANCE_API_KEY"] = "test-key"
        os.environ["BINANCE_API_SECRET"] = "test-secret"
        os.environ["QUANT_LIVE_MAX_OPEN_TRADES"] = "0"

        with self.assertRaises(ValueError):
            Settings.from_env()

    def test_binance_endpoint_overrides_and_timeout_are_loaded(self) -> None:
        self._clear_runtime_env()
        os.environ["QUANT_BINANCE_MARKET_BASE_URL"] = "https://data-api.binance.vision"
        os.environ["QUANT_BINANCE_ACCOUNT_BASE_URL"] = "https://api1.binance.com"
        os.environ["QUANT_BINANCE_TIMEOUT_SECONDS"] = "6.5"

        settings = Settings.from_env()

        self.assertEqual(settings.binance_market_base_url, "https://data-api.binance.vision")
        self.assertEqual(settings.binance_account_base_url, "https://api1.binance.com")
        self.assertEqual(settings.binance_timeout_seconds, 6.5)

    def test_binance_timeout_requires_positive_number(self) -> None:
        self._clear_runtime_env()
        os.environ["QUANT_BINANCE_TIMEOUT_SECONDS"] = "0"

        with self.assertRaises(ValueError):
            Settings.from_env()

    def _clear_runtime_env(self) -> None:
        os.environ.pop("QUANT_RUNTIME_MODE", None)
        os.environ.pop("BINANCE_API_KEY", None)
        os.environ.pop("BINANCE_API_SECRET", None)
        os.environ.pop("QUANT_MARKET_SYMBOLS", None)
        os.environ.pop("QUANT_FREQTRADE_API_URL", None)
        os.environ.pop("QUANT_FREQTRADE_API_USERNAME", None)
        os.environ.pop("QUANT_FREQTRADE_API_PASSWORD", None)
        os.environ.pop("QUANT_ALLOW_LIVE_EXECUTION", None)
        os.environ.pop("QUANT_LIVE_ALLOWED_SYMBOLS", None)
        os.environ.pop("QUANT_LIVE_MAX_STAKE_USDT", None)
        os.environ.pop("QUANT_LIVE_MAX_OPEN_TRADES", None)
        os.environ.pop("QUANT_BINANCE_MARKET_BASE_URL", None)
        os.environ.pop("QUANT_BINANCE_ACCOUNT_BASE_URL", None)
        os.environ.pop("QUANT_BINANCE_TIMEOUT_SECONDS", None)


if __name__ == "__main__":
    unittest.main()
