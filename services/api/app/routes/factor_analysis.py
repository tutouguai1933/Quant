"""因子分析API路由。

提供以下接口:
- GET /api/v1/factor/analysis - 因子贡献分析
- GET /api/v1/factor/correlation - 相关性矩阵
- GET /api/v1/factor/effectiveness - 有效性评分
- GET /api/v1/factor/performance - 因子表现汇总
"""

from __future__ import annotations

from typing import Any

from services.api.app.services.factor_analysis_service import factor_analysis_service
from services.api.app.services.auth_service import auth_service


try:
    from fastapi import APIRouter, Header
except ImportError:
    class APIRouter:  # pragma: no cover - lightweight local fallback
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

    def Header(default: str = "") -> str:  # pragma: no cover - fallback stub
        return default


router = APIRouter(prefix="/api/v1/factor", tags=["factor-analysis"])


def _success(data: dict, meta: dict | None = None) -> dict:
    return {"data": data, "error": None, "meta": meta or {}}


def _error(code: str, message: str, meta: dict | None = None) -> dict:
    return {"data": None, "error": {"code": code, "message": message}, "meta": meta or {}}


def _build_meta(action: str, **kwargs: object) -> dict[str, object]:
    """构建统一的元数据结构。"""
    meta: dict[str, object] = {
        "source": "control-plane-api",
        "action": action,
    }
    meta.update(kwargs)
    return meta


@router.get("")
def get_factor_status() -> dict:
    """获取因子分析服务状态。"""
    summary = factor_analysis_service.get_factor_performance_summary()
    return _success(summary, _build_meta("status"))


@router.get("/analysis")
def get_factor_analysis(strategy_id: str = "") -> dict:
    """分析各因子对收益的贡献。

    Args:
        strategy_id: 策略标识（symbol或strategy名称）
    """
    if not strategy_id.strip():
        strategy_id = "default"

    result = factor_analysis_service.analyze_factor_contribution(strategy_id.strip())
    return _success(
        {"analysis": result.to_dict()},
        _build_meta(
            "factor-analysis",
            strategy_id=result.strategy_id,
            factor_count=len(result.contributions),
            top_factors=result.top_factors,
        ),
    )


@router.get("/correlation")
def get_factor_correlation() -> dict:
    """计算因子相关性矩阵。"""
    result = factor_analysis_service.calculate_factor_correlation()
    return _success(
        {"correlation": result.to_dict()},
        _build_meta(
            "factor-correlation",
            factor_count=len(result.factors),
        ),
    )


@router.get("/effectiveness")
def get_factor_effectiveness(period: str = "30d") -> dict:
    """评估因子有效性。

    Args:
        period: 评估周期，如 7d, 30d, 90d
    """
    if period not in ["7d", "30d", "90d"]:
        period = "30d"

    results = factor_analysis_service.evaluate_factor_effectiveness(period)
    return _success(
        {"effectiveness": [r.to_dict() for r in results]},
        _build_meta(
            "factor-effectiveness",
            period=period,
            factor_count=len(results),
        ),
    )


@router.get("/performance")
def get_factor_performance_summary() -> dict:
    """获取因子表现汇总。"""
    summary = factor_analysis_service.get_factor_performance_summary()
    return _success(
        {"summary": summary},
        _build_meta("factor-performance-summary"),
    )