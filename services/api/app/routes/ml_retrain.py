"""ML 模型重训练路由。"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Header

from services.api.app.core.settings import Settings
from services.api.app.services.auth_service import auth_service


router = APIRouter(prefix="/api/v1/ml/retrain", tags=["ml-retrain"])


def _success(data: dict | None, meta: dict | None = None) -> dict:
    return {"data": data, "error": None, "meta": meta or {}}


def _error(code: str, message: str) -> dict:
    return {"data": None, "error": {"code": code, "message": message}, "meta": {}}


@router.get("/status")
def get_retrain_status() -> dict:
    """获取重训练状态。

    返回当前重训练配置和上次训练信息。
    """
    from services.worker.auto_retrain import get_auto_retrainer

    retrainer = get_auto_retrainer()
    status = retrainer.get_status()

    return _success({
        "last_retrain_time": status.get("last_retrain_time"),
        "last_sample_count": status.get("last_sample_count"),
        "last_metrics": status.get("last_metrics"),
        "hours_since_last_retrain": status.get("hours_since_last_retrain"),
        "config": status.get("config"),
    })


@router.get("/check")
def check_retrain_needed() -> dict:
    """检查是否需要重训练。

    根据配置的触发条件评估是否应该进行重训练。
    """
    from services.worker.auto_retrain import get_auto_retrainer
    from services.worker.model_registry import get_model_registry

    retrainer = get_auto_retrainer()
    registry = get_model_registry()

    # 获取当前生产模型指标
    production_model = registry.get_production_model()
    current_metrics = {}
    if production_model:
        current_metrics = {
            "val_auc": production_model.metrics.get("val_auc", 0.0),
            "val_f1": production_model.metrics.get("val_f1", 0.0),
        }

    # 检查重训练需求
    decision = retrainer.check_retrain_needed(
        current_metrics=current_metrics,
        current_sample_count=None,  # 需要从实际数据源获取
    )

    return _success({
        "should_retrain": decision.should_retrain,
        "trigger": decision.trigger,
        "reason": decision.reason,
        "metrics": decision.metrics,
        "thresholds": decision.thresholds,
    })


@router.post("/trigger")
def trigger_retrain(
    source: str = "manual",
    token: str = "",
    authorization: str = Header(""),
) -> dict:
    """手动触发重训练。需要控制平面认证。

    Args:
        source: 触发来源标识
    """
    auth_service.require_control_plane_access(auth_service.resolve_access_token(token, authorization))

    from services.api.app.routes.tasks import run_train_task_impl

    result = run_train_task_impl(source=f"retrain-{source}")

    return _success({
        "status": result.get("status"),
        "task_id": result.get("id"),
        "triggered_at": datetime.now(timezone.utc).isoformat(),
        "source": source,
    })


@router.post("/reset")
def reset_retrain_state(
    token: str = "",
    authorization: str = Header(""),
) -> dict:
    """重置重训练状态。需要控制平面认证。

    清除上次训练记录，使系统认为从未训练过。
    """
    auth_service.require_control_plane_access(auth_service.resolve_access_token(token, authorization))

    from services.worker.auto_retrain import get_auto_retrainer

    retrainer = get_auto_retrainer()
    retrainer._last_retrain_time = None
    retrainer._last_sample_count = 0
    retrainer._last_metrics = {}

    return _success({
        "status": "reset",
        "reset_at": datetime.now(timezone.utc).isoformat(),
    })


@router.get("/config")
def get_retrain_config() -> dict:
    """获取重训练配置。"""
    from services.worker.auto_retrain import get_auto_retrainer

    retrainer = get_auto_retrainer()
    status = retrainer.get_status()

    return _success({
        "config": status.get("config"),
    })


@router.post("/config")
def update_retrain_config(
    performance_drop_threshold: float | None = None,
    schedule_interval_days: int | None = None,
    sample_increase_threshold: int | None = None,
    min_retrain_interval_hours: int | None = None,
    token: str = "",
    authorization: str = Header(""),
) -> dict:
    """更新重训练配置。需要控制平面认证。

    仅更新提供的参数，未提供的参数保持不变。
    """
    auth_service.require_control_plane_access(auth_service.resolve_access_token(token, authorization))

    from services.worker.auto_retrain import get_auto_retrainer, RetrainConfig

    retrainer = get_auto_retrainer()

    # 更新配置
    if performance_drop_threshold is not None:
        retrainer._retrain_config.performance_drop_threshold = performance_drop_threshold
    if schedule_interval_days is not None:
        retrainer._retrain_config.schedule_interval_days = schedule_interval_days
    if sample_increase_threshold is not None:
        retrainer._retrain_config.sample_increase_threshold = sample_increase_threshold
    if min_retrain_interval_hours is not None:
        retrainer._retrain_config.min_retrain_interval_hours = min_retrain_interval_hours

    return _success({
        "config": retrainer.get_status().get("config"),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })
