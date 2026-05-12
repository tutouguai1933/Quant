"""Control Plane API skeleton for Quant phase 1.

This file stays dependency-light so the repository can define the API surface
before the user approves dependency installation.
"""

from __future__ import annotations

import asyncio
import logging
import time

try:
    from fastapi import FastAPI, Request, Response
except ImportError:
    class FastAPI:  # pragma: no cover - lightweight local fallback
        def __init__(self, *args, **kwargs) -> None:
            self.args = args
            self.kwargs = kwargs
            self.routers = []

        def include_router(self, router) -> None:
            self.routers.append(router)

    class Request:  # pragma: no cover
        pass

    class Response:  # pragma: no cover
        pass


from services.api.app.routes.accounts import router as accounts_router
from services.api.app.routes.analytics import router as analytics_router
from services.api.app.routes.backtest_charts import router as backtest_charts_router
from services.api.app.routes.backtest_validation import router as backtest_validation_router
from services.api.app.routes.auth import router as auth_router
from services.api.app.routes.backtest_workspace import router as backtest_workspace_router
from services.api.app.routes.balances import router as balances_router
from services.api.app.routes.config import router as config_router
from services.api.app.routes.data_workspace import router as data_workspace_router
from services.api.app.routes.evaluation_workspace import router as evaluation_workspace_router
from services.api.app.routes.exchange import router as exchange_router
from services.api.app.routes.feature_workspace import router as feature_workspace_router
from services.api.app.routes.health import router as health_router
from services.api.app.routes.market import router as market_router, alias_router as quotes_router
from services.api.app.routes.model_suggestion import router as model_suggestion_router
from services.api.app.routes.openclaw import router as openclaw_router
from services.api.app.routes.orders import router as orders_router
from services.api.app.routes.patrol import router as patrol_router
from services.api.app.routes.stoploss import router as stoploss_router
from services.api.app.routes.scoring import router as scoring_router
from services.api.app.routes.performance import router as performance_router
from services.api.app.routes.positions import router as positions_router
from services.api.app.routes.research_workspace import router as research_workspace_router
from services.api.app.routes.risk_events import router as risk_events_router
from services.api.app.routes.strategy import router as strategy_router
from services.api.app.routes.signals import router as signals_router
from services.api.app.routes.strategies import router as strategies_router
from services.api.app.routes.tasks import router as tasks_router
from services.api.app.routes.websocket import router as websocket_router
from services.api.app.routes.workbench_config import router as workbench_config_router
from services.api.app.routes.feishu import router as feishu_router
from services.api.app.routes.alert_management import router as alert_management_router
from services.api.app.routes.factor_analysis import router as factor_analysis_router
from services.api.app.routes.report import router as report_router
from services.api.app.routes.strategy_tuning import router as strategy_tuning_router
from services.api.app.routes.position_management import router as position_management_router
from services.api.app.routes.ai_training import router as ai_training_router
from services.api.app.routes.trade_log import router as trade_log_router
from services.api.app.routes.hyperopt import router as hyperopt_router
from services.api.app.routes.ml_hyperopt import router as ml_hyperopt_router
from services.api.app.routes.ml_models import router as ml_models_router
from services.api.app.routes.ml_retrain import router as ml_retrain_router
from services.api.app.routes.system_status import router as system_status_router
from services.api.app.routes.freqtrade_proxy import router as freqtrade_proxy_router
from services.api.app.websocket.manager import connection_manager

logger = logging.getLogger(__name__)


app = FastAPI(
    title="Quant Control Plane API",
    version="0.1.0",
    description="Phase-1 skeleton for crypto + Binance + Freqtrade.",
)

if not hasattr(app, "routers"):
    app.routers = []  # type: ignore[attr-defined]

