"""评分系统API路由。

提供评分计算、因子管理、阈值设置等API端点。
"""

from __future__ import annotations

from typing import Any

from services.api.app.services.scoring.scoring_service import scoring_service
from services.api.app.services.auth_service import auth_service

try:
    from fastapi import APIRouter, Header
except ImportError:
    class APIRouter:  # pragma: no cover
        def __init__(self, *args, **kwargs) -> None:
            self.args = args
            self.kwargs = kwargs

        def get(self, *args, **kwargs):
            def decorator(func):
                return func
            return decorator

        def post(self, *args, **kwargs):
            def decorator(func):
                return func
            return decorator

    def Header(default: str = "") -> str:  # pragma: no cover
        return default


router = APIRouter(prefix="/api/v1/scoring", tags=["scoring"])


def _success(data: dict, meta: dict | None = None) -> dict:
    return {"data": data, "error": None, "meta": meta or {}}


def _error(code: str, message: str, meta: dict | None = None) -> dict:
    return {"data": None, "error": {"code": code, "message": message}, "meta": meta or {}}


def _unauthorized() -> dict:
    return _error("unauthorized", "authentication required", {"source": "control-plane-api"})


@router.get("/current")
def get_current_score(symbol: str = "") -> dict:
    """获取当前评分。

    如果symbol参数为空，返回所有已评分标的的最新结果。
    """
    if not symbol.strip():
        # 返回所有已评分标的
        all_scores = scoring_service._last_scores
        return _success(
            {"items": [s.to_dict() for s in all_scores.values()]},
            {"source": "control-plane-api", "count": len(all_scores)},
        )

    result = scoring_service.get_current_score(symbol)
    if result is None:
        return _success(
            {"item": None},
            {"source": "control-plane-api", "symbol": symbol.strip().upper(), "status": "no_score_available"},
        )

    return _success(
        {"item": result.to_dict()},
        {"source": "control-plane-api", "symbol": symbol.strip().upper(), "passed": result.passed_threshold},
    )


@router.get("/calculate")
def calculate_score(symbol: str, data: dict[str, Any] = {}) -> dict:
    """实时计算评分。

    根据提供的市场数据实时计算评分。
    """
    if not symbol.strip():
        return _error("invalid_request", "symbol is required")

    result = scoring_service.calculate_score(symbol, data)
    return _success(
        {"item": result.to_dict()},
        {
            "source": "control-plane-api",
            "symbol": result.symbol,
            "passed": result.passed_threshold,
            "threshold": result.threshold,
        },
    )


@router.get("/history")
def get_score_history(symbol: str, limit: int = 10) -> dict:
    """获取评分历史。"""
    if not symbol.strip():
        return _error("invalid_request", "symbol is required")

    if limit < 1 or limit > 100:
        limit = 10

    history = scoring_service.get_score_history(symbol, limit)
    return _success(
        {"items": [h.to_dict() for h in history]},
        {
            "source": "control-plane-api",
            "symbol": symbol.strip().upper(),
            "count": len(history),
            "limit": limit,
        },
    )


@router.get("/factors")
def get_factors() -> dict:
    """获取因子列表和权重配置。"""
    factors = scoring_service.get_factors()
    weights_config = scoring_service.get_factor_weights()

    return _success(
        {
            "factors": factors,
            "weights": weights_config["weights"],
            "enabled_factors": weights_config["enabled_factors"],
            "min_entry_score": weights_config["min_entry_score"],
        },
        {"source": "control-plane-api", "count": len(factors)},
    )


