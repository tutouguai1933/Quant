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

    def get(self, interval: str = "1h", ttl_seconds: int = 900) -> dict[str, Any] | None:
        """读取缓存的RSI数据。

        Args:
            interval: 数据间隔，如 "1h", "4h", "1d"
            ttl_seconds: 缓存有效期，默认 15 分钟（RSI 是慢变量；5 分钟过期会让
                         16 币全量重算（约 70 秒）频繁触发，曾导致 api 线程堆积卡死）
        """
        with self._lock:
            if not self._cache_file.exists():
                return None
            try:
                data = json.loads(self._cache_file.read_text())
                if data.get("interval") != interval:
                    return None
                # 检查缓存是否过期
                cached_at = data.get("cached_at", "")
                if cached_at:
                    try:
                        cached_dt = datetime.fromisoformat(cached_at.replace("Z", "+00:00"))
                        now = datetime.now(timezone.utc)
                        if (now - cached_dt).total_seconds() > ttl_seconds:
                            return None  # 缓存过期，触发重新计算
                    except (ValueError, TypeError):
                        pass  # 无法解析时间，使用缓存数据
                return data
            except (json.JSONDecodeError, OSError):
                return None

    def set(self, data: dict[str, Any]) -> None:
        """保存RSI数据到缓存。"""
        with self._lock:
            self._cache_dir.mkdir(parents=True, exist_ok=True)
            data["cached_at"] = datetime.now(timezone.utc).isoformat()
            # 写临时文件 + os.replace 原子替换，避免读取方读到半个文件
            temp_path = Path(f"{self._cache_file}.{os.getpid()}.{threading.get_ident()}.tmp")
            temp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(str(temp_path), str(self._cache_file))

    def get_summary(self, interval: str = "1h") -> dict[str, Any] | None:
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
