from __future__ import annotations

import base64
import json
import os
import socket
import sys
import threading
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.api.app.adapters.freqtrade.client import FreqtradeClient  # noqa: E402
from services.api.app.domain.contracts import ExecutionActionContract, ExecutionActionType, SignalSide  # noqa: E402


def _unused_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _make_server(state: dict[str, object]) -> tuple[ThreadingHTTPServer, str]:
    class Handler(BaseHTTPRequestHandler):
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

        def _record(self, body: dict[str, object] | None = None) -> None:
            state.setdefault("requests", []).append(
                {
                    "method": self.command,
                    "path": self.path,
                    "authorization": self.headers.get("Authorization", ""),
                    "body": body or {},
                }
            )

        def do_GET(self) -> None:  # noqa: N802
            body = self._read_body()
            path = urlsplit(self.path).path
            self._record(body)
            if path == "/api/v1/status":
                self._send_json(200, {"status": state.get("positions", [])})
                return
            if path == "/api/v1/trades":
                self._send_json(200, {"trades": state.get("trades", [])})
                return
            if path == "/api/v1/show_config":
                self._send_json(200, {"dry_run": state.get("dry_run", True)})
                return
            if path == "/api/v1/balance":
                self._send_json(200, {"balances": state.get("balances", [])})
                return
            if path == "/api/v1/strategies":
                self._send_json(200, {"strategies": state.get("strategies", [])})
                return
            self._send_json(200, {"status": "pong"})

        def do_POST(self) -> None:  # noqa: N802
            body = self._read_body()
            path = urlsplit(self.path).path
            self._record(body)
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
                self._send_json(200, {"trade_id": 88, "status": "ok"})
                return
            self._send_json(404, {"detail": "not found"})

        def log_message(self, format: str, *args: object) -> None:  # noqa: A003
            return

    server = ThreadingHTTPServer(("127.0.0.1", _unused_port()), Handler)
    server.timeout = 1
    return server, f"http://127.0.0.1:{server.server_address[1]}"


class FreqtradeRuntimeServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._env_backup = os.environ.copy()

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._env_backup)

    @staticmethod
    def _build_action() -> dict[str, object]:
        return ExecutionActionContract(
            action_type=ExecutionActionType.OPEN_POSITION,
            symbol="BTCUSDT",
            side=SignalSide.LONG,
            quantity=Decimal("0.0100000000"),
            source_signal_id=1,
            strategy_id=1,
            account_id=1,
        ).to_dict()

    def test_no_freqtrade_config_falls_back_to_memory_backend(self) -> None:
        os.environ.pop("QUANT_FREQTRADE_API_URL", None)
        os.environ.pop("QUANT_FREQTRADE_API_USERNAME", None)
        os.environ.pop("QUANT_FREQTRADE_API_PASSWORD", None)
        os.environ["QUANT_RUNTIME_MODE"] = "demo"

        client = FreqtradeClient()
        snapshot = client.get_runtime_snapshot()
        order = client.submit_execution_action(self._build_action())

        self.assertEqual(snapshot["backend"], "memory")
        self.assertEqual(snapshot["mode"], "demo")
        self.assertEqual(snapshot["executor"], "freqtrade")
        self.assertEqual(order["runtimeMode"], "demo")
        self.assertTrue(str(order["id"]).startswith("ft-demo-order-"))

    def test_freqtrade_config_uses_rest_backend(self) -> None:
        state: dict[str, object] = {
            "positions": [{"id": "trade-88", "symbol": "BTC/USDT", "side": "long"}],
            "trades": [{"id": "trade-88", "symbol": "BTC/USDT", "status": "filled"}],
            "balances": [{"asset": "USDT", "total": "100.0", "available": "90.0", "locked": "10.0"}],
            "strategies": [{"id": 1, "name": "TrendBreakout", "status": "running"}],
            "dry_run": True,
        }
        server, base_url = _make_server(state)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            os.environ["QUANT_RUNTIME_MODE"] = "dry-run"
            os.environ["QUANT_FREQTRADE_API_URL"] = base_url
            os.environ["QUANT_FREQTRADE_API_USERNAME"] = "bot"
            os.environ["QUANT_FREQTRADE_API_PASSWORD"] = "secret"

            client = FreqtradeClient()
            snapshot = client.get_runtime_snapshot()
            started = client.control_strategy(1, "start")
            order = client.submit_execution_action(self._build_action())
            sync_snapshot = client.get_snapshot()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

        self.assertEqual(snapshot["backend"], "rest")
        self.assertEqual(snapshot["mode"], "dry-run")
        self.assertEqual(snapshot["connection_status"], "connected")
        self.assertEqual(started["status"], "running")
        self.assertEqual(order["runtimeMode"], "dry-run")
        self.assertTrue(str(order["id"]).startswith("ft-rest-order-"))
        self.assertEqual(sync_snapshot.balances[0]["asset"], "USDT")
        self.assertEqual(state["login_seen"], True)
        self.assertEqual(state["action_seen"], "start")
        self.assertTrue(any(urlsplit(item["path"]).path == "/api/v1/forceenter" for item in state["requests"]))

    def test_partial_freqtrade_config_rejects_value(self) -> None:
        os.environ["QUANT_FREQTRADE_API_URL"] = "http://127.0.0.1:8080"
        os.environ["QUANT_FREQTRADE_API_USERNAME"] = "bot"
        os.environ.pop("QUANT_FREQTRADE_API_PASSWORD", None)
        os.environ["QUANT_RUNTIME_MODE"] = "demo"

        with self.assertRaises(ValueError):
            FreqtradeClient()

    def test_demo_mode_keeps_memory_backend_even_when_rest_config_exists(self) -> None:
        os.environ["QUANT_RUNTIME_MODE"] = "demo"
        os.environ["QUANT_FREQTRADE_API_URL"] = "http://127.0.0.1:9000"
        os.environ["QUANT_FREQTRADE_API_USERNAME"] = "bot"
        os.environ["QUANT_FREQTRADE_API_PASSWORD"] = "secret"

        snapshot = FreqtradeClient().get_runtime_snapshot()

        self.assertEqual(snapshot["backend"], "memory")
        self.assertEqual(snapshot["mode"], "demo")


if __name__ == "__main__":
    unittest.main()
