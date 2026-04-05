from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path
from io import BytesIO
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlparse
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.api.app.adapters.binance.account_client import BinanceAccountClient  # noqa: E402
from services.api.app.adapters.binance.market_client import BinanceMarketClient  # noqa: E402
from services.api.app.routes import balances, orders, positions  # noqa: E402
from services.api.app.services.account_sync_service import (  # noqa: E402
    AccountSyncService,
    normalize_balance_row,
)


class FakeBinanceAccountClient:
    def get_balances(self) -> list[dict[str, object]]:
        return [{"asset": "USDT", "free": "12.5000000000", "locked": "0.5000000000"}]

    def get_orders(self, symbol: str | None = None, limit: int = 100) -> list[dict[str, object]]:
        if symbol not in {None, "BTCUSDT"}:
            return []
        return [
            {
                "orderId": "1",
                "symbol": "BTCUSDT",
                "status": "FILLED",
                "type": "LIMIT",
                "price": "86000.0000000000",
                "origQty": "0.0100000000",
                "executedQty": "0.0100000000",
            }
        ]

    def get_positions(self) -> list[dict[str, object]]:
        return [{"symbol": "BTCUSDT", "size": "0.0100000000", "side": "long"}]


class FakeMarketLikeAccountClient:
    def get_balances(self) -> list[dict[str, object]]:
        return [{"coin": "BTC", "free": "1.0000000000", "locked": "0.0000000000"}]

    def get_orders(self, symbol: str | None = None, limit: int = 100) -> list[dict[str, object]]:
        if symbol not in {None, "BTCUSDT"}:
            return []
        return [
            {
                "orderId": "55",
                "symbol": "BTCUSDT",
                "status": "FILLED",
                "side": "BUY",
                "type": "LIMIT",
                "price": "86000.0000000000",
                "origQty": "0.0100000000",
                "executedQty": "0.0100000000",
            }
        ]

    def get_positions(self) -> list[dict[str, object]]:
        return [
            {
                "symbol": "BTCUSDT",
                "side": "long",
                "quantity": "0.0100000000",
                "entryPrice": "86000.0000000000",
                "markPrice": "86500.0000000000",
                "unrealizedPnl": "5.0000000000",
            }
        ]


class FakeBalanceMarketClient:
    def get_exchange_info(self, symbols: tuple[str, ...] | None = None) -> dict[str, object]:
        requested = {item for item in (symbols or ())}
        rows = [
            {
                "symbol": "BTCUSDT",
                "filters": [
                    {"filterType": "LOT_SIZE", "stepSize": "0.00001000"},
                    {"filterType": "NOTIONAL", "minNotional": "5.00000000"},
                ],
            },
            {
                "symbol": "DOGEUSDT",
                "filters": [
                    {"filterType": "LOT_SIZE", "stepSize": "1.00000000"},
                    {"filterType": "NOTIONAL", "minNotional": "1.00000000"},
                ],
            },
        ]
        if requested:
            rows = [item for item in rows if item["symbol"] in requested]
        return {"symbols": rows}

    def get_tickers(self) -> list[dict[str, object]]:
        return [
            {"symbol": "BTCUSDT", "lastPrice": "86000.00000000"},
            {"symbol": "DOGEUSDT", "lastPrice": "0.09056000"},
        ]


class ExplodingAccountSyncService:
    def list_balances(self, limit: int = 100) -> list[dict[str, object]]:
        raise AssertionError("demo mode should not use account sync balances")

    def list_orders(self, limit: int = 100) -> list[dict[str, object]]:
        raise AssertionError("demo mode should not use account sync orders")

    def list_positions(self, limit: int = 100) -> list[dict[str, object]]:
        raise AssertionError("demo mode should not use account sync positions")


class FakeSyncService:
    def list_orders(self, limit: int = 100) -> list[dict[str, object]]:
        return [{"id": "ft-1", "symbol": "BTCUSDT", "status": "filled"}]

    def list_positions(self, limit: int = 100) -> list[dict[str, object]]:
        return [
            {
                "id": "ft-pos-1",
                "symbol": "BTCUSDT",
                "side": "long",
                "quantity": "0.0100000000",
                "unrealizedPnl": "0.0000000000",
            }
        ]


class FakeResponse:
    def __init__(self, body: str, status: int = 200) -> None:
        self._body = body
        self.status = status

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def read(self) -> bytes:
        return self._body.encode("utf-8")


