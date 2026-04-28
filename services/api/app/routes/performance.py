"""性能监控路由。

提供API响应时间和交易延迟的监控数据。
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from services.api.app.services.performance_monitor_service import (
    performance_monitor_service,
    PerformanceConfig,
)

router = APIRouter(prefix="/api/v1", tags=["performance"])


def _success(data: Any, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    """构建成功响应。"""
    return {"data": data, "error": None, "meta": meta or {}}


def _error(message: str, code: str = "PERFORMANCE_ERROR") -> dict[str, Any]:
    """构建错误响应。"""
    return {"data": None, "error": {"message": message, "code": code}, "meta": {}}


@router.get("/performance")
def get_performance() -> dict[str, Any]:
    """获取性能统计数据。

    返回API响应时间和交易延迟的完整统计信息。

    Returns:
        data: 包含API和交易性能指标的字典
            - timestamp: 时间戳
            - uptime_seconds: 服务运行时间
            - config: 配置信息
            - api: API性能指标
            - trade: 交易性能指标
            - alerts: 告警统计
    """
    metrics = performance_monitor_service.get_performance_metrics()
    return _success(metrics)


@router.get("/performance/summary")
def get_performance_summary() -> dict[str, Any]:
    """获取性能统计摘要。

    返回关键性能指标的简要摘要。

    Returns:
        data: 性能摘要
            - api_total_requests: API总请求数
            - api_avg_response_ms: API平均响应时间
            - api_max_response_ms: API最大响应时间
            - api_slow_requests: API慢请求数
            - trade_total_orders: 交易总订单数
            - trade_avg_latency_ms: 交易平均延迟
            - trade_max_latency_ms: 交易最大延迟
            - trade_slow_orders: 交易慢订单数
            - alert_count: 告警次数
            - uptime_seconds: 运行时间
    """
    metrics = performance_monitor_service.get_performance_metrics()

    summary = {
        "api_total_requests": metrics["api"]["total_requests"],
        "api_avg_response_ms": metrics["api"]["overall_avg_ms"],
        "api_max_response_ms": metrics["api"]["max_response_ms"],
        "api_slow_requests": metrics["api"]["total_slow_requests"],
        "trade_total_orders": metrics["trade"]["total_orders"],
        "trade_avg_latency_ms": metrics["trade"]["overall_avg_ms"],
        "trade_max_latency_ms": metrics["trade"]["max_latency_ms"],
        "trade_slow_orders": metrics["trade"]["total_slow_orders"],
        "alert_count": metrics["alerts"]["total_count"],
        "uptime_seconds": metrics["uptime_seconds"],
        "config": metrics["config"],
    }

    return _success(summary)


@router.get("/performance/alerts")
def get_performance_alerts(
    threshold_ms: float | None = Query(
        None,
        description="自定义阈值（毫秒），默认使用配置值",
    ),
) -> dict[str, Any]:
    """获取超时告警列表。

    检查并返回超过阈值的端点和订单类型。

    Args:
        threshold_ms: 自定义阈值（可选）

    Returns:
        data: 包含告警信息的字典
            - slow_endpoints: 慢端点列表
            - total_count: 总告警数
    """
    slow_endpoints = performance_monitor_service.alert_on_slow_response(threshold_ms)

    return _success(
        {
            "slow_endpoints": slow_endpoints,
            "total_count": len(slow_endpoints),
            "threshold_ms": threshold_ms,
        }
    )


@router.get("/performance/api")
def get_api_performance() -> dict[str, Any]:
    """获取API性能指标。

    返回所有API端点的详细性能数据。

    Returns:
        data: API性能指标
            - total_requests: 总请求数
            - total_slow_requests: 慢请求数
            - max_response_ms: 最大响应时间
            - overall_avg_ms: 总体平均响应时间
            - endpoints: 各端点详细指标列表
    """
    metrics = performance_monitor_service.get_performance_metrics()
    return _success(metrics["api"])


@router.get("/performance/trade")
def get_trade_performance() -> dict[str, Any]:
    """获取交易性能指标。

    返回所有订单类型的详细延迟数据。

    Returns:
        data: 交易性能指标
            - total_orders: 总订单数
            - total_slow_orders: 慢订单数
            - max_latency_ms: 最大延迟
            - overall_avg_ms: 总体平均延迟
            - order_types: 各订单类型详细指标列表
    """
    metrics = performance_monitor_service.get_performance_metrics()
    return _success(metrics["trade"])


@router.post("/performance/reset")
def reset_performance_metrics() -> dict[str, Any]:
    """重置性能指标。

    清除所有性能统计数据并重新开始统计。

    Returns:
        data: 操作结果
    """
    performance_monitor_service.reset_metrics()
    return _success(
        {
            "message": "性能指标已重置",
            "timestamp": performance_monitor_service.get_performance_metrics()["timestamp"],
        }
    )


@router.get("/performance/config")
def get_performance_config() -> dict[str, Any]:
    """获取性能监控配置。

    Returns:
        data: 配置信息
            - api_latency_threshold_ms: API响应阈值
            - trade_latency_threshold_ms: 交易延迟阈值
            - log_interval_seconds: 日志间隔
            - enable_alerts: 是否启用告警
    """
    config = performance_monitor_service.config
    return _success(
        {
            "api_latency_threshold_ms": config.api_latency_threshold_ms,
            "trade_latency_threshold_ms": config.trade_latency_threshold_ms,
            "log_interval_seconds": config.log_interval_seconds,
            "max_records_per_endpoint": config.max_records_per_endpoint,
            "enable_alerts": config.enable_alerts,
        }
    )


@router.put("/performance/config")
def update_performance_config(
    api_latency_threshold_ms: float | None = Query(
        None,
        description="API响应阈值（毫秒）",
    ),
    trade_latency_threshold_ms: float | None = Query(
        None,
        description="交易延迟阈值（毫秒）",
    ),
    enable_alerts: bool | None = Query(
        None,
        description="是否启用告警",
    ),
) -> dict[str, Any]:
    """更新性能监控配置。

    Args:
        api_latency_threshold_ms: API响应阈值
        trade_latency_threshold_ms: 交易延迟阈值
        enable_alerts: 是否启用告警

    Returns:
        data: 更新后的配置
    """
    config = performance_monitor_service.config

    if api_latency_threshold_ms is not None:
        config.api_latency_threshold_ms = api_latency_threshold_ms
    if trade_latency_threshold_ms is not None:
        config.trade_latency_threshold_ms = trade_latency_threshold_ms
    if enable_alerts is not None:
        config.enable_alerts = enable_alerts

    return _success(
        {
            "message": "配置已更新",
            "config": {
                "api_latency_threshold_ms": config.api_latency_threshold_ms,
                "trade_latency_threshold_ms": config.trade_latency_threshold_ms,
                "enable_alerts": config.enable_alerts,
            },
        }
    )