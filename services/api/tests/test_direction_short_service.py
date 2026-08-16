"""方向做空调度服务测试。"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import services.api.app.services.direction_short_service as ds_module
from services.api.app.services.direction_short_service import DirectionShortService


class DirectionShortServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self._env_patcher = mock.patch.dict(
            "os.environ",
            {"QUANT_DIRECTION_SHORT_STATE_PATH": str(Path(self._temp_dir.name) / "dir_short.json")},
            clear=False,
        )
        self._env_patcher.start()

    def tearDown(self) -> None:
        self._env_patcher.stop()
        self._temp_dir.cleanup()

    def test_should_open_short_when_bearish_and_no_position(self) -> None:
        """极度看跌且无空仓 → 应开空。"""
        service = DirectionShortService()
        decision = service.decide(avg_score=0.35, has_short_position=False)
        self.assertEqual(decision["action"], "open_short")

    def test_should_not_open_short_when_neutral(self) -> None:
        """中性分数不开空。"""
        service = DirectionShortService()
        decision = service.decide(avg_score=0.42, has_short_position=False)
        self.assertEqual(decision["action"], "hold")

    def test_should_close_short_when_recovered(self) -> None:
        """分数回升且有空仓 → 应平空。"""
        service = DirectionShortService()
        decision = service.decide(avg_score=0.50, has_short_position=True)
        self.assertEqual(decision["action"], "close_short")

    def test_should_hold_when_bearish_with_position(self) -> None:
        """仍看跌且已有空仓 → 继续持有。"""
        service = DirectionShortService()
        decision = service.decide(avg_score=0.36, has_short_position=True)
        self.assertEqual(decision["action"], "hold")

    def test_state_persistence_roundtrip(self) -> None:
        """开空/平空状态持久化。"""
        service = DirectionShortService()
        service.mark_short_open(symbol="BTCUSDT")
        state = service.get_state()
        self.assertTrue(state["has_short_position"])
        self.assertEqual(state["symbol"], "BTCUSDT")

        # 重新加载服务验证状态恢复
        service2 = DirectionShortService()
        state2 = service2.get_state()
        self.assertTrue(state2["has_short_position"])

        service2.mark_short_closed()
        self.assertFalse(service2.get_state()["has_short_position"])

    def test_reconcile_closes_stale_open_state(self) -> None:
        """状态文件说已开空、真实交易已平仓 → 自动修正为已平仓。"""
        service = DirectionShortService()
        service.mark_short_open(symbol="BTCUSDT")

        changed = service.reconcile_with_open_trades(
            [{"trade_id": 1, "is_open": False, "is_short": True, "exit_reason": "stop_loss"}]
        )

        self.assertTrue(changed)
        state = service.get_state()
        self.assertFalse(state["has_short_position"])
        self.assertTrue(state["closed_at"])

    def test_reconcile_opens_when_real_position_exists(self) -> None:
        """状态文件说无空仓、真实持仓已有空仓 → 自动修正为已开空。"""
        service = DirectionShortService()

        changed = service.reconcile_with_open_trades(
            [{"trade_id": 2, "is_open": True, "is_short": True, "pair": "BTC/USDT:USDT"}]
        )

        self.assertTrue(changed)
        state = service.get_state()
        self.assertTrue(state["has_short_position"])
        self.assertEqual(state["symbol"], "BTCUSDT")

    def test_reconcile_noop_when_state_matches(self) -> None:
        """状态与真实持仓一致 → 不做修正。"""
        service = DirectionShortService()
        service.mark_short_open(symbol="BTCUSDT")

        changed = service.reconcile_with_open_trades(
            [{"trade_id": 2, "is_open": True, "is_short": True, "pair": "BTC/USDT:USDT"}]
        )

        self.assertFalse(changed)
        self.assertTrue(service.get_state()["has_short_position"])

    def test_reconcile_ignores_long_trades(self) -> None:
        """只按 is_short 判断，多头持仓不参与方向做空状态对齐。"""
        service = DirectionShortService()

        changed = service.reconcile_with_open_trades(
            [{"trade_id": 3, "is_open": True, "is_short": False, "pair": "BTC/USDT"}]
        )

        self.assertFalse(changed)
        self.assertFalse(service.get_state()["has_short_position"])


if __name__ == "__main__":
    unittest.main()
