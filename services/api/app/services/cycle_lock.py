"""自动化周期互斥锁。

使用文件锁实现跨进程的周期互斥，避免多个并发请求同时执行自动化工作流。
"""

import fcntl
import os
from pathlib import Path


class CycleLock:
    """自动化周期互斥锁。"""

    def __init__(self, lock_file: str = ".runtime/cycle.lock"):
        candidate = Path(lock_file)
        if not candidate.is_absolute():
            candidate = Path.cwd() / candidate
        self.lock_file = candidate
        self.lock_file.parent.mkdir(parents=True, exist_ok=True)
        self._fd = None

    def acquire(self, blocking: bool = False) -> bool:
        """尝试获取锁。

        Args:
            blocking: 是否阻塞等待锁释放

        Returns:
            是否成功获取锁
        """
        try:
            self._fd = open(self.lock_file, 'w')
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

    def __enter__(self):
        if not self.acquire(blocking=False):
            raise RuntimeError("无法获取周期锁")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
        return False
