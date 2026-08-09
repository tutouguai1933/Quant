"""自动化周期互斥锁。

使用文件锁实现跨进程的周期互斥，避免多个并发请求同时执行自动化工作流。
"""

import fcntl
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path


# 陈旧锁判定阈值（秒）。
# 注意：自动化工作流单轮会依次执行多个子任务，每个子任务默认超时 300s（见 tasks/scheduler.py），
# 阈值设太小会把仍在正常执行的长任务误判为陈旧并强制夺锁，导致两个周期同时运行。
# 默认 600s 与任务超时错开，可通过环境变量 QUANT_CYCLE_LOCK_STALE_SECONDS 覆盖。
STALE_LOCK_THRESHOLD_SECONDS = int(os.getenv("QUANT_CYCLE_LOCK_STALE_SECONDS", "600"))


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
            self.lock_file.parent.mkdir(parents=True, exist_ok=True)
            # 先打开文件但不截断内容（O_CREAT 只负责创建），flock 成功后才写元数据。
            # 之前先写 pid/timestamp 再 flock，非阻塞获取失败时会把持锁者的元数据
            # 覆盖掉，导致陈旧检测完全失效；现在失败时文件内容保持不变。
            fd = os.open(self.lock_file, os.O_CREAT | os.O_RDWR)
            self._fd = os.fdopen(fd, "r+")

            flags = fcntl.LOCK_EX
            if not blocking:
                flags |= fcntl.LOCK_NB
            fcntl.flock(self._fd.fileno(), flags)

            # flock 成功后才写入持有者元数据
            lock_metadata = {
                "pid": os.getpid(),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            self._fd.seek(0)
            self._fd.truncate(0)
            self._fd.write(json.dumps(lock_metadata, ensure_ascii=False))
            self._fd.flush()
            os.fsync(self._fd.fileno())
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

        flock 绑定的是文件 inode，unlink 删除文件并不能释放旧持有者的锁，
        新进程在新建文件上加锁后会与旧持锁者同时进入临界区（旧文件句柄仍持有锁）。
        因此这里改为：先读元数据判断是否陈旧，陈旧时阻塞获取锁——真正的持锁进程
        已退出时内核会自动释放 flock，阻塞获取会立即成功；拿到后立即释放即可。
        """
        if not self._is_stale_lock():
            return False

        try:
            if self.acquire(blocking=True):
                self.release()
                return True
        except Exception:
            pass

        return False

    def __enter__(self):
        if not self.acquire(blocking=False):
            raise RuntimeError("无法获取周期锁")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
        return False
