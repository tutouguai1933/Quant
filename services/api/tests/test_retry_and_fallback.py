"""测试重试和降级策略。"""

from __future__ import annotations

import socket
import sys
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.error import URLError

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.api.app.adapters.binance.market_client import BinanceMarketClient  # noqa: E402
from services.api.app.adapters.freqtrade.rest_client import FreqtradeRestClient, FreqtradeRestConfig  # noqa: E402


def _unused_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class TestBinanceMarketClientRetry(unittest.TestCase):
    def test_binance_client_retries_on_timeout(self) -> None:
        """测试 Binance client 在超时时重试。"""
        attempt_count = {"count": 0}

        def mock_opener(url, timeout=None):
            attempt_count["count"] += 1
            if attempt_count["count"] < 3:
                raise URLError("Connection timeout")
            mock_response = Mock()
            mock_response.read.return_value = b'[{"symbol": "BTCUSDT", "lastPrice": "50000"}]'
            mock_response.__enter__ = Mock(return_value=mock_response)
            mock_response.__exit__ = Mock(return_value=False)
            return mock_response

        client = BinanceMarketClient(
            base_url="https://api.binance.com",
            timeout_seconds=5.0,
            opener=mock_opener,
            max_retries=3,
            base_delay=0.1,
        )

        result = client.get_tickers()
        self.assertEqual(attempt_count["count"], 3)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["symbol"], "BTCUSDT")

    def test_binance_client_returns_empty_after_max_retries(self) -> None:
        """测试 Binance client 在达到最大重试次数后返回空结果。"""
        attempt_count = {"count": 0}

        def mock_opener(url, timeout=None):
            attempt_count["count"] += 1
            raise URLError("Connection refused")

        client = BinanceMarketClient(
            base_url="https://api.binance.com",
            timeout_seconds=5.0,
            opener=mock_opener,
            max_retries=3,
            base_delay=0.1,
        )

        result = client.get_tickers()
        self.assertEqual(attempt_count["count"], 3)
        self.assertEqual(result, [])

    def test_binance_client_uses_exponential_backoff(self) -> None:
        """测试 Binance client 使用指数退避。"""
        attempt_times = []

        def mock_opener(url, timeout=None):
            attempt_times.append(time.time())
            raise URLError("Connection timeout")

        client = BinanceMarketClient(
            base_url="https://api.binance.com",
            timeout_seconds=5.0,
            opener=mock_opener,
            max_retries=3,
            base_delay=0.1,
        )

        client.get_tickers()

        self.assertEqual(len(attempt_times), 3)
        if len(attempt_times) >= 3:
            delay1 = attempt_times[1] - attempt_times[0]
            delay2 = attempt_times[2] - attempt_times[1]
            self.assertGreaterEqual(delay1, 0.1)
            self.assertGreaterEqual(delay2, 0.2)
            self.assertLess(delay1, 0.3)
            self.assertLess(delay2, 0.6)


class TestFreqtradeRestClientRetry(unittest.TestCase):
    def test_freqtrade_client_retries_on_500_error(self) -> None:
        """测试 Freqtrade client 在 500 错误时重试。"""
        state = {"attempt": 0}

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                state["attempt"] += 1
                if self.path == "/api/v1/ping":
                    if state["attempt"] < 3:
                        self.send_response(503)
                        self.send_header("Content-Type", "application/json")
                        self.end_headers()
                        self.wfile.write(b'{"detail": "Service Unavailable"}')
                    else:
                        self.send_response(200)
                        self.send_header("Content-Type", "application/json")
                        self.end_headers()
                        self.wfile.write(b'{"status": "pong"}')
                    return
                self.send_response(404)
                self.end_headers()

            def log_message(self, format: str, *args: object) -> None:  # noqa: A003
                return

        server = ThreadingHTTPServer(("127.0.0.1", _unused_port()), Handler)
        base_url = f"http://127.0.0.1:{server.server_address[1]}"
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        try:
            client = FreqtradeRestClient(
                FreqtradeRestConfig(
                    base_url=base_url,
                    username="bot",
                    password="secret",
                    timeout_seconds=2.0,
                    max_retries=3,
                    base_delay=0.1,
                )
            )
            result = client.ping()
            self.assertEqual(result["status"], "pong")
            self.assertEqual(state["attempt"], 3)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_freqtrade_client_raises_after_max_retries(self) -> None:
        """测试 Freqtrade client 在达到最大重试次数后抛出异常。"""
        state = {"attempt": 0}

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                state["attempt"] += 1
                if self.path == "/api/v1/ping":
                    self.send_response(503)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(b'{"detail": "Service Unavailable"}')
                    return
                self.send_response(404)
                self.end_headers()

            def log_message(self, format: str, *args: object) -> None:  # noqa: A003
                return

        server = ThreadingHTTPServer(("127.0.0.1", _unused_port()), Handler)
        base_url = f"http://127.0.0.1:{server.server_address[1]}"
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        try:
            client = FreqtradeRestClient(
                FreqtradeRestConfig(
                    base_url=base_url,
                    username="bot",
                    password="secret",
                    timeout_seconds=2.0,
                    max_retries=3,
                    base_delay=0.1,
                )
            )
            with self.assertRaises(RuntimeError) as ctx:
                client.ping()
            self.assertIn("503", str(ctx.exception))
            self.assertEqual(state["attempt"], 3)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_freqtrade_client_retries_on_connection_error(self) -> None:
        """测试 Freqtrade client 在连接错误时重试。"""
        client = FreqtradeRestClient(
            FreqtradeRestConfig(
                base_url=f"http://127.0.0.1:{_unused_port()}",
                username="bot",
                password="secret",
                timeout_seconds=0.2,
                max_retries=3,
                base_delay=0.1,
            )
        )

        with self.assertRaises(RuntimeError) as ctx:
            client.ping()

        self.assertIn("无法连接", str(ctx.exception))

    def test_freqtrade_client_uses_exponential_backoff(self) -> None:
        """测试 Freqtrade client 使用指数退避。"""
        state = {"attempts": []}

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                state["attempts"].append(time.time())
                if self.path == "/api/v1/ping":
                    self.send_response(503)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(b'{"detail": "Service Unavailable"}')
                    return
                self.send_response(404)
                self.end_headers()

            def log_message(self, format: str, *args: object) -> None:  # noqa: A003
                return

        server = ThreadingHTTPServer(("127.0.0.1", _unused_port()), Handler)
        base_url = f"http://127.0.0.1:{server.server_address[1]}"
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        try:
            client = FreqtradeRestClient(
                FreqtradeRestConfig(
                    base_url=base_url,
                    username="bot",
                    password="secret",
                    timeout_seconds=2.0,
                    max_retries=3,
                    base_delay=0.1,
                )
            )
            with self.assertRaises(RuntimeError):
                client.ping()

            self.assertEqual(len(state["attempts"]), 3)
            if len(state["attempts"]) >= 3:
                delay1 = state["attempts"][1] - state["attempts"][0]
                delay2 = state["attempts"][2] - state["attempts"][1]
                self.assertGreaterEqual(delay1, 0.1)
                self.assertGreaterEqual(delay2, 0.2)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
