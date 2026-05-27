"""认证异常处理的 API 回归测试。"""

from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from services.api.app.main import app


class AuthExceptionHandlingTests(unittest.TestCase):
    """认证异常处理回归测试。"""

    def test_unauthenticated_protected_route_returns_401_without_asgi_exception(self) -> None:
        """未认证访问受保护接口时返回标准 401，而不是冒泡成 ASGI 异常。"""
        client = TestClient(app)

        response = client.post("/api/v1/ml/hyperopt/start")

        self.assertEqual(response.status_code, 401)
        payload = response.json()
        self.assertEqual(payload["error"]["code"], "unauthorized")


if __name__ == "__main__":
    unittest.main()