class FakeBinanceOpener:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.timeouts: list[float | None] = []

    def __call__(self, request, timeout=None) -> FakeResponse:
        parsed = urlparse(request.full_url)
        query = parse_qs(parsed.query)
        symbol = query.get("symbol", [""])[0]
        self.calls.append(f"{parsed.path}:{symbol}")
        self.timeouts.append(timeout)

        if parsed.path == "/api/v3/account":
            return FakeResponse(
                json.dumps(
                    {
                        "balances": [
                            {"asset": "BTC", "free": "0.5000000000", "locked": "1.0000000000"},
                            {"asset": "ETH", "free": "0.2500000000", "locked": "0.0000000000"},
                            {"asset": "USDT", "free": "0.0000000000", "locked": "0.0000000000"},
                        ]
                    }
                )
            )
        if parsed.path == "/api/v3/allOrders":
            if symbol == "BTCUSDT":
                return FakeResponse(
                    json.dumps(
                        [
                            {
                                "orderId": "101",
                                "symbol": "BTCUSDT",
                                "status": "FILLED",
                                "side": "BUY",
                                "type": "LIMIT",
                                "updateTime": 1000,
                                "price": "86000.0000000000",
                                "origQty": "0.0100000000",
                                "executedQty": "0.0100000000",
                            }
                        ]
                    )
                )
            if symbol == "SOLUSDT":
                return FakeResponse(
                    json.dumps(
                        [
                            {
                                "orderId": "103",
                                "symbol": "SOLUSDT",
                                "status": "PARTIALLY_FILLED",
                                "side": "BUY",
                                "type": "LIMIT",
                                "price": "180.0000000000",
                                "origQty": "1.0000000000",
                                "executedQty": "0.2500000000",
                            }
                        ]
                    )
                )
            if symbol == "ETHUSDT":
                return FakeResponse(
                    json.dumps(
                        [
                            {
                                "orderId": "102",
                                "symbol": "ETHUSDT",
                                "status": "NEW",
                                "side": "SELL",
                                "type": "MARKET",
                                "time": 2000,
                                "price": "0.0000000000",
                                "origQty": "0.2000000000",
                                "executedQty": "0.0000000000",
                            }
                        ]
                    )
                )
            return FakeResponse("[]")
        if parsed.path == "/api/v3/myTrades":
            return FakeResponse("[]")
        raise AssertionError(f"unexpected Binance path: {parsed.path}")


class AccountSyncServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._env_patch = patch.dict(os.environ, {}, clear=False)
        self._env_patch.start()
        self.addCleanup(self._env_patch.stop)

    def test_normalize_balance_row_standardizes_asset_available_locked(self) -> None:
        row = normalize_balance_row(
            {
                "coin": "USDT",
                "free": 12.5,
                "locked": 0.5,
                "availableBalance": 99.0,
                "freeze": 7,
                "exchange": "binance",
            }
        )

        self.assertEqual(set(row.keys()), {"asset", "available", "locked"})
        self.assertEqual(row["asset"], "USDT")
        self.assertEqual(row["available"], "12.5")
        self.assertEqual(row["locked"], "0.5")
        self.assertIsInstance(row["asset"], str)
        self.assertIsInstance(row["available"], str)
        self.assertIsInstance(row["locked"], str)

    def test_default_binance_account_client_returns_empty_lists_without_keys(self) -> None:
        with patch.dict(os.environ, {"BINANCE_API_KEY": "", "BINANCE_API_SECRET": ""}, clear=False):
            client = BinanceAccountClient()

        self.assertEqual(client.get_balances(), [])
        self.assertEqual(client.get_orders(symbol="BTCUSDT"), [])
        self.assertEqual(client.get_trades(symbol="BTCUSDT"), [])
        self.assertEqual(client.get_positions(), [])

    def test_binance_account_client_returns_empty_lists_when_signed_request_is_rejected(self) -> None:
        def rejecting_opener(request, timeout=None):
            raise HTTPError(
                request.full_url,
                401,
                "Unauthorized",
                hdrs=None,
                fp=BytesIO(b'{"code":-2015,"msg":"Invalid API-key, IP, or permissions for action."}'),
            )

        client = BinanceAccountClient(
            api_key="k",
            api_secret="s",
            base_url="https://example.com",
            opener=rejecting_opener,
        )

        self.assertEqual(client.get_balances(), [])
        self.assertEqual(client.get_orders(symbol="BTCUSDT"), [])
        self.assertEqual(client.get_trades(symbol="BTCUSDT"), [])
        self.assertEqual(client.get_positions(), [])

    def test_default_binance_clients_use_env_endpoint_overrides(self) -> None:
        opener = FakeBinanceOpener()

        def fake_market_urlopen(url: str, timeout: float | None = None):
            self.assertEqual(url, "https://data-api.binance.vision/api/v3/ticker/24hr")
            self.assertEqual(timeout, 6.0)
            return FakeResponse("[]")

        with patch.dict(
            os.environ,
            {
                "BINANCE_API_KEY": "k",
                "BINANCE_API_SECRET": "s",
                "QUANT_BINANCE_MARKET_BASE_URL": "https://data-api.binance.vision",
                "QUANT_BINANCE_ACCOUNT_BASE_URL": "https://api1.binance.com",
                "QUANT_BINANCE_TIMEOUT_SECONDS": "6",
            },
            clear=False,
        ):
            market_client = BinanceMarketClient(opener=fake_market_urlopen)
            account_client = BinanceAccountClient(opener=opener)

            self.assertEqual(market_client.get_tickers(), [])
            self.assertEqual(account_client.base_url, "https://api1.binance.com")
            self.assertEqual(account_client.get_balances()[0]["asset"], "BTC")
            self.assertEqual(opener.timeouts, [6.0])

    def test_account_sync_service_normalizes_orders_and_positions_fields(self) -> None:
        service = AccountSyncService(FakeMarketLikeAccountClient())

        orders_result = service.list_orders(limit=10)
        positions_result = service.list_positions(limit=10)

        self.assertEqual(orders_result[0]["id"], "55")
        self.assertEqual(orders_result[0]["symbol"], "BTCUSDT")
        self.assertEqual(orders_result[0]["status"], "FILLED")
        self.assertEqual(orders_result[0]["side"], "buy")
        self.assertEqual(orders_result[0]["orderType"], "LIMIT")
        self.assertEqual(orders_result[0]["order_type"], "LIMIT")
        self.assertEqual(orders_result[0]["lifecycle"], "filled_entry")
        self.assertEqual(positions_result[0]["id"], "position-BTCUSDT")
        self.assertEqual(positions_result[0]["symbol"], "BTCUSDT")
        self.assertEqual(positions_result[0]["side"], "long")
        self.assertEqual(positions_result[0]["quantity"], "0.0100000000")
        self.assertEqual(positions_result[0]["unrealizedPnl"], "5.0000000000")

    def test_account_sync_service_marks_dust_balances_for_non_sellable_residuals(self) -> None:
        class DustBalanceClient:
            def get_balances(self) -> list[dict[str, object]]:
                return [
                    {"asset": "DOGE", "free": "0.97600000", "locked": "0.00000000"},
                    {"asset": "BTC", "free": "0.50000000", "locked": "0.00000000"},
                    {"asset": "USDT", "free": "20.00000000", "locked": "0.00000000"},
                ]

        service = AccountSyncService(DustBalanceClient(), market_client=FakeBalanceMarketClient())

        balances_result = service.list_balances(limit=10)

        self.assertEqual(balances_result[0]["asset"], "DOGE")
        self.assertEqual(balances_result[0]["tradeStatus"], "dust")
        self.assertIn("零头", balances_result[0]["tradeHint"])
        self.assertEqual(balances_result[0]["sellableQuantity"], "0")
        self.assertEqual(balances_result[0]["dustQuantity"], "0.976")
        self.assertEqual(balances_result[1]["tradeStatus"], "tradable")
        self.assertEqual(balances_result[2]["tradeStatus"], "tradable")

    def test_account_sync_service_marks_pending_exit_order_lifecycle(self) -> None:
        class PendingExitClient:
            def get_orders(self, symbol: str | None = None, limit: int = 100) -> list[dict[str, object]]:
                if symbol != "ETHUSDT":
                    return []
                return [
                    {
                        "orderId": "102",
                        "symbol": "ETHUSDT",
                        "status": "NEW",
                        "side": "SELL",
                        "type": "MARKET",
                        "time": 2000,
                        "price": "0.0000000000",
                        "origQty": "0.2000000000",
                        "executedQty": "0.0000000000",
                    }
                ]

        service = AccountSyncService(PendingExitClient(), market_client=FakeBalanceMarketClient())

        orders_result = service.list_orders(limit=10, symbols=("ETHUSDT",))

        self.assertEqual(orders_result[0]["side"], "sell")
        self.assertEqual(orders_result[0]["status"], "NEW")
        self.assertEqual(orders_result[0]["lifecycle"], "pending_exit")

    def test_dry_run_mode_uses_binance_only_for_balances(self) -> None:
        with patch.dict(os.environ, {"QUANT_RUNTIME_MODE": "dry-run"}):
            service = AccountSyncService(FakeBinanceAccountClient(), market_client=FakeBalanceMarketClient())
            with patch.object(balances, "account_sync_service", service), patch.object(
                orders, "sync_service", FakeSyncService()
            ), patch.object(
                orders, "account_sync_service", ExplodingAccountSyncService()
            ), patch.object(positions, "sync_service", FakeSyncService()), patch.object(
                positions, "account_sync_service", ExplodingAccountSyncService()
            ):
                balance_response = balances.list_balances(limit=5)
                order_response = orders.list_orders(limit=5)
                position_response = positions.list_positions(limit=5)

        self.assertEqual(balance_response["meta"]["source"], "binance-account-sync")
        self.assertEqual(balance_response["data"]["items"][0]["available"], "12.5000000000")
        self.assertEqual(balance_response["data"]["items"][0]["tradeStatus"], "tradable")
        self.assertEqual(order_response["meta"]["source"], "freqtrade-sync")
        self.assertEqual(order_response["data"]["items"][0]["id"], "ft-1")
        self.assertEqual(order_response["data"]["items"][0]["symbol"], "BTCUSDT")
        self.assertEqual(position_response["meta"]["source"], "freqtrade-sync")
        self.assertEqual(position_response["data"]["items"][0]["id"], "ft-pos-1")
        self.assertEqual(position_response["data"]["items"][0]["side"], "long")

    def test_live_mode_uses_binance_account_sync_for_orders_and_positions(self) -> None:
        opener = FakeBinanceOpener()
        with patch.dict(
            os.environ,
            {
                "QUANT_RUNTIME_MODE": "live",
                "BINANCE_API_KEY": "k",
                "BINANCE_API_SECRET": "s",
                "QUANT_MARKET_SYMBOLS": "BTCUSDT,ETHUSDT,SOLUSDT",
                "QUANT_LIVE_ALLOWED_SYMBOLS": "BTCUSDT,ETHUSDT,SOLUSDT",
            },
        ):
            with patch(
                "services.api.app.adapters.binance.account_client.create_binance_account_client",
                side_effect=lambda: BinanceAccountClient(
                    api_key="k",
                    api_secret="s",
                    base_url="https://example.com",
                    opener=opener,
                ),
            ):
                service = AccountSyncService()
                with patch.object(orders, "account_sync_service", service), patch.object(
                    positions, "account_sync_service", service
                ):
                    order_response = orders.list_orders(limit=5)
                    position_response = positions.list_positions(limit=5)

        self.assertEqual(order_response["meta"]["source"], "binance-account-sync")
        self.assertEqual(position_response["meta"]["source"], "binance-account-sync")
        self.assertEqual([item["symbol"] for item in order_response["data"]["items"]], ["ETHUSDT", "BTCUSDT", "SOLUSDT"])
        self.assertEqual(order_response["data"]["items"][0]["side"], "sell")
        self.assertEqual(order_response["data"]["items"][0]["orderType"], "MARKET")
        self.assertEqual(order_response["data"]["items"][0]["order_type"], "MARKET")
        self.assertEqual(order_response["data"]["items"][1]["side"], "buy")
        self.assertEqual(order_response["data"]["items"][1]["orderType"], "LIMIT")
        self.assertEqual(order_response["data"]["items"][1]["order_type"], "LIMIT")
        self.assertEqual(order_response["data"]["items"][2]["side"], "buy")
        self.assertEqual(order_response["data"]["items"][2]["orderType"], "LIMIT")
        self.assertEqual(order_response["data"]["items"][2]["order_type"], "LIMIT")
        self.assertEqual([item["symbol"] for item in position_response["data"]["items"]], ["BTC", "ETH"])
        self.assertEqual(position_response["data"]["items"][0]["quantity"], "1.5000000000")
        self.assertEqual(position_response["data"]["items"][1]["quantity"], "0.2500000000")

    def test_live_mode_prefers_live_allowed_symbols_for_order_sync(self) -> None:
        opener = FakeBinanceOpener()
        with patch.dict(
            os.environ,
            {
                "QUANT_RUNTIME_MODE": "live",
                "BINANCE_API_KEY": "k",
                "BINANCE_API_SECRET": "s",
                "QUANT_MARKET_SYMBOLS": "BTCUSDT,ETHUSDT",
                "QUANT_LIVE_ALLOWED_SYMBOLS": "SOLUSDT",
            },
        ):
            with patch(
                "services.api.app.adapters.binance.account_client.create_binance_account_client",
                side_effect=lambda: BinanceAccountClient(
                    api_key="k",
                    api_secret="s",
                    base_url="https://example.com",
                    opener=opener,
                ),
            ):
                service = AccountSyncService()
                orders_result = service.list_orders(limit=5)

        self.assertEqual([item["symbol"] for item in orders_result], ["SOLUSDT"])
        self.assertIn("/api/v3/allOrders:SOLUSDT", opener.calls)
        self.assertNotIn("/api/v3/allOrders:BTCUSDT", opener.calls)
        self.assertNotIn("/api/v3/allOrders:ETHUSDT", opener.calls)

    def test_live_mode_without_live_whitelist_does_not_fallback_to_market_symbols(self) -> None:
        opener = FakeBinanceOpener()
        with patch.dict(
            os.environ,
            {
                "QUANT_RUNTIME_MODE": "live",
                "BINANCE_API_KEY": "k",
                "BINANCE_API_SECRET": "s",
                "QUANT_MARKET_SYMBOLS": "BTCUSDT,ETHUSDT,SOLUSDT",
                "QUANT_LIVE_ALLOWED_SYMBOLS": "",
            },
        ):
            with patch(
                "services.api.app.adapters.binance.account_client.create_binance_account_client",
                side_effect=lambda: BinanceAccountClient(
                    api_key="k",
                    api_secret="s",
                    base_url="https://example.com",
                    opener=opener,
                ),
            ):
                service = AccountSyncService()
                orders_result = service.list_orders(limit=5)

        self.assertEqual(orders_result, [])
        self.assertEqual(opener.calls, [])

    def test_binance_account_client_reads_balances_orders_and_positions_from_opener(self) -> None:
        client = BinanceAccountClient(
            api_key="k",
            api_secret="s",
            base_url="https://example.com",
            opener=FakeBinanceOpener(),
        )

        self.assertEqual(
            client.get_balances(),
            [
                {"asset": "BTC", "free": "0.5000000000", "locked": "1.0000000000"},
                {"asset": "ETH", "free": "0.2500000000", "locked": "0.0000000000"},
                {"asset": "USDT", "free": "0.0000000000", "locked": "0.0000000000"},
            ],
        )
        self.assertEqual(
            client.get_orders(symbol="BTCUSDT"),
            [
                {
                    "orderId": "101",
                    "symbol": "BTCUSDT",
                    "status": "FILLED",
                    "side": "BUY",
                    "type": "LIMIT",
                    "updateTime": 1000,
                    "price": "86000.0000000000",
                    "origQty": "0.0100000000",
                    "executedQty": "0.0100000000",
                }
            ],
        )
        self.assertEqual(
            client.get_positions(),
            [
                {
                    "id": "position-BTC",
                    "symbol": "BTC",
                    "side": "long",
                    "quantity": "1.5000000000",
                    "unrealizedPnl": "0.0000000000",
                    "entryPrice": "0.0000000000",
                    "markPrice": "0.0000000000",
                    "source": "binance",
                },
                {
                    "id": "position-ETH",
                    "symbol": "ETH",
                    "side": "long",
                    "quantity": "0.2500000000",
                    "unrealizedPnl": "0.0000000000",
                    "entryPrice": "0.0000000000",
                    "markPrice": "0.0000000000",
                    "source": "binance",
                },
            ],
        )

    def test_demo_mode_keeps_current_fallback_sources_for_balances_orders_and_positions(self) -> None:
        with patch.dict(os.environ, {"QUANT_RUNTIME_MODE": "demo"}):
            with patch.object(balances, "account_sync_service", ExplodingAccountSyncService()), patch.object(
                orders, "account_sync_service", ExplodingAccountSyncService()
            ), patch.object(positions, "account_sync_service", ExplodingAccountSyncService()):
                balance_response = balances.list_balances(limit=5)
                order_response = orders.list_orders(limit=5)
                position_response = positions.list_positions(limit=5)

        self.assertEqual(balance_response["meta"]["source"], "api-skeleton")
        self.assertEqual(order_response["meta"]["source"], "freqtrade-sync")
        self.assertEqual(order_response["meta"]["truth_source"], "freqtrade")
        self.assertEqual(position_response["meta"]["source"], "freqtrade-sync")
        self.assertEqual(position_response["meta"]["truth_source"], "freqtrade")

if __name__ == "__main__":
    unittest.main()
