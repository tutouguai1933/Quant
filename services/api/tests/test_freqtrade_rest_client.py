from __future__ import annotations

import base64
import json
import socket
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.api.app.adapters.freqtrade.rest_client import FreqtradeRestClient, FreqtradeRestConfig  # noqa: E402


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
            if path == "/api/v1/ping":
                self._send_json(200, {"status": "pong"})
                return
            if path == "/api/v1/status":
                self._send_json(200, {"status": state.get("positions", [])})
                return
            if path == "/api/v1/trades":
                if state.get("fail_trades"):
                    self._send_json(503, {"detail": "temporarily unavailable"})
                    return
                self._send_json(200, {"trades": state.get("trades", [])})
                return
            if path == "/api/v1/show_config":
                self._send_json(
                    200,
                    {
                        "dry_run": state.get("dry_run", True),
                        "stake_amount": state.get("stake_amount", 50),
                        "state": state.get("bot_state", "running"),
                        "strategy": state.get("strategy_name", "Freqtrade Bot"),
                    },
                )
                return
            if path == "/api/v1/balance":
                self._send_json(200, {"balances": state.get("balances", [])})
                return
            if path == "/api/v1/strategies":
                self._send_json(200, {"strategies": state.get("strategies", [])})
                return
            if path == "/api/v1/strategy/TrendBreakout":
                self._send_json(200, {"strategy": state.get("strategy_detail", {})})
                return
            self._send_json(404, {"detail": "not found"})

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
                self._send_json(200, {"trade_id": 77, "status": "ok"})
                return
            if path == "/api/v1/forceexit":
                state["forceexit_seen"] = body
                self._send_json(200, {"trade_id": 77, "status": "ok"})
                return
            self._send_json(404, {"detail": "not found"})

        def log_message(self, format: str, *args: object) -> None:  # noqa: A003
            return

    server = ThreadingHTTPServer(("127.0.0.1", _unused_port()), Handler)
    server.timeout = 1
    return server, f"http://127.0.0.1:{server.server_address[1]}"