app.include_router(health_router)
app.routers.append(health_router)  # type: ignore[attr-defined]
app.include_router(auth_router)
app.routers.append(auth_router)  # type: ignore[attr-defined]
app.include_router(config_router)
app.routers.append(config_router)  # type: ignore[attr-defined]
app.include_router(backtest_workspace_router)
app.routers.append(backtest_workspace_router)  # type: ignore[attr-defined]
app.include_router(evaluation_workspace_router)
app.routers.append(evaluation_workspace_router)  # type: ignore[attr-defined]
app.include_router(accounts_router)
app.routers.append(accounts_router)  # type: ignore[attr-defined]
app.include_router(balances_router)
app.routers.append(balances_router)  # type: ignore[attr-defined]
app.include_router(data_workspace_router)
app.include_router(feature_workspace_router)
app.routers.append(data_workspace_router)  # type: ignore[attr-defined]
app.routers.append(feature_workspace_router)  # type: ignore[attr-defined]
app.include_router(workbench_config_router)
app.routers.append(workbench_config_router)  # type: ignore[attr-defined]
app.include_router(research_workspace_router)
app.routers.append(research_workspace_router)  # type: ignore[attr-defined]
app.include_router(market_router)
app.routers.append(market_router)  # type: ignore[attr-defined]
app.include_router(quotes_router)
app.routers.append(quotes_router)  # type: ignore[attr-defined]
app.include_router(positions_router)
app.routers.append(positions_router)  # type: ignore[attr-defined]
app.include_router(orders_router)
app.routers.append(orders_router)  # type: ignore[attr-defined]
app.include_router(strategies_router)
app.routers.append(strategies_router)  # type: ignore[attr-defined]
app.include_router(strategy_router)
app.routers.append(strategy_router)  # type: ignore[attr-defined]
app.include_router(signals_router)
app.routers.append(signals_router)  # type: ignore[attr-defined]
app.include_router(tasks_router)
app.routers.append(tasks_router)  # type: ignore[attr-defined]
app.include_router(risk_events_router)
app.routers.append(risk_events_router)  # type: ignore[attr-defined]
app.include_router(openclaw_router)
app.routers.append(openclaw_router)  # type: ignore[attr-defined]
app.include_router(websocket_router, prefix="/api/v1")
app.routers.append(websocket_router)  # type: ignore[attr-defined]
app.include_router(analytics_router)
app.routers.append(analytics_router)  # type: ignore[attr-defined]
app.include_router(performance_router)
app.routers.append(performance_router)  # type: ignore[attr-defined]
app.include_router(backtest_validation_router)
app.routers.append(backtest_validation_router)  # type: ignore[attr-defined]
app.include_router(model_suggestion_router)
app.routers.append(model_suggestion_router)  # type: ignore[attr-defined]
app.include_router(patrol_router)
app.routers.append(patrol_router)  # type: ignore[attr-defined]
app.include_router(stoploss_router)
app.routers.append(stoploss_router)  # type: ignore[attr-defined]
app.include_router(scoring_router)
app.routers.append(scoring_router)  # type: ignore[attr-defined]
app.include_router(backtest_charts_router)
app.routers.append(backtest_charts_router)  # type: ignore[attr-defined]
app.include_router(feishu_router)
app.routers.append(feishu_router)  # type: ignore[attr-defined]
app.include_router(alert_management_router)
app.routers.append(alert_management_router)  # type: ignore[attr-defined]
app.include_router(factor_analysis_router)
app.routers.append(factor_analysis_router)  # type: ignore[attr-defined]
app.include_router(report_router)
app.routers.append(report_router)  # type: ignore[attr-defined]
app.include_router(strategy_tuning_router)
app.routers.append(strategy_tuning_router)  # type: ignore[attr-defined]
app.include_router(system_status_router)
app.routers.append(system_status_router)  # type: ignore[attr-defined]
app.include_router(freqtrade_proxy_router)
app.routers.append(freqtrade_proxy_router)  # type: ignore[attr-defined]
app.include_router(position_management_router)
app.routers.append(position_management_router)  # type: ignore[attr-defined]
app.include_router(exchange_router)
app.routers.append(exchange_router)  # type: ignore[attr-defined]
app.include_router(ai_training_router)
app.routers.append(ai_training_router)  # type: ignore[attr-defined]
app.include_router(trade_log_router)
app.routers.append(trade_log_router)  # type: ignore[attr-defined]
app.include_router(hyperopt_router)
app.routers.append(hyperopt_router)  # type: ignore[attr-defined]
app.include_router(ml_hyperopt_router)
app.routers.append(ml_hyperopt_router)  # type: ignore[attr-defined]
app.include_router(ml_models_router)
app.routers.append(ml_models_router)  # type: ignore[attr-defined]
app.include_router(ml_retrain_router)
app.routers.append(ml_retrain_router)  # type: ignore[attr-defined]


