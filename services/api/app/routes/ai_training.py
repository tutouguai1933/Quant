"""AI训练数据收集API路由。

提供以下端点：
- POST /api/v1/ai/training/collect - 收集当前状态样本
- GET /api/v1/ai/training/samples - 获取已收集样本列表
- POST /api/v1/ai/training/export - 导出训练数据集
- DELETE /api/v1/ai/training/clear - 清空样本数据
"""

from __future__ import annotations

from datetime import date
from typing import Any

from services.api.app.services.ai.training_data_service import training_data_service
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

        def delete(self, *args, **kwargs):
            def decorator(func):
                return func
            return decorator

    def Header(default=""):  # pragma: no cover
        return default


router = APIRouter(prefix="/api/v1/ai/training", tags=["ai-training"])


def _success(data: dict[str, Any], meta: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"data": data, "error": None, "meta": meta or {}}


def _unauthorized() -> dict[str, Any]:
    return {
        "data": None,
        "error": {"code": "unauthorized", "message": "需要登录才能访问"},
        "meta": {"source": "ai-training-service"},
    }


def _error(code: str, message: str, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "data": None,
        "error": {"code": code, "message": message},
        "meta": meta or {},
    }


@router.post("/collect")
def collect_sample(
    data: dict[str, Any] = None,
    token: str = "",
    authorization: str = Header(""),
) -> dict[str, Any]:
    """收集当前状态样本。

    Args:
        data: 包含以下字段：
            - symbol: 交易标的符号（必需）
            - candles: K线数据列表（必需）
            - indicators: 技术指标数据（可选）
            - position_info: 持仓信息（可选）
            - source_strategy: 来源策略名称（可选）

    Returns:
        收集的样本信息
    """
    try:
        auth_service.require_control_plane_access(
            auth_service.resolve_access_token(token, authorization)
        )
    except PermissionError:
        return _unauthorized()

    if data is None:
        data = {}

    symbol = data.get("symbol", "")
    if not symbol or not symbol.strip():
        return _error("invalid_request", "symbol 参数必须提供")

    candles = data.get("candles", [])
    if not candles:
        return _error("invalid_request", "candles 参数必须提供且非空")

    indicators = data.get("indicators")
    position_info = data.get("position_info")
    source_strategy = data.get("source_strategy", "")

    try:
        sample = training_data_service.collect_sample(
            symbol=symbol.strip(),
            candles=candles,
            indicators=indicators,
            position_info=position_info,
            source_strategy=source_strategy,
        )
    except Exception as e:
        return _error("collection_failed", f"样本收集失败: {str(e)}")

    return _success(
        {
            "sample": sample.to_dict(),
            "total_samples": training_data_service.get_sample_count(),
        },
        {
            "source": "ai-training-service",
            "action": "collect_sample",
            "symbol": sample.symbol,
        },
    )


@router.get("/samples")
def get_samples(
    symbol: str = "",
    token: str = "",
    authorization: str = Header(""),
) -> dict[str, Any]:
    """获取已收集样本列表。

    Args:
        symbol: 交易标的符号（可选，不提供则返回所有符号的统计）

    Returns:
        样本统计信息
    """
    try:
        auth_service.require_control_plane_access(
            auth_service.resolve_access_token(token, authorization)
        )
    except PermissionError:
        return _unauthorized()

    if symbol and symbol.strip():
        symbol_key = symbol.strip().upper()
        count = training_data_service.get_sample_count(symbol_key)
        samples_data = []
        for s in training_data_service._samples.get(symbol_key, []):
            samples_data.append({
                "timestamp": s.timestamp.isoformat(),
                "symbol": s.symbol,
                "has_label": s.label is not None,
                "has_outcome": s.outcome is not None,
                "source_strategy": s.metadata.source_strategy,
                "data_quality": s.metadata.data_quality,
            })
        return _success(
            {
                "symbol": symbol_key,
                "count": count,
                "samples": samples_data,
            },
            {"source": "ai-training-service"},
        )

    statistics = training_data_service.get_statistics()
    return _success(
        {
            "total_samples": statistics["total_samples"],
            "symbols": statistics["symbols"],
            "buffer_size": statistics["buffer_size"],
            "state_dimension_means": statistics["state_dimension_means"],
        },
        {"source": "ai-training-service"},
    )


@router.post("/export")
def export_dataset(
    data: dict[str, Any] = None,
    token: str = "",
    authorization: str = Header(""),
) -> dict[str, Any]:
    """导出训练数据集。

    Args:
        data: 包含以下字段：
            - symbols: 要导出的符号列表（可选，默认全部）
            - start_date: 开始日期 YYYY-MM-DD（可选）
            - end_date: 结束日期 YYYY-MM-DD（可选）
            - format: 导出格式（可选，默认json）

    Returns:
        导出文件路径和样本数量
    """
    try:
        auth_service.require_control_plane_access(
            auth_service.resolve_access_token(token, authorization)
        )
    except PermissionError:
        return _unauthorized()

    if data is None:
        data = {}

    symbols = data.get("symbols")
    start_date_str = data.get("start_date")
    end_date_str = data.get("end_date")
    export_format = data.get("format", "json")

    start_date = None
    if start_date_str:
        try:
            start_date = date.fromisoformat(start_date_str)
        except ValueError:
            return _error("invalid_request", "start_date 格式无效，请使用 YYYY-MM-DD")

    end_date = None
    if end_date_str:
        try:
            end_date = date.fromisoformat(end_date_str)
        except ValueError:
            return _error("invalid_request", "end_date 格式无效，请使用 YYYY-MM-DD")

    try:
        filepath = training_data_service.export_dataset(
            symbols=symbols,
            start_date=start_date,
            end_date=end_date,
            format=export_format,
        )
    except Exception as e:
        return _error("export_failed", f"导出失败: {str(e)}")

    if not filepath:
        return _error("no_data", "没有可导出的训练样本")

    return _success(
        {
            "filepath": filepath,
            "format": export_format,
            "symbols": symbols,
            "start_date": start_date_str,
            "end_date": end_date_str,
        },
        {
            "source": "ai-training-service",
            "action": "export_dataset",
        },
    )


@router.delete("/clear")
def clear_samples(
    symbol: str = "",
    token: str = "",
    authorization: str = Header(""),
) -> dict[str, Any]:
    """清空样本数据。

    Args:
        symbol: 交易标的符号（可选，不提供则清空所有）

    Returns:
        清除的样本数量
    """
    try:
        auth_service.require_control_plane_access(
            auth_service.resolve_access_token(token, authorization)
        )
    except PermissionError:
        return _unauthorized()

    if symbol and symbol.strip():
        cleared_count = training_data_service.clear_samples(symbol.strip())
    else:
        cleared_count = training_data_service.clear_samples()

    return _success(
        {
            "cleared_count": cleared_count,
            "symbol": symbol.strip().upper() if symbol and symbol.strip() else "ALL",
        },
        {
            "source": "ai-training-service",
            "action": "clear_samples",
        },
    )