"""定时巡检调度服务。

定期自动调用 openclaw_patrol_service 执行巡检。
"""

import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any

from services.api.app.services.openclaw_patrol_service import openclaw_patrol_service

logger = logging.getLogger(__name__)


class ScheduledPatrolService:
    """定时巡检调度服务。

    使用 threading.Timer 实现定时调度，
    定期调用 openclaw_patrol_service.patrol() 执行巡检。
    """

    DEFAULT_INTERVAL_MINUTES = 60  # 默认每60分钟执行一次

    def __init__(self):
        """初始化调度服务。"""
        self._timer: threading.Timer | None = None
        self._interval_seconds: float = self.DEFAULT_INTERVAL_MINUTES * 60
        self._running: bool = False
        self._last_run_at: datetime | None = None
        self._last_run_result: dict[str, Any] | None = None
        self._total_runs: int = 0
        self._failed_runs: int = 0
        self._lock = threading.Lock()

    def start_schedule(self, interval_minutes: int = 60) -> dict[str, Any]:
        """启动定时巡检。

        Args:
            interval_minutes: 巡检间隔分钟数，默认60分钟

        Returns:
            启动结果
        """
        with self._lock:
            if self._running:
                return {
                    "success": False,
                    "message": "巡检调度已在运行中",
                    "status": self.get_schedule_status(),
                }

            self._interval_seconds = interval_minutes * 60
            self._running = True
            self._schedule_next_run()

            logger.info("定时巡检已启动，间隔: %d 分钟", interval_minutes)
            return {
                "success": True,
                "message": f"定时巡检已启动，间隔 {interval_minutes} 分钟",
                "interval_minutes": interval_minutes,
                "status": self.get_schedule_status(),
            }

    def stop_schedule(self) -> dict[str, Any]:
        """停止定时巡检。

        Returns:
            停止结果
        """
        with self._lock:
            if not self._running:
                return {
                    "success": False,
                    "message": "巡检调度未在运行",
                    "status": self.get_schedule_status(),
                }

            self._running = False
            if self._timer:
                self._timer.cancel()
                self._timer = None

            logger.info("定时巡检已停止")
            return {
                "success": True,
                "message": "定时巡检已停止",
                "status": self.get_schedule_status(),
            }

    def run_patrol_now(self, patrol_type: str = "full") -> dict[str, Any]:
        """立即执行巡检（不依赖调度状态）。

        Args:
            patrol_type: 巡检类型

        Returns:
            巡检结果
        """
        now = datetime.now(timezone.utc)
        logger.info("立即执行巡检: %s", patrol_type)

        try:
            result = openclaw_patrol_service.patrol(patrol_type=patrol_type)
            success = bool(result.get("patrolled", False))

            with self._lock:
                self._last_run_at = now
                self._last_run_result = result
                self._total_runs += 1
                if not success:
                    self._failed_runs += 1

            return {
                "success": success,
                "message": f"巡检执行完成",
                "executed_at": now.isoformat(),
                "result": result,
            }
        except Exception as e:
            logger.exception("巡检执行失败: %s", e)
            with self._lock:
                self._last_run_at = now
                self._last_run_result = {"error": str(e)}
                self._total_runs += 1
                self._failed_runs += 1

            return {
                "success": False,
                "message": f"巡检执行失败: {e}",
                "executed_at": now.isoformat(),
                "error": str(e),
            }

    def get_schedule_status(self) -> dict[str, Any]:
        """获取调度状态。

        Returns:
            调度状态信息
        """
        with self._lock:
            interval_minutes = self._interval_seconds / 60
            next_run_at = None

            if self._running and self._timer:
                # Timer 已经在倒计时，无法精确获取下次执行时间
                # 只能估算
                next_run_at = datetime.now(timezone.utc).isoformat()

            return {
                "running": self._running,
                "interval_minutes": interval_minutes,
                "last_run_at": self._last_run_at.isoformat() if self._last_run_at else None,
                "last_run_status": (
                    self._last_run_result.get("status", "unknown")
                    if self._last_run_result else None
                ),
                "total_runs": self._total_runs,
                "failed_runs": self._failed_runs,
                "success_rate": (
                    (self._total_runs - self._failed_runs) / self._total_runs * 100
                    if self._total_runs > 0 else 100.0
                ),
            }

    def _schedule_next_run(self) -> None:
        """调度下一次巡检执行。"""
        if not self._running:
            return

        self._timer = threading.Timer(self._interval_seconds, self._run_patrol_cycle)
        self._timer.daemon = True  # 不阻塞主线程退出
        self._timer.start()

    def _run_patrol_cycle(self) -> None:
        """执行巡检周期（在 Timer 中调用）。"""
        if not self._running:
            return

        now = datetime.now(timezone.utc)
        logger.info("定时巡检触发: %s", now.isoformat())

        try:
            result = openclaw_patrol_service.patrol(patrol_type="full")
            success = bool(result.get("patrolled", False))

            with self._lock:
                self._last_run_at = now
                self._last_run_result = result
                self._total_runs += 1
                if not success:
                    self._failed_runs += 1

            logger.info(
                "巡检完成: status=%s, actions=%d",
                result.get("status", "unknown"),
                len(result.get("actions_taken", [])),
            )
        except Exception as e:
            logger.exception("定时巡检执行失败: %s", e)
            with self._lock:
                self._last_run_at = now
                self._last_run_result = {"error": str(e)}
                self._total_runs += 1
                self._failed_runs += 1

        # 调度下一次执行
        self._schedule_next_run()


# 单例实例
scheduled_patrol_service = ScheduledPatrolService()