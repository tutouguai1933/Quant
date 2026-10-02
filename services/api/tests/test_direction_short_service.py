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
        decision = service.decide(avg_score=0.35, has_short_position=False, opening_allowed=True)
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
            [{"trade_id": 2, "is_open": True, "is_short": True, "pair": "BTC/USDT:USDT", "enter_tag": "quant-direction-short:fixture"}]
        )

        self.assertTrue(changed)
        state = service.get_state()
        self.assertTrue(state["has_short_position"])
        self.assertEqual(state["symbol"], "BTC/USDT:USDT")
        self.assertEqual(state["trade_id"], 2)
        self.assertEqual(DirectionShortService().get_state()["trade_id"], 2)

    def test_reconcile_noop_when_state_matches(self) -> None:
        """状态与真实持仓一致 → 不做修正。"""
        service = DirectionShortService()
        service.mark_short_open(symbol="BTC/USDT:USDT", trade_id=2)

        changed = service.reconcile_with_open_trades(
            [{"trade_id": 2, "is_open": True, "is_short": True, "pair": "BTC/USDT:USDT", "enter_tag": "quant-direction-short:fixture"}]
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

    def test_default_unadmitted_bearish_signal_holds(self) -> None:
        """未经执行层准入的看跌信号不开户。"""
        service = DirectionShortService()
        self.assertEqual(service.decide(avg_score=.35)["action"], "hold")

    def test_foreign_short_position_is_not_claimed(self) -> None:
        """异币、无归属标记的BTC空仓和自然多仓都不能被认领。"""
        service = DirectionShortService()
        rows = [
            {"trade_id": 1, "is_open": True, "is_short": True, "pair": "XRP/USDT:USDT", "enter_tag": "quant-direction-short:x"},
            {"trade_id": 2, "is_open": True, "is_short": True, "pair": "BTC/USDT:USDT", "enter_tag": "force_entry"},
            {"trade_id": 3, "is_open": True, "is_short": False, "pair": "BTC/USDT:USDT", "enter_tag": "quant-direction-short:x"},
        ]
        self.assertFalse(service.reconcile_with_open_trades(rows))
        self.assertFalse(service.get_state()["has_short_position"])
        self.assertEqual(service.owned_short_trades(rows), [])

    def test_owned_position_normalizes_symbol_and_boolean(self) -> None:
        """明确归属BTC空仓可认领，字符串false不当真。"""
        service = DirectionShortService()
        rows = [
            {"trade_id": 4, "is_open": "true", "is_short": "true", "pair": "BTCUSDT", "enter_tag": "quant-direction-short:model-a"},
            {"trade_id": 5, "is_open": "false", "is_short": True, "pair": "BTC/USDT:USDT", "enter_tag": "quant-direction-short:model-a"},
        ]
        self.assertEqual(service.owned_short_trades(rows), [rows[0]])
        self.assertTrue(service.reconcile_with_open_trades(rows))
        self.assertEqual(service.get_state()["symbol"], "BTC/USDT:USDT")
        self.assertEqual(service.get_state()["trade_id"], 4)

    def test_reconcile_replaces_persisted_id_when_owned_trade_changes(self) -> None:
        """已记录空仓被新归属空仓替换时更新真实交易编号。"""
        service = DirectionShortService()
        first = {"trade_id": 10, "is_open": True, "is_short": True, "pair": "BTC/USDT:USDT", "enter_tag": "quant-direction-short:a"}
        service.reconcile_with_open_trades([first])
        second = dict(first, trade_id=11)
        self.assertTrue(service.reconcile_with_open_trades([second]))
        self.assertEqual(DirectionShortService().get_state()["trade_id"], 11)

    def test_belongs_includes_owned_closed_short_history(self) -> None:
        """方向策略已平空仓仍属于本策略历史，但不能算在场仓位。"""
        row = {"is_open": False, "is_short": True, "pair": "BTC/USDT:USDT", "enter_tag": "quant-direction-short:model-x"}
        self.assertTrue(DirectionShortService.belongs_to_strategy(row))
        self.assertEqual(DirectionShortService.owned_short_trades([row]), [])

    def test_belongs_rejects_other_strategy_or_symbol_history(self) -> None:
        """没有明确归属或币种不符的历史不归入方向策略。"""
        rows = [
            {"is_short": True, "pair": "BTC/USDT:USDT", "enter_tag": "force_entry"},
            {"is_short": True, "pair": "XRP/USDT:USDT", "enter_tag": "quant-direction-short:x"},
            {"is_short": False, "pair": "BTC/USDT:USDT", "enter_tag": "quant-direction-short:x"},
        ]
        for row in rows:
            self.assertFalse(DirectionShortService.belongs_to_strategy(row))

    def test_belongs_ignores_open_status_and_normalizes_alias(self) -> None:
        """历史归属只由符号、空仓方向及标签判断，不依赖在场字段。"""
        row = {"is_short": "true", "pair": " btcusdt ", "enter_tag": "quant-direction-short:x"}
        self.assertTrue(DirectionShortService.belongs_to_strategy(row))
        self.assertEqual(DirectionShortService.owned_short_trades([row]), [])



if __name__ == "__main__":
    unittest.main()
