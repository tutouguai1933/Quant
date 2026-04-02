"""Binance 账户客户端。

这个文件提供最小的签名 HTTP 读取边界，供账户同步服务注入使用。
"""

from __future__ import annotations

import hashlib
import hmac
import json
from decimal import Decimal
from dataclasses import dataclass
from time import time
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from services.api.app.core.settings import Settings


@dataclass(slots=True)
class BinanceResponse:
    """标准化的 Binance 响应包装。"""

    status: int
    body: object


class BinanceAccountClient:
    """最小账户接口，方便测试时注入 fake client 或使用真实读取边界。"""

    def __init__(
        self,
        api_key: str | None = None,
        api_secret: str | None = None,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
        opener=None,
    ) -> None:
        settings = Settings.from_env()
        if api_key is None or api_secret is None:
            api_key = settings.binance_api_key
            api_secret = settings.binance_api_secret
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = (base_url or settings.binance_account_base_url).rstrip("/")
        self._opener = opener or urlopen
        self._timeout_seconds = timeout_seconds or settings.binance_timeout_seconds
        self._recv_window = 5000

    def _has_credentials(self) -> bool:
        """判断当前实例是否具备可签名请求所需的凭据。"""

        return bool(self.api_key and self.api_secret)

    def get_balances(self) -> list[dict[str, object]]:
        """读取账户资产余额。"""

        if not self._has_credentials():
            return []
        response = self._safe_signed_get("/api/v3/account")
        if response is None:
            return []
        balances = response.body.get("balances", []) if isinstance(response.body, dict) else []
        return list(balances)

    def get_orders(self, symbol: str | None = None, limit: int = 100) -> list[dict[str, object]]:
        """读取订单。"""

        if not symbol or not self._has_credentials():
            return []
        response = self._safe_signed_get(
            "/api/v3/allOrders",
            {"symbol": symbol, "limit": min(limit, 1000)},
        )
        if response is None:
            return []
        if not isinstance(response.body, list):
            return []
        return list(response.body)

    def get_trades(self, symbol: str | None = None, limit: int = 100) -> list[dict[str, object]]:
        """读取成交记录。"""

        if not symbol or not self._has_credentials():
            return []
        response = self._safe_signed_get(
            "/api/v3/myTrades",
            {"symbol": symbol, "limit": min(limit, 1000)},
        )
        if response is None:
            return []
        if not isinstance(response.body, list):
            return []
        return list(response.body)

    def get_positions(self) -> list[dict[str, object]]:
        """用余额近似持仓视图。"""

        if not self._has_credentials():
            return []
        response = self._safe_signed_get("/api/v3/account")
        if response is None:
            return []
        balances = response.body.get("balances", []) if isinstance(response.body, dict) else []

        positions: list[dict[str, object]] = []
        for row in balances:
            asset = str(row.get("asset", "")).strip()
            if not asset:
                continue

            free = Decimal(str(row.get("free", "0") or "0"))
            locked = Decimal(str(row.get("locked", "0") or "0"))
            total = free + locked
            if total <= 0:
                continue

            positions.append(
                {
                    "id": f"position-{asset}",
                    "symbol": asset,
                    "side": "long",
                    "quantity": f"{total:.10f}",
                    "unrealizedPnl": "0.0000000000",
                    "entryPrice": "0.0000000000",
                    "markPrice": "0.0000000000",
                    "source": "binance",
                }
            )
        return positions

    def _signed_get(self, path: str, params: dict[str, object] | None = None) -> BinanceResponse:
        query = dict(params or {})
        query["timestamp"] = int(time() * 1000)
        query["recvWindow"] = self._recv_window
        encoded_query = urlencode(query)
        signature = hmac.new(
            self.api_secret.encode("utf-8"),
            encoded_query.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        url = f"{self.base_url}{path}?{encoded_query}&signature={signature}"
        request = Request(url, method="GET")
        request.add_header("X-MBX-APIKEY", self.api_key)
        request.add_header("Accept", "application/json")
        with self._opener(request, timeout=self._timeout_seconds) as response:
            payload = response.read().decode("utf-8") if hasattr(response, "read") else ""
            body = json.loads(payload) if payload else {}
            return BinanceResponse(status=getattr(response, "status", 200), body=body)

    def _safe_signed_get(self, path: str, params: dict[str, object] | None = None) -> BinanceResponse | None:
        """读取签名接口，失败时平稳降级为空结果。"""

        try:
            return self._signed_get(path, params)
        except (HTTPError, URLError, TimeoutError, OSError):
            return None


def create_binance_account_client() -> BinanceAccountClient:
    """按当前环境创建默认账户客户端。"""

    return BinanceAccountClient()


class LazyBinanceAccountClient:
    """按当前环境惰性创建默认账户客户端。"""

    def _client(self) -> BinanceAccountClient:
        return create_binance_account_client()

    @property
    def api_key(self) -> str:
        return self._client().api_key

    @property
    def api_secret(self) -> str:
        return self._client().api_secret

    @property
    def base_url(self) -> str:
        return self._client().base_url

    def get_balances(self) -> list[dict[str, object]]:
        return self._client().get_balances()

    def get_orders(self, symbol: str | None = None, limit: int = 100) -> list[dict[str, object]]:
        return self._client().get_orders(symbol=symbol, limit=limit)

    def get_trades(self, symbol: str | None = None, limit: int = 100) -> list[dict[str, object]]:
        return self._client().get_trades(symbol=symbol, limit=limit)

    def get_positions(self) -> list[dict[str, object]]:
        return self._client().get_positions()


binance_account_client = LazyBinanceAccountClient()
