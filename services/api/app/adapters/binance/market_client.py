"""Binance 市场数据客户端。"""

from __future__ import annotations

import json
from urllib.parse import urlencode
from urllib.request import urlopen


class BinanceMarketClient:
    """最小 Binance 公共市场数据客户端。"""

    def __init__(self, base_url: str = "https://api.binance.com") -> None:
        self.base_url = base_url.rstrip("/")

    def get_tickers(self) -> list[dict[str, object]]:
        """读取 24 小时行情汇总。"""

        url = f"{self.base_url}/api/v3/ticker/24hr"
        with urlopen(url) as response:
            return json.load(response)

    def get_klines(self, symbol: str, interval: str = "4h", limit: int = 200) -> list[list[object]]:
        """读取指定币种的 K 线。"""

        query = urlencode({"symbol": symbol.strip().upper(), "interval": interval, "limit": limit})
        url = f"{self.base_url}/api/v3/klines?{query}"
        with urlopen(url) as response:
            return json.load(response)