class FreqtradeRestClientTests(unittest.TestCase):
    def test_client_round_trip_reads_state_and_submits_actions(self) -> None:
        state: dict[str, object] = {
            "balances": [{"asset": "USDT", "total": "100.0", "available": "90.0", "locked": "10.0"}],
            "positions": [{"id": "trade-1", "symbol": "BTC/USDT", "side": "long", "quantity": "0.0100000000"}],
            "trades": [{"id": "trade-1", "symbol": "BTC/USDT", "status": "filled"}],
            "strategies": [{"id": 1, "name": "TrendBreakout", "status": "running"}],
            "strategy_detail": {"id": 1, "name": "TrendBreakout", "status": "running"},
            "stake_amount": 50,
        }
        server, base_url = _make_server(state)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            client = FreqtradeRestClient(
                FreqtradeRestConfig(
                    base_url=base_url,
                    username="bot",
                    password="secret",
                    timeout_seconds=2.0,
                )
            )

            ping = client.ping()
            started = client.control_strategy(1, "start")
            runtime = client.get_runtime_snapshot()
            snapshot = client.get_snapshot()
            order = client.submit_execution_action(
                {
                    "symbol": "BTCUSDT",
                    "side": "long",
                    "quantity": "0.0100000000",
                    "source_signal_id": 5,
                    "strategy_id": 1,
                }
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

        self.assertEqual(ping["status"], "pong")
        self.assertEqual(started["status"], "running")
        self.assertEqual(started["scope"], "executor")
        self.assertEqual(snapshot.balances[0]["asset"], "USDT")
        self.assertEqual(snapshot.positions[0]["symbol"], "BTC/USDT")
        self.assertEqual(snapshot.orders[0]["id"], "trade-1")
        self.assertEqual(snapshot.strategies[0]["name"], "TrendBreakout")
        self.assertEqual(runtime["mode"], "dry-run")
        self.assertEqual(order["runtimeMode"], "dry-run")
        self.assertTrue(str(order["id"]).startswith("ft-rest-order-"))
        self.assertEqual(state["login_seen"], True)
        self.assertEqual(state["action_seen"], "start")
        self.assertTrue(any(urlsplit(item["path"]).path == "/api/v1/forceenter" for item in state["requests"]))
        self.assertEqual(state["forceenter_seen"]["stakeamount"], 50.0)

    def test_client_falls_back_to_runtime_strategy_when_list_endpoint_unavailable(self) -> None:
        state: dict[str, object] = {
            "balances": [{"asset": "USDT", "total": "100.0", "available": "90.0", "locked": "10.0"}],
            "positions": [],
            "trades": [],
            "dry_run": True,
            "strategy_name": "Freqtrade Bot",
        }
        server, base_url = _make_server(state)
        original_make_server = _make_server
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        original_handler = server.RequestHandlerClass.do_GET

        def patched_do_get(self) -> None:  # type: ignore[no-redef]
            path = urlsplit(self.path).path
            if path == "/api/v1/strategies":
                self.send_response(409)
                self.send_header("Content-Type", "application/json")
                payload = json.dumps({"detail": "Bot is not in the correct state."}).encode("utf-8")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return
            original_handler(self)

        server.RequestHandlerClass.do_GET = patched_do_get
        try:
            client = FreqtradeRestClient(
                FreqtradeRestConfig(
                    base_url=base_url,
                    username="bot",
                    password="secret",
                    timeout_seconds=2.0,
                )
            )
            snapshot = client.get_snapshot()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
            server.RequestHandlerClass.do_GET = original_handler

        self.assertEqual(snapshot.strategies[0]["name"], "Freqtrade Bot")
        self.assertEqual(snapshot.strategies[0]["status"], "running")

    def test_client_uses_open_trade_orders_when_closed_trade_list_is_empty(self) -> None:
        state: dict[str, object] = {
            "balances": [{"asset": "USDT", "total": "100.0", "available": "90.0", "locked": "10.0"}],
            "positions": [
                {
                    "trade_id": 1,
                    "pair": "BTC/USDT",
                    "amount": 0.00075,
                    "open_rate": 66299.98,
                    "orders": [
                        {
                            "order_id": "dry_run_buy_BTC/USDT_1",
                            "status": "closed",
                            "filled": 0.00075,
                            "safe_price": 66299.98,
                            "ft_order_side": "buy",
                            "order_type": "market",
                        }
                    ],
                }
            ],
            "trades": [],
            "dry_run": True,
        }
        server, base_url = _make_server(state)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            client = FreqtradeRestClient(
                FreqtradeRestConfig(
                    base_url=base_url,
                    username="bot",
                    password="secret",
                    timeout_seconds=2.0,
                )
            )
            snapshot = client.get_snapshot()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

        self.assertEqual(snapshot.orders[0]["id"], "dry_run_buy_BTC/USDT_1")
        self.assertEqual(snapshot.orders[0]["status"], "closed")
        self.assertEqual(snapshot.orders[0]["symbol"], "BTC/USDT")

    def test_client_raises_clear_error_for_non_200(self) -> None:
        state: dict[str, object] = {
            "balances": [{"asset": "USDT", "total": "100.0", "available": "90.0", "locked": "10.0"}],
            "positions": [{"id": "trade-1", "symbol": "BTC/USDT", "side": "long"}],
            "trades": [{"id": "trade-1", "symbol": "BTC/USDT", "status": "filled"}],
            "strategies": [{"id": 1, "name": "TrendBreakout", "status": "running"}],
            "fail_trades": True,
        }
        server, base_url = _make_server(state)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            client = FreqtradeRestClient(
                FreqtradeRestConfig(
                    base_url=base_url,
                    username="bot",
                    password="secret",
                    timeout_seconds=2.0,
                )
            )
            state["strategies"] = [{"id": 1, "name": "TrendBreakout", "status": "running"}]
            with self.assertRaises(RuntimeError) as ctx:
                client.get_snapshot()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

        self.assertIn("Freqtrade REST", str(ctx.exception))

    def test_client_raises_clear_error_for_network_failure(self) -> None:
        client = FreqtradeRestClient(
            FreqtradeRestConfig(
                base_url=f"http://127.0.0.1:{_unused_port()}",
                username="bot",
                password="secret",
                timeout_seconds=0.2,
            )
        )

        with self.assertRaises(RuntimeError) as ctx:
            client.ping()

        self.assertIn("无法连接", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
