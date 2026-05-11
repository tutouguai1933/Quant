"""超参数优化调度服务。

提供定期触发超参数优化的后台服务。
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(slots=True)
class HyperoptSchedule:
    """优化调度配置。"""

    enabled: bool = True
    interval_hours: int = 24  # 每 24 小时运行一次
    n_trials: int = 50
    model_type: str = "lightgbm"
    last_run_at: datetime | None = None
    last_result: dict[str, Any] | None = None


class HyperoptScheduleService:
    """定期触发超参数优化。

    在后台自动运行超参数优化，保持模型参数持续改进。
    """

    def __init__(self) -> None:
        self._schedule = HyperoptSchedule()
        self._running = False
        self._lock = threading.Lock()

    def should_run(self) -> bool:
        """检查是否应该运行优化。

        Returns:
            bool: 是否应该运行
        """
        with self._lock:
            if not self._schedule.enabled:
                return False
            if self._running:
                return False

            if self._schedule.last_run_at is None:
                return True

            elapsed = datetime.now(timezone.utc) - self._schedule.last_run_at
            return elapsed.total_seconds() >= self._schedule.interval_hours * 3600

    def mark_started(self) -> None:
        """标记开始运行。"""
        with self._lock:
            self._running = True

    def mark_completed(self, result: dict[str, Any] | None = None) -> None:
        """标记完成。

        Args:
            result: 优化结果
        """
        with self._lock:
            self._running = False
            self._schedule.last_run_at = datetime.now(timezone.utc)
            if result:
                self._schedule.last_result = result

    def mark_failed(self, error: str) -> None:
        """标记失败。

        Args:
            error: 错误信息
        """
        with self._lock:
            self._running = False
            self._schedule.last_result = {
                "status": "failed",
                "error": error,
                "failed_at": datetime.now(timezone.utc).isoformat(),
            }

    def get_status(self) -> dict[str, Any]:
        """获取调度状态。

        Returns:
            dict: 状态信息
        """
        with self._lock:
            return {
                "enabled": self._schedule.enabled,
                "running": self._running,
                "interval_hours": self._schedule.interval_hours,
                "n_trials": self._schedule.n_trials,
                "model_type": self._schedule.model_type,
                "last_run_at": self._schedule.last_run_at.isoformat() if self._schedule.last_run_at else None,
                "last_result": self._schedule.last_result,
                "next_run_in_hours": self._calculate_next_run_hours(),
            }

    def _calculate_next_run_hours(self) -> float | None:
        """计算下次运行的剩余小时数。"""
        if self._schedule.last_run_at is None:
            return 0.0
        elapsed = datetime.now(timezone.utc) - self._schedule.last_run_at
        remaining = self._schedule.interval_hours * 3600 - elapsed.total_seconds()
        return max(0.0, remaining / 3600)

    def update_config(
        self,
        enabled: bool | None = None,
        interval_hours: int | None = None,
        n_trials: int | None = None,
        model_type: str | None = None,
    ) -> None:
        """更新调度配置。

        Args:
            enabled: 是否启用
            interval_hours: 间隔小时数
            n_trials: 优化轮数
            model_type: 模型类型
        """
        with self._lock:
            if enabled is not None:
                self._schedule.enabled = enabled
            if interval_hours is not None:
                self._schedule.interval_hours = interval_hours
            if n_trials is not None:
                self._schedule.n_trials = n_trials
            if model_type is not None:
                self._schedule.model_type = model_type

    def run_optimization_async(self) -> str:
        """异步启动优化。

        Returns:
            str: 优化器 ID
        """
        import uuid
        from services.worker.optuna_optimizer import start_optimization

        optimizer_id = f"scheduled-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"

        # 加载训练数据
        training_rows, validation_rows, feature_columns = self._load_training_data()
        if not training_rows or len(training_rows) < 20:
            raise RuntimeError("没有足够的训练数据")

        self.mark_started()

        def run():
            try:
                start_optimization(
                    optimizer_id=optimizer_id,
                    training_rows=training_rows,
                    validation_rows=validation_rows or [],
                    feature_columns=feature_columns or (),
                    model_type=self._schedule.model_type,
                    n_trials=self._schedule.n_trials,
                )
                self.mark_completed({"optimizer_id": optimizer_id})
            except Exception as e:
                self.mark_failed(str(e))

        thread = threading.Thread(target=run, daemon=True)
        thread.start()

        return optimizer_id

    def _load_training_data(self) -> tuple[list[dict[str, Any]] | None, list[dict[str, Any]] | None, tuple[str, ...] | None]:
        """加载训练数据。

        Returns:
            tuple: (training_rows, validation_rows, feature_columns)
        """
        import json
        from services.worker.qlib_config import load_qlib_config
        from services.worker.qlib_dataset import deserialize_dataset_bundle

        try:
            config = load_qlib_config()
            snapshot_path = config.paths.latest_dataset_snapshot_path

            if not snapshot_path.exists():
                return None, None, None

            payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
            bundle = deserialize_dataset_bundle(payload)

            training_rows = list(bundle.training_rows)
            validation_rows = list(bundle.validation_rows) if bundle.validation_rows else []
            feature_columns = tuple(bundle.feature_columns)

            return training_rows, validation_rows, feature_columns
        except Exception:
            return None, None, None


# 全局调度服务实例
_schedule_service: HyperoptScheduleService | None = None


def get_hyperopt_schedule_service() -> HyperoptScheduleService:
    """获取调度服务实例。

    Returns:
        HyperoptScheduleService: 调度服务实例
    """
    global _schedule_service
    if _schedule_service is None:
        _schedule_service = HyperoptScheduleService()
    return _schedule_service
