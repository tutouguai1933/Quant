"""方向做空状态接口测试。

覆盖：正常组合状态、模拟盘不可达降级、无推理信号、状态文件与真实持仓不一致。
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import services.api.app.routes.signals as signals_route  # noqa: E402
from services.api.app.routes.signals import get_direction_short_status  # noqa: E402


class _FakeStateService:
    """测试用状态服务：返回固定状态。"""

    def __init__(self, state: dict) -> None:
        self._state = state

    def get_state(self) -> dict:
        return dict(self._state)


class _FakeSimClient:
    """测试用模拟盘客户端：返回固定交易列表。"""

    def __init__(self, trades: list[dict]) -> None:
        self._trades = trades

    def list_trades(self, limit: int | None = None) -> list[dict]:
        return list(self._trades[:limit])


def _signal_result(avg_score: float) -> dict:
    """构造一份只含两个信号的最近推理结果，平均分可控。"""
    return {
        "latest_inference": {
            "model_version": "test-model",
            "generated_at": "2026-08-17T00:00:00+00:00",
            "signals": [{"score": avg_score - 0.01}, {"score": avg_score + 0.01}],
        }
    }


class DirectionShortStatusRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self._research_patcher = mock.patch.object(
            signals_route.research_service,
            "get_latest_result",
            return_value=_signal_result(0.37),
        )
        self._research_patcher.start()

    def tearDown(self) -> None:
        self._research_patcher.stop()

    def _patch_route(self, state: dict, client) -> None:
        """临时替换路由模块依赖的调度状态服务与模拟盘客户端构建函数。"""
        state_patcher = mock.patch.object(signals_route, "direction_short_service", _FakeStateService(state))
        client_patcher = mock.patch.object(signals_route, "build_sim_client", return_value=client)
        state_patcher.start()
        client_patcher.start()
        self.addCleanup(client_patcher.stop)
        self.addCleanup(state_patcher.stop)

    def test_returns_open_position_profit_and_market_score(self) -> None:
        """有空仓持仓：返回模型分数、开空时间与浮盈，且无状态不一致。"""
        self._patch_route(
            state={"has_short_position": True, "symbol": "BTCUSDT", "opened_at": "2026-08-12T19:29:16+00:00"},
            client=_FakeSimClient(
                [
                    {
                        "trade_id": 2,
                        "pair": "BTC/USDT:USDT",
                        "is_open": True,
                        "is_short": True,
                        "amount": 0.001,
                        "stake_amount": 20.0,
                        "open_rate": 63000.0,
                        "current_rate": 62500.0,
                        "profit_abs": 0.79,
                        "profit_pct": 0.79,
                        "open_date": "2026-08-16 01:00:00",
                        "enter_tag": "quant-control-plane",
                    }
                ]
            ),
        )

        response = get_direction_short_status()

        self.assertIsNone(response["error"])
        data = response["data"]
        self.assertAlmostEqual(data["market"]["avg_score"], 0.37)
        self.assertTrue(data["market"]["short_trigger"])
        self.assertTrue(data["state"]["has_short_position"])
        self.assertTrue(data["simulation"]["connected"])
        self.assertEqual(data["simulation"]["open_position"]["trade_id"], 2)
        self.assertFalse(data["position_state_mismatch"])

    def test_marks_mismatch_when_state_says_open_but_no_position(self) -> None:
        """状态文件说已开空、模拟盘实际无空仓：应标记不一致并给出最近平仓记录。"""
        self._patch_route(
            state={"has_short_position": True, "symbol": "BTCUSDT", "opened_at": "2026-08-12T19:29:16+00:00"},
            client=_FakeSimClient(
                [
                    {
                        "trade_id": 1,
                        "pair": "BTC/USDT:USDT",
                        "is_open": False,
                        "is_short": True,
                        "realized_profit": -0.53,
                        "open_date": "2026-08-12 19:26:17",
                        "close_date": "2026-08-13 05:07:29",
                        "exit_reason": "stop_loss",
                    }
                ]
            ),
        )

        response = get_direction_short_status()
        data = response["data"]

        self.assertIsNone(data["simulation"]["open_position"])
        self.assertEqual(data["simulation"]["last_closed_trade"]["trade_id"], 1)
        self.assertTrue(data["position_state_mismatch"])

    def test_waits_for_signal_when_no_position_and_state_flat(self) -> None:
        """状态文件与模拟盘都无空仓：正常等待状态。"""
        self._patch_route(
            state={"has_short_position": False, "symbol": "", "opened_at": ""},
            client=_FakeSimClient([]),
        )

        data = get_direction_short_status()["data"]

        self.assertFalse(data["state"]["has_short_position"])
        self.assertIsNone(data["simulation"]["open_position"])
        self.assertFalse(data["position_state_mismatch"])

    def test_simulation_failure_keeps_state_and_reports_error(self) -> None:
        """模拟盘不可达：接口不崩溃，返回状态文件数据并标记连接失败。"""

        class _BrokenClient:
            def list_trades(self, limit: int | None = None):
                raise RuntimeError("connection refused")

        state_patcher = mock.patch.object(
            signals_route,
            "direction_short_service",
            _FakeStateService({"has_short_position": True, "symbol": "BTCUSDT", "opened_at": "2026-08-12T19:29:16+00:00"}),
        )
        client_patcher = mock.patch.object(signals_route, "build_sim_client", return_value=_BrokenClient())

        with state_patcher, client_patcher:
            data = get_direction_short_status()["data"]

        self.assertFalse(data["simulation"]["connected"])
        self.assertIn("connection refused", data["simulation"]["message"])
        self.assertTrue(data["state"]["has_short_position"])
        # 模拟盘不可达时不能断言“状态不一致”（真实持仓未知）
        self.assertFalse(data["position_state_mismatch"])


if __name__ == "__main__":
    unittest.main()
