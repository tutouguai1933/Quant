"""本地 K 线数据仓库。

默认根目录 .runtime/kline_store，文件布局 {SYMBOL}_{INTERVAL}.jsonl。
每行一个规范化 bar dict。按 open_time 去重合并，写操作加 fcntl.flock。
"""

from __future__ import annotations

import fcntl
import json
import os
import threading
from pathlib import Path


class KlineStore:
    """基于 JSONL 的本地 K 线存储。

    读操作无锁；写操作通过 fcntl.flock 保证同一进程内多线程安全。
    """

    # 全局实例缓存：按 root 路径复用，避免重复构造时全量重建索引
    # （重建需解析全部 jsonl，16 币×4 周期可达数百 MB，曾拖慢整个进程）
    _instance_cache: dict[str, "KlineStore"] = {}
    _instance_cache_lock = threading.Lock()

    @classmethod
    def get_cached(cls, root: str) -> "KlineStore":
        """获取（或创建）按 root 路径共享的 KlineStore 实例。"""
        with cls._instance_cache_lock:
            store = cls._instance_cache.get(root)
            if store is None:
                store = cls(root=root)
                cls._instance_cache[root] = store
            return store

    def __init__(self, root: Path | str | None = None) -> None:
        if root is None:
            root = Path(".runtime/kline_store")
        if isinstance(root, str):
            root = Path(root)
        self._root = root
        self._root.mkdir(parents=True, exist_ok=True)
        # 内存索引：{(symbol, interval): set[open_time]}
        self._index: dict[tuple[str, str], set[int]] = {}
        self._index_lock = threading.Lock()
        # 读缓存：{filepath: (mtime, bars)}，mtime 未变化时直接返回缓存，
        # 避免 read/last_timestamp/gaps 每次全量扫描解析整个 JSONL（图表热路径）
        self._read_cache: dict[Path, tuple[float, list[dict]]] = {}
        self._read_cache_lock = threading.Lock()
        self._rebuild_index()

    # ── 公共接口 ──────────────────────────────────────────────────────────

    def upsert(self, symbol: str, interval: str, rows: list[dict]) -> int:
        """按 open_time 去重合并，返回新增条数。

        如果有新行，追加写到文件尾部。写操作加文件锁。
        """

        if not rows:
            return 0

        key = (symbol, interval)
        filepath = self._filepath(symbol, interval)
        new_rows: list[dict] = []

        with self._index_lock:
            known = self._index.get(key, set())
            for row in rows:
                open_time = self._bar_open_time(row)
                if open_time is None or open_time in known:
                    continue
                known.add(open_time)
                new_rows.append(row)
            if new_rows:
                self._index[key] = known
                self._append_bars(filepath, new_rows)

        return len(new_rows)

    def read(
        self,
        symbol: str,
        interval: str,
        start_ts: int | None = None,
        end_ts: int | None = None,
    ) -> list[dict]:
        """升序返回规范化 bar。

        可指定 start_ts/end_ts（毫秒 Unix 时间戳，含边界）过滤范围。
        """

        filepath = self._filepath(symbol, interval)
        bars = self._load_bars(filepath)
        if start_ts is not None:
            bars = [b for b in bars if self._bar_open_time(b) is not None and self._bar_open_time(b) >= start_ts]  # type: ignore[operator]
        if end_ts is not None:
            bars = [b for b in bars if self._bar_open_time(b) is not None and self._bar_open_time(b) <= end_ts]  # type: ignore[operator]
        return bars

    def last_timestamp(self, symbol: str, interval: str) -> int | None:
        """返回该符号和周期最新一根 bar 的 open_time，无数据返回 None。"""

        filepath = self._filepath(symbol, interval)
        bars = self._load_bars(filepath)
        if not bars:
            return None

        try:
            return int(bars[-1].get("open_time", 0))
        except (TypeError, ValueError):
            return None

    def gaps(
        self,
        symbol: str,
        interval: str,
        start_ts: int,
        end_ts: int,
        interval_ms: int,
    ) -> list[tuple[int, int]]:
        """检测指定时间区间内的 K 线缺口。

        返回缺口区间列表 [(gap_start, gap_end), ...]，区间包含边界。
        """

        if interval_ms <= 0 or start_ts >= end_ts:
            return []

        filepath = self._filepath(symbol, interval)
        bars = self._load_bars(filepath)
        bars = [b for b in bars if self._bar_open_time(b) is not None and start_ts <= self._bar_open_time(b) <= end_ts]  # type: ignore[operator]
        if not bars:
            return [(start_ts, end_ts)]

        gaps_list: list[tuple[int, int]] = []

        # 检查起始缺口
        first_ot = self._bar_open_time(bars[0])
        if first_ot is not None and first_ot > start_ts:
            gaps_list.append((start_ts, first_ot))

        # 检查中间缺口
        for i in range(len(bars) - 1):
            cur_ot = self._bar_open_time(bars[i])
            next_ot = self._bar_open_time(bars[i + 1])
            if cur_ot is None or next_ot is None:
                continue
            expected = cur_ot + interval_ms
            if next_ot > expected:
                gaps_list.append((expected, next_ot))

        # 检查末尾缺口
        last_ot = self._bar_open_time(bars[-1])
        if last_ot is not None and last_ot + interval_ms < end_ts:
            gaps_list.append((last_ot + interval_ms, end_ts))

        return gaps_list

    # ── 内部方法 ──────────────────────────────────────────────────────────

    def _filepath(self, symbol: str, interval: str) -> Path:
        return self._root / f"{symbol}_{interval}.jsonl"

    @staticmethod
    def _bar_open_time(row: dict) -> int | None:
        try:
            val = row.get("open_time")
            if val is None:
                return None
            ot = int(val)
            if ot <= 0:
                return None
            return ot
        except (TypeError, ValueError):
            return None

    def _rebuild_index(self) -> None:
        """从磁盘文件重建内存索引。"""

        with self._index_lock:
            self._index.clear()
            for filepath in sorted(self._root.glob("*.jsonl")):
                key = self._parse_key_from_filename(filepath)
                if key is None:
                    continue
                bars = self._load_bars(filepath)
                open_times = {
                    ot for b in bars
                    if (ot := self._bar_open_time(b)) is not None
                }
                if open_times:
                    self._index[key] = open_times

    @staticmethod
    def _parse_key_from_filename(filepath: Path) -> tuple[str, str] | None:
        stem = filepath.stem  # e.g. "BTCUSDT_4h"
        parts = stem.rsplit("_", 1)
        if len(parts) != 2:
            return None
        symbol, interval = parts
        if not symbol or not interval:
            return None
        return (symbol, interval)

    def _load_bars(self, filepath: Path) -> list[dict]:
        """从 JSONL 文件加载所有 bar 记录，按 open_time 升序。

        按文件 mtime 做内存缓存：mtime 没变直接返回解析结果，
        文件变化（upsert 追加）时重新解析。返回列表只读使用，调用方不得原地修改。
        """

        if not filepath.exists():
            # 文件不存在时清掉对应缓存，避免误用旧内容
            with self._read_cache_lock:
                self._read_cache.pop(filepath, None)
            return []

        try:
            mtime = filepath.stat().st_mtime
        except OSError:
            return []

        # 命中缓存直接返回
        with self._read_cache_lock:
            cached = self._read_cache.get(filepath)
            if cached is not None and cached[0] == mtime:
                return cached[1]

        bars = self._parse_bars(filepath)

        with self._read_cache_lock:
            self._read_cache[filepath] = (mtime, bars)
        return bars

    def _parse_bars(self, filepath: Path) -> list[dict]:
        """解析 JSONL 文件内容，按 open_time 升序返回。"""

        bars: list[dict] = []
        try:
            with open(filepath, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        bar = json.loads(line)
                        if isinstance(bar, dict) and "open_time" in bar:
                            bars.append(bar)
                    except json.JSONDecodeError:
                        continue
        except OSError:
            return []

        bars.sort(key=lambda b: self._bar_open_time(b) or 0)
        return bars

    def _append_bars(self, filepath: Path, bars: list[dict]) -> None:
        """将 bars 追加写入文件，加 fcntl.flock 排他锁。"""

        if not bars:
            return

        bars.sort(key=lambda b: self._bar_open_time(b) or 0)

        try:
            with open(filepath, "a", encoding="utf-8") as fh:
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
                try:
                    for bar in bars:
                        fh.write(json.dumps(bar, ensure_ascii=False, sort_keys=True) + "\n")
                    fh.flush()
                    os.fsync(fh.fileno())
                finally:
                    fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
