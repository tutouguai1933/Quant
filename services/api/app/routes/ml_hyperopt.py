"""ML 模型超参数优化路由。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Header

from services.api.app.core.settings import Settings
from services.api.app.services.auth_service import auth_service


router = APIRouter(prefix="/api/v1/ml/hyperopt", tags=["ml-hyperopt"])


def _success(data: dict, meta: dict | None = None) -> dict:
    return {"data": data, "error": None, "meta": meta or {}}


def _error(code: str, message: str) -> dict:
    return {"data": None, "error": {"code": code, "message": message}, "meta": {}}


@router.get("/status")
def get_ml_hyperopt_status(optimizer_id: str = "default") -> dict:
    """获取 ML 超参数优化状态。"""
    from services.worker.optuna_optimizer import get_optimization_progress

    progress = get_optimization_progress(optimizer_id)
    if progress is None:
        return _success({"status": "idle"})

    return _success({
        "status": progress.status,
        "current_trial": progress.current_trial,
        "total_trials": progress.total_trials,
        "best_value": progress.best_value,
        "best_params": progress.best_params,
        "elapsed_seconds": progress.elapsed_seconds,
        "message": progress.message,
    })


@router.post("/start")
def start_ml_hyperopt(
    model_type: str = "lightgbm",
    n_trials: int = 50,
    timeout_seconds: int | None = None,
    optimizer_id: str = "default",
    token: str = "",
    authorization: str = Header(""),
) -> dict:
    """启动 ML 超参数优化。需要控制平面认证。

    从最新数据快照加载真实训练数据进行优化。
    """
    auth_service.require_control_plane_access(auth_service.resolve_access_token(token, authorization))

    from services.worker.optuna_optimizer import (
        start_optimization,
        get_optimization_progress,
    )

    # 检查是否已有运行中的优化
    progress = get_optimization_progress(optimizer_id)
    if progress and progress.status == "running":
        return _error("hyperopt_already_running", f"优化 {optimizer_id} 已在运行中")

    # 从数据快照加载真实数据
    training_rows, validation_rows, feature_columns = _load_training_data_from_snapshot()

    if training_rows is None or len(training_rows) < 20:
        return _error("no_training_data", "没有足够的训练数据，请先执行研究训练")

    if not feature_columns:
        return _error("no_features", "训练数据中没有特征列信息")

    # 启动优化
    start_optimization(
        optimizer_id=optimizer_id,
        training_rows=training_rows,
        validation_rows=validation_rows or [],
        feature_columns=feature_columns,
        model_type=model_type,
        n_trials=n_trials,
        timeout_seconds=timeout_seconds,
    )

    return _success({
        "status": "running",
        "optimizer_id": optimizer_id,
        "model_type": model_type,
        "n_trials": n_trials,
        "training_samples": len(training_rows),
        "validation_samples": len(validation_rows or []),
        "feature_count": len(feature_columns),
        "started_at": datetime.now(timezone.utc).isoformat(),
    })


@router.post("/stop")
def stop_ml_hyperopt(
    optimizer_id: str = "default",
    token: str = "",
    authorization: str = Header(""),
) -> dict:
    """停止 ML 超参数优化。需要控制平面认证。"""
    auth_service.require_control_plane_access(auth_service.resolve_access_token(token, authorization))

    from services.worker.optuna_optimizer import stop_optimization

    success = stop_optimization(optimizer_id)
    if success:
        return _success({"status": "stopped", "optimizer_id": optimizer_id})
    return _error("stop_failed", f"无法停止优化 {optimizer_id}")


@router.get("/result/{optimizer_id}")
def get_ml_hyperopt_result(optimizer_id: str, save_best: bool = True) -> dict:
    """获取 ML 超参数优化结果。

    Args:
        optimizer_id: 优化器 ID
        save_best: 是否保存最优参数到存储（默认 True）
    """
    from services.worker.optuna_optimizer import get_optimization_result

    result = get_optimization_result(optimizer_id)
    if result is None:
        return _error("result_not_found", f"优化结果 {optimizer_id} 不存在")

    # 保存最优参数到存储
    if save_best and result.best_value > 0.5:
        _save_best_params(result.best_params, result.best_value, result.n_trials, result.study_name.split("-")[0])

    return _success({
        "study_name": result.study_name,
        "best_params": result.best_params,
        "best_value": result.best_value,
        "n_trials": result.n_trials,
        "duration_seconds": result.duration_seconds,
        "param_importance": result.param_importance,
        "generated_at": result.generated_at.isoformat(),
        "saved_to_store": save_best and result.best_value > 0.5,
    })


@router.get("/history")
def list_ml_hyperopt_history(limit: int = 20) -> dict:
    """列出 ML 超参数优化历史。"""
    from services.worker.best_params_store import get_best_params_store

    store = get_best_params_store()
    info = store.get_info()

    if not info.get("exists"):
        return _success({
            "optimizations": [],
            "total": 0,
            "current_best": None,
        })

    return _success({
        "optimizations": [
            {
                "auc": info["auc"],
                "n_trials": info["n_trials"],
                "model_type": info["model_type"],
                "generated_at": info["generated_at"],
            }
        ],
        "total": 1,
        "current_best": {
            "auc": info["auc"],
            "params": info["params"],
        },
    })


@router.post("/clear-best")
def clear_best_params(
    token: str = "",
    authorization: str = Header(""),
) -> dict:
    """清除存储的最优参数。需要控制平面认证。"""
    auth_service.require_control_plane_access(auth_service.resolve_access_token(token, authorization))

    from services.worker.best_params_store import get_best_params_store

    store = get_best_params_store()
    store.clear()

    return _success({"status": "cleared"})


@router.get("/schedule/status")
def get_hyperopt_schedule_status() -> dict:
    """获取超参数优化调度状态。"""
    from services.api.app.services.hyperopt_schedule_service import get_hyperopt_schedule_service

    service = get_hyperopt_schedule_service()
    return _success(service.get_status())


@router.get("/schedule/check")
def check_hyperopt_schedule() -> dict:
    """检查是否应该运行超参数优化。

    供 OpenClaw 调度器调用。
    """
    from services.api.app.services.hyperopt_schedule_service import get_hyperopt_schedule_service

    service = get_hyperopt_schedule_service()

    should_run = service.should_run()

    result = {
        "should_run": should_run,
        "reason": "",
    }

    if should_run:
        result["reason"] = "scheduled_interval_reached"
    else:
        status = service.get_status()
        if not status.get("enabled"):
            result["reason"] = "schedule_disabled"
        elif status.get("running"):
            result["reason"] = "optimization_in_progress"
        else:
            next_run = status.get("next_run_in_hours", 0)
            result["reason"] = f"next_run_in_{next_run:.1f}_hours"

    return _success(result)


@router.post("/schedule/config")
def update_hyperopt_schedule_config(
    enabled: bool | None = None,
    interval_hours: int | None = None,
    n_trials: int | None = None,
    model_type: str | None = None,
    token: str = "",
    authorization: str = Header(""),
) -> dict:
    """更新超参数优化调度配置。需要控制平面认证。"""
    auth_service.require_control_plane_access(auth_service.resolve_access_token(token, authorization))

    from services.api.app.services.hyperopt_schedule_service import get_hyperopt_schedule_service

    service = get_hyperopt_schedule_service()
    service.update_config(
        enabled=enabled,
        interval_hours=interval_hours,
        n_trials=n_trials,
        model_type=model_type,
    )

    return _success({
        "updated": True,
        "status": service.get_status(),
    })


def _load_training_data_from_snapshot() -> tuple[list[dict[str, Any]] | None, list[dict[str, Any]] | None, tuple[str, ...] | None]:
    """从数据快照加载训练数据。

    Returns:
        tuple: (training_rows, validation_rows, feature_columns) 或 (None, None, None)
    """
    import json
    from services.worker.qlib_config import load_qlib_config
    from services.worker.qlib_dataset import deserialize_dataset_bundle

    config = load_qlib_config()
    snapshot_path = config.paths.latest_dataset_snapshot_path

    if not snapshot_path.exists():
        # 尝试从最新训练结果加载
        training_path = config.paths.latest_training_path
        if training_path.exists():
            try:
                training_payload = json.loads(training_path.read_text(encoding="utf-8"))
                feature_columns = tuple(training_payload.get("feature_columns", []))

                # 检查是否有 dataset_snapshot_path
                dataset_snapshot_path_str = training_payload.get("dataset_snapshot_path")
                if dataset_snapshot_path_str:
                    dataset_snapshot_path = config.paths.runtime_root / "dataset" / "snapshots" / Path(dataset_snapshot_path_str).name
                    if dataset_snapshot_path.exists():
                        snapshot_path = dataset_snapshot_path
            except Exception:
                pass

    if not snapshot_path.exists():
        return None, None, None

    try:
        payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
        bundle = deserialize_dataset_bundle(payload)

        training_rows = list(bundle.training_rows)
        validation_rows = list(bundle.validation_rows) if bundle.validation_rows else []
        feature_columns = tuple(bundle.feature_columns)

        return training_rows, validation_rows, feature_columns
    except Exception:
        return None, None, None


def _save_best_params(params: dict[str, Any], auc: float, n_trials: int, model_type: str) -> bool:
    """保存最优参数到存储。

    Args:
        params: 最优参数
        auc: AUC 值
        n_trials: 优化轮数
        model_type: 模型类型

    Returns:
        bool: 是否保存成功
    """
    try:
        from services.worker.best_params_store import get_best_params_store

        store = get_best_params_store()
        store.save(params, auc, n_trials, model_type)
        return True
    except Exception:
        return False