@router.post("/factors")
def update_factor_weights(
    payload: dict[str, Any],
    token: str = "",
    authorization: str = Header(""),
) -> dict:
    """更新因子权重。

    需要认证。
    """
    try:
        auth_service.require_control_plane_access(
            auth_service.resolve_access_token(token, authorization)
        )
    except PermissionError:
        return _unauthorized()

    weights = payload.get("weights", {})
    if not isinstance(weights, dict):
        return _error("invalid_request", "weights must be a dictionary")

    # 验证权重值
    for name, weight in weights.items():
        if not isinstance(name, str):
            return _error("invalid_request", "factor name must be string")
        if not isinstance(weight, (int, float)):
            return _error("invalid_request", f"weight for {name} must be numeric")
        if weight < 0 or weight > 5.0:
            return _error("invalid_request", f"weight for {name} must be in range [0, 5.0]")

    success = scoring_service.set_factor_weights(weights)
    if not success:
        return _error("update_failed", "failed to update factor weights")

    return _success(
        {"updated": True, "weights": weights},
        {"source": "control-plane-api", "action": "update_weights"},
    )


@router.post("/factors/enable")
def enable_factor(
    payload: dict[str, Any],
    token: str = "",
    authorization: str = Header(""),
) -> dict:
    """启用因子。"""
    try:
        auth_service.require_control_plane_access(
            auth_service.resolve_access_token(token, authorization)
        )
    except PermissionError:
        return _unauthorized()

    factor_name = payload.get("factor_name", "")
    if not factor_name.strip():
        return _error("invalid_request", "factor_name is required")

    success = scoring_service.enable_factor(factor_name.strip())
    return _success(
        {"enabled": success, "factor_name": factor_name.strip()},
        {"source": "control-plane-api", "action": "enable_factor"},
    )


@router.post("/factors/disable")
def disable_factor(
    payload: dict[str, Any],
    token: str = "",
    authorization: str = Header(""),
) -> dict:
    """禁用因子。"""
    try:
        auth_service.require_control_plane_access(
            auth_service.resolve_access_token(token, authorization)
        )
    except PermissionError:
        return _unauthorized()

    factor_name = payload.get("factor_name", "")
    if not factor_name.strip():
        return _error("invalid_request", "factor_name is required")

    success = scoring_service.disable_factor(factor_name.strip())
    return _success(
        {"disabled": success, "factor_name": factor_name.strip()},
        {"source": "control-plane-api", "action": "disable_factor"},
    )


@router.post("/threshold")
def set_threshold(
    payload: dict[str, Any],
    token: str = "",
    authorization: str = Header(""),
) -> dict:
    """设置入场阈值。"""
    try:
        auth_service.require_control_plane_access(
            auth_service.resolve_access_token(token, authorization)
        )
    except PermissionError:
        return _unauthorized()

    threshold = payload.get("threshold")
    if threshold is None:
        return _error("invalid_request", "threshold is required")

    if not isinstance(threshold, (int, float)):
        return _error("invalid_request", "threshold must be numeric")

    if threshold < 0 or threshold > 1.0:
        return _error("invalid_request", "threshold must be in range [0, 1.0]")

    success = scoring_service.set_min_entry_score(float(threshold))
    if not success:
        return _error("update_failed", "failed to update threshold")

    return _success(
        {"updated": True, "threshold": threshold},
        {"source": "control-plane-api", "action": "set_threshold"},
    )


@router.get("/threshold")
def get_threshold() -> dict:
    """获取当前入场阈值。"""
    threshold = scoring_service.get_min_entry_score()
    return _success(
        {"threshold": threshold},
        {"source": "control-plane-api"},
    )


@router.get("/config")
def get_config() -> dict:
    """获取完整评分配置。"""
    config = scoring_service.get_config()
    return _success(
        {"config": config},
        {"source": "control-plane-api"},
    )


@router.post("/evaluate")
def evaluate_entry(
    payload: dict[str, Any],
) -> dict:
    """评估入场决策。

    根据评分结果判断是否应该入场。
    """
    symbol = payload.get("symbol", "")
    if not symbol.strip():
        return _error("invalid_request", "symbol is required")

    data = payload.get("data", {})
    if not isinstance(data, dict):
        return _error("invalid_request", "data must be a dictionary")

    should_enter, result = scoring_service.should_enter(symbol, data)

    return _success(
        {
            "should_enter": should_enter,
            "score": result.to_dict(),
        },
        {
            "source": "control-plane-api",
            "symbol": result.symbol,
            "decision": "enter" if should_enter else "wait",
        },
    )