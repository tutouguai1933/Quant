"""性能监控服务。

监控API响应时间和交易延迟，支持超时告警。
"""

from __future__ import annotations

import functools
import logging
import os
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from statistics import mean, median
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

# 类型变量用于装饰器
F = TypeVar("F", bound=Callable[..., Any])


class LatencyType(str, Enum):
    """延迟类型。"""

    API = "api"
    TRADE = "trade"


@dataclass
class PerformanceConfig:
    """性能监控配置。"""

    api_latency_threshold_ms: float = 500.0
    trade_latency_threshold_ms: float = 2000.0
    log_interval_seconds: int = 60
    max_records_per_endpoint: int = 1000
    enable_alerts: bool = True

    @classmethod
    def from_env(cls) -> "PerformanceConfig":
        """从环境变量读取配置。"""
        api_threshold = float(os.getenv("QUANT_API_LATENCY_THRESHOLD_MS", "500"))
        trade_threshold = float(os.getenv("QUANT_TRADE_LATENCY_THRESHOLD_MS", "2000"))
        log_interval = int(os.getenv("QUANT_PERFORMANCE_LOG_INTERVAL", "60"))
        max_records = int(os.getenv("QUANT_PERFORMANCE_MAX_RECORDS", "1000"))
        enable_alerts = os.getenv("QUANT_PERFORMANCE_ENABLE_ALERTS", "true").lower() == "true"

        return cls(
            api_latency_threshold_ms=api_threshold,
            trade_latency_threshold_ms=trade_threshold,
            log_interval_seconds=log_interval,
            max_records_per_endpoint=max_records,
            enable_alerts=enable_alerts,
        )


@dataclass
class LatencyRecord:
    """延迟记录。"""

    endpoint: str
    duration_ms: float
    timestamp: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class EndpointMetrics:
    """端点性能指标。"""

    endpoint: str
    count: int = 0
    total_ms: float = 0.0
    min_ms: float = float("inf")
    max_ms: float = 0.0
    durations: list[float] = field(default_factory=list)
    slow_count: int = 0  # 超过阈值的次数

    @property
    def avg_ms(self) -> float:
        """计算平均延迟。"""
        return self.total_ms / self.count if self.count > 0 else 0.0

    @property
    def p50_ms(self) -> float:
        """计算P50延迟。"""
        if not self.durations:
            return 0.0
        return median(self.durations)

    @property
    def p95_ms(self) -> float:
        """计算P95延迟。"""
        if not self.durations:
            return 0.0
        sorted_durations = sorted(self.durations)
        index = int(len(sorted_durations) * 0.95)
        return sorted_durations[min(index, len(sorted_durations) - 1)]

    @property
    def p99_ms(self) -> float:
        """计算P99延迟。"""
        if not self.durations:
            return 0.0
        sorted_durations = sorted(self.durations)
        index = int(len(sorted_durations) * 0.99)
        return sorted_durations[min(index, len(sorted_durations) - 1)]


