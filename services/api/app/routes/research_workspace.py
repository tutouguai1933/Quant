"""策略研究工作台路由。"""

from __future__ import annotations

from pathlib import Path

from services.api.app.services.research_workspace_service import research_workspace_service

try:
    from fastapi import APIRouter
except ImportError:
    class APIRouter:  # pragma: no cover
        def __init__(self, *args, **kwargs) -> None:
            self.args = args
            self.kwargs = kwargs

        def get(self, *args, **kwargs):
            def decorator(func):
                return func

            return decorator


router = APIRouter(prefix="/api/v1/research", tags=["research"])


def _success(data: dict[str, object], meta: dict[str, object] | None = None) -> dict[str, object]:
    """统一成功包裹。"""

    return {"data": data, "error": None, "meta": meta or {}}


@router.get("/workspace")
def get_research_workspace() -> dict[str, object]:
    """返回策略研究工作台聚合结果。"""

    workspace = research_workspace_service.get_workspace()
    return _success({"item": workspace}, {"source": "research-workspace"})


@router.get("/training-result")
def get_ml_training_result() -> dict[str, object]:
    """返回 ML 训练结果（训练曲线、特征重要性、评估指标）。"""
    import json

    from services.worker.qlib_config import load_qlib_config

    config = load_qlib_config()
    training_path = config.paths.latest_training_path

    if not training_path.exists():
        return _success(None, {"source": "ml-training", "status": "no_data"})

    try:
        payload = json.loads(training_path.read_text(encoding="utf-8"))
    except Exception:
        return _success(None, {"source": "ml-training", "status": "invalid_data"})

    # 提取训练曲线
    training_curve = []
    curve_data = payload.get("training_curve") or {}
    series = curve_data.get("series") or []
    for item in series:
        if isinstance(item, dict):
            training_curve.append({
                "step": int(item.get("step", 0) or 0),
                "train_score": item.get("train_score"),
                "validation_score": item.get("validation_score"),
                "train_loss": item.get("train_loss"),
                "validation_loss": item.get("validation_loss"),
            })

    # 提取特征重要性
    feature_importance = []
    importance_data = payload.get("feature_importance") or {}
    series = importance_data.get("series") or []
    for i, item in enumerate(series):
        if isinstance(item, dict):
            feature_importance.append({
                "feature": str(item.get("factor") or item.get("feature", "")),
                "importance": float(item.get("importance", 0) or 0),
                "category": item.get("category"),
                "rank": i + 1,
            })

    # 提取训练指标
    metrics = payload.get("metrics") or {}
    training_metrics = {
        "train_auc": metrics.get("train_auc"),
        "validation_auc": metrics.get("validation_auc"),
        "train_accuracy": metrics.get("train_accuracy"),
        "validation_accuracy": metrics.get("validation_accuracy"),
        "train_f1": metrics.get("train_f1"),
        "validation_f1": metrics.get("validation_f1"),
        "best_iteration": metrics.get("best_iteration"),
        "n_features": metrics.get("n_features"),
        "n_samples_train": metrics.get("n_samples_train"),
        "n_samples_validation": metrics.get("n_samples_validation"),
    }

    # 提取模型信息
    model_path_str = payload.get("model_path", "")
    model_type = payload.get("model_type", "lightgbm")
    duration_seconds = float(payload.get("duration_seconds", 0) or 0)
    created_at = payload.get("generated_at", "")

    result = {
        "model_path": model_path_str,
        "model_type": model_type,
        "training_curve": training_curve,
        "feature_importance": feature_importance,
        "metrics": training_metrics,
        "duration_seconds": duration_seconds,
        "created_at": created_at,
    }

    return _success(result, {"source": "ml-training", "status": "available"})
