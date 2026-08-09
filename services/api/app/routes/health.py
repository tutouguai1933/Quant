"""Health routes for the Control Plane API.

提供基础健康检查和Docker容器健康监控API。
"""

from __future__ import annotations

import logging
from typing import Any

try:
    from fastapi import APIRouter, Header, Response
except ImportError:
    class APIRouter:  # pragma: no cover - lightweight local fallback
        def __init__(self, *args, **kwargs) -> None:
            self.args = args
            self.kwargs = kwargs

        def get(self, *args, **kwargs):
            def decorator(func):
                return func

            return decorator

    def Header(default=""):  # pragma: no cover
        return default

    class Response:  # pragma: no cover
        def __init__(self, content: str = "", media_type: str = "") -> None:
            self.body = content.encode("utf-8")
            self.media_type = media_type

from services.api.app.routes._helpers import _success, _error
from services.api.app.services.auth_service import auth_service


router = APIRouter(tags=["health"])
_PROCESS_START_TIME_SECONDS = __import__("time").time()


@router.get("/health")
def get_health() -> dict:
    """基础健康检查端点。"""
    return _success({"status": "ok", "service": "control-plane-api"})


@router.get("/healthz")
def get_healthz() -> dict:
    """Kubernetes风格健康检查端点。"""
    return _success({"status": "ok", "service": "control-plane-api"})


@router.get("/metrics")
def get_metrics() -> Response:
    """提供 Prometheus 可抓取的 API 基础存活指标。"""
    import threading
    import time

    # 线程数反映线程堆积（卡死前线程数会飙升）
    thread_count = threading.active_count()

    # 尝试读取进程 CPU/内存（/proc 在容器内可用）
    cpu_usage = ""
    mem_rss = ""
    try:
        with open("/proc/self/status", encoding="utf-8") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    mem_rss = line.split()[1]
    except OSError:
        pass

    lines = [
        "# HELP quant_api_up Control plane API process is serving requests.",
        "# TYPE quant_api_up gauge",
        "quant_api_up 1",
        "# HELP quant_api_process_start_time_seconds API process start time.",
        "# TYPE quant_api_process_start_time_seconds gauge",
        f"quant_api_process_start_time_seconds {_PROCESS_START_TIME_SECONDS:.0f}",
        "# HELP quant_api_threads_active Number of active threads (proxy for thread pool saturation).",
        "# TYPE quant_api_threads_active gauge",
        f"quant_api_threads_active {thread_count}",
    ]
    if mem_rss:
        lines.extend(
            [
                "# HELP quant_api_process_memory_rss_bytes Resident memory in bytes.",
                "# TYPE quant_api_process_memory_rss_bytes gauge",
                f"quant_api_process_memory_rss_bytes {int(mem_rss) * 1024}",
            ]
        )

    # 输出每个端点的延迟统计（卡死前慢请求会在这里留下痕迹）
    try:
        from services.api.app.services.performance_monitor_service import (
            performance_monitor_service,
        )

        for endpoint, metrics in sorted(performance_monitor_service._api_metrics.items()):
            ep = endpoint.replace('"', '\\"')
            lines.extend(
                [
                    f'# HELP quant_api_latency_count_total Requests completed per endpoint.',
                    f'# TYPE quant_api_latency_count_total counter',
                    f'quant_api_latency_count_total{{endpoint="{ep}"}} {metrics.count}',
                    f'# TYPE quant_api_latency_max_seconds gauge',
                    f'quant_api_latency_max_seconds{{endpoint="{ep}"}} {metrics.max_ms / 1000.0:.6f}',
                    f'# TYPE quant_api_latency_avg_seconds gauge',
                    f'quant_api_latency_avg_seconds{{endpoint="{ep}"}} {(metrics.total_ms / metrics.count if metrics.count else 0) / 1000.0:.6f}',
                    f'# TYPE quant_api_slow_count_total counter',
                    f'quant_api_slow_count_total{{endpoint="{ep}"}} {metrics.slow_count}',
                ]
            )
    except Exception:
        pass

    lines.append("")
    return Response(content="\n".join(lines), media_type="text/plain; version=0.0.4")


