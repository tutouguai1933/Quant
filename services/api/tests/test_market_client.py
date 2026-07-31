"""BinanceMarketClient 单元测试（mock URL 断言）。"""

from __future__ import annotations

import json
from io import BytesIO
from unittest import TestCase
from urllib.request import urlopen

from services.api.app.adapters.binance.market_client import BinanceMarketClient


class _MockOpener:
    """模拟 urlopen，记录请求 URL 并返回预设 JSON。"""

    def __init__(self, response_data: object = None) -> None:
        self.response_data = response_data or []
        self.captured_urls: list[str] = []

    def __call__(self, url: str, timeout: float = 5.0) -> BytesIO:
        self.captured_urls.append(url)
        return BytesIO(json.dumps(self.response_data).encode("utf-8"))


class MarketClientTests(TestCase):
    def setUp(self) -> None:
        self.mock_opener = _MockOpener()
        self.client = BinanceMarketClient(
            base_url="https://data-api.binance.vision",
            opener=self.mock_opener,
        )

    # ── get_klines ──────────────────────────────────────────────────────

    def _make_client(self, response_data: object = None) -> BinanceMarketClient:
        """构造带 mock opener 的客户端，mock 返回指定数据。"""
        self.mock_opener = _MockOpener(response_data)
        return BinanceMarketClient(
            base_url="https://data-api.binance.vision",
            opener=self.mock_opener,
        )

    def setUp(self) -> None:
        self.mock_opener = _MockOpener()
        self.client = BinanceMarketClient(
            base_url="https://data-api.binance.vision",
            opener=self.mock_opener,
        )

    def test_get_klines_default_params_preserve_behavior(self) -> None:
        """无参调用与现有行为一致。"""
        client = self._make_client([])
        result = client.get_klines("BTCUSDT")
        self.assertIsInstance(result, list)
        self.assertEqual(len(self.mock_opener.captured_urls), 1)
        url = self.mock_opener.captured_urls[0]
        self.assertIn("symbol=BTCUSDT", url)
        self.assertIn("interval=4h", url)
        self.assertIn("limit=200", url)
        self.assertNotIn("startTime", url)
        self.assertNotIn("endTime", url)

    def test_get_klines_with_start_ts(self) -> None:
        """start_ts 参数拼入 URL。"""
        self.client.get_klines("ETHUSDT", interval="1h", limit=500, start_ts=1700000000000)
        self.assertEqual(len(self.mock_opener.captured_urls), 1)
        url = self.mock_opener.captured_urls[0]
        self.assertIn("symbol=ETHUSDT", url)
        self.assertIn("interval=1h", url)
        self.assertIn("limit=500", url)
        self.assertIn("startTime=1700000000000", url)

    def test_get_klines_with_end_ts(self) -> None:
        """end_ts 参数拼入 URL。"""
        self.client.get_klines("BNBUSDT", interval="15m", limit=100, end_ts=1710000000000)
        self.assertEqual(len(self.mock_opener.captured_urls), 1)
        url = self.mock_opener.captured_urls[0]
        self.assertIn("symbol=BNBUSDT", url)
        self.assertIn("interval=15m", url)
        self.assertIn("limit=100", url)
        self.assertIn("endTime=1710000000000", url)

    def test_get_klines_with_start_and_end(self) -> None:
        """start_ts 和 end_ts 同时出现。"""
        self.client.get_klines(
            "SOLUSDT", interval="4h", limit=1000,
            start_ts=1700000000000, end_ts=1710000000000,
        )
        self.assertEqual(len(self.mock_opener.captured_urls), 1)
        url = self.mock_opener.captured_urls[0]
        self.assertIn("symbol=SOLUSDT", url)
        self.assertIn("interval=4h", url)
        self.assertIn("limit=1000", url)
        self.assertIn("startTime=1700000000000", url)
        self.assertIn("endTime=1710000000000", url)

    # ── get_order_book ──────────────────────────────────────────────────

    def test_get_order_book_default_limit(self) -> None:
        """默认 limit=20 拼入 URL。"""
        client = self._make_client({"bids": [], "asks": []})
        result = client.get_order_book("BTCUSDT")
        self.assertIsInstance(result, dict)
        self.assertIn("bids", result)
        self.assertIn("asks", result)
        self.assertEqual(len(self.mock_opener.captured_urls), 1)
        url = self.mock_opener.captured_urls[0]
        self.assertIn("symbol=BTCUSDT", url)
        self.assertIn("limit=20", url)
        self.assertIn("/api/v3/depth", url)

    def test_get_order_book_custom_limit(self) -> None:
        """自定义 limit 拼入 URL。"""
        self.client.get_order_book("ETHUSDT", limit=50)
        self.assertEqual(len(self.mock_opener.captured_urls), 1)
        url = self.mock_opener.captured_urls[0]
        self.assertIn("symbol=ETHUSDT", url)
        self.assertIn("limit=50", url)

    def test_get_order_book_returns_structured_dict(self) -> None:
        """返回结构包含 bids/asks 字段。"""
        mock_opener = _MockOpener({
            "bids": [["50000.00", "1.5"], ["49900.00", "2.0"]],
            "asks": [["50100.00", "0.8"], ["50200.00", "1.2"]],
        })
        client = BinanceMarketClient(
            base_url="https://data-api.binance.vision",
            opener=mock_opener,
        )
        result = client.get_order_book("BTCUSDT")
        self.assertEqual(result["bids"], [["50000.00", "1.5"], ["49900.00", "2.0"]])
        self.assertEqual(result["asks"], [["50100.00", "0.8"], ["50200.00", "1.2"]])

    def test_get_order_book_empty_on_error(self) -> None:
        """网络错误时返回空结构不抛异常。"""

        def _failing(url: str, timeout: float = 5.0) -> BytesIO:
            raise OSError("connection refused")

        client = BinanceMarketClient(
            base_url="https://data-api.binance.vision",
            opener=_failing,
            max_retries=1,
        )
        result = client.get_order_book("BTCUSDT")
        self.assertEqual(result, {"bids": [], "asks": []})
