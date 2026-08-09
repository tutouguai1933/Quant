"""带TTL的内存缓存服务。

用于缓存慢速API调用结果，减少响应时间。
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import Future
from typing import Any, Callable, TypeVar

T = TypeVar("T")


class TTLCache:
    """线程安全的带TTL内存缓存。"""

    def __init__(self) -> None:
        self._store: dict[str, tuple[Any, float, float]] = {}
        self._lock = threading.RLock()
        # 单飞表：key -> Future，记录缓存 miss 后正在计算中的任务。
        # 计算期间其他线程复用同一个 future，避免同一 key 并发重复计算
        # （调用方会在每次 miss 时新建线程池并发调 Binance，堆积会导致线程爆炸）。
        self._inflight: dict[str, Future] = {}
        # 单飞表 owner：key -> 正在执行 compute 的线程 id 集合，用于防止
        # compute 内部递归获取同一 key 时自等待死锁。
        self._inflight_owners: dict[str, set[int]] = {}

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
                # 一并清掉计算中的任务，允许后续调用重新发起计算
                self._inflight.clear()
                self._inflight_owners.clear()
            else:
                self._store.pop(key, None)
                self._inflight.pop(key, None)
                self._inflight_owners.pop(key, None)

    def get_or_compute(self, key: str, compute: Callable[[], T], ttl_seconds: float) -> T:
        """获取缓存值，如果不存在则计算并缓存。

        同一 key 并发访问时只执行一次 compute，其他线程等待同一个 future。
        compute 会在独立的工作线程中执行，等待期间不持有内部锁，不会死锁。
        """
        value, found = self.get(key)
        if found:
            return value

        with self._lock:
            # 双检：拿到锁后再查一次，避免多个线程同时创建 future
            value, found = self.get(key)
            if found:
                return value
            future = self._inflight.get(key)
            created = False
            if future is None:
                future = Future()
                self._inflight[key] = future
                self._inflight_owners[key] = set()
                created = True

        if created:
            # 创建者负责在独立线程中执行 compute 并回填缓存
            self._start_compute(key, future, compute, ttl_seconds)

        if self._is_current_owner(key):
            # 当前线程自己正在计算该 key（compute 内部递归调用同一 key），
            # 直接执行 compute 返回，避免等待自己的 future 而死锁
            return compute()

        # 等待计算结果（工作线程完成，此处不持锁）
        return future.result()

    def _is_current_owner(self, key: str) -> bool:
        """判断当前线程是否是该 key 正在执行 compute 的线程。"""
        with self._lock:
            owners = self._inflight_owners.get(key)
            return owners is not None and threading.get_ident() in owners

    def _start_compute(
        self, key: str, future: Future, compute: Callable[[], T], ttl_seconds: float
    ) -> None:
        """在独立线程中执行 compute，完成后回填缓存并清理单飞表。"""

        def _run() -> None:
            # 登记 owner，供 compute 内部递归调用时识别自己
            with self._lock:
                owners = self._inflight_owners.get(key)
                if owners is not None:
                    owners.add(threading.get_ident())
            try:
                result = compute()
                self.set(key, result, ttl_seconds)
                future.set_result(result)
            except BaseException as exc:  # noqa: BLE001
                # 计算失败不写缓存，异常原样传给所有等待者
                future.set_exception(exc)
            finally:
                # 计算结束必须清理，保证下次调用可以重新发起计算
                with self._lock:
                    self._inflight.pop(key, None)
                    self._inflight_owners.pop(key, None)

        threading.Thread(
            target=_run, name=f"cache-compute-{key[:32]}", daemon=True
        ).start()


# 全局缓存实例
cache = TTLCache()