@router.get("/api/v1/health")
def get_health_status() -> dict:
    """返回所有Docker容器健康状态。

    Returns:
        包含所有监控容器健康状态的响应
    """
    from services.api.app.services.health_monitor_service import health_monitor_service

    try:
        status = health_monitor_service.check_all_services()
        return _success(status)
    except Exception as e:
        return _error(f"健康检查失败: {e}", "HEALTH_CHECK_ERROR")


@router.get("/api/v1/health/cached")
def get_cached_health_status() -> dict:
    """返回缓存的健康状态（快速响应，不触发实时检查）。

    Returns:
        包含缓存健康状态的响应
    """
    from services.api.app.services.health_monitor_service import health_monitor_service

    try:
        status = health_monitor_service.get_cached_status()
        return _success(status)
    except Exception as e:
        return _error(f"获取缓存状态失败: {e}", "HEALTH_CACHE_ERROR")


@router.get("/api/v1/health/{service}")
def get_service_health(service: str) -> dict:
    """单个服务健康状态。

    Args:
        service: 服务/容器名称（如 quant-api, quant-web 等）

    Returns:
        单个容器健康状态响应
    """
    from services.api.app.services.health_monitor_service import (
        health_monitor_service,
        ContainerStatus,
        HealthStatus,
    )

    try:
        info = health_monitor_service.check_container_health(service)
        return _success({
            "name": info.name,
            "status": info.status.value,
            "health": info.health.value,
            "container_id": info.container_id,
            "image": info.image,
            "error": info.error,
            "last_check_at": info.last_check_at,
            "is_healthy": info.status == ContainerStatus.RUNNING and info.health in (HealthStatus.HEALTHY, HealthStatus.NONE),
        })
    except Exception as e:
        return _error(f"健康检查失败: {e}", "HEALTH_CHECK_ERROR")


@router.post("/api/v1/health/monitoring/start")
def start_monitoring(interval_seconds: int = 60, token: str = "", authorization: str = Header("")) -> dict:
    """启动健康监控。需要控制平面认证。

    Args:
        interval_seconds: 监控间隔（秒），默认60

    Returns:
        启动结果
    """
    auth_service.require_control_plane_access(auth_service.resolve_access_token(token, authorization))

    from services.api.app.services.health_monitor_service import health_monitor_service

    try:
        success = health_monitor_service.start_monitoring(interval_seconds)
        if success:
            return _success({
                "status": "started",
                "interval_seconds": interval_seconds,
                "message": "健康监控已启动",
            })
        return _error("健康监控启动失败，可能已在运行中", "MONITORING_START_FAILED")
    except Exception as e:
        return _error(f"启动监控失败: {e}", "MONITORING_ERROR")


@router.post("/api/v1/health/monitoring/stop")
def stop_monitoring(token: str = "", authorization: str = Header("")) -> dict:
    """停止健康监控。需要控制平面认证。

    Returns:
        停止结果
    """
    auth_service.require_control_plane_access(auth_service.resolve_access_token(token, authorization))

    from services.api.app.services.health_monitor_service import health_monitor_service

    try:
        health_monitor_service.stop_monitoring()
        return _success({
            "status": "stopped",
            "message": "健康监控已停止",
        })
    except Exception as e:
        return _error(f"停止监控失败: {e}", "MONITORING_ERROR")


@router.get("/api/v1/health/monitoring/status")
def get_monitoring_status() -> dict:
    """获取监控状态。

    Returns:
        监控状态信息
    """
    from services.api.app.services.health_monitor_service import health_monitor_service

    return _success({
        "active": health_monitor_service.is_monitoring,
        "interval_seconds": health_monitor_service.config.interval_seconds,
        "enabled": health_monitor_service.config.enabled,
        "monitored_containers": health_monitor_service.config.monitored_containers,
        "alert_on_unhealthy": health_monitor_service.config.alert_on_unhealthy,
        "alert_on_exit": health_monitor_service.config.alert_on_exit,
    })


# ==================== 日志管理 API ====================

logger = logging.getLogger(__name__)


