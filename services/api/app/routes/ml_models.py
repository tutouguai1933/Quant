"""ML 模型管理路由。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header

from services.api.app.core.settings import Settings
from services.api.app.services.auth_service import auth_service


router = APIRouter(prefix="/api/v1/ml/models", tags=["ml-models"])


def _success(data: dict | None, meta: dict | None = None) -> dict:
    return {"data": data, "error": None, "meta": meta or {}}


def _error(code: str, message: str) -> dict:
    return {"data": None, "error": {"code": code, "message": message}, "meta": {}}


@router.get("")
def list_ml_models(
    limit: int = 20,
    stage: str | None = None,
) -> dict:
    """列出 ML 模型版本。"""
    from services.worker.model_registry import get_model_registry

    registry = get_model_registry()
    models = registry.list_models(limit=limit, stage=stage)

    return _success({
        "models": [
            {
                "version_id": m.version_id,
                "model_type": m.model_type,
                "model_path": str(m.model_path),
                "metrics": m.metrics,
                "training_context": m.training_context,
                "tags": m.tags,
                "stage": m.stage,
                "created_at": m.created_at.isoformat(),
                "updated_at": m.updated_at.isoformat(),
                "description": m.description,
            }
            for m in models
        ],
        "total": len(models),
    })


# 注意：特定路径必须在参数化路径之前定义
@router.get("/production")
def get_production_model() -> dict:
    """获取当前生产模型。"""
    from services.worker.model_registry import get_model_registry

    registry = get_model_registry()
    model = registry.get_production_model()

    if model is None:
        return _success(None, {"status": "no_production_model"})

    return _success({
        "version_id": model.version_id,
        "model_type": model.model_type,
        "model_path": str(model.model_path),
        "metrics": model.metrics,
        "training_context": model.training_context,
        "tags": model.tags,
        "stage": model.stage,
        "created_at": model.created_at.isoformat(),
        "updated_at": model.updated_at.isoformat(),
        "description": model.description,
    })


@router.get("/compare")
def compare_ml_models(
    a: str,
    b: str,
) -> dict:
    """比较两个 ML 模型版本。"""
    from services.worker.model_registry import get_model_registry

    registry = get_model_registry()
    comparison = registry.compare(a, b)

    if comparison is None:
        return _error("comparison_failed", f"无法比较模型 {a} 和 {b}")

    return _success({
        "version_a": comparison.version_a,
        "version_b": comparison.version_b,
        "metrics_diff": comparison.metrics_diff,
        "winner": comparison.winner,
        "recommendation": comparison.recommendation,
    })


@router.get("/{version_id}")
def get_ml_model(version_id: str) -> dict:
    """获取指定 ML 模型版本。"""
    from services.worker.model_registry import get_model_registry

    registry = get_model_registry()
    model = registry.get_model(version_id)

    if model is None:
        return _error("model_not_found", f"模型 {version_id} 不存在")

    return _success({
        "version_id": model.version_id,
        "model_type": model.model_type,
        "model_path": str(model.model_path),
        "metrics": model.metrics,
        "training_context": model.training_context,
        "tags": model.tags,
        "stage": model.stage,
        "created_at": model.created_at.isoformat(),
        "updated_at": model.updated_at.isoformat(),
        "description": model.description,
    })


@router.post("/{version_id}/promote")
def promote_ml_model(
    version_id: str,
    stage: str,
    token: str = "",
    authorization: str = Header(""),
) -> dict:
    """提升 ML 模型到指定阶段。需要控制平面认证。"""
    auth_service.require_control_plane_access(auth_service.resolve_access_token(token, authorization))

    from services.worker.model_registry import get_model_registry

    if stage not in ("staging", "production", "archived"):
        return _error("invalid_stage", f"无效的阶段: {stage}，必须是 staging/production/archived")

    registry = get_model_registry()
    success = registry.promote(version_id, stage)

    if not success:
        return _error("promote_failed", f"无法将模型 {version_id} 提升到 {stage}")

    return _success({"success": True, "version_id": version_id, "stage": stage})


@router.delete("/{version_id}")
def delete_ml_model(
    version_id: str,
    token: str = "",
    authorization: str = Header(""),
) -> dict:
    """删除 ML 模型版本。需要控制平面认证。"""
    auth_service.require_control_plane_access(auth_service.resolve_access_token(token, authorization))

    from services.worker.model_registry import get_model_registry

    registry = get_model_registry()
    success = registry.delete(version_id)

    if not success:
        return _error("delete_failed", f"无法删除模型 {version_id}，可能不存在或为生产模型")

    return _success({"success": True, "version_id": version_id})
