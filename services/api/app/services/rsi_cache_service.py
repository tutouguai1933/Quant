"""RSI缓存服务。

用于存储和读取预计算的RSI结果，避免实时调用Binance API。
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class RsiCacheService:
    """管理RSI缓存文件的读写。"""

    def __init__(self, cache_dir: str | None = None) -> None:
        self._cache_dir = Path(cache_dir or os.environ.get("QUANT_RUNTIME_DIR", "/app/.runtime"))
        self._cache_file = self._cache_dir / "rsi_cache.json"
        self._lock = threading.RLock()

    def get(self, interval: str = "1d") -> dict[str, Any] | None:
        """读取缓存的RSI数据。"""
        with self._lock:
            if not self._cache_file.exists():
                return None
            try:
                data = json.loads(self._cache_file.read_text())
                if data.get("interval") != interval:
                    return None
                return data
            except (json.JSONDecodeError, OSError):
                return None

    def set(self, data: dict[str, Any]) -> None:
        """保存RSI数据到缓存。"""
        with self._lock:
            self._cache_dir.mkdir(parents=True, exist_ok=True)
            data["cached_at"] = datetime.now(timezone.utc).isoformat()
            self._cache_file.write_text(json.dumps(data, ensure_ascii=False, indent=2))

    def get_summary(self, interval: str = "1d") -> dict[str, Any] | None:
        """获取缓存的RSI摘要，用于API返回。"""
        cached = self.get(interval)
        if cached is None:
            return None
        return {
            "items": cached.get("items", []),
            "total": cached.get("total", 0),
            "interval": cached.get("interval", interval),
            "updated_at": cached.get("cached_at", ""),
            "from_cache": True,
        }


# 全局实例
rsi_cache = RsiCacheService()