@router.get("/api/v1/logs/status")
def get_log_status() -> dict:
    """查看日志大小统计。

    Returns:
        包含各日志目录和文件大小信息的字典
    """
    try:
        from scripts.cleanup_logs import get_log_sizes

        sizes = get_log_sizes()

        return _success({
            "total_size_mb": sizes["total_size_mb"],
            "total_size_bytes": sizes["total_size_bytes"],
            "directories": sizes["directories"],
            "oldest_file": sizes["oldest_file"],
            "largest_file": sizes["largest_file"],
        })
    except ImportError as e:
        logger.error("无法导入 cleanup_logs 模块: %s", e)
        return _error("日志模块未配置", "LOG_MODULE_NOT_FOUND")
    except Exception as e:
        logger.error("获取日志状态失败: %s", e)
        return _error(str(e), "LOG_STATUS_ERROR")


@router.post("/api/v1/logs/cleanup")
def trigger_cleanup(days_to_keep: int = 30, token: str = "", authorization: str = Header("")) -> dict:
    """手动触发日志清理。需要控制平面认证。

    Args:
        days_to_keep: 保留的日志天数，默认 30 天

    Returns:
        清理结果
    """
    auth_service.require_control_plane_access(auth_service.resolve_access_token(token, authorization))

    if days_to_keep < 1:
        return _error("days_to_keep 必须大于 0", "INVALID_DAYS")

    if days_to_keep > 365:
        return _error("days_to_keep 不能超过 365 天", "INVALID_DAYS")

    try:
        from scripts.cleanup_logs import cleanup_old_logs

        result = cleanup_old_logs(days_to_keep)

        logger.info(
            "日志清理完成: 删除 %d 个文件，释放 %.2f MB",
            result["files_deleted"],
            result["bytes_freed_mb"],
        )

        return _success({
            "status": "completed",
            "files_deleted": result["files_deleted"],
            "bytes_freed_mb": result["bytes_freed_mb"],
            "days_to_keep": days_to_keep,
            "directories_processed": result["directories_processed"],
            "errors": result.get("errors", []),
        })
    except ImportError as e:
        logger.error("无法导入 cleanup_logs 模块: %s", e)
        return _error("日志模块未配置", "LOG_MODULE_NOT_FOUND")
    except Exception as e:
        logger.error("日志清理失败: %s", e)
        return _error(str(e), "LOG_CLEANUP_ERROR")


@router.get("/api/v1/logs/check")
def check_log_rotation_needed(max_size_mb: float = 50.0) -> dict:
    """检查是否需要日志轮转或清理。

    Args:
        max_size_mb: 最大允许的日志总大小（MB），默认 50MB

    Returns:
        检查结果和建议
    """
    try:
        from scripts.cleanup_logs import check_log_rotation_needed as check_func

        result = check_func(max_size_mb)

        return _success({
            "current_total_mb": result["current_total_mb"],
            "threshold_mb": result["threshold_mb"],
            "needs_cleanup": result["needs_cleanup"],
            "recommendation": result["recommendation"],
        })
    except ImportError as e:
        logger.error("无法导入 cleanup_logs 模块: %s", e)
        return _error("日志模块未配置", "LOG_MODULE_NOT_FOUND")
    except Exception as e:
        logger.error("检查日志轮转状态失败: %s", e)
        return _error(str(e), "LOG_CHECK_ERROR")


@router.get("/api/v1/logs/config")
def get_log_config() -> dict:
    """获取日志轮转配置信息。

    Returns:
        当前日志配置
    """
    try:
        from services.api.app.core.logging_config import get_log_config as get_config_func

        config = get_config_func()

        return _success({
            "max_bytes": config["max_bytes"],
            "max_bytes_mb": config["max_bytes_mb"],
            "backup_count": config["backup_count"],
            "log_dir_api": config["log_dir_api"],
            "log_dir_freqtrade": config["log_dir_freqtrade"],
        })
    except ImportError as e:
        logger.error("无法导入 logging_config 模块: %s", e)
        return _error("日志配置模块未配置", "LOG_CONFIG_MODULE_NOT_FOUND")
    except Exception as e:
        logger.error("获取日志配置失败: %s", e)
        return _error(str(e), "LOG_CONFIG_ERROR")
