"""K 线同步服务。

提供回填、增量同步和窗口补齐，配合 KlineStore 实现本地数据仓库。
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from services.api.app.services.kline_store import KlineStore

if TYPE_CHECKING:
    from services.api.app.adapters.binance.market_client import BinanceMarketClient


@dataclass
class SyncReport:
    symbol: str
    interval: str
    fetched: int
    inserted: int
    gaps_filled: int
    duration_s: float


_INTERVAL_MS: dict[str, int] = {
    "1m": 60000,
    "3m": 180000,
    "5m": 300000,
    "15m": 900000,
    "30m": 1800000,
    "1h": 3600000,
    "2h": 7200000,
    "4h": 14400000,
    "6h": 21600000,
    "8h": 28800000,
    "12h": 43200000,
    "1d": 86400000,
    "3d": 259200000,
    "1w": 604800000,
}


def _resolve_interval_ms(interval: str) -> int:
    """把 Binance interval 字符串转成毫秒。"""
    return _INTERVAL_MS.get(interval, 3600000)


def _normalize_kline_rows(rows: list[list[object]]) -> tuple[list[dict], list[str]]:
    """把 Binance K 线数组统一成规范化 bar dict，跳过坏行。"""
    normalized_rows: list[dict] = []
    warnings: list[str] = []
    for index, row in enumerate(rows):
        try:
            if len(row) < 7:
                raise ValueError("kline row has insufficient columns")
            normalized_rows.append(
                {
                    "open_time": int(row[0]),
                    "open": str(row[1]),
                    "high": str(row[2]),
                    "low": str(row[3]),
                    "close": str(row[4]),
                    "volume": str(row[5]),
                    "close_time": int(row[6]),
                }
            )
        except (TypeError, ValueError, IndexError):
            warnings.append(f"invalid_kline_row:{index}")
    return normalized_rows, warnings


def _now_ms() -> int:
    return int(time.time() * 1000)


class KlineSyncService:
    """K 线同步服务，管理回填和增量同步。"""

    def __init__(
        self,
        store: KlineStore,
        market_client: "BinanceMarketClient",
    ) -> None:
        self._store = store
        self._client = market_client

    def backfill(
        self,
        symbols: list[str],
        intervals: list[str],
        days: int = 90,
    ) -> list[SyncReport]:
        """回填指定天数内的历史 K 线。

        用 get_klines(limit=1000) 分页倒序拉取，通过每页首根 bar 的 open_time
        作为下页 end_ts 衔接。
        """

        reports: list[SyncReport] = []
        for symbol in symbols:
            for interval in intervals:
                t0 = time.time()
                start_ts = _now_ms() - days * 86400000
                fetched, inserted = self._backfill_one(symbol, interval, start_ts)
                duration = time.time() - t0
                reports.append(SyncReport(
                    symbol=symbol,
                    interval=interval,
                    fetched=fetched,
                    inserted=inserted,
                    gaps_filled=0,
                    duration_s=round(duration, 3),
                ))
        return reports

    def incremental_sync(
        self,
        symbols: list[str],
        intervals: list[str],
    ) -> list[SyncReport]:
        """从 last_timestamp 起增量拉取新 K 线。"""

        reports: list[SyncReport] = []
        for symbol in symbols:
            for interval in intervals:
                t0 = time.time()
                fetched, inserted = self._incremental_sync_one(symbol, interval)
                duration = time.time() - t0
                reports.append(SyncReport(
                    symbol=symbol,
                    interval=interval,
                    fetched=fetched,
                    inserted=inserted,
                    gaps_filled=0,
                    duration_s=round(duration, 3),
                ))
        return reports

    def ensure_window(self, symbol: str, interval: str, days: int) -> None:
        """补齐指定天数内的缺口。

        检测缺口 → 按缺口头尾 fetch → upsert。
        """

        interval_ms = _resolve_interval_ms(interval)
        end_ts = _now_ms()
        start_ts = end_ts - days * 86400000
        gaps = self._store.gaps(symbol, interval, start_ts, end_ts, interval_ms)
        for gap_start, gap_end in gaps:
            self._backfill_one(symbol, interval, gap_start, end_ts=gap_end)

    # ── 内部方法 ──────────────────────────────────────────────────────────

    def _backfill_one(
        self,
        symbol: str,
        interval: str,
        start_ts: int,
        end_ts: int | None = None,
    ) -> tuple[int, int]:
        """回填单个 symbol 的单个周期。返回 (fetched, inserted)。"""

        total_fetched = 0
        total_inserted = 0
        cursor_end = end_ts if end_ts is not None else _now_ms()

        while cursor_end > start_ts:
            raw = self._client.get_klines(
                symbol=symbol,
                interval=interval,
                limit=1000,
                end_ts=cursor_end,
            )
            if not raw:
                break

            bars, _ = _normalize_kline_rows(raw)
            total_fetched += len(bars)
            total_inserted += self._store.upsert(symbol, interval, bars)

            # 用本页最早 bar 的 open_time 作为下页 end_ts
            earliest = bars[0].get("open_time") if bars else None
            if earliest is None:
                break
            try:
                earliest_ts = int(earliest)
            except (TypeError, ValueError):
                break
            if earliest_ts <= start_ts or earliest_ts >= cursor_end:
                break
            cursor_end = earliest_ts

        return total_fetched, total_inserted

    def _incremental_sync_one(
        self,
        symbol: str,
        interval: str,
    ) -> tuple[int, int]:
        """增量同步单个 symbol 的单个周期。"""

        last_ts = self._store.last_timestamp(symbol, interval)
        if last_ts is None:
            # 没有历史数据，跳过增量同步（应先 backfill）
            return 0, 0

        interval_ms = _resolve_interval_ms(interval)
        start_ts = last_ts + interval_ms

        raw = self._client.get_klines(
            symbol=symbol,
            interval=interval,
            limit=1000,
            start_ts=start_ts,
        )
        if not raw:
            return 0, 0

        bars, _ = _normalize_kline_rows(raw)
        inserted = self._store.upsert(symbol, interval, bars)
        return len(bars), inserted
