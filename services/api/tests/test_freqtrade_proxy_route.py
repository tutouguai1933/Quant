from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.api.app.routes import freqtrade_proxy  # noqa: E402


class _FakeResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return {"profit_all_percent": 0, "trade_count": 0}


class _FakeAsyncClient:
    calls: list[dict[str, object]] = []

    def __init__(self, **kwargs: object) -> None:
        self.calls.append(kwargs)

    async def __aenter__(self) -> "_FakeAsyncClient":
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def get(self, *args: object, **kwargs: object) -> _FakeResponse:
        return _FakeResponse()


class FreqtradeProxyRouteTests(unittest.TestCase):
    def test_freqtrade_proxy_uses_direct_client_ignoring_global_proxy_env(self) -> None:
        _FakeAsyncClient.calls.clear()

        with patch.object(freqtrade_proxy.httpx, "AsyncClient", _FakeAsyncClient):
            result = asyncio.run(freqtrade_proxy.get_freqtrade_profit())

        self.assertIsNone(result["error"])
        self.assertTrue(_FakeAsyncClient.calls)
        self.assertEqual(_FakeAsyncClient.calls[0]["trust_env"], False)


if __name__ == "__main__":
    unittest.main()
