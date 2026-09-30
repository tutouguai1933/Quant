"""验证 K 线仓库在读取完整历史时保持有限缓存，并避免并发重复解析。"""

import json
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from services.api.app.services.kline_store import KlineStore


class KlineStoreMemoryTests(unittest.TestCase):
    """覆盖历史数据完整性与缓存内存边界。"""

    def setUp(self):
        """准备隔离的数据目录和可调整的缓存容量。"""
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)
        self.env = patch.dict("os.environ", {"QUANT_KLINE_CACHE_MAX_ROWS": "4"})
        self.env.start()
        self.addCleanup(self.env.stop)

    def write_rows(self, symbol, count):
        """直接写入历史数据，模拟重启前已经存在的文件。"""
        path = self.root / f"{symbol}_1h.jsonl"
        path.write_text(
            "".join(json.dumps({"open_time": i + 1, "close": "100"}) + "\n"
                    for i in range(count)),
            encoding="utf-8",
        )
        return path

    def test_startup_does_not_cache_all_history(self):
        """重建去重索引时不把每个历史文件加载进读取缓存。"""
        self.write_rows("BTCUSDT", 10)
        self.write_rows("ETHUSDT", 10)
        store = KlineStore(self.root)
        self.assertEqual(store._read_cache, {})
        self.assertEqual(store.upsert("BTCUSDT", "1h", [{"open_time": 1}]), 0)

    def test_large_read_returns_all_rows_without_retaining_them(self):
        """超过缓存容量的完整历史仍返回给调用方，但不长期保存。"""
        self.write_rows("BTCUSDT", 10)
        store = KlineStore(self.root)
        self.assertEqual(len(store.read("BTCUSDT", "1h")), 10)
        self.assertEqual(store._read_cache, {})

    def test_cache_evicts_least_recently_read_history(self):
        """小文件也要共享总容量，避免币种和周期数量放大缓存。"""
        for symbol in ("BTCUSDT", "ETHUSDT", "SOLUSDT"):
            self.write_rows(symbol, 2)
        store = KlineStore(self.root)
        store.read("BTCUSDT", "1h")
        store.read("ETHUSDT", "1h")
        store.read("BTCUSDT", "1h")
        store.read("SOLUSDT", "1h")
        self.assertEqual(set(store._read_cache), {
            self.root / "BTCUSDT_1h.jsonl", self.root / "SOLUSDT_1h.jsonl",
        })

    def test_timestamp_query_does_not_parse_full_history_into_a_list(self):
        """增量同步只查时间戳时不构造完整 K 线列表。"""
        self.write_rows("BTCUSDT", 10)
        store = KlineStore(self.root)
        with patch.object(store, "_parse_bars", side_effect=AssertionError("全量加载")):
            self.assertEqual(store.last_timestamp("BTCUSDT", "1h"), 10)

    def test_concurrent_cache_misses_parse_small_file_once(self):
        """并发请求同一个冷缓存只解析一次，避免瞬时内存倍增。"""
        self.write_rows("BTCUSDT", 2)
        store = KlineStore(self.root)
        store._read_cache.clear()
        original = store._parse_bars
        barrier = threading.Barrier(5)

        def slow_parse(path):
            """放大并发窗口，确保测试确实覆盖冷缓存竞争。"""
            time.sleep(0.02)
            return original(path)

        def read():
            """同时进入读取流程。"""
            barrier.wait(timeout=2)
            return store.read("BTCUSDT", "1h")

        with patch.object(store, "_parse_bars", side_effect=slow_parse) as parser:
            with ThreadPoolExecutor(max_workers=5) as pool:
                results = list(pool.map(lambda _: read(), range(5)))
        self.assertEqual([len(rows) for rows in results], [2] * 5)
        self.assertEqual(parser.call_count, 1)

    def test_appended_history_invalidates_timestamp_and_read_cache(self):
        """磁盘追加后读到新数据，不因缓存限制丢失历史。"""
        path = self.write_rows("BTCUSDT", 2)
        store = KlineStore(self.root)
        self.assertEqual(store.last_timestamp("BTCUSDT", "1h"), 2)
        store.read("BTCUSDT", "1h")
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"open_time": 3}) + "\n")
        self.assertEqual(store.last_timestamp("BTCUSDT", "1h"), 3)
        self.assertEqual(len(store.read("BTCUSDT", "1h")), 3)


    def test_large_history_is_shared_only_while_loading(self):
        """并发读取超容量历史共享本次结果，读取完仍不长期缓存。"""
        self.write_rows("BTCUSDT", 10)
        store = KlineStore(self.root)
        original = store._parse_bars
        barrier = threading.Barrier(5)

        def parse(path):
            """等待其他请求进入，重现大文件慢解析。"""
            time.sleep(0.03)
            return original(path)

        def read():
            """同时读取同一文件。"""
            barrier.wait(timeout=2)
            return store.read("BTCUSDT", "1h")

        with patch.object(store, "_parse_bars", side_effect=parse) as parser:
            with ThreadPoolExecutor(max_workers=5) as pool:
                results = list(pool.map(lambda _: read(), range(5)))
        self.assertEqual(parser.call_count, 1)
        self.assertEqual(len({id(result) for result in results}), 1)
        self.assertEqual(store._read_cache, {})


if __name__ == "__main__":
    unittest.main()
