"""带TTL的内存缓存服务。

用于缓存慢速API调用结果，减少响应时间。
"""

from __future__ import annotations

import threading
import time
from typing import Any, Callable, TypeVar

T = TypeVar("T")


class TTLCache:
    """线程安全的带TTL内存缓存。"""

    def __init__(self) -> None:
        self._store: dict[str, tuple[Any, float, float]] = {}
        self._lock = threading.RLock()

    def get(self, key: str) -> tuple[Any, bool]:
        """获取缓存值，返回 (value, found)。"""
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None, False
            value, expires_at, _ = entry
            if time.time() > expires_at:
                del self._store[key]
                return None, False
            return value, True

    def set(self, key: str, value: Any, ttl_seconds: float) -> None:
        """设置缓存值和TTL。"""
        with self._lock:
            expires_at = time.time() + ttl_seconds
            self._store[key] = (value, expires_at, time.time())

    def clear(self, key: str | None = None) -> None:
        """清除指定key或全部缓存。"""
        with self._lock:
            if key is None:
                self._store.clear()
            else:
                self._store.pop(key, None)

    def get_or_compute(self, key: str, compute: Callable[[], T], ttl_seconds: float) -> T:
        """获取缓存值，如果不存在则计算并缓存。"""
        value, found = self.get(key)
        if found:
            return value
        computed = compute()
        self.set(key, computed, ttl_seconds)
        return computed


# 全局缓存实例
cache = TTLCache()
