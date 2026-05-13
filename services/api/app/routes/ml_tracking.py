"""ML 预测实盘追踪路由。"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/ml/tracking", tags=["ml-tracking"])


def _success(data: dict | None, meta: dict | None = None) -> dict:
    return {"data": data, "error": None, "meta": meta or {}}


def _error(code: str, message: str) -> dict:
    return {"data": None, "error": {"code": code, "message": message}, "meta": {}}


@router.get("/calibration")
def get_calibration() -> dict:
    """获取 ML 预测校准分析。"""
    try:
        from services.worker.ml_prediction_tracker import get_prediction_tracker
        tracker = get_prediction_tracker()
        calibration = tracker.get_calibration()
        return _success({
            "total_predictions": calibration.total_predictions,
            "completed_predictions": calibration.completed_predictions,
            "win_rate": calibration.win_rate,
            "mean_return_pct": calibration.mean_return_pct,
            "brier_score": calibration.brier_score,
            "probability_buckets": calibration.probability_buckets,
        })
    except Exception as e:
        return _error("calibration_error", str(e))


@router.get("/records")
def get_records(limit: int = 50) -> dict:
    """获取最近的预测记录。"""
    try:
        from services.worker.ml_prediction_tracker import get_prediction_tracker
        tracker = get_prediction_tracker()
        records = tracker.get_recent_records(limit=limit)
        return _success({"items": records, "count": len(records)})
    except Exception as e:
        return _error("records_error", str(e))


@router.get("/ab-comparison")
def get_ab_comparison() -> dict:
    """获取 ML vs 启发式 A/B 对比。"""
    try:
        from services.worker.ml_prediction_tracker import get_prediction_tracker
        tracker = get_prediction_tracker()
        comparison = tracker.get_ab_comparison()
        return _success(comparison)
    except Exception as e:
        return _error("comparison_error", str(e))


@router.post("/outcome")
def record_outcome(symbol: str, return_pct: float, holding_hours: float | None = None) -> dict:
    """记录预测的实际结果。"""
    try:
        from services.worker.ml_prediction_tracker import get_prediction_tracker
        tracker = get_prediction_tracker()
        ok = tracker.record_outcome_by_symbol(
            symbol=symbol,
            return_pct=return_pct,
            holding_hours=holding_hours,
        )
        return _success({"recorded": ok})
    except Exception as e:
        return _error("outcome_error", str(e))
