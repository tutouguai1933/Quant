"""测试客户端连接失败时的优雅降级。"""

from __future__ import annotations

import socket
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock
from urllib.error import URLError

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.api.app.adapters.binance.market_client import BinanceMarketClient  # noqa: E402
from services.api.app.services.market_service import MarketService  # noqa: E402


def _unused_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class TestGracefulDegradation(unittest.TestCase):
    def test_binance_market_client_returns_empty_list_on_connection_failure(self) -> None:
        """测试 Binance market client 连接失败时返回空列表而不是抛异常。"""

        def mock_opener(url, timeout=None):
            raise URLError("Connection refused")

        client = BinanceMarketClient(
            base_url="https://api.binance.com",
            timeout_seconds=5.0,
            opener=mock_opener,
            max_retries=2,
            base_delay=0.05,
        )

        tickers = client.get_tickers()
        self.assertEqual(tickers, [])

        klines = client.get_klines("BTCUSDT")
        self.assertEqual(klines, [])

        exchange_info = client.get_exchange_info(("BTCUSDT",))
        self.assertEqual(exchange_info, {"symbols": []})

    def test_binance_market_client_returns_empty_list_on_timeout(self) -> None:
        """测试 Binance market client 超时时返回空列表。"""

        def mock_opener(url, timeout=None):
            raise TimeoutError("Request timeout")

        client = BinanceMarketClient(
            base_url="https://api.binance.com",
            timeout_seconds=5.0,
            opener=mock_opener,
            max_retries=2,
            base_delay=0.05,
        )

        tickers = client.get_tickers()
        self.assertEqual(tickers, [])

    def test_market_service_handles_empty_tickers_gracefully(self) -> None:
        """测试 market service 能够处理空的 ticker 列表。"""

        def mock_opener(url, timeout=None):
            raise URLError("Connection refused")

        client = BinanceMarketClient(
            base_url="https://api.binance.com",
            timeout_seconds=5.0,
            opener=mock_opener,
            max_retries=2,
            base_delay=0.05,
        )

        service = MarketService(client=client)
        snapshots = service.list_market_snapshots(("BTCUSDT", "ETHUSDT"))

        self.assertEqual(snapshots, [])

    def test_binance_client_with_unreachable_endpoint(self) -> None:
        """测试 Binance client 连接到不可达的端点时优雅降级。"""
        client = BinanceMarketClient(
            base_url=f"http://127.0.0.1:{_unused_port()}",
            timeout_seconds=0.2,
            max_retries=2,
            base_delay=0.05,
        )

        tickers = client.get_tickers()
        self.assertEqual(tickers, [])

        klines = client.get_klines("BTCUSDT")
        self.assertEqual(klines, [])

    def test_binance_client_retries_before_degrading(self) -> None:
        """测试 Binance client 在降级前会重试。"""
        attempt_count = {"count": 0}

        def mock_opener(url, timeout=None):
            attempt_count["count"] += 1
            raise URLError("Connection refused")

        client = BinanceMarketClient(
            base_url="https://api.binance.com",
            timeout_seconds=5.0,
            opener=mock_opener,
            max_retries=3,
            base_delay=0.05,
        )

        tickers = client.get_tickers()

        self.assertEqual(tickers, [])
        self.assertEqual(attempt_count["count"], 3)


if __name__ == "__main__":
    unittest.main()
