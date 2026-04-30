"""飞书推送 API 路由。

提供飞书配置管理、测试推送等功能。
"""

from __future__ import annotations

import logging
from typing import Any

try:
    from fastapi import APIRouter, HTTPException
    from pydantic import BaseModel, Field
except ImportError:
    class APIRouter:  # pragma: no cover
        def __init__(self, *args, **kwargs) -> None:
            pass

    class HTTPException(Exception):  # pragma: no cover
        pass

    class BaseModel:  # pragma: no cover
        pass

    def Field(*args, **kwargs):  # pragma: no cover
        return None


from services.api.app.services.feishu_push_service import (
    FeishuConfig,
    FeishuAlertLevel,
    AlertCardMessage,
    TradeSignalMessage,
    ReportCardMessage,
    feishu_push_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/feishu", tags=["Feishu"])


class FeishuTestRequest(BaseModel):
    """测试推送请求。"""

    custom_message: str | None = Field(None, description="自定义测试消息内容")


class FeishuConfigRequest(BaseModel):
    """飞书配置更新请求。"""

    webhook_url: str | None = Field(None, description="飞书机器人 Webhook URL")
    enabled: bool | None = Field(None, description="是否启用推送")


class FeishuAlertRequest(BaseModel):
    """飞书告警请求。"""

    level: str = Field(..., description="告警级别: info, warning, error, critical")
    title: str = Field(..., description="告警标题")
    message: str = Field(..., description="告警内容")
    details: dict[str, Any] | None = Field(None, description="告警详情")


class FeishuTradeSignalRequest(BaseModel):
    """飞书交易信号请求。"""

    signal_type: str = Field(..., description="信号类型: buy, sell")
    symbol: str = Field(..., description="交易币种")
    price: float | None = Field(None, description="价格")
    quantity: float | None = Field(None, description="数量")
    strategy_name: str | None = Field(None, description="策略名称")
    confidence: float | None = Field(None, description="置信度")


class FeishuReportRequest(BaseModel):
    """飞书报告请求。"""

    report_type: str = Field(..., description="报告类型: daily, weekly, monthly")
    summary: str = Field(..., description="报告摘要")
    metrics: dict[str, Any] | None = Field(None, description="报告指标")


@router.post("/test")
async def test_feishu_push(request: FeishuTestRequest | None = None) -> dict[str, Any]:
    """测试飞书推送。

    发送一条测试消息到飞书群，验证配置是否正确。
    """
    if request and request.custom_message:
        success = feishu_push_service.send_text(request.custom_message)
        return {
            "success": success,
            "message": "自定义消息已发送" if success else "消息发送失败",
            "webhook_configured": feishu_push_service.config.has_webhook(),
        }

    result = feishu_push_service.test_push()
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message"))

    return result


@router.get("/config")
async def get_feishu_config() -> dict[str, Any]:
    """获取飞书推送配置。

    返回当前飞书推送服务的配置状态。
    """
    config = feishu_push_service.config
    return {
        "enabled": config.enabled,
        "webhook_configured": config.has_webhook(),
        "webhook_url": "(已配置)" if config.has_webhook() else "(未配置)",
        "app_credentials_configured": config.has_app_credentials(),
    }


@router.post("/config")
async def update_feishu_config(request: FeishuConfigRequest) -> dict[str, Any]:
    """更新飞书推送配置。

    注意：此接口仅更新运行时配置，不持久化。
    要永久更改配置，请设置环境变量。
    """
    if request.webhook_url is not None:
        feishu_push_service._config.webhook_url = request.webhook_url

    if request.enabled is not None:
        feishu_push_service._config.enabled = request.enabled

    return {
        "success": True,
        "message": "运行时配置已更新（注意：重启后将恢复为环境变量配置）",
        "config": {
            "enabled": feishu_push_service._config.enabled,
            "webhook_configured": feishu_push_service.config.has_webhook(),
        },
    }


@router.post("/alert")
async def send_feishu_alert(request: FeishuAlertRequest) -> dict[str, Any]:
    """发送飞书告警。

    通过飞书机器人推送告警卡片消息。
    """
    try:
        level = FeishuAlertLevel(request.level.lower())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"无效的告警级别: {request.level}，可选值: info, warning, error, critical",
        )

    alert = AlertCardMessage(
        level=level,
        title=request.title,
        message=request.message,
        details=request.details or {},
    )

    success = feishu_push_service.send_alert(alert)

    return {
        "success": success,
        "message": "告警已推送" if success else "告警推送失败",
        "alert": {
            "level": level.value,
            "title": request.title,
        },
    }


@router.post("/signal")
async def send_feishu_signal(request: FeishuTradeSignalRequest) -> dict[str, Any]:
    """发送飞书交易信号。

    通过飞书机器人推送交易信号卡片消息。
    """
    if request.signal_type.lower() not in ("buy", "sell"):
        raise HTTPException(
            status_code=400,
            detail=f"无效的信号类型: {request.signal_type}，可选值: buy, sell",
        )

    signal = TradeSignalMessage(
        signal_type=request.signal_type.lower(),
        symbol=request.symbol,
        price=request.price,
        quantity=request.quantity,
        strategy_name=request.strategy_name,
        confidence=request.confidence,
    )

    success = feishu_push_service.send_trade_signal(signal)

    return {
        "success": success,
        "message": "交易信号已推送" if success else "交易信号推送失败",
        "signal": {
            "type": request.signal_type,
            "symbol": request.symbol,
        },
    }


@router.post("/report")
async def send_feishu_report(request: FeishuReportRequest) -> dict[str, Any]:
    """发送飞书报告。

    通过飞书机器人推送报告卡片消息。
    """
    if request.report_type.lower() not in ("daily", "weekly", "monthly"):
        raise HTTPException(
            status_code=400,
            detail=f"无效的报告类型: {request.report_type}，可选值: daily, weekly, monthly",
        )

    report = ReportCardMessage(
        report_type=request.report_type.lower(),
        summary=request.summary,
        metrics=request.metrics or {},
    )

    success = feishu_push_service.send_report(report)

    return {
        "success": success,
        "message": "报告已推送" if success else "报告推送失败",
        "report": {
            "type": request.report_type,
        },
    }


@router.get("/status")
async def get_feishu_status() -> dict[str, Any]:
    """获取飞书推送状态。

    返回飞书推送服务的当前状态信息。
    """
    return {
        "service": "feishu_push_service",
        "enabled": feishu_push_service.enabled,
        "webhook_configured": feishu_push_service.config.has_webhook(),
        "ready": feishu_push_service.enabled,
    }