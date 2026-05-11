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
    """启动 ML 超参数优化。需要控制平面认证。"""
    auth_service.require_control_plane_access(auth_service.resolve_access_token(token, authorization))

    from services.worker.optuna_optimizer import (
        start_optimization,
        get_optimization_progress,
    )

    # 检查是否已有运行中的优化
    progress = get_optimization_progress(optimizer_id)
    if progress and progress.status == "running":
        return _error("hyperopt_already_running", f"优化 {optimizer_id} 已在运行中")

    # 获取训练数据（从最新训练结果）
    from services.worker.qlib_config import load_qlib_config
    import json

    config = load_qlib_config()
    training_path = config.paths.latest_training_path

    if not training_path.exists():
        return _error("no_training_data", "没有可用的训练数据，请先执行研究训练")

    try:
        training_payload = json.loads(training_path.read_text(encoding="utf-8"))
    except Exception:
        return _error("training_data_invalid", "训练数据格式无效")

    # 提取特征列和样本（简化版，实际应从数据快照获取）
    feature_columns = tuple(training_payload.get("feature_columns", []))
    if not feature_columns:
        return _error("no_features", "训练数据中没有特征列信息")

    # 生成模拟训练数据（实际应用应从数据快照加载）
    # 这里简化处理，实际部署需要完善
    training_rows = _generate_sample_data(100, feature_columns)
    validation_rows = _generate_sample_data(30, feature_columns)

    # 启动优化
    start_optimization(
        optimizer_id=optimizer_id,
        training_rows=training_rows,
        validation_rows=validation_rows,
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
def get_ml_hyperopt_result(optimizer_id: str) -> dict:
    """获取 ML 超参数优化结果。"""
    from services.worker.optuna_optimizer import get_optimization_result

    result = get_optimization_result(optimizer_id)
    if result is None:
        return _error("result_not_found", f"优化结果 {optimizer_id} 不存在")

    return _success({
        "study_name": result.study_name,
        "best_params": result.best_params,
        "best_value": result.best_value,
        "n_trials": result.n_trials,
        "duration_seconds": result.duration_seconds,
        "param_importance": result.param_importance,
        "generated_at": result.generated_at.isoformat(),
    })


@router.get("/history")
def list_ml_hyperopt_history(limit: int = 20) -> dict:
    """列出 ML 超参数优化历史。"""
    # 简化实现，返回空列表
    # 实际应用应从数据库或文件系统加载
    return _success({
        "optimizations": [],
        "total": 0,
    })


def _generate_sample_data(n_samples: int, feature_columns: tuple[str, ...]) -> list[dict[str, Any]]:
    """生成模拟数据（用于测试）。

    实际应用应从数据快照加载真实数据。
    """
    import random

    rows = []
    for i in range(n_samples):
        row = {}
        for col in feature_columns:
            row[col] = random.uniform(-5, 5)
        # 生成标签：特征和大于 0 为正样本
        row["future_return_pct"] = 1.0 if sum(row.values()) > 0 else -0.5
        rows.append(row)

    return rows
