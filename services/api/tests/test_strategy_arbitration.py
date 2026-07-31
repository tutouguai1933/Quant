"""双策略协同仲裁服务的单元测试。"""

from __future__ import annotations

import os
import tempfile
import unittest
from decimal import Decimal
from unittest import mock

from services.api.app.services.strategy_arbitration_service import (
    ML_ENTRY_TAG,
    StrategyArbitrationService,
)


class _FakeFreqtradeClient:
    """mock freqtrade 客户端：list_open_trades + get_runtime_snapshot。"""

    def __init__(self, open_trades: list[dict[str, object]], max_open_trades: object = 3) -> None:
        self._open_trades = open_trades
        self._max_open_trades = max_open_trades
        self.list_calls = 0

    def list_open_trades(self) -> list[dict[str, object]]:
        self.list_calls += 1
        return list(self._open_trades)

    def get_runtime_snapshot(self) -> dict[str, object]:
        return {"max_open_trades": self._max_open_trades}


def _trade(pair: str, enter_tag: str) -> dict[str, object]:
    return {"pair": pair, "is_open": True, "enter_tag": enter_tag}


class StrategyArbitrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self._log_dir = tempfile.mkdtemp()
        self._env = mock.patch.dict(
            os.environ,
            {
                "QUANT_RUNTIME_MODE": "live",
                "BINANCE_API_KEY": "test-key",
                "BINANCE_API_SECRET": "test-secret",
                "QUANT_ARBITRATION_LOG_PATH": os.path.join(self._log_dir, "arbitration_log.jsonl"),
            },
        )
        self._env.start()
        self.service = StrategyArbitrationService()
        self.service._settings = None

    def tearDown(self) -> None:
        self._env.stop()

    def test_blocked_when_symbol_held_by_enhanced(self) -> None:
        client = _FakeFreqtradeClient([_trade("BTC/USDT", "")])
        decision = self.service.evaluate("BTCUSDT", client)
        self.assertFalse(decision.allowed)
        self.assertTrue(any("already_held" in r and "enhanced" in r for r in decision.reasons))

    def test_blocked_when_symbol_held_by_ml(self) -> None:
        client = _FakeFreqtradeClient([_trade("BTC/USDT", ML_ENTRY_TAG)])
        decision = self.service.evaluate("BTCUSDT", client)
        self.assertFalse(decision.allowed)
        self.assertTrue(any("already_held" in r and "ml" in r for r in decision.reasons))

    def test_blocked_when_max_open_trades_reached(self) -> None:
        client = _FakeFreqtradeClient(
            [
                _trade("ETH/USDT", ""),
                _trade("SOL/USDT", ""),
                _trade("XRP/USDT", ""),
            ],
            max_open_trades=3,
        )
        decision = self.service.evaluate("BTCUSDT", client)
        self.assertFalse(decision.allowed)
        self.assertTrue(any("max_open_trades" in r for r in decision.reasons))

    def test_allowed_when_slot_free_and_symbol_not_held(self) -> None:
        client = _FakeFreqtradeClient([_trade("ETH/USDT", "")], max_open_trades=3)
        decision = self.service.evaluate("BTCUSDT", client)
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.reasons, [])

    def test_allowed_when_arbitration_disabled_skips_client_calls(self) -> None:
        with mock.patch.dict(os.environ, {"QUANT_ARBITRATION_ENABLED": "false"}):
            client = _FakeFreqtradeClient([_trade("BTC/USDT", "")])
            decision = self.service.evaluate("BTCUSDT", client)
        self.assertTrue(decision.allowed)
        self.assertEqual(client.list_calls, 0)

    def test_fail_closed_on_client_error(self) -> None:
        client = _FakeFreqtradeClient([])

        def boom() -> list[dict[str, object]]:
            raise RuntimeError("freqtrade down")

        client.list_open_trades = boom  # type: ignore[method-assign]
        decision = self.service.evaluate("BTCUSDT", client)
        self.assertFalse(decision.allowed)
        self.assertTrue(any("arbitration_unavailable" in r for r in decision.reasons))

    def test_fail_open_on_client_error(self) -> None:
        with mock.patch.dict(os.environ, {"QUANT_ARBITRATION_FAIL_OPEN": "true"}):
            client = _FakeFreqtradeClient([])

            def boom() -> list[dict[str, object]]:
                raise RuntimeError("freqtrade down")

            client.list_open_trades = boom  # type: ignore[method-assign]
            decision = self.service.evaluate("BTCUSDT", client)
        self.assertTrue(decision.allowed)

    def test_log_written_for_blocked_decision(self) -> None:
        client = _FakeFreqtradeClient([_trade("BTC/USDT", "")])
        self.service.evaluate("BTCUSDT", client)
        log_path = os.path.join(self._log_dir, "arbitration_log.jsonl")
        with open(log_path, encoding="utf-8") as f:
            lines = [line for line in f if line.strip()]
        self.assertEqual(len(lines), 1)
        self.assertIn('"allowed": false', lines[0])
        self.assertIn("BTCUSDT", lines[0])


