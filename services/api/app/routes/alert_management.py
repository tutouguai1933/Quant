"""告警管理 API 路由。

提供告警级别管理、静默控制、自动恢复等功能。
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services.api.app.services.alert_upgrade_service import (
    alert_upgrade_service,
    AlertLevel,
)
from services.api.app.services.auto_recovery_service import (
    auto_recovery_service,
    alert_silence_service,
    RecoveryStatus,
)
from services.api.app.services.trade_alert_service import (
    trade_alert_service,
    TradeAlertType,
    TradeAlertLevel,
    TradeAlertMessage,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/alert", tags=["alert-management"])


# ==================== 响应模型 ====================


class AlertLevelResponse(BaseModel):
    """告警级别响应。"""

    success: bool
    alert_key: str | None = None
    level: str | None = None
    counters: dict[str, Any] | None = None
    upgrade_history: list[dict[str, Any]] | None = None
    error: str | None = None


class SilenceRequest(BaseModel):
    """静默请求。"""

    alert_key: str
    duration_seconds: int = 300
    reason: str = ""


class SilenceResponse(BaseModel):
    """静默响应。"""

    success: bool
    silence: dict[str, Any] | None = None
    silences: list[dict[str, Any]] | None = None
    error: str | None = None


class RecoveryRequest(BaseModel):
    """恢复请求。"""

    service_name: str


class RecoveryResponse(BaseModel):
    """恢复响应。"""

    success: bool
    recovery: dict[str, Any] | None = None
    history: list[dict[str, Any]] | None = None
    health: dict[str, Any] | None = None
    error: str | None = None


# ==================== 告警级别 API ====================


@router.get("/level", response_model=AlertLevelResponse)
def get_alert_levels():
    """获取所有告警级别状态。

    Returns:
        所有告警计数器和当前级别
    """
    try:
        counters = alert_upgrade_service.get_all_counters()
        upgrade_history = alert_upgrade_service.get_upgrade_history(limit=20)
        return AlertLevelResponse(
            success=True,
            counters=counters,
            upgrade_history=upgrade_history,
        )
    except Exception as e:
        logger.error("获取告警级别失败: %s", e)
        return AlertLevelResponse(success=False, error=str(e))


@router.get("/level/{alert_key}", response_model=AlertLevelResponse)
def get_alert_level(alert_key: str):
    """获取指定告警的级别。

    Args:
        alert_key: 告警唯一标识

    Returns:
        告警级别状态
    """
    try:
        status = alert_upgrade_service.get_counter_status(alert_key)
        if status is None:
            return AlertLevelResponse(
                success=True,
                alert_key=alert_key,
                level=AlertLevel.INFO.value,
            )
        return AlertLevelResponse(
            success=True,
            alert_key=alert_key,
            level=status["level"],
            counters=status,
        )
    except Exception as e:
        logger.error("获取告警级别失败: %s", e)
        return AlertLevelResponse(success=False, error=str(e))


@router.post("/level/reset", response_model=AlertLevelResponse)
def reset_alert_counter(alert_key: str):
    """重置告警计数器。

    Args:
        alert_key: 告警唯一标识

    Returns:
        重置结果
    """
    try:
        success = alert_upgrade_service.reset_counter(alert_key)
        return AlertLevelResponse(
            success=success,
            alert_key=alert_key,
            level=AlertLevel.INFO.value if success else None,
        )
    except Exception as e:
        logger.error("重置告警计数器失败: %s", e)
        return AlertLevelResponse(success=False, error=str(e))


@router.get("/upgrade/history", response_model=AlertLevelResponse)
def get_upgrade_history(limit: int = 50):
    """获取告警升级历史。

    Args:
        limit: 返回数量限制

    Returns:
        升级历史列表
    """
    try:
        history = alert_upgrade_service.get_upgrade_history(limit=limit)
        return AlertLevelResponse(
            success=True,
            upgrade_history=history,
        )
    except Exception as e:
        logger.error("获取升级历史失败: %s", e)
        return AlertLevelResponse(success=False, error=str(e))


# ==================== 告警静默 API ====================


@router.get("/silence", response_model=SilenceResponse)
def get_active_silences():
    """获取所有活跃的告警静默。

    Returns:
        静默列表
    """
    try:
        silences = alert_silence_service.get_active_silences()
        return SilenceResponse(
            success=True,
            silences=silences,
        )
    except Exception as e:
        logger.error("获取静默列表失败: %s", e)
        return SilenceResponse(success=False, error=str(e))


@router.post("/silence", response_model=SilenceResponse)
def add_silence(request: SilenceRequest):
    """添加告警静默。

    Args:
        request: 静默请求

    Returns:
        静默记录
    """
    try:
        silence = alert_silence_service.add_silence(
            alert_key=request.alert_key,
            duration_seconds=request.duration_seconds,
            reason=request.reason,
        )
        logger.info("添加告警静默: %s, duration=%ds", request.alert_key, request.duration_seconds)
        return SilenceResponse(
            success=True,
            silence=silence,
        )
    except Exception as e:
        logger.error("添加静默失败: %s", e)
        return SilenceResponse(success=False, error=str(e))


@router.delete("/silence/{alert_key}", response_model=SilenceResponse)
def remove_silence(alert_key: str):
    """移除告警静默。

    Args:
        alert_key: 告警唯一标识

    Returns:
        移除结果
    """
    try:
        success = alert_silence_service.remove_silence(alert_key)
        return SilenceResponse(
            success=success,
            silence={"alert_key": alert_key, "removed": success},
        )
    except Exception as e:
        logger.error("移除静默失败: %s", e)
        return SilenceResponse(success=False, error=str(e))


@router.post("/silence/clear-expired", response_model=SilenceResponse)
def clear_expired_silences():
    """清理过期静默。

    Returns:
        清理结果
    """
    try:
        cleared = alert_silence_service.clear_expired_silences()
        return SilenceResponse(
            success=True,
            silence={"cleared_count": cleared},
        )
    except Exception as e:
        logger.error("清理过期静默失败: %s", e)
        return SilenceResponse(success=False, error=str(e))


# ==================== 自动恢复 API ====================


@router.get("/recovery/history", response_model=RecoveryResponse)
def get_recovery_history(limit: int = 50):
    """获取恢复历史。

    Args:
        limit: 返回数量限制

    Returns:
        恢复历史列表
    """
    try:
        history = auto_recovery_service.get_recovery_history(limit=limit)
        return RecoveryResponse(
            success=True,
            history=history,
        )
    except Exception as e:
        logger.error("获取恢复历史失败: %s", e)
        return RecoveryResponse(success=False, error=str(e))


@router.get("/recovery/status", response_model=RecoveryResponse)
def get_recovery_status():
    """获取恢复服务状态。

    Returns:
        恢复服务配置和状态
    """
    try:
        config = auto_recovery_service.config
        return RecoveryResponse(
            success=True,
            recovery={
                "auto_recovery_enabled": config.auto_recovery_enabled,
                "cooldown_seconds": config.cooldown_seconds,
                "max_recovery_attempts": config.max_recovery_attempts,
                "recovery_timeout_seconds": config.recovery_timeout_seconds,
                "enabled_services": config.enabled_services,
                "is_running": auto_recovery_service.is_running,
            },
        )
    except Exception as e:
        logger.error("获取恢复状态失败: %s", e)
        return RecoveryResponse(success=False, error=str(e))


@router.get("/recovery/health", response_model=RecoveryResponse)
def check_services_health():
    """检查所有服务健康状态。

    Returns:
        服务健康状态
    """
    try:
        health = auto_recovery_service.check_all_services_health()
        return RecoveryResponse(
            success=True,
            health=health,
        )
    except Exception as e:
        logger.error("检查服务健康状态失败: %s", e)
        return RecoveryResponse(success=False, error=str(e))


@router.get("/recovery/health/{service_name}", response_model=RecoveryResponse)
def check_service_health(service_name: str):
    """检查单个服务健康状态。

    Args:
        service_name: 服务名称

    Returns:
        服务健康状态
    """
    try:
        health = auto_recovery_service.check_service_health(service_name)
        return RecoveryResponse(
            success=True,
            health=health,
        )
    except Exception as e:
        logger.error("检查服务健康状态失败: %s", e)
        return RecoveryResponse(success=False, error=str(e))


@router.post("/recovery/manual", response_model=RecoveryResponse)
def manual_recovery(request: RecoveryRequest):
    """手动触发服务恢复。

    Args:
        request: 恢复请求

    Returns:
        恢复结果
    """
    try:
        record = auto_recovery_service.manual_recovery(request.service_name)
        recovery_dict = {
            "service_name": record.service_name,
            "action": record.action.value,
            "status": record.status.value,
            "timestamp": record.timestamp,
            "duration_ms": record.duration_ms,
            "error": record.error,
            "details": record.details,
        }

        if record.status == RecoveryStatus.SUCCESS:
            logger.info("手动恢复成功: %s", request.service_name)
        else:
            logger.warning("手动恢复失败: %s, 错误: %s", request.service_name, record.error)

        return RecoveryResponse(
            success=record.status == RecoveryStatus.SUCCESS,
            recovery=recovery_dict,
        )
    except Exception as e:
        logger.error("手动恢复失败: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/recovery/reset-attempts", response_model=RecoveryResponse)
def reset_recovery_attempts(service_name: str):
    """重置服务恢复尝试次数。

    Args:
        service_name: 服务名称

    Returns:
        重置结果
    """
    try:
        auto_recovery_service.reset_recovery_attempts(service_name)
        return RecoveryResponse(
            success=True,
            recovery={"service_name": service_name, "attempts_reset": True},
        )
    except Exception as e:
        logger.error("重置恢复尝试次数失败: %s", e)
        return RecoveryResponse(success=False, error=str(e))


@router.post("/recovery/clear-history", response_model=RecoveryResponse)
def clear_recovery_history():
    """清空恢复历史。

    Returns:
        清理结果
    """
    try:
        count = auto_recovery_service.clear_recovery_history()
        return RecoveryResponse(
            success=True,
            recovery={"cleared_count": count},
        )
    except Exception as e:
        logger.error("清空恢复历史失败: %s", e)
        return RecoveryResponse(success=False, error=str(e))


# ==================== 交易告警 API ====================


class TradeAlertRequest(BaseModel):
    """交易告警请求。"""

    alert_type: str  # large_loss, price_deviation, consecutive_loss, daily_loss_limit
    symbol: str
    message: str
    details: dict[str, Any] = {}
    timestamp: str | None = None


class TradeAlertResponse(BaseModel):
    """交易告警响应。"""

    success: bool
    alert_type: str | None = None
    symbol: str | None = None
    message: str | None = None
    error: str | None = None


class TradeExitAlertRequest(BaseModel):
    """交易退出告警请求。"""

    symbol: str
    entry_price: float
    exit_price: float
    profit_ratio: float
    trade_id: str | None = None


class TradeEntryAlertRequest(BaseModel):
    """交易入场告警请求。"""

    symbol: str
    entry_price: float
    market_price: float
    trade_id: str | None = None


@router.post("/trade", response_model=TradeAlertResponse)
def send_trade_alert(request: TradeAlertRequest):
    """发送交易告警。

    Args:
        request: 交易告警请求

    Returns:
        告警发送结果
    """
    try:
        # 映射告警类型
        alert_type_map = {
            "large_loss": TradeAlertType.LARGE_LOSS,
            "price_deviation": TradeAlertType.PRICE_DEVIATION,
            "consecutive_loss": TradeAlertType.CONSECUTIVE_LOSS,
            "daily_loss_limit": TradeAlertType.DAILY_LOSS_LIMIT,
        }

        alert_type = alert_type_map.get(request.alert_type)
        if alert_type is None:
            return TradeAlertResponse(
                success=False,
                error=f"未知的告警类型: {request.alert_type}",
            )

        # 根据告警类型设置级别
        level_map = {
            TradeAlertType.LARGE_LOSS: TradeAlertLevel.ERROR,
            TradeAlertType.PRICE_DEVIATION: TradeAlertLevel.WARNING,
            TradeAlertType.CONSECUTIVE_LOSS: TradeAlertLevel.WARNING,
            TradeAlertType.DAILY_LOSS_LIMIT: TradeAlertLevel.CRITICAL,
        }

        # 构建告警标题
        title_map = {
            TradeAlertType.LARGE_LOSS: "大额亏损告警",
            TradeAlertType.PRICE_DEVIATION: "异常价格告警",
            TradeAlertType.CONSECUTIVE_LOSS: "连续亏损告警",
            TradeAlertType.DAILY_LOSS_LIMIT: "日亏损超标告警",
        }

        alert = TradeAlertMessage(
            alert_type=alert_type,
            level=level_map.get(alert_type, TradeAlertLevel.WARNING),
            title=title_map.get(alert_type, "交易告警"),
            message=request.message,
            details=request.details,
            timestamp=request.timestamp or "",
        )

        success = trade_alert_service._send_alert(alert)

        logger.info("交易告警发送: type=%s, symbol=%s, success=%s", request.alert_type, request.symbol, success)

        return TradeAlertResponse(
            success=success,
            alert_type=request.alert_type,
            symbol=request.symbol,
            message=request.message,
        )
    except Exception as e:
        logger.error("发送交易告警失败: %s", e)
        return TradeAlertResponse(success=False, error=str(e))


@router.post("/trade/exit", response_model=TradeAlertResponse)
def check_trade_exit_alert(request: TradeExitAlertRequest):
    """检查交易退出告警条件。

    Args:
        request: 交易退出告警请求

    Returns:
        告警检查结果
    """
    try:
        results = trade_alert_service.record_trade(
            symbol=request.symbol,
            entry_price=request.entry_price,
            exit_price=request.exit_price,
            profit_ratio=request.profit_ratio,
            trade_id=request.trade_id or "unknown",
        )

        triggered_types = [k for k, v in results.items() if v]

        logger.info(
            "交易退出告警检查: symbol=%s, profit=%.2f%%, triggered=%s",
            request.symbol,
            request.profit_ratio * 100,
            triggered_types,
        )

        return TradeAlertResponse(
            success=True,
            symbol=request.symbol,
            message=f"告警检查完成，触发: {triggered_types}" if triggered_types else "无告警触发",
        )
    except Exception as e:
        logger.error("检查交易退出告警失败: %s", e)
        return TradeAlertResponse(success=False, error=str(e))


@router.post("/trade/entry", response_model=TradeAlertResponse)
def check_trade_entry_alert(request: TradeEntryAlertRequest):
    """检查交易入场告警条件。

    Args:
        request: 交易入场告警请求

    Returns:
        告警检查结果
    """
    try:
        triggered = trade_alert_service.check_entry(
            symbol=request.symbol,
            entry_price=request.entry_price,
            market_price=request.market_price,
            trade_id=request.trade_id,
        )

        logger.info(
            "交易入场告警检查: symbol=%s, entry=%.4f, market=%.4f, triggered=%s",
            request.symbol,
            request.entry_price,
            request.market_price,
            triggered,
        )

        return TradeAlertResponse(
            success=True,
            symbol=request.symbol,
            message="价格偏离告警触发" if triggered else "入场价格正常",
        )
    except Exception as e:
        logger.error("检查交易入场告警失败: %s", e)
        return TradeAlertResponse(success=False, error=str(e))


@router.get("/trade/stats/{symbol}", response_model=dict)
def get_trade_alert_stats(symbol: str):
    """获取交易告警统计。

    Args:
        symbol: 币种符号

    Returns:
        交易统计信息
    """
    try:
        stats = trade_alert_service.get_trade_stats(symbol)
        return {"success": True, "stats": stats}
    except Exception as e:
        logger.error("获取交易告警统计失败: %s", e)
        return {"success": False, "error": str(e)}