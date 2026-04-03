from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from datetime import datetime, timezone
from decimal import Decimal
import base64
import json
import threading
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch
from urllib.parse import urlsplit


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import services.api.app.adapters.freqtrade.client as freqtrade_client_module  # noqa: E402
import services.api.app.services.execution_service as execution_service_module  # noqa: E402
import services.api.app.services.sync_service as sync_service_module  # noqa: E402
from services.api.app.adapters.freqtrade.client import FreqtradeClient  # noqa: E402
from services.api.app.domain.contracts import ExecutionActionContract, ExecutionActionType, SignalSide  # noqa: E402
from services.api.app.services.execution_service import ExecutionService  # noqa: E402
from services.api.app.services.signal_service import SignalService  # noqa: E402
from services.api.app.services.sync_service import SyncService  # noqa: E402


class _FakeBinanceMarketClient:
    def __init__(
        self,
        min_notional_map: dict[str, str],
        *,
        step_size_map: dict[str, str] | None = None,
        last_price_map: dict[str, str] | None = None,
    ) -> None:
        self._min_notional_map = {key.upper(): value for key, value in min_notional_map.items()}
        self._step_size_map = {key.upper(): value for key, value in (step_size_map or {}).items()}
        self._last_price_map = {key.upper(): value for key, value in (last_price_map or {}).items()}

    def get_exchange_info(self, symbols: tuple[str, ...] | None = None) -> dict[str, object]:
        requested_symbols = tuple(symbols or self._min_notional_map.keys())
        items: list[dict[str, object]] = []
        for symbol in requested_symbols:
            normalized_symbol = str(symbol).upper()
            min_notional = self._min_notional_map.get(normalized_symbol, "5")
            step_size = self._step_size_map.get(normalized_symbol, "0.0001")
            items.append(
                {
                    "symbol": normalized_symbol,
                    "filters": [
                        {
                            "filterType": "NOTIONAL",
                            "minNotional": min_notional,
                            "applyMinToMarket": True,
                            "maxNotional": "9000000.00000000",
                            "applyMaxToMarket": False,
                            "avgPriceMins": 5,
                        },
                        {
                            "filterType": "LOT_SIZE",
                            "minQty": step_size,
                            "maxQty": "9000000.00000000",
                            "stepSize": step_size,
                        },
                    ],
                }
            )
        return {"symbols": items}

    def get_tickers(self) -> list[dict[str, object]]:
        symbols = set(self._min_notional_map) | set(self._last_price_map)
        if not symbols:
            symbols = {"BTCUSDT"}
        return [
            {
                "symbol": symbol,
                "lastPrice": self._last_price_map.get(symbol, "100"),
            }
            for symbol in sorted(symbols)
        ]


class ExecutionFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self._env_backup = os.environ.copy()
        self.client = FreqtradeClient()
        self.signal_service = SignalService()
        self.execution_service = ExecutionService()
        self.sync_service = SyncService()
        freqtrade_client_module.freqtrade_client = self.client
        execution_service_module.freqtrade_client = self.client
        sync_service_module.freqtrade_client = self.client

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._env_backup)

    def test_freqtrade_client_runtime_snapshot_reports_executor_and_mode(self) -> None:
        for mode in ("demo", "dry-run", "live"):
            env = {"QUANT_RUNTIME_MODE": mode}
            if mode == "live":
                env.update({"BINANCE_API_KEY": "k", "BINANCE_API_SECRET": "s"})
            with self.subTest(mode=mode), patch.dict(os.environ, env, clear=False):
                client = FreqtradeClient()
                snapshot = client.get_runtime_snapshot()

                self.assertEqual(snapshot["executor"], "freqtrade")
                self.assertEqual(snapshot["mode"], mode)
                self.assertIn(snapshot["backend"], {"memory", "rest"})
                self.assertIn(snapshot["mode"], {"demo", "dry-run", "live"})

    def test_freqtrade_client_supports_start_pause_stop(self) -> None:
        started = self.client.control_strategy(1, "start")
        paused = self.client.control_strategy(1, "pause")
        stopped = self.client.control_strategy(1, "stop")

        self.assertEqual(started["status"], "running")
        self.assertEqual(paused["status"], "paused")
        self.assertEqual(stopped["status"], "stopped")

    def test_sync_service_uses_adapter_truth_source(self) -> None:
        snapshot = self.sync_service.sync_execution_state()

        self.assertIn("strategies", snapshot)
        self.assertIn("orders", snapshot)
        self.assertIn("positions", snapshot)
        self.assertIn("balances", snapshot)

    def test_demo_mode_still_uses_current_in_memory_fake_execution(self) -> None:
        with patch.dict(os.environ, {"QUANT_RUNTIME_MODE": "demo"}, clear=False):
            client = FreqtradeClient()
            snapshot = client.get_runtime_snapshot()
            freqtrade_client_module.freqtrade_client = client
            execution_service_module.freqtrade_client = client
            sync_service_module.freqtrade_client = client
            dispatch_result = ExecutionService().dispatch_signal(1)

        self.assertEqual(snapshot["mode"], "demo")
        self.assertEqual(snapshot["backend"], "memory")
        self.assertEqual(dispatch_result["runtime"]["mode"], "demo")
        self.assertEqual(dispatch_result["runtime"]["backend"], "memory")
        self.assertEqual(dispatch_result["order"]["status"], "filled")
        self.assertEqual(dispatch_result["order"]["runtimeMode"], "demo")
        self.assertTrue(str(dispatch_result["order"]["id"]).startswith("ft-demo-order-"))
        self.assertEqual(dispatch_result["order"]["venueOrderId"], dispatch_result["order"]["id"])

    def test_dry_run_mode_exposes_dry_run_runtime_mode(self) -> None:
        with patch.dict(os.environ, {"QUANT_RUNTIME_MODE": "dry-run"}, clear=False):
            client = FreqtradeClient()
            snapshot = client.get_runtime_snapshot()
            freqtrade_client_module.freqtrade_client = client
            execution_service_module.freqtrade_client = client
            sync_service_module.freqtrade_client = client
            dispatch_result = ExecutionService().dispatch_signal(1)

        self.assertEqual(snapshot["mode"], "dry-run")
        self.assertEqual(dispatch_result["runtime"]["mode"], "dry-run")
        self.assertEqual(dispatch_result["order"]["status"], "filled")
        self.assertEqual(dispatch_result["order"]["runtimeMode"], "dry-run")
        self.assertTrue(str(dispatch_result["order"]["id"]).startswith("ft-dry-run-order-"))

    def test_unconfigured_dry_run_mode_keeps_memory_backend(self) -> None:
        with patch.dict(
            os.environ,
            {
                "QUANT_RUNTIME_MODE": "dry-run",
                "QUANT_FREQTRADE_API_URL": "",
                "QUANT_FREQTRADE_API_USERNAME": "",
                "QUANT_FREQTRADE_API_PASSWORD": "",
            },
            clear=False,
        ):
            snapshot = FreqtradeClient().get_runtime_snapshot()

        self.assertEqual(snapshot["backend"], "memory")
        self.assertEqual(snapshot["mode"], "dry-run")

    def test_live_mode_requires_explicit_confirmation_before_dispatch(self) -> None:
        with patch.dict(
            os.environ,
            {
                "QUANT_RUNTIME_MODE": "live",
                "BINANCE_API_KEY": "k",
                "BINANCE_API_SECRET": "s",
            },
            clear=False,
        ):
            with self.assertRaises(PermissionError):
                ExecutionService().dispatch_signal(1)

    def test_live_mode_requires_binance_credentials_even_when_confirmation_enabled(self) -> None:
        with patch.dict(
            os.environ,
            {
                "QUANT_RUNTIME_MODE": "live",
                "QUANT_ALLOW_LIVE_EXECUTION": "true",
                "BINANCE_API_KEY": "",
                "BINANCE_API_SECRET": "",
            },
            clear=False,
        ):
            with self.assertRaises(ValueError):
                ExecutionService().dispatch_signal(1)

    def test_live_mode_rejects_non_whitelisted_symbol_even_when_executor_is_live(self) -> None:
        state: dict[str, object] = {
            "positions": [],
            "trades": [],
            "balances": [{"asset": "USDT", "total": "20.0", "available": "20.0", "locked": "0.0"}],
            "strategies": [{"id": 1, "name": "TrendBreakout", "status": "running"}],
            "dry_run": False,
            "stake_amount": 1,
            "max_open_trades": 1,
        }

        class Handler(BaseHTTPRequestHandler):
            def _record(self) -> None:
                state.setdefault("requests", []).append(
                    {
                        "method": self.command,
                        "path": self.path,
                        "authorization": self.headers.get("Authorization", ""),
                    }
                )

            def _read_body(self) -> dict[str, object]:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0:
                    return {}
                raw = self.rfile.read(length).decode("utf-8")
                return json.loads(raw) if raw else {}

            def _send_json(self, status: int, payload: dict[str, object]) -> None:
                encoded = json.dumps(payload).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

            def do_GET(self) -> None:  # noqa: N802
                path = urlsplit(self.path).path
                self._record()
                if path == "/api/v1/show_config":
                    self._send_json(
                        200,
                        {
                            "dry_run": False,
                            "stake_amount": 1,
                            "max_open_trades": 1,
                            "trading_mode": "spot",
                        },
                    )
                    return
                if path == "/api/v1/status":
                    self._send_json(200, {"status": state["positions"]})
                    return
                if path == "/api/v1/trades":
                    self._send_json(200, {"trades": state["trades"]})
                    return
                if path == "/api/v1/balance":
                    self._send_json(200, {"balances": state["balances"]})
                    return
                if path == "/api/v1/strategies":
                    self._send_json(200, {"strategies": state["strategies"]})
                    return
                self._send_json(200, {"status": "pong"})

            def do_POST(self) -> None:  # noqa: N802
                body = self._read_body()
                path = urlsplit(self.path).path
                self._record()
                if path == "/api/v1/token/login":
                    expected = "Basic " + base64.b64encode(b"bot:secret").decode("ascii")
                    if self.headers.get("Authorization") != expected:
                        self._send_json(401, {"detail": "unauthorized"})
                        return
                    self._send_json(200, {"access_token": "token-1", "refresh_token": "refresh-1"})
                    return
                if path == "/api/v1/forceenter":
                    self._send_json(200, {"trade_id": 99, "status": "ok"})
                    return
                self._send_json(404, {"detail": "not found"})

            def log_message(self, format: str, *args: object) -> None:  # noqa: A003
                return

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        server.timeout = 1
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            port = int(server.server_address[1])
            with patch.dict(
                os.environ,
                {
                    "QUANT_RUNTIME_MODE": "live",
                    "QUANT_ALLOW_LIVE_EXECUTION": "true",
                    "BINANCE_API_KEY": "k",
                    "BINANCE_API_SECRET": "s",
                    "QUANT_FREQTRADE_API_URL": f"http://127.0.0.1:{port}",
                    "QUANT_FREQTRADE_API_USERNAME": "bot",
                    "QUANT_FREQTRADE_API_PASSWORD": "secret",
                    "QUANT_LIVE_ALLOWED_SYMBOLS": "DOGEUSDT",
                    "QUANT_LIVE_MAX_STAKE_USDT": "1",
                    "QUANT_LIVE_MAX_OPEN_TRADES": "1",
                },
                clear=False,
            ):
                original_client = freqtrade_client_module.freqtrade_client
                original_execution_client = execution_service_module.freqtrade_client
                original_sync_client = sync_service_module.freqtrade_client
                original_signal_service = execution_service_module.signal_service
                try:
                    signal_service = SignalService()
                    signal = signal_service.ingest_signal(
                        {
                            "symbol": "BTCUSDT",
                            "side": "long",
                            "score": "0.91",
                            "confidence": "0.88",
                            "target_weight": "0.25",
                            "generated_at": datetime.now(timezone.utc).isoformat(),
                            "source": "rule-based",
                            "strategy_id": 1,
                        }
                    )
                    execution_service = ExecutionService(market_client=_FakeBinanceMarketClient({"BTCUSDT": "5"}))
                    client = FreqtradeClient()
                    freqtrade_client_module.freqtrade_client = client
                    execution_service_module.freqtrade_client = client
                    sync_service_module.freqtrade_client = client
                    execution_service_module.signal_service = signal_service
                    with self.assertRaises(PermissionError):
                        execution_service.dispatch_signal(int(signal["signal_id"]))
                finally:
                    freqtrade_client_module.freqtrade_client = original_client
                    execution_service_module.freqtrade_client = original_execution_client
                    sync_service_module.freqtrade_client = original_sync_client
                    execution_service_module.signal_service = original_signal_service
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_live_mode_rejects_doge_order_when_safe_exit_notional_is_not_met(self) -> None:
        state: dict[str, object] = {
            "positions": [],
            "trades": [],
            "balances": [{"asset": "USDT", "total": "20.0", "available": "20.0", "locked": "0.0"}],
            "strategies": [{"id": 1, "name": "TrendBreakout", "status": "running"}],
            "dry_run": False,
            "stake_amount": 1,
            "max_open_trades": 1,
        }

        class Handler(BaseHTTPRequestHandler):
            def _record(self) -> None:
                state.setdefault("requests", []).append(
                    {
                        "method": self.command,
                        "path": self.path,
                        "authorization": self.headers.get("Authorization", ""),
                    }
                )

            def _read_body(self) -> dict[str, object]:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0:
                    return {}
                raw = self.rfile.read(length).decode("utf-8")
                return json.loads(raw) if raw else {}

            def _send_json(self, status: int, payload: dict[str, object]) -> None:
                encoded = json.dumps(payload).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

            def do_GET(self) -> None:  # noqa: N802
                path = urlsplit(self.path).path
                self._record()
                if path == "/api/v1/show_config":
                    self._send_json(
                        200,
                        {
                            "dry_run": False,
                            "stake_amount": 1,
                            "max_open_trades": 1,
                            "trading_mode": "spot",
                        },
                    )
                    return
                if path == "/api/v1/status":
                    self._send_json(200, {"status": state["positions"]})
                    return
                if path == "/api/v1/trades":
                    self._send_json(200, {"trades": state["trades"]})
                    return
                if path == "/api/v1/balance":
                    self._send_json(200, {"balances": state["balances"]})
                    return
                if path == "/api/v1/strategies":
                    self._send_json(200, {"strategies": state["strategies"]})
                    return
                self._send_json(200, {"status": "pong"})

            def do_POST(self) -> None:  # noqa: N802
                body = self._read_body()
                path = urlsplit(self.path).path
                self._record()
                if path == "/api/v1/token/login":
                    expected = "Basic " + base64.b64encode(b"bot:secret").decode("ascii")
                    if self.headers.get("Authorization") != expected:
                        self._send_json(401, {"detail": "unauthorized"})
                        return
                    self._send_json(200, {"access_token": "token-1", "refresh_token": "refresh-1"})
                    return
                if path == "/api/v1/forceenter":
                    state["forceenter_seen"] = body
                    self._send_json(
                        200,
                        {
                            "trade_id": 199,
                            "status": "ok",
                            "pair": "DOGE/USDT",
                            "amount": 8,
                            "open_rate": 0.125,
                        },
                    )
                    return
                self._send_json(404, {"detail": "not found"})

            def log_message(self, format: str, *args: object) -> None:  # noqa: A003
                return

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        server.timeout = 1
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            port = int(server.server_address[1])
            with patch.dict(
                os.environ,
                {
                    "QUANT_RUNTIME_MODE": "live",
                    "QUANT_ALLOW_LIVE_EXECUTION": "true",
                    "BINANCE_API_KEY": "k",
                    "BINANCE_API_SECRET": "s",
                    "QUANT_FREQTRADE_API_URL": f"http://127.0.0.1:{port}",
                    "QUANT_FREQTRADE_API_USERNAME": "bot",
                    "QUANT_FREQTRADE_API_PASSWORD": "secret",
                    "QUANT_LIVE_ALLOWED_SYMBOLS": "DOGEUSDT",
                    "QUANT_LIVE_MAX_STAKE_USDT": "1",
                    "QUANT_LIVE_MAX_OPEN_TRADES": "1",
                },
                clear=False,
            ):
                original_client = freqtrade_client_module.freqtrade_client
                original_execution_client = execution_service_module.freqtrade_client
                original_sync_client = sync_service_module.freqtrade_client
                original_signal_service = execution_service_module.signal_service
                try:
                    signal_service = SignalService()
                    signal = signal_service.ingest_signal(
                        {
                            "symbol": "DOGEUSDT",
                            "side": "long",
                            "score": "0.91",
                            "confidence": "0.88",
                            "target_weight": "0.25",
                            "generated_at": datetime.now(timezone.utc).isoformat(),
                            "source": "rule-based",
                            "strategy_id": 1,
                        }
                    )
                    execution_service = ExecutionService(
                        market_client=_FakeBinanceMarketClient(
                            {"DOGEUSDT": "1"},
                            step_size_map={"DOGEUSDT": "1"},
                            last_price_map={"DOGEUSDT": "0.09069"},
                        )
                    )
                    client = FreqtradeClient()
                    freqtrade_client_module.freqtrade_client = client
                    execution_service_module.freqtrade_client = client
                    sync_service_module.freqtrade_client = client
                    execution_service_module.signal_service = signal_service

                    with self.assertRaises(PermissionError) as ctx:
                        execution_service.dispatch_signal(int(signal["signal_id"]))
                finally:
                    freqtrade_client_module.freqtrade_client = original_client
                    execution_service_module.freqtrade_client = original_execution_client
                    sync_service_module.freqtrade_client = original_sync_client
                    execution_service_module.signal_service = original_signal_service
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

        self.assertIn("最小卖出额", str(ctx.exception))
        self.assertNotIn("forceenter_seen", state)

    def test_live_mode_allows_doge_order_when_safe_exit_notional_is_met(self) -> None:
        state: dict[str, object] = {
            "positions": [],
            "trades": [],
            "balances": [{"asset": "USDT", "total": "20.0", "available": "20.0", "locked": "0.0"}],
            "strategies": [{"id": 1, "name": "TrendBreakout", "status": "running"}],
            "dry_run": False,
            "stake_amount": "1.3",
            "max_open_trades": 1,
        }

        class Handler(BaseHTTPRequestHandler):
            def _record(self) -> None:
                state.setdefault("requests", []).append(
                    {
                        "method": self.command,
                        "path": self.path,
                        "authorization": self.headers.get("Authorization", ""),
                    }
                )

            def _read_body(self) -> dict[str, object]:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0:
                    return {}
                raw = self.rfile.read(length).decode("utf-8")
                return json.loads(raw) if raw else {}

            def _send_json(self, status: int, payload: dict[str, object]) -> None:
                encoded = json.dumps(payload).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

            def do_GET(self) -> None:  # noqa: N802
                path = urlsplit(self.path).path
                self._record()
                if path == "/api/v1/show_config":
                    self._send_json(
                        200,
                        {
                            "dry_run": False,
                            "stake_amount": "1.3",
                            "max_open_trades": 1,
                            "trading_mode": "spot",
                        },
                    )
                    return
                if path == "/api/v1/status":
                    self._send_json(200, {"status": state["positions"]})
                    return
                if path == "/api/v1/trades":
                    self._send_json(200, {"trades": state["trades"]})
                    return
                if path == "/api/v1/balance":
                    self._send_json(200, {"balances": state["balances"]})
                    return
                if path == "/api/v1/strategies":
                    self._send_json(200, {"strategies": state["strategies"]})
                    return
                self._send_json(200, {"status": "pong"})

            def do_POST(self) -> None:  # noqa: N802
                body = self._read_body()
                path = urlsplit(self.path).path
                self._record()
                if path == "/api/v1/token/login":
                    expected = "Basic " + base64.b64encode(b"bot:secret").decode("ascii")
                    if self.headers.get("Authorization") != expected:
                        self._send_json(401, {"detail": "unauthorized"})
                        return
                    self._send_json(200, {"access_token": "token-1", "refresh_token": "refresh-1"})
                    return
                if path == "/api/v1/forceenter":
                    state["forceenter_seen"] = body
                    self._send_json(
                        200,
                        {
                            "trade_id": 199,
                            "status": "ok",
                            "pair": "DOGE/USDT",
                            "amount": 8,
                            "open_rate": 0.125,
                        },
                    )
                    return
                self._send_json(404, {"detail": "not found"})

            def log_message(self, format: str, *args: object) -> None:  # noqa: A003
                return

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        server.timeout = 1
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            port = int(server.server_address[1])
            with patch.dict(
                os.environ,
                {
                    "QUANT_RUNTIME_MODE": "live",
                    "QUANT_ALLOW_LIVE_EXECUTION": "true",
                    "BINANCE_API_KEY": "k",
                    "BINANCE_API_SECRET": "s",
                    "QUANT_FREQTRADE_API_URL": f"http://127.0.0.1:{port}",
                    "QUANT_FREQTRADE_API_USERNAME": "bot",
                    "QUANT_FREQTRADE_API_PASSWORD": "secret",
                    "QUANT_LIVE_ALLOWED_SYMBOLS": "DOGEUSDT",
                    "QUANT_LIVE_MAX_STAKE_USDT": "1.3",
                    "QUANT_LIVE_MAX_OPEN_TRADES": "1",
                },
                clear=False,
            ):
                original_client = freqtrade_client_module.freqtrade_client
                original_execution_client = execution_service_module.freqtrade_client
                original_sync_client = sync_service_module.freqtrade_client
                original_signal_service = execution_service_module.signal_service
                try:
                    signal_service = SignalService()
                    signal = signal_service.ingest_signal(
                        {
                            "symbol": "DOGEUSDT",
                            "side": "long",
                            "score": "0.91",
                            "confidence": "0.88",
                            "target_weight": "0.25",
                            "generated_at": datetime.now(timezone.utc).isoformat(),
                            "source": "rule-based",
                            "strategy_id": 1,
                        }
                    )
                    execution_service = ExecutionService(
                        market_client=_FakeBinanceMarketClient(
                            {"DOGEUSDT": "1"},
                            step_size_map={"DOGEUSDT": "1"},
                            last_price_map={"DOGEUSDT": "0.09069"},
                        )
                    )
                    client = FreqtradeClient()
                    freqtrade_client_module.freqtrade_client = client
                    execution_service_module.freqtrade_client = client
                    sync_service_module.freqtrade_client = client
                    execution_service_module.signal_service = signal_service

                    dispatch_result = execution_service.dispatch_signal(int(signal["signal_id"]))
                finally:
                    freqtrade_client_module.freqtrade_client = original_client
                    execution_service_module.freqtrade_client = original_execution_client
                    sync_service_module.freqtrade_client = original_sync_client
                    execution_service_module.signal_service = original_signal_service
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

        self.assertEqual(dispatch_result["runtime"]["mode"], "live")
        self.assertEqual(dispatch_result["runtime"]["backend"], "rest")
        self.assertEqual(dispatch_result["order"]["runtimeMode"], "live")
        self.assertEqual(dispatch_result["order"]["symbol"], "DOGE/USDT")
        self.assertEqual(state["forceenter_seen"]["pair"], "DOGE/USDT")
        self.assertEqual(state["forceenter_seen"]["side"], "long")
        self.assertEqual(state["forceenter_seen"]["stakeamount"], 1.3)

    def test_live_mode_rejects_missing_spot_trading_mode(self) -> None:
        state: dict[str, object] = {
            "positions": [],
            "trades": [],
            "balances": [{"asset": "USDT", "total": "20.0", "available": "20.0", "locked": "0.0"}],
            "strategies": [{"id": 1, "name": "TrendBreakout", "status": "running"}],
            "dry_run": False,
            "stake_amount": 1,
            "max_open_trades": 1,
        }

        class Handler(BaseHTTPRequestHandler):
            def _record(self) -> None:
                state.setdefault("requests", []).append({"method": self.command, "path": self.path})

            def _read_body(self) -> dict[str, object]:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0:
                    return {}
                raw = self.rfile.read(length).decode("utf-8")
                return json.loads(raw) if raw else {}

            def _send_json(self, status: int, payload: dict[str, object]) -> None:
                encoded = json.dumps(payload).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

            def do_GET(self) -> None:  # noqa: N802
                path = urlsplit(self.path).path
                self._record()
                if path == "/api/v1/show_config":
                    self._send_json(200, {"dry_run": False, "stake_amount": 1, "max_open_trades": 1})
                    return
                if path == "/api/v1/status":
                    self._send_json(200, {"status": state["positions"]})
                    return
                if path == "/api/v1/trades":
                    self._send_json(200, {"trades": state["trades"]})
                    return
                if path == "/api/v1/balance":
                    self._send_json(200, {"balances": state["balances"]})
                    return
                if path == "/api/v1/strategies":
                    self._send_json(200, {"strategies": state["strategies"]})
                    return
                self._send_json(200, {"status": "pong"})

            def do_POST(self) -> None:  # noqa: N802
                path = urlsplit(self.path).path
                if path == "/api/v1/token/login":
                    expected = "Basic " + base64.b64encode(b"bot:secret").decode("ascii")
                    if self.headers.get("Authorization") != expected:
                        self._send_json(401, {"detail": "unauthorized"})
                        return
                    self._send_json(200, {"access_token": "token-1", "refresh_token": "refresh-1"})
                    return
                self._send_json(404, {"detail": "not found"})

            def log_message(self, format: str, *args: object) -> None:  # noqa: A003
                return

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        server.timeout = 1
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            port = int(server.server_address[1])
            with patch.dict(
                os.environ,
                {
                    "QUANT_RUNTIME_MODE": "live",
                    "QUANT_ALLOW_LIVE_EXECUTION": "true",
                    "BINANCE_API_KEY": "k",
                    "BINANCE_API_SECRET": "s",
                    "QUANT_FREQTRADE_API_URL": f"http://127.0.0.1:{port}",
                    "QUANT_FREQTRADE_API_USERNAME": "bot",
                    "QUANT_FREQTRADE_API_PASSWORD": "secret",
                    "QUANT_LIVE_ALLOWED_SYMBOLS": "DOGEUSDT",
                    "QUANT_LIVE_MAX_STAKE_USDT": "1",
                    "QUANT_LIVE_MAX_OPEN_TRADES": "1",
                },
                clear=False,
            ):
                original_client = freqtrade_client_module.freqtrade_client
                original_execution_client = execution_service_module.freqtrade_client
                original_sync_client = sync_service_module.freqtrade_client
                original_signal_service = execution_service_module.signal_service
                try:
                    signal_service = SignalService()
                    signal = signal_service.ingest_signal(
                        {
                            "symbol": "DOGEUSDT",
                            "side": "long",
                            "score": "0.91",
                            "confidence": "0.88",
                            "target_weight": "0.25",
                            "generated_at": datetime.now(timezone.utc).isoformat(),
                            "source": "rule-based",
                            "strategy_id": 1,
                        }
                    )
                    execution_service = ExecutionService(market_client=_FakeBinanceMarketClient({"DOGEUSDT": "1"}))
                    client = FreqtradeClient()
                    freqtrade_client_module.freqtrade_client = client
                    execution_service_module.freqtrade_client = client
                    sync_service_module.freqtrade_client = client
                    execution_service_module.signal_service = signal_service
                    with self.assertRaises(PermissionError):
                        execution_service.dispatch_signal(int(signal["signal_id"]))
                finally:
                    freqtrade_client_module.freqtrade_client = original_client
                    execution_service_module.freqtrade_client = original_execution_client
                    sync_service_module.freqtrade_client = original_sync_client
                    execution_service_module.signal_service = original_signal_service
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_live_mode_rejects_remote_max_open_trades_above_local_limit(self) -> None:
        state: dict[str, object] = {
            "positions": [],
            "trades": [],
            "balances": [{"asset": "USDT", "total": "20.0", "available": "20.0", "locked": "0.0"}],
            "strategies": [{"id": 1, "name": "TrendBreakout", "status": "running"}],
            "dry_run": False,
            "stake_amount": 1,
            "max_open_trades": 3,
            "trading_mode": "spot",
        }

        class Handler(BaseHTTPRequestHandler):
            def _record(self) -> None:
                state.setdefault("requests", []).append({"method": self.command, "path": self.path})

            def _read_body(self) -> dict[str, object]:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0:
                    return {}
                raw = self.rfile.read(length).decode("utf-8")
                return json.loads(raw) if raw else {}

            def _send_json(self, status: int, payload: dict[str, object]) -> None:
                encoded = json.dumps(payload).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

            def do_GET(self) -> None:  # noqa: N802
                path = urlsplit(self.path).path
                self._record()
                if path == "/api/v1/show_config":
                    self._send_json(
                        200,
                        {"dry_run": False, "stake_amount": 1, "max_open_trades": 3, "trading_mode": "spot"},
                    )
                    return
                if path == "/api/v1/status":
                    self._send_json(200, {"status": state["positions"]})
                    return
                if path == "/api/v1/trades":
                    self._send_json(200, {"trades": state["trades"]})
                    return
                if path == "/api/v1/balance":
                    self._send_json(200, {"balances": state["balances"]})
                    return
                if path == "/api/v1/strategies":
                    self._send_json(200, {"strategies": state["strategies"]})
                    return
                self._send_json(200, {"status": "pong"})

            def do_POST(self) -> None:  # noqa: N802
                path = urlsplit(self.path).path
                if path == "/api/v1/token/login":
                    expected = "Basic " + base64.b64encode(b"bot:secret").decode("ascii")
                    if self.headers.get("Authorization") != expected:
                        self._send_json(401, {"detail": "unauthorized"})
                        return
                    self._send_json(200, {"access_token": "token-1", "refresh_token": "refresh-1"})
                    return
                self._send_json(404, {"detail": "not found"})

            def log_message(self, format: str, *args: object) -> None:  # noqa: A003
                return

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        server.timeout = 1
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            port = int(server.server_address[1])
            with patch.dict(
                os.environ,
                {
                    "QUANT_RUNTIME_MODE": "live",
                    "QUANT_ALLOW_LIVE_EXECUTION": "true",
                    "BINANCE_API_KEY": "k",
                    "BINANCE_API_SECRET": "s",
                    "QUANT_FREQTRADE_API_URL": f"http://127.0.0.1:{port}",
                    "QUANT_FREQTRADE_API_USERNAME": "bot",
                    "QUANT_FREQTRADE_API_PASSWORD": "secret",
                    "QUANT_LIVE_ALLOWED_SYMBOLS": "DOGEUSDT",
                    "QUANT_LIVE_MAX_STAKE_USDT": "1",
                    "QUANT_LIVE_MAX_OPEN_TRADES": "1",
                },
                clear=False,
            ):
                original_client = freqtrade_client_module.freqtrade_client
                original_execution_client = execution_service_module.freqtrade_client
                original_sync_client = sync_service_module.freqtrade_client
                original_signal_service = execution_service_module.signal_service
                try:
                    signal_service = SignalService()
                    signal = signal_service.ingest_signal(
                        {
                            "symbol": "DOGEUSDT",
                            "side": "long",
                            "score": "0.91",
                            "confidence": "0.88",
                            "target_weight": "0.25",
                            "generated_at": datetime.now(timezone.utc).isoformat(),
                            "source": "rule-based",
                            "strategy_id": 1,
                        }
                    )
                    execution_service = ExecutionService(market_client=_FakeBinanceMarketClient({"DOGEUSDT": "1"}))
                    client = FreqtradeClient()
                    freqtrade_client_module.freqtrade_client = client
                    execution_service_module.freqtrade_client = client
                    sync_service_module.freqtrade_client = client
                    execution_service_module.signal_service = signal_service
                    with self.assertRaises(PermissionError):
                        execution_service.dispatch_signal(int(signal["signal_id"]))
                finally:
                    freqtrade_client_module.freqtrade_client = original_client
                    execution_service_module.freqtrade_client = original_execution_client
                    sync_service_module.freqtrade_client = original_sync_client
                    execution_service_module.signal_service = original_signal_service
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_rest_mode_uses_real_backend_for_execution_and_sync(self) -> None:
        state: dict[str, object] = {
            "positions": [{"id": "trade-99", "symbol": "BTC/USDT", "side": "long"}],
            "trades": [{"id": "trade-99", "symbol": "BTC/USDT", "status": "filled"}],
            "balances": [{"asset": "USDT", "total": "100.0", "available": "90.0", "locked": "10.0"}],
            "strategies": [{"id": 1, "name": "TrendBreakout", "status": "running"}],
        }

        class Handler(BaseHTTPRequestHandler):
            def _record(self) -> None:
                state.setdefault("requests", []).append(
                    {
                        "method": self.command,
                        "path": self.path,
                        "authorization": self.headers.get("Authorization", ""),
                    }
                )

            def _read_body(self) -> dict[str, object]:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0:
                    return {}
                raw = self.rfile.read(length).decode("utf-8")
                return json.loads(raw) if raw else {}

            def _send_json(self, status: int, payload: dict[str, object]) -> None:
                encoded = json.dumps(payload).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

            def do_GET(self) -> None:  # noqa: N802
                path = urlsplit(self.path).path
                self._record()
                if path == "/api/v1/show_config":
                    self._send_json(200, {"dry_run": state.get("dry_run", True)})
                    return
                if path == "/api/v1/status":
                    self._send_json(200, {"status": state["positions"]})
                    return
                if path == "/api/v1/trades":
                    self._send_json(200, {"trades": state["trades"]})
                    return
                if path == "/api/v1/balance":
                    self._send_json(200, {"balances": state["balances"]})
                    return
                if path == "/api/v1/strategies":
                    self._send_json(200, {"strategies": state["strategies"]})
                    return
                self._send_json(200, {"status": "pong"})

            def do_POST(self) -> None:  # noqa: N802
                body = self._read_body()
                path = urlsplit(self.path).path
                self._record()
                if path == "/api/v1/token/login":
                    expected = "Basic " + base64.b64encode(b"bot:secret").decode("ascii")
                    if self.headers.get("Authorization") != expected:
                        self._send_json(401, {"detail": "unauthorized"})
                        return
                    state["login_seen"] = True
                    self._send_json(200, {"access_token": "token-1", "refresh_token": "refresh-1"})
                    return
                if path in {"/api/v1/start", "/api/v1/pause", "/api/v1/stop"}:
                    state["action_seen"] = path.rsplit("/", 1)[-1]
                    self._send_json(200, {"status": state["action_seen"]})
                    return
                if path == "/api/v1/forceenter":
                    state["forceenter_seen"] = body
                    self._send_json(200, {"trade_id": 99, "status": "ok"})
                    return
                self._send_json(404, {"detail": "not found"})

            def log_message(self, format: str, *args: object) -> None:  # noqa: A003
                return

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        server.timeout = 1
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            port = int(server.server_address[1])
            with patch.dict(
                os.environ,
                {
                    "QUANT_RUNTIME_MODE": "dry-run",
                    "QUANT_FREQTRADE_API_URL": f"http://127.0.0.1:{port}",
                    "QUANT_FREQTRADE_API_USERNAME": "bot",
                    "QUANT_FREQTRADE_API_PASSWORD": "secret",
                },
                clear=False,
            ):
                original_client = freqtrade_client_module.freqtrade_client
                original_execution_client = execution_service_module.freqtrade_client
                original_sync_client = sync_service_module.freqtrade_client
                try:
                    client = FreqtradeClient()
                    freqtrade_client_module.freqtrade_client = client
                    execution_service_module.freqtrade_client = client
                    sync_service_module.freqtrade_client = client

                    dispatch_result = ExecutionService().dispatch_signal(1)
                    sync_snapshot = SyncService().sync_execution_state()
                finally:
                    freqtrade_client_module.freqtrade_client = original_client
                    execution_service_module.freqtrade_client = original_execution_client
                    sync_service_module.freqtrade_client = original_sync_client
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

        self.assertEqual(dispatch_result["runtime"]["backend"], "rest")
        self.assertEqual(dispatch_result["runtime"]["connection_status"], "connected")
        self.assertEqual(dispatch_result["runtime"]["mode"], "dry-run")
        self.assertEqual(dispatch_result["order"]["runtimeMode"], "dry-run")
        self.assertEqual(sync_snapshot["balances"][0]["asset"], "USDT")
        self.assertEqual(state["login_seen"], True)
        self.assertTrue(any(urlsplit(item["path"]).path == "/api/v1/forceenter" for item in state.get("requests", [])))

    def test_dry_run_rejects_rest_backend_when_remote_mode_is_live(self) -> None:
        state: dict[str, object] = {"strategies": [{"id": 1, "name": "TrendBreakout", "status": "running"}]}

        class Handler(BaseHTTPRequestHandler):
            def _send_json(self, status: int, payload: dict[str, object]) -> None:
                encoded = json.dumps(payload).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

            def do_GET(self) -> None:  # noqa: N802
                path = urlsplit(self.path).path
                if path == "/api/v1/show_config":
                    self._send_json(200, {"dry_run": False})
                    return
                if path == "/api/v1/status":
                    self._send_json(200, {"status": []})
                    return
                if path == "/api/v1/trades":
                    self._send_json(200, {"trades": []})
                    return
                if path == "/api/v1/balance":
                    self._send_json(200, {"balances": []})
                    return
                if path == "/api/v1/strategies":
                    self._send_json(200, {"strategies": state["strategies"]})
                    return
                self._send_json(200, {"status": "pong"})

            def do_POST(self) -> None:  # noqa: N802
                path = urlsplit(self.path).path
                if path == "/api/v1/token/login":
                    expected = "Basic " + base64.b64encode(b"bot:secret").decode("ascii")
                    if self.headers.get("Authorization") != expected:
                        self._send_json(401, {"detail": "unauthorized"})
                        return
                    self._send_json(200, {"access_token": "token-1", "refresh_token": "refresh-1"})
                    return
                self._send_json(404, {"detail": "not found"})

            def log_message(self, format: str, *args: object) -> None:  # noqa: A003
                return

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        server.timeout = 1
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            port = int(server.server_address[1])
            with patch.dict(
                os.environ,
                {
                    "QUANT_RUNTIME_MODE": "dry-run",
                    "QUANT_FREQTRADE_API_URL": f"http://127.0.0.1:{port}",
                    "QUANT_FREQTRADE_API_USERNAME": "bot",
                    "QUANT_FREQTRADE_API_PASSWORD": "secret",
                },
                clear=False,
            ):
                original_client = freqtrade_client_module.freqtrade_client
                original_execution_client = execution_service_module.freqtrade_client
                original_sync_client = sync_service_module.freqtrade_client
                try:
                    client = FreqtradeClient()
                    freqtrade_client_module.freqtrade_client = client
                    execution_service_module.freqtrade_client = client
                    sync_service_module.freqtrade_client = client
                    with self.assertRaises(PermissionError):
                        ExecutionService().dispatch_signal(1)
                finally:
                    freqtrade_client_module.freqtrade_client = original_client
                    execution_service_module.freqtrade_client = original_execution_client
                    sync_service_module.freqtrade_client = original_sync_client
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