class PerformanceMonitorService:
    """性能监控服务。"""

    def __init__(self, config: PerformanceConfig | None = None) -> None:
        self._config = config or PerformanceConfig.from_env()
        self._api_metrics: dict[str, EndpointMetrics] = defaultdict(
            lambda: EndpointMetrics(endpoint="")
        )
        self._trade_metrics: dict[str, EndpointMetrics] = defaultdict(
            lambda: EndpointMetrics(endpoint="")
        )
        self._alert_count: int = 0
        self._last_log_time: float = time.time()
        self._lock = threading.RLock()
        self._start_time: float = time.time()

        # 延迟导入以避免循环依赖
        self._alert_service: Any = None

    @property
    def config(self) -> PerformanceConfig:
        """返回当前配置。"""
        return self._config

    @property
    def uptime_seconds(self) -> float:
        """返回服务运行时间（秒）。"""
        return time.time() - self._start_time

    def _get_alert_service(self) -> Any:
        """延迟获取告警服务。"""
        if self._alert_service is None:
            try:
                from services.api.app.services.alert_push_service import (
                    alert_push_service,
                    AlertEventType,
                    AlertLevel,
                )

                self._alert_service = alert_push_service
            except ImportError:
                logger.warning("无法导入告警服务，告警功能将被禁用")
        return self._alert_service

    def track_api_latency(
        self,
        endpoint: str,
        duration_ms: float,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """记录API调用耗时。

        Args:
            endpoint: API端点名称
            duration_ms: 耗时（毫秒）
            metadata: 额外元数据
        """
        with self._lock:
            metrics = self._api_metrics[endpoint]
            metrics.endpoint = endpoint
            metrics.count += 1
            metrics.total_ms += duration_ms
            metrics.min_ms = min(metrics.min_ms, duration_ms)
            metrics.max_ms = max(metrics.max_ms, duration_ms)

            # 保留最近的记录用于计算百分位
            metrics.durations.append(duration_ms)
            if len(metrics.durations) > self._config.max_records_per_endpoint:
                metrics.durations = metrics.durations[
                    -self._config.max_records_per_endpoint :
                ]

            # 检查是否超时
            if duration_ms > self._config.api_latency_threshold_ms:
                metrics.slow_count += 1
                logger.warning(
                    "API慢响应: %s 耗时 %.2fms (阈值 %.2fms)",
                    endpoint,
                    duration_ms,
                    self._config.api_latency_threshold_ms,
                )
                self._trigger_slow_alert(
                    LatencyType.API, endpoint, duration_ms, metadata
                )

            # 定期日志记录
            self._maybe_log_metrics()

    def track_trade_latency(
        self,
        order_type: str,
        duration_ms: float,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """记录订单执行延迟。

        Args:
            order_type: 订单类型（如 "market", "limit"）
            duration_ms: 延迟（毫秒）
            metadata: 额外元数据
        """
        with self._lock:
            metrics = self._trade_metrics[order_type]
            metrics.endpoint = order_type
            metrics.count += 1
            metrics.total_ms += duration_ms
            metrics.min_ms = min(metrics.min_ms, duration_ms)
            metrics.max_ms = max(metrics.max_ms, duration_ms)

            # 保留最近的记录用于计算百分位
            metrics.durations.append(duration_ms)
            if len(metrics.durations) > self._config.max_records_per_endpoint:
                metrics.durations = metrics.durations[
                    -self._config.max_records_per_endpoint :
                ]

            # 检查是否超时
            if duration_ms > self._config.trade_latency_threshold_ms:
                metrics.slow_count += 1
                logger.warning(
                    "交易慢执行: %s 耗时 %.2fms (阈值 %.2fms)",
                    order_type,
                    duration_ms,
                    self._config.trade_latency_threshold_ms,
                )
                self._trigger_slow_alert(
                    LatencyType.TRADE, order_type, duration_ms, metadata
                )

            # 定期日志记录
            self._maybe_log_metrics()

    def _trigger_slow_alert(
        self,
        latency_type: LatencyType,
        endpoint: str,
        duration_ms: float,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """触发慢响应告警。"""
        self._alert_count += 1

        if not self._config.enable_alerts:
            return

        try:
            from services.api.app.services.alert_push_service import (
                AlertEventType,
                AlertLevel,
                AlertMessage,
            )

            if latency_type == LatencyType.API:
                threshold = self._config.api_latency_threshold_ms
                title = "API响应超时告警"
                message = f"API端点 {endpoint} 响应时间 {duration_ms:.2f}ms 超过阈值 {threshold:.2f}ms"
            else:
                threshold = self._config.trade_latency_threshold_ms
                title = "交易延迟超时告警"
                message = f"订单类型 {endpoint} 执行延迟 {duration_ms:.2f}ms 超过阈值 {threshold:.2f}ms"

            details = {
                "latency_type": latency_type.value,
                "endpoint": endpoint,
                "duration_ms": duration_ms,
                "threshold_ms": threshold,
                "exceeded_ms": duration_ms - threshold,
            }
            if metadata:
                details["metadata"] = metadata

            alert = AlertMessage(
                event_type=AlertEventType.SYSTEM_ERROR,
                level=AlertLevel.WARNING,
                title=title,
                message=message,
                details=details,
            )

            # 异步推送告警
            import asyncio

            try:
                loop = asyncio.get_running_loop()
                asyncio.create_task(self._push_alert_async(alert))
            except RuntimeError:
                # 没有运行的事件循环，使用同步推送
                self._push_alert_sync(alert)

        except Exception as e:
            logger.error("发送性能告警失败: %s", e)

    def _push_alert_sync(self, alert: Any) -> None:
        """同步推送告警。"""
        alert_service = self._get_alert_service()
        if alert_service:
            alert_service.push_sync(alert)

    async def _push_alert_async(self, alert: Any) -> None:
        """异步推送告警。"""
        alert_service = self._get_alert_service()
        if alert_service:
            await alert_service.push_async(alert)

    def _maybe_log_metrics(self) -> None:
        """定期记录性能指标日志。"""
        current_time = time.time()
        if current_time - self._last_log_time >= self._config.log_interval_seconds:
            self._last_log_time = current_time
            self._log_metrics()

    def _log_metrics(self) -> None:
        """记录性能指标日志。"""
        with self._lock:
            # API指标
            if self._api_metrics:
                logger.info("=== API性能指标 ===")
                for endpoint, metrics in self._api_metrics.items():
                    logger.info(
                        "API %s: 调用=%d, 平均=%.2fms, 最大=%.2fms, P95=%.2fms, 慢响应=%d",
                        endpoint,
                        metrics.count,
                        metrics.avg_ms,
                        metrics.max_ms,
                        metrics.p95_ms,
                        metrics.slow_count,
                    )

            # 交易指标
            if self._trade_metrics:
                logger.info("=== 交易性能指标 ===")
                for order_type, metrics in self._trade_metrics.items():
                    logger.info(
                        "交易 %s: 调用=%d, 平均=%.2fms, 最大=%.2fms, P95=%.2fms, 慢响应=%d",
                        order_type,
                        metrics.count,
                        metrics.avg_ms,
                        metrics.max_ms,
                        metrics.p95_ms,
                        metrics.slow_count,
                    )

            logger.info("总告警次数: %d", self._alert_count)

    def get_performance_metrics(self) -> dict[str, Any]:
        """获取性能统计数据。

        Returns:
            包含API和交易性能指标的字典
        """
        with self._lock:
            # API指标汇总
            api_metrics = []
            total_api_count = 0
            total_api_slow = 0
            api_max_ms = 0.0
            api_avg_sum = 0.0

            for endpoint, metrics in self._api_metrics.items():
                total_api_count += metrics.count
                total_api_slow += metrics.slow_count
                if metrics.max_ms > api_max_ms:
                    api_max_ms = metrics.max_ms
                api_avg_sum += metrics.avg_ms

                api_metrics.append(
                    {
                        "endpoint": endpoint,
                        "count": metrics.count,
                        "avg_ms": round(metrics.avg_ms, 2),
                        "min_ms": round(metrics.min_ms, 2) if metrics.min_ms != float("inf") else 0.0,
                        "max_ms": round(metrics.max_ms, 2),
                        "p50_ms": round(metrics.p50_ms, 2),
                        "p95_ms": round(metrics.p95_ms, 2),
                        "p99_ms": round(metrics.p99_ms, 2),
                        "slow_count": metrics.slow_count,
                    }
                )

            # 交易指标汇总
            trade_metrics = []
            total_trade_count = 0
            total_trade_slow = 0
            trade_max_ms = 0.0
            trade_avg_sum = 0.0

            for order_type, metrics in self._trade_metrics.items():
                total_trade_count += metrics.count
                total_trade_slow += metrics.slow_count
                if metrics.max_ms > trade_max_ms:
                    trade_max_ms = metrics.max_ms
                trade_avg_sum += metrics.avg_ms

                trade_metrics.append(
                    {
                        "order_type": order_type,
                        "count": metrics.count,
                        "avg_ms": round(metrics.avg_ms, 2),
                        "min_ms": round(metrics.min_ms, 2) if metrics.min_ms != float("inf") else 0.0,
                        "max_ms": round(metrics.max_ms, 2),
                        "p50_ms": round(metrics.p50_ms, 2),
                        "p95_ms": round(metrics.p95_ms, 2),
                        "p99_ms": round(metrics.p99_ms, 2),
                        "slow_count": metrics.slow_count,
                    }
                )

            return {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "uptime_seconds": round(self.uptime_seconds, 2),
                "config": {
                    "api_latency_threshold_ms": self._config.api_latency_threshold_ms,
                    "trade_latency_threshold_ms": self._config.trade_latency_threshold_ms,
                    "log_interval_seconds": self._config.log_interval_seconds,
                    "enable_alerts": self._config.enable_alerts,
                },
                "api": {
                    "total_requests": total_api_count,
                    "total_slow_requests": total_api_slow,
                    "max_response_ms": round(api_max_ms, 2),
                    "overall_avg_ms": round(api_avg_sum / len(self._api_metrics), 2) if self._api_metrics else 0.0,
                    "endpoints": api_metrics,
                },
                "trade": {
                    "total_orders": total_trade_count,
                    "total_slow_orders": total_trade_slow,
                    "max_latency_ms": round(trade_max_ms, 2),
                    "overall_avg_ms": round(trade_avg_sum / len(self._trade_metrics), 2) if self._trade_metrics else 0.0,
                    "order_types": trade_metrics,
                },
                "alerts": {
                    "total_count": self._alert_count,
                },
            }

    def alert_on_slow_response(self, threshold_ms: float | None = None) -> list[dict[str, Any]]:
        """检查并返回超时告警列表。

        Args:
            threshold_ms: 自定义阈值（可选，默认使用配置值）

        Returns:
            超过阈值的端点列表
        """
        api_threshold = threshold_ms or self._config.api_latency_threshold_ms
        trade_threshold = threshold_ms or self._config.trade_latency_threshold_ms

        slow_endpoints = []

        with self._lock:
            # 检查API端点
            for endpoint, metrics in self._api_metrics.items():
                if metrics.max_ms > api_threshold or metrics.avg_ms > api_threshold:
                    slow_endpoints.append(
                        {
                            "type": "api",
                            "endpoint": endpoint,
                            "max_ms": round(metrics.max_ms, 2),
                            "avg_ms": round(metrics.avg_ms, 2),
                            "threshold_ms": api_threshold,
                            "slow_count": metrics.slow_count,
                            "severity": "high" if metrics.max_ms > api_threshold * 2 else "medium",
                        }
                    )

            # 检查交易类型
            for order_type, metrics in self._trade_metrics.items():
                if metrics.max_ms > trade_threshold or metrics.avg_ms > trade_threshold:
                    slow_endpoints.append(
                        {
                            "type": "trade",
                            "endpoint": order_type,
                            "max_ms": round(metrics.max_ms, 2),
                            "avg_ms": round(metrics.avg_ms, 2),
                            "threshold_ms": trade_threshold,
                            "slow_count": metrics.slow_count,
                            "severity": "high" if metrics.max_ms > trade_threshold * 2 else "medium",
                        }
                    )

        return slow_endpoints

    def reset_metrics(self) -> None:
        """重置所有性能指标。"""
        with self._lock:
            self._api_metrics.clear()
            self._trade_metrics.clear()
            self._alert_count = 0
            self._start_time = time.time()
            logger.info("性能监控指标已重置")


# 全局实例
performance_monitor_service = PerformanceMonitorService()


def track_api_latency_decorator(endpoint: str) -> Callable[[F], F]:
    """装饰器：自动记录API调用耗时。

    Usage:
        @track_api_latency_decorator("/api/v1/orders")
        async def create_order(...):
            ...
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                duration_ms = (time.time() - start_time) * 1000
                performance_monitor_service.track_api_latency(endpoint, duration_ms)

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                duration_ms = (time.time() - start_time) * 1000
                performance_monitor_service.track_api_latency(endpoint, duration_ms)

        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        return sync_wrapper  # type: ignore

    return decorator


def track_trade_latency_decorator(order_type: str) -> Callable[[F], F]:
    """装饰器：自动记录订单执行延迟。

    Usage:
        @track_trade_latency_decorator("market")
        async def execute_market_order(...):
            ...
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                duration_ms = (time.time() - start_time) * 1000
                performance_monitor_service.track_trade_latency(order_type, duration_ms)

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                duration_ms = (time.time() - start_time) * 1000
                performance_monitor_service.track_trade_latency(order_type, duration_ms)

        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        return sync_wrapper  # type: ignore

    return decorator


class PerformanceContext:
    """性能监控上下文管理器，用于代码块级别的性能追踪。"""

    def __init__(
        self,
        name: str,
        latency_type: LatencyType = LatencyType.API,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self._name = name
        self._latency_type = latency_type
        self._metadata = metadata
        self._start_time: float = 0.0

    def __enter__(self) -> "PerformanceContext":
        self._start_time = time.time()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        duration_ms = (time.time() - self._start_time) * 1000
        if self._latency_type == LatencyType.API:
            performance_monitor_service.track_api_latency(
                self._name, duration_ms, self._metadata
            )
        else:
            performance_monitor_service.track_trade_latency(
                self._name, duration_ms, self._metadata
            )

    async def __aenter__(self) -> "PerformanceContext":
        self._start_time = time.time()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        duration_ms = (time.time() - self._start_time) * 1000
        if self._latency_type == LatencyType.API:
            performance_monitor_service.track_api_latency(
                self._name, duration_ms, self._metadata
            )
        else:
            performance_monitor_service.track_trade_latency(
                self._name, duration_ms, self._metadata
            )