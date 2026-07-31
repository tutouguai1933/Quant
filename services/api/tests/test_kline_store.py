"""KlineStore 单元测试。"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest import TestCase

from services.api.app.services.kline_store import KlineStore

_BTC_4H_BAR1 = {
    "open_time": 1700000000000,
    "open": "42000.00",
    "high": "42100.00",
    "low": "41900.00",
    "close": "42050.00",
    "volume": "123.45",
    "close_time": 1700014400000,
}

_BTC_4H_BAR2 = {
    "open_time": 1700014400000,
    "open": "42050.00",
    "high": "42200.00",
    "low": "42000.00",
    "close": "42180.00",
    "volume": "150.00",
    "close_time": 1700028800000,
}

_BTC_4H_BAR3 = {
    "open_time": 1700028800000,
    "open": "42180.00",
    "high": "42300.00",
    "low": "42150.00",
    "close": "42250.00",
    "volume": "200.00",
    "close_time": 1700043200000,
}


class KlineStoreTests(TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.store = KlineStore(root=Path(self._tmpdir.name))

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    # ── upsert ───────────────────────────────────────────────────────────

    def test_upsert_inserts_new_bars(self) -> None:
        """首次 upsert 返回新增条数，数据持久化。"""
        count = self.store.upsert("BTCUSDT", "4h", [_BTC_4H_BAR1, _BTC_4H_BAR2])
        self.assertEqual(count, 2)
        bars = self.store.read("BTCUSDT", "4h")
        self.assertEqual(len(bars), 2)

    def test_upsert_idempotent(self) -> None:
        """重复 upsert 相同数据不增加行数。"""
        self.store.upsert("BTCUSDT", "4h", [_BTC_4H_BAR1, _BTC_4H_BAR2])
        count = self.store.upsert("BTCUSDT", "4h", [_BTC_4H_BAR1, _BTC_4H_BAR2])
        self.assertEqual(count, 0)
        bars = self.store.read("BTCUSDT", "4h")
        self.assertEqual(len(bars), 2)

    def test_upsert_mixed_new_and_old(self) -> None:
        """混合新旧数据时只插入新 bar。"""
        self.store.upsert("BTCUSDT", "4h", [_BTC_4H_BAR1])
        count = self.store.upsert(
            "BTCUSDT", "4h", [_BTC_4H_BAR1, _BTC_4H_BAR2, _BTC_4H_BAR3]
        )
        self.assertEqual(count, 2)
        bars = self.store.read("BTCUSDT", "4h")
        self.assertEqual(len(bars), 3)

    def test_upsert_empty(self) -> None:
        """空列表返回 0。"""
        count = self.store.upsert("BTCUSDT", "4h", [])
        self.assertEqual(count, 0)

    def test_upsert_skips_rows_without_open_time(self) -> None:
        """缺少 open_time 的行被跳过。"""
        count = self.store.upsert("BTCUSDT", "4h", [{"close": "100"}])
        self.assertEqual(count, 0)

    # ── read ─────────────────────────────────────────────────────────────

    def test_read_sorted_ascending(self) -> None:
        """乱序 upsert 后 read 返回升序。"""
        self.store.upsert("BTCUSDT", "4h", [_BTC_4H_BAR3, _BTC_4H_BAR1, _BTC_4H_BAR2])
        bars = self.store.read("BTCUSDT", "4h")
        self.assertEqual(len(bars), 3)
        self.assertEqual(bars[0]["open_time"], 1700000000000)
        self.assertEqual(bars[1]["open_time"], 1700014400000)
        self.assertEqual(bars[2]["open_time"], 1700028800000)

    def test_read_with_start_ts(self) -> None:
        """start_ts 过滤有效。"""
        self.store.upsert("BTCUSDT", "4h", [_BTC_4H_BAR1, _BTC_4H_BAR2, _BTC_4H_BAR3])
        bars = self.store.read("BTCUSDT", "4h", start_ts=1700014400000)
        self.assertEqual(len(bars), 2)
        self.assertEqual(bars[0]["open_time"], 1700014400000)
        self.assertEqual(bars[1]["open_time"], 1700028800000)

    def test_read_with_end_ts(self) -> None:
        """end_ts 过滤有效。"""
        self.store.upsert("BTCUSDT", "4h", [_BTC_4H_BAR1, _BTC_4H_BAR2, _BTC_4H_BAR3])
        bars = self.store.read("BTCUSDT", "4h", end_ts=1700014400000)
        self.assertEqual(len(bars), 2)
        self.assertEqual(bars[0]["open_time"], 1700000000000)
        self.assertEqual(bars[1]["open_time"], 1700014400000)

    def test_read_with_both_ts(self) -> None:
        """同时指定 start_ts 和 end_ts。"""
        self.store.upsert("BTCUSDT", "4h", [_BTC_4H_BAR1, _BTC_4H_BAR2, _BTC_4H_BAR3])
        bars = self.store.read(
            "BTCUSDT", "4h",
            start_ts=1700014400000,
            end_ts=1700014400000,
        )
        self.assertEqual(len(bars), 1)
        self.assertEqual(bars[0]["open_time"], 1700014400000)

    def test_read_empty_for_unknown_symbol(self) -> None:
        """未知符号返回空列表。"""
        bars = self.store.read("UNKNOWN", "4h")
        self.assertEqual(bars, [])

    # ── last_timestamp ───────────────────────────────────────────────────

    def test_last_timestamp_empty(self) -> None:
        """无数据时返回 None。"""
        self.assertIsNone(self.store.last_timestamp("BTCUSDT", "4h"))

    def test_last_timestamp_returns_latest(self) -> None:
        """返回最新 bar 的 open_time。"""
        self.store.upsert("BTCUSDT", "4h", [_BTC_4H_BAR1, _BTC_4H_BAR3, _BTC_4H_BAR2])
        self.assertEqual(
            self.store.last_timestamp("BTCUSDT", "4h"),
            1700028800000,
        )

    # ── gaps ─────────────────────────────────────────────────────────────

    def test_gaps_no_gaps(self) -> None:
        """连续数据无缺口。"""
        self.store.upsert("BTCUSDT", "4h", [_BTC_4H_BAR1, _BTC_4H_BAR2, _BTC_4H_BAR3])
        gaps = self.store.gaps(
            "BTCUSDT", "4h",
            start_ts=1700000000000,
            end_ts=1700043200000,
            interval_ms=14400000,  # 4h
        )
        self.assertEqual(gaps, [])

    def test_gaps_middle_missing(self) -> None:
        """中间缺少一根 bar。"""
        self.store.upsert("BTCUSDT", "4h", [_BTC_4H_BAR1, _BTC_4H_BAR3])
        gaps = self.store.gaps(
            "BTCUSDT", "4h",
            start_ts=1700000000000,
            end_ts=1700043200000,
            interval_ms=14400000,
        )
        self.assertEqual(len(gaps), 1)
        self.assertEqual(gaps[0], (1700014400000, 1700028800000))

    def test_gaps_start_missing(self) -> None:
        """起始段缺失。"""
        self.store.upsert("BTCUSDT", "4h", [_BTC_4H_BAR2, _BTC_4H_BAR3])
        gaps = self.store.gaps(
            "BTCUSDT", "4h",
            start_ts=1700000000000,
            end_ts=1700043200000,
            interval_ms=14400000,
        )
        self.assertEqual(len(gaps), 1)
        self.assertEqual(gaps[0][0], 1700000000000)
        self.assertEqual(gaps[0][1], 1700014400000)

    def test_gaps_end_missing(self) -> None:
        """末尾段缺失。"""
        self.store.upsert("BTCUSDT", "4h", [_BTC_4H_BAR1, _BTC_4H_BAR2])
        gaps = self.store.gaps(
            "BTCUSDT", "4h",
            start_ts=1700000000000,
            end_ts=1700043200000,
            interval_ms=14400000,
        )
        self.assertEqual(len(gaps), 1)
        self.assertEqual(gaps[0][0], 1700028800000)
        self.assertEqual(gaps[0][1], 1700043200000)

    def test_gaps_empty_file(self) -> None:
        """文件为空时整个区间都是缺口。"""
        gaps = self.store.gaps(
            "BTCUSDT", "4h",
            start_ts=1700000000000,
            end_ts=1700043200000,
            interval_ms=14400000,
        )
        self.assertEqual(gaps, [(1700000000000, 1700043200000)])

    def test_gaps_invalid_params(self) -> None:
        """无效参数返回空列表。"""
        gaps = self.store.gaps(
            "BTCUSDT", "4h",
            start_ts=1700043200000,
            end_ts=1700000000000,
            interval_ms=14400000,
        )
        self.assertEqual(gaps, [])

    # ── 多符号隔离 ─────────────────────────────────────────────────────

    def test_different_symbols_isolated(self) -> None:
        """不同符号的数据互不干扰。"""
        self.store.upsert("BTCUSDT", "4h", [_BTC_4H_BAR1])
        self.store.upsert("ETHUSDT", "4h", [_BTC_4H_BAR2])
        self.assertEqual(len(self.store.read("BTCUSDT", "4h")), 1)
        self.assertEqual(len(self.store.read("ETHUSDT", "4h")), 1)

    # ── 重新加载后索引一致 ──────────────────────────────────────────────

    def test_reload_preserves_data(self) -> None:
        """新建 store 实例可以读到持久化的数据。"""
        self.store.upsert("BTCUSDT", "4h", [_BTC_4H_BAR1, _BTC_4H_BAR2])
        store2 = KlineStore(root=Path(self._tmpdir.name))
        bars = store2.read("BTCUSDT", "4h")
        self.assertEqual(len(bars), 2)

    def test_reload_preserves_dedup(self) -> None:
        """新建 store 实例不会重复插入已有数据。"""
        self.store.upsert("BTCUSDT", "4h", [_BTC_4H_BAR1, _BTC_4H_BAR2])
        store2 = KlineStore(root=Path(self._tmpdir.name))
        count = store2.upsert("BTCUSDT", "4h", [_BTC_4H_BAR1, _BTC_4H_BAR3])
        self.assertEqual(count, 1)