# 性能监控中间件
@app.middleware("http")
async def performance_monitor_middleware(request: Request, call_next) -> Response:
    """自动追踪所有API请求的响应时间。"""
    # 排除性能监控端点本身，避免递归
    # 排除 WebSocket 端点，WebSocket 使用协议升级，不应被 HTTP 中间件追踪
    if request.url.path.startswith("/api/v1/performance") or request.url.path.startswith("/api/v1/ws"):
        return await call_next(request)

    start_time = time.time()
    response = await call_next(request)
    duration_ms = (time.time() - start_time) * 1000

    # 延迟导入以避免循环依赖
    from services.api.app.services.performance_monitor_service import (
        performance_monitor_service,
    )

    # 记录API延迟
    performance_monitor_service.track_api_latency(
        endpoint=request.url.path,
        duration_ms=duration_ms,
        metadata={
            "method": request.method,
            "status_code": response.status_code,
        },
    )

    return response


@app.on_event("startup")
async def setup_event_loop() -> None:
    """在 FastAPI 启动时设置事件循环引用，用于 WebSocket 推送，并启动健康监控。"""
    loop = asyncio.get_running_loop()
    connection_manager.set_loop(loop)

    # 启动健康监控服务
    from services.api.app.services.health_monitor_service import health_monitor_service
    health_monitor_service.start_monitoring(interval_seconds=60)
    logger.info("健康监控服务已启动")

    # 启动定时巡检（默认禁用，由 OpenClaw 容器统一调度）
    import os
    auto_start = os.getenv("QUANT_PATROL_AUTO_START", "false").lower() == "true"
    interval_minutes = int(os.getenv("QUANT_PATROL_INTERVAL_MINUTES", "60"))

    if auto_start:
        from services.api.app.services.scheduled_patrol_service import scheduled_patrol_service
        result = scheduled_patrol_service.start_schedule(interval_minutes=interval_minutes)
        if result.get("success"):
            logger.info("定时巡检已自动启动: interval=%d 分钟", interval_minutes)
        else:
            logger.warning("定时巡检自动启动失败: %s", result.get("message"))

    # 启动定时报告生成（可通过环境变量 QUANT_SCHEDULED_REPORTS_AUTO_START 控制）
    reports_auto_start = os.getenv("QUANT_SCHEDULED_REPORTS_AUTO_START", "false").lower() == "true"
    if reports_auto_start:
        from services.api.app.services.report_service import report_service
        result = report_service.start_scheduled_reports()
        if result.get("success"):
            logger.info("定时报告生成已自动启动: 每日6:00 UTC日报, 每周一6:00 UTC周报")
        else:
            logger.warning("定时报告生成自动启动失败: %s", result.get("message"))


@app.on_event("shutdown")
async def shutdown_event_loop() -> None:
    """在 FastAPI 关闭时停止健康监控和定时巡检。"""
    from services.api.app.services.health_monitor_service import health_monitor_service
    health_monitor_service.stop_monitoring()
    logger.info("健康监控服务已停止")

    # 停止定时巡检
    from services.api.app.services.scheduled_patrol_service import scheduled_patrol_service
    scheduled_patrol_service.stop_schedule()
    logger.info("定时巡检已停止")

    # 停止定时报告生成
    from services.api.app.services.report_service import report_service
    report_service.stop_scheduled_reports()
    logger.info("定时报告生成已停止")
