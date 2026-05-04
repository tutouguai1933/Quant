"""Binance 市场数据客户端。"""

from __future__ import annotations

import json
import os
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen, ProxyHandler, build_opener

from services.api.app.core.settings import Settings


class BinanceMarketClient:
    """最小 Binance 公共市场数据客户端。"""

    def __init__(
        self,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
        opener=None,
        max_retries: int = 2,
        base_delay: float = 0.3,
    ) -> None:
        settings = Settings.from_env()
        self.base_url = (base_url or settings.binance_market_base_url).rstrip("/")
        self.timeout_seconds = timeout_seconds or settings.binance_timeout_seconds
        self.max_retries = max_retries
        self.base_delay = base_delay

        # 配置代理
        if opener is not None:
            self._opener = opener
        else:
            http_proxy = os.getenv("HTTP_PROXY", "")
            https_proxy = os.getenv("HTTPS_PROXY", "")
            if http_proxy or https_proxy:
                proxy_handler = ProxyHandler({
                    "http": http_proxy or None,
                    "https": https_proxy or None,
                })
                self._opener = build_opener(proxy_handler).open
            else:
                self._opener = urlopen

    def _safe_public_get(self, url: str, default):
        """读取公共接口，带重试和指数退避，异常时回退到空结果。"""

        last_exception: Exception | None = None

        for attempt in range(self.max_retries):
            try:
                response = self._opener(url, timeout=self.timeout_seconds)
                return json.load(response)
            except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
                last_exception = exc
                if attempt < self.max_retries - 1:
                    delay = self.base_delay * (2 ** attempt)
                    time.sleep(delay)
                continue
            except Exception:
                # 捕获所有其他异常，避免阻塞
                break

        return default

    def get_tickers(self, symbols: tuple[str, ...] | None = None) -> list[dict[str, object]]:
        """读取 24 小时行情汇总。"""

        if symbols:
            # Binance API 要求 JSON 数组格式，且不能有空格
            symbols_json = json.dumps([s.strip().upper() for s in symbols if s.strip()], separators=(',', ':'))
            query = urlencode({"symbols": symbols_json})
            url = f"{self.base_url}/api/v3/ticker/24hr?{query}"
        else:
            url = f"{self.base_url}/api/v3/ticker/24hr"
        return self._safe_public_get(url, [])

    def get_klines(self, symbol: str, interval: str = "4h", limit: int = 200) -> list[list[object]]:
        """读取指定币种的 K 线。"""

        query = urlencode({"symbol": symbol.strip().upper(), "interval": interval, "limit": limit})
        url = f"{self.base_url}/api/v3/klines?{query}"
        return self._safe_public_get(url, [])

    def get_exchange_info(self, symbols: tuple[str, ...] | None = None) -> dict[str, object]:
        """读取指定交易对的交易规则。"""

        query: dict[str, object] = {}
        if symbols:
            # Binance API 要求 JSON 数组格式，且不能有空格
            query["symbols"] = json.dumps([symbol.strip().upper() for symbol in symbols if symbol.strip()], separators=(',', ':'))
        query_string = urlencode(query)
        suffix = f"?{query_string}" if query_string else ""
        url = f"{self.base_url}/api/v3/exchangeInfo{suffix}"
        return self._safe_public_get(url, {"symbols": []})
