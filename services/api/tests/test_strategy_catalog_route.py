from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import services.api.app.routes.auth as auth_route  # noqa: E402
import services.api.app.routes.strategies as strategies_route  # noqa: E402
import services.api.app.services.auth_service as auth_service_module  # noqa: E402
import services.api.app.services.strategy_catalog as strategy_catalog_module  # noqa: E402
from services.api.app.routes.auth import login  # noqa: E402
from services.api.app.core.settings import DEFAULT_MARKET_SYMBOLS  # noqa: E402
from services.api.app.routes.strategies import get_strategy_catalog  # noqa: E402
from services.api.app.services.auth_service import AuthService  # noqa: E402
from services.api.app.services.strategy_catalog import StrategyCatalogService  # noqa: E402


class StrategyCatalogRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self._reset_singletons()

    @staticmethod
    def _reset_singletons() -> None:
        new_auth_service = AuthService()
        auth_service_module.auth_service = new_auth_service
        auth_route.auth_service = new_auth_service
        strategies_route.auth_service = new_auth_service

        new_strategy_catalog_service = StrategyCatalogService()
        strategy_catalog_module.strategy_catalog_service = new_strategy_catalog_service
        strategies_route.strategy_catalog_service = new_strategy_catalog_service

    @staticmethod
    def _login_token() -> str:
        response = login(username="admin", password="1933")
        return str(response["data"]["item"]["token"])

    def test_strategy_catalog_service_exposes_fixed_strategies(self) -> None:
        strategies = strategy_catalog_module.strategy_catalog_service.list_strategies()

        self.assertEqual([item["key"] for item in strategies], ["trend_breakout", "trend_pullback"])

    def test_strategy_catalog_service_exposes_default_whitelist(self) -> None:
        whitelist = strategy_catalog_module.strategy_catalog_service.get_whitelist()

        self.assertEqual(whitelist, list(DEFAULT_MARKET_SYMBOLS))

    def test_strategy_catalog_route_requires_login(self) -> None:
        response = get_strategy_catalog()

        self.assertEqual(set(response.keys()), {"data", "error", "meta"})
        self.assertEqual(response["error"]["code"], "unauthorized")

    def test_strategy_catalog_route_accepts_bearer_token(self) -> None:
        token = self._login_token()

        response = get_strategy_catalog(authorization=f"Bearer {token}")

        self.assertEqual(set(response.keys()), {"data", "error", "meta"})
        self.assertIsNone(response["error"])
        self.assertEqual(response["meta"]["source"], "strategy-catalog")

    def test_strategy_catalog_response_isolated_from_internal_state(self) -> None:
        token = self._login_token()

        response = get_strategy_catalog(token=token)
        response["data"]["whitelist"].append("FAKEUSDT")
        response["data"]["strategies"][0]["default_params"]["timeframe"] = "15m"

        next_response = get_strategy_catalog(token=token)

        self.assertEqual(next_response["data"]["whitelist"], list(DEFAULT_MARKET_SYMBOLS))
        self.assertEqual(next_response["data"]["strategies"][0]["default_params"]["timeframe"], "1h")

    def test_strategy_catalog_entry_contains_key_fields(self) -> None:
        strategies = strategy_catalog_module.strategy_catalog_service.list_strategies()

        item = strategies[0]
        self.assertEqual(item["key"], "trend_breakout")
        self.assertEqual(item["display_name"], "趋势突破")
        self.assertIn("default_params", item)
        self.assertEqual(item["default_params"]["timeframe"], "1h")
        self.assertIn("lookback_bars", item["default_params"])
        self.assertIn("breakout_buffer_pct", item["default_params"])


if __name__ == "__main__":
    unittest.main()
