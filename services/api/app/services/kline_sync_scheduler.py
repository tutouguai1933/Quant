"""K 线定时同步服务。

后台线程定期增量同步本地 K 线仓库（16 币 × 多周期），避免页面请求时
现场拉币安补缺口（曾导致 rsi-summary 每次请求耗时 ~70 秒、线程堆积卡死）。
"""

from __future__ import annotations

import logging
import os
import threading
import time

logger = logging.getLogger(__name__)


class KlineSyncScheduler:
    """周期增量同步本地 K 线仓库。"""

    def __init__(self) -> None:
        self._thread: threading.Thread | None = None
        self._running = False

    def start(self, interval_minutes: int = 15) -> bool:
        """启动后台同步线程（daemon，不阻塞退出）。"""

        if self._running:
            logger.warning("K 线同步已在运行中")
            return False
        self._running = True
        self._thread = threading.Thread(
            target=self._sync_loop,
            args=(max(1, interval_minutes),),
            name="kline-sync-scheduler",
            daemon=True,
        )
        self._thread.start()
        logger.info("K 线定时同步已启动: interval=%d 分钟", interval_minutes)
        return True

    def stop(self) -> None:
        """停止同步线程。"""

        self._running = False

    def _sync_loop(self, interval_minutes: int) -> None:
        """同步主循环。"""

        while self._running:
            try:
                self._sync_once()
            except Exception as exc:
                logger.warning("K 线定时同步失败: %s", exc)
            # 睡眠按小步拆分，便于及时响应 stop
            slept = 0.0
            step = 5.0
            target = interval_minutes * 60
            while self._running and slept < target:
                time.sleep(step)
                slept += step

    def _sync_once(self) -> None:
        """执行一轮增量同步（16 币 × 已选周期）。"""

        from services.api.app.adapters.binance.market_client import BinanceMarketClient
        from services.api.app.core.settings import Settings
        from services.api.app.services.kline_store import KlineStore
        from services.api.app.services.kline_sync_service import KlineSyncService

        settings = Settings.from_env()
        if not settings.kline_store_enabled:
            return

        store = KlineStore(root=settings.kline_store_root)
        sync_service = KlineSyncService(store=store, market_client=BinanceMarketClient())
        symbols = list(settings.market_symbols)
        # 默认同步 1h/4h/15m/1d 四个常用周期（与本地仓库文件一致）
        timeframes = [f for f in ("15m", "1h", "4h", "1d")]
        started = time.time()
        sync_service.incremental_sync(symbols, timeframes)
        logger.info("K 线增量同步完成: %d 币 × %d 周期, 耗时 %.1fs", len(symbols), len(timeframes), time.time() - started)


# 默认实例
kline_sync_scheduler = KlineSyncScheduler()