class DispatchArbitrationIntegrationTests(unittest.TestCase):
    """完整派发链上的仲裁集成测试（mock 信号管线 + 真实仲裁逻辑）。"""

    @classmethod
    def setUpClass(cls) -> None:
        import services.api.app.routes.auth as auth_route
        import services.api.app.routes.signals as signals_route
        import services.api.app.routes.strategies as strategies_route
        import services.api.app.services.execution_service as execution_service_module
        import services.api.app.services.risk_guard_service as risk_guard_module
        import services.api.app.services.signal_service as signal_service_module
        import services.api.app.services.strategy_engine_service as strategy_engine_module
        import services.api.app.tasks.scheduler as scheduler_module
        from services.api.app.adapters.freqtrade.client import freqtrade_client
        from services.api.app.routes.auth import login
        from services.api.app.routes.signals import run_signal_pipeline
        from services.api.app.routes.strategies import dispatch_latest_signal, start_strategy

        cls.auth_route = auth_route
        cls.signals_route = signals_route
        cls.strategies_route = strategies_route
        cls.execution_service_module = execution_service_module
        cls.risk_guard_module = risk_guard_module
        cls.signal_service_module = signal_service_module
        cls.strategy_engine_module = strategy_engine_module
        cls.scheduler_module = scheduler_module
        cls.freqtrade_client = freqtrade_client
        cls.login = login
        cls.run_signal_pipeline = run_signal_pipeline
        cls.dispatch_latest_signal = dispatch_latest_signal
        cls.start_strategy = start_strategy

    def setUp(self) -> None:
        self._env = mock.patch.dict(
            os.environ,
            {
                "QUANT_RUNTIME_MODE": "dry-run",
                "QUANT_ARBITRATION_ENABLED": "true",
                "QUANT_ARBITRATION_LOG_PATH": os.path.join(tempfile.mkdtemp(), "arbitration_log.jsonl"),
            },
        )
        self._env.start()
        # 清空风控熔断计数，避免其他测试派发产生的交易计数拦截本用例
        self.risk_guard_module.risk_guard_service.__init__()

    def tearDown(self) -> None:
        self._env.stop()

    def test_dispatch_blocked_when_symbol_held_by_enhanced(self) -> None:
        token = self.auth_route.login(username="admin", password="1933")
        token_value = str(token["data"]["item"]["token"])
        self.signals_route.run_signal_pipeline("mock")
        self.strategies_route.start_strategy(1, token=token_value)

        # 链路走到仲裁前需要策略引擎和风控都通过，这里只 mock 策略引擎
        entry_decision = mock.Mock()
        entry_decision.allowed = True
        entry_decision.reason = ""
        entry_decision.score = 0.7
        entry_decision.suggested_position_ratio = 0.25
        entry_decision.to_dict = lambda: {"allowed": True, "score": "0.70"}

        with mock.patch.object(
            self.strategy_engine_module.strategy_engine_service,
            "calculate_entry_score",
            return_value=entry_decision,
        ), mock.patch.object(
            self.risk_guard_module.risk_guard_service,
            "_detect_market_crash",
            return_value=(False, Decimal("0"), []),
        ), mock.patch.object(
            self.freqtrade_client,
            "list_open_trades",
            return_value=[{"pair": "BTC/USDT", "is_open": True, "enter_tag": ""}],
        ), mock.patch.object(
            self.freqtrade_client,
            "get_runtime_snapshot",
            return_value={"max_open_trades": 3},
        ):
            response = self.strategies_route.dispatch_latest_signal(1, token=token_value)

        self.assertEqual(response["error"]["code"], "arbitration_blocked")
        self.assertIn("already_held", response["error"]["message"])
        # 被拦截后信号 claim 被释放，回到可派发状态
        status = self.signal_service_module.signal_service.get_signal(1)
        self.assertIn(status["status"], {"received", "accepted"})


if __name__ == "__main__":
    unittest.main()
