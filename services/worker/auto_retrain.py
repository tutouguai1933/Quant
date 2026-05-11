"""自动重训练触发器。

提供模型性能监控和自动重训练触发功能。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from services.worker.model_registry import ModelRegistry, get_model_registry
from services.worker.qlib_config import QlibRuntimeConfig


@dataclass(slots=True)
class RetrainDecision:
    """重训练决策数据类。"""

    should_retrain: bool
    trigger: str  # "performance_drop", "data_drift", "schedule", "sample_increase", "manual"
    reason: str
    metrics: dict[str, float]
    thresholds: dict[str, float]


@dataclass(slots=True)
class RetrainConfig:
    """重训练配置数据类。"""

    # 性能下降阈值
    performance_drop_threshold: float = 0.05  # AUC 下降超过 5%
    # 数据漂移阈值（特征分布变化）
    data_drift_threshold: float = 0.1
    # 定时重训练间隔（天）
    schedule_interval_days: int = 7
    # 样本增加阈值
    sample_increase_threshold: int = 1000
    # 最小训练间隔（小时）
    min_retrain_interval_hours: int = 6


class AutoRetrainer:
    """自动重训练触发器。

    监控模型性能，触发自动重训练。
    """

    def __init__(
        self,
        config: QlibRuntimeConfig,
        retrain_config: RetrainConfig | None = None,
    ) -> None:
        """初始化自动重训练器。

        Args:
            config: 研究层配置
            retrain_config: 重训练配置
        """
        self._config = config
        self._retrain_config = retrain_config or RetrainConfig()
        self._last_retrain_time: datetime | None = None
        self._last_sample_count: int = 0
        self._last_metrics: dict[str, float] = {}

    def check_retrain_needed(
        self,
        current_metrics: dict[str, float] | None = None,
        current_sample_count: int | None = None,
        current_feature_distribution: dict[str, float] | None = None,
    ) -> RetrainDecision:
        """检查是否需要重训练。

        Args:
            current_metrics: 当前模型指标
            current_sample_count: 当前样本数量
            current_feature_distribution: 当前特征分布

        Returns:
            RetrainDecision: 重训练决策
        """
        now = datetime.now(timezone.utc)
        triggers: list[str] = []
        reasons: list[str] = []
        metrics: dict[str, float] = {}

        # 1. 检查定时触发
        if self._last_retrain_time is None:
            triggers.append("schedule")
            reasons.append("首次训练")
        else:
            hours_since_last = (now - self._last_retrain_time).total_seconds() / 3600
            if hours_since_last >= self._retrain_config.schedule_interval_days * 24:
                triggers.append("schedule")
                reasons.append(f"距离上次训练已超过 {self._retrain_config.schedule_interval_days} 天")

        # 2. 检查性能下降
        if current_metrics and self._last_metrics:
            last_auc = self._last_metrics.get("val_auc", 0.0)
            current_auc = current_metrics.get("val_auc", 0.0)
            if last_auc > 0 and current_auc > 0:
                drop = last_auc - current_auc
                if drop > self._retrain_config.performance_drop_threshold:
                    triggers.append("performance_drop")
                    reasons.append(f"AUC 下降了 {drop:.4f}，超过阈值 {self._retrain_config.performance_drop_threshold}")
                    metrics["auc_drop"] = drop

        # 3. 检查样本数量增加
        if current_sample_count is not None and self._last_sample_count > 0:
            increase = current_sample_count - self._last_sample_count
            if increase >= self._retrain_config.sample_increase_threshold:
                triggers.append("sample_increase")
                reasons.append(f"样本数量增加了 {increase}，超过阈值 {self._retrain_config.sample_increase_threshold}")
                metrics["sample_increase"] = float(increase)

        # 4. 检查最小训练间隔
        if self._last_retrain_time:
            hours_since_last = (now - self._last_retrain_time).total_seconds() / 3600
            if hours_since_last < self._retrain_config.min_retrain_interval_hours:
                # 间隔太短，不触发重训练
                return RetrainDecision(
                    should_retrain=False,
                    trigger="",
                    reason=f"距离上次训练仅 {hours_since_last:.1f} 小时，未达到最小间隔 {self._retrain_config.min_retrain_interval_hours} 小时",
                    metrics=metrics,
                    thresholds={
                        "min_retrain_interval_hours": self._retrain_config.min_retrain_interval_hours,
                    },
                )

        should_retrain = len(triggers) > 0
        trigger = triggers[0] if triggers else ""
        reason = "; ".join(reasons) if reasons else ""

        return RetrainDecision(
            should_retrain=should_retrain,
            trigger=trigger,
            reason=reason,
            metrics=metrics,
            thresholds={
                "performance_drop_threshold": self._retrain_config.performance_drop_threshold,
                "schedule_interval_days": self._retrain_config.schedule_interval_days,
                "sample_increase_threshold": self._retrain_config.sample_increase_threshold,
            },
        )

    def record_retrain(
        self,
        sample_count: int,
        metrics: dict[str, float],
    ) -> None:
        """记录重训练完成。

        Args:
            sample_count: 训练样本数量
            metrics: 训练指标
        """
        self._last_retrain_time = datetime.now(timezone.utc)
        self._last_sample_count = sample_count
        self._last_metrics = dict(metrics)

    def get_status(self) -> dict[str, Any]:
        """获取重训练状态。

        Returns:
            dict: 状态信息
        """
        now = datetime.now(timezone.utc)
        hours_since_last = None
        if self._last_retrain_time:
            hours_since_last = (now - self._last_retrain_time).total_seconds() / 3600

        return {
            "last_retrain_time": self._last_retrain_time.isoformat() if self._last_retrain_time else None,
            "last_sample_count": self._last_sample_count,
            "last_metrics": self._last_metrics,
            "hours_since_last_retrain": hours_since_last,
            "config": {
                "performance_drop_threshold": self._retrain_config.performance_drop_threshold,
                "schedule_interval_days": self._retrain_config.schedule_interval_days,
                "sample_increase_threshold": self._retrain_config.sample_increase_threshold,
                "min_retrain_interval_hours": self._retrain_config.min_retrain_interval_hours,
            },
        }


# 全局自动重训练器实例
_auto_retrainer: AutoRetrainer | None = None


def get_auto_retrainer(config: QlibRuntimeConfig | None = None) -> AutoRetrainer:
    """获取自动重训练器实例。

    Args:
        config: 研究层配置

    Returns:
        AutoRetrainer: 自动重训练器实例
    """
    global _auto_retrainer
    if _auto_retrainer is None and config is not None:
        _auto_retrainer = AutoRetrainer(config)
    elif _auto_retrainer is None:
        from services.worker.qlib_config import load_qlib_config
        _auto_retrainer = AutoRetrainer(load_qlib_config())
    return _auto_retrainer
