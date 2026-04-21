"""自动化周期互斥锁。

使用文件锁实现跨进程的周期互斥，避免多个并发请求同时执行自动化工作流。
"""

import fcntl
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path


# Stale lock detection threshold in seconds (5 minutes by default)
STALE_LOCK_THRESHOLD_SECONDS = 300


class CycleLock:
    """自动化周期互斥锁。"""

    def __init__(self, lock_file: str = ".runtime/cycle.lock", stale_threshold_seconds: int = STALE_LOCK_THRESHOLD_SECONDS):
        candidate = Path(lock_file)
        if not candidate.is_absolute():
            candidate = Path.cwd() / candidate
        self.lock_file = candidate
        self.lock_file.parent.mkdir(parents=True, exist_ok=True)
        self._fd = None
        self._stale_threshold_seconds = stale_threshold_seconds

    def acquire(self, blocking: bool = False) -> bool:
        """尝试获取锁。

        Args:
            blocking: 是否阻塞等待锁释放

        Returns:
            是否成功获取锁
        """
        try:
            # Write lock metadata before acquiring lock
            lock_metadata = {
                "pid": os.getpid(),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            self.lock_file.parent.mkdir(parents=True, exist_ok=True)
            # Open file for writing metadata
            self._fd = open(self.lock_file, 'w')
            self._fd.write(json.dumps(lock_metadata, ensure_ascii=False))
            self._fd.flush()
            os.fsync(self._fd.fileno())

            flags = fcntl.LOCK_EX
            if not blocking:
                flags |= fcntl.LOCK_NB
            fcntl.flock(self._fd.fileno(), flags)
            return True
        except (IOError, OSError):
            if self._fd:
                self._fd.close()
                self._fd = None
            return False

    def release(self):
        """释放锁。"""
        if self._fd:
            try:
                fcntl.flock(self._fd.fileno(), fcntl.LOCK_UN)
                self._fd.close()
            except (IOError, OSError):
                pass
            finally:
                self._fd = None

    def _is_stale_lock(self) -> bool:
        """检测锁是否陈旧（持有者进程已不存在或超时）。

        Returns:
            是否为陈旧锁
        """
        if not self.lock_file.exists():
            return False

        try:
            content = self.lock_file.read_text(encoding="utf-8")
            metadata = json.loads(content)
        except (json.JSONDecodeError, OSError, ValueError):
            # If we can't read the metadata, consider it stale
            return True

        if not isinstance(metadata, dict):
            return True

        # Check if the process that created the lock is still alive
        pid = metadata.get("pid")
        if pid is not None:
            try:
                # Sending signal 0 to a process checks if it exists
                os.kill(int(pid), 0)
                # Process exists, check timestamp
            except (OSError, ProcessLookupError, ValueError):
                # Process does not exist, lock is stale
                return True

        # Check timestamp threshold
        timestamp_str = metadata.get("timestamp")
        if timestamp_str:
            try:
                lock_time = datetime.fromisoformat(timestamp_str)
                if lock_time.tzinfo is None:
                    lock_time = lock_time.replace(tzinfo=timezone.utc)
                elapsed = (datetime.now(timezone.utc) - lock_time).total_seconds()
                if elapsed > self._stale_threshold_seconds:
                    return True
            except (ValueError, TypeError):
                return True

        return False

    def force_release(self) -> bool:
        """强制释放陈旧锁。

        Returns:
            是否成功释放
        """
        if not self._is_stale_lock():
            return False

        try:
            # Try to acquire and immediately release to clear stale lock
            if self.acquire(blocking=False):
                self.release()
                return True
        except Exception:
            pass

        # If flock approach didn't work, try to remove the file directly
        try:
            self.lock_file.unlink(missing_ok=True)
            return True
        except OSError:
            return False

    def __enter__(self):
        if not self.acquire(blocking=False):
            raise RuntimeError("无法获取周期锁")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
        return False
