"""交易告警推送服务。

支持通过 Telegram 和 Webhook 推送交易相关告警。
事件类型：开仓、平仓、止损触发、节点故障、系统异常。
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class AlertEventType(str, Enum):
    """告警事件类型。"""

    OPEN_POSITION = "open_position"
    CLOSE_POSITION = "close_position"
    STOP_LOSS_TRIGGERED = "stop_loss_triggered"
    RISK_ALERT = "risk_alert"
    NODE_FAILURE = "node_failure"
    SYSTEM_ERROR = "system_error"


class AlertLevel(str, Enum):
    """告警级别。"""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class AlertConfig:
    """告警配置。"""

    telegram_token: str = ""
    telegram_chat_id: str = ""
    webhook_url: str = ""
    enabled: bool = True

    @classmethod
    def from_env(cls) -> "AlertConfig":
        """从环境变量读取配置。"""
        telegram_token = os.getenv("QUANT_ALERT_TELEGRAM_TOKEN", "").strip()
        telegram_chat_id = os.getenv("QUANT_ALERT_TELEGRAM_CHAT_ID", "").strip()
        webhook_url = os.getenv("QUANT_ALERT_WEBHOOK_URL", "").strip()
        enabled = os.getenv("QUANT_ALERT_ENABLED", "true").strip().lower() == "true"

        return cls(
            telegram_token=telegram_token,
            telegram_chat_id=telegram_chat_id,
            webhook_url=webhook_url,
            enabled=enabled,
        )

    def has_telegram(self) -> bool:
        """检查是否配置了 Telegram。"""
        return bool(self.telegram_token and self.telegram_chat_id)

    def has_webhook(self) -> bool:
        """检查是否配置了 Webhook。"""
        return bool(self.webhook_url)


@dataclass
class AlertMessage:
    """告警消息。"""

    event_type: AlertEventType
    level: AlertLevel
    title: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_telegram_text(self) -> str:
        """生成 Telegram 消息文本。"""
        level_emoji = {
            AlertLevel.INFO: "\U0001F4CA",  # chart
            AlertLevel.WARNING: "⚠️",  # warning
            AlertLevel.ERROR: "❌",  # x
            AlertLevel.CRITICAL: "\U0001F6A8",  # police car light
        }
        event_emoji = {
            AlertEventType.OPEN_POSITION: "\U0001F4C8",  # chart increasing
            AlertEventType.CLOSE_POSITION: "\U0001F4C9",  # chart decreasing
            AlertEventType.STOP_LOSS_TRIGGERED: "\U0001F6D1",  # stop sign
            AlertEventType.RISK_ALERT: "\U0001F6A8",  # police car light
            AlertEventType.NODE_FAILURE: "\U0001F4A5",  # collision
            AlertEventType.SYSTEM_ERROR: "⚠️",  # warning
        }

        emoji = event_emoji.get(self.event_type, "\U0001F514")
        level_icon = level_emoji.get(self.level, "")

        lines = [
            f"{emoji} *{self.title}*",
            f"{level_icon} 级别: {self.level.value.upper()}",
            f"\U0001F4CD 事件: {self.event_type.value}",
            f"⏰ 时间: {self.timestamp}",
            "",
            self.message,
        ]

        if self.details:
            lines.append("")
            lines.append("*详情:*")
            for key, value in self.details.items():
                value_str = str(value)[:100]  # 限制长度
                lines.append(f"  `{key}`: {value_str}")

        return "\n".join(lines)

    def to_webhook_payload(self) -> dict[str, Any]:
        """生成 Webhook 请求体。"""
        return {
            "event_type": self.event_type.value,
            "level": self.level.value,
            "title": self.title,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp,
        }


class AlertPushService:
    """告警推送服务。"""

    def __init__(self, config: AlertConfig | None = None) -> None:
        self._config = config or AlertConfig.from_env()
        self._http_client: httpx.AsyncClient | None = None
        self._sync_client: httpx.Client | None = None
        self._feishu_service: FeishuPushService | None = None

    @property
    def config(self) -> AlertConfig:
        """返回当前配置。"""
        return self._config

    @property
    def enabled(self) -> bool:
        """返回是否启用推送。"""
        return self._config.enabled

    def _get_feishu_service(self) -> FeishuPushService:
        """获取飞书推送服务实例。"""
        if self._feishu_service is None:
            from services.api.app.services.feishu_push_service import feishu_push_service
            self._feishu_service = feishu_push_service
        return self._feishu_service

    def _get_sync_client(self) -> httpx.Client:
        """获取同步 HTTP 客户端。"""
        if self._sync_client is None:
            self._sync_client = httpx.Client(timeout=10.0)
        return self._sync_client

    async def _get_async_client(self) -> httpx.AsyncClient:
        """获取异步 HTTP 客户端。"""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=10.0)
        return self._http_client

    def push_sync(self, alert: AlertMessage) -> dict[str, Any]:
        """同步推送告警。"""
        if not self._config.enabled:
            logger.debug("告警推送已禁用，跳过推送: %s", alert.title)
            return {"status": "disabled", "message": "告警推送已禁用"}

        results: dict[str, Any] = {
            "alert": alert.to_webhook_payload(),
            "telegram": None,
            "webhook": None,
            "feishu": None,
        }

        if self._config.has_telegram():
            results["telegram"] = self._push_telegram_sync(alert)

        if self._config.has_webhook():
            results["webhook"] = self._push_webhook_sync(alert)

        # 推送到飞书
        results["feishu"] = self._push_feishu_sync(alert)

        return results

    async def push_async(self, alert: AlertMessage) -> dict[str, Any]:
        """异步推送告警。"""
        if not self._config.enabled:
            logger.debug("告警推送已禁用，跳过推送: %s", alert.title)
            return {"status": "disabled", "message": "告警推送已禁用"}

        results: dict[str, Any] = {
            "alert": alert.to_webhook_payload(),
            "telegram": None,
            "webhook": None,
            "feishu": None,
        }

        if self._config.has_telegram():
            results["telegram"] = await self._push_telegram_async(alert)

        if self._config.has_webhook():
            results["webhook"] = await self._push_webhook_async(alert)

        # 推送到飞书
        results["feishu"] = await self._push_feishu_async(alert)

        return results

    def _push_telegram_sync(self, alert: AlertMessage) -> dict[str, Any]:
        """同步推送 Telegram 消息。"""
        if not self._config.has_telegram():
            return {"status": "skipped", "message": "Telegram 未配置"}

        url = f"https://api.telegram.org/bot{self._config.telegram_token}/sendMessage"
        text = alert.to_telegram_text()

        try:
            client = self._get_sync_client()
            response = client.post(
                url,
                json={
                    "chat_id": self._config.telegram_chat_id,
                    "text": text,
                    "parse_mode": "Markdown",
                },
            )
            response.raise_for_status()
            logger.info("Telegram 告警推送成功: %s", alert.title)
            return {"status": "success", "response": response.json()}
        except httpx.HTTPStatusError as e:
            logger.error("Telegram 告警推送失败 (HTTP %s): %s", e.response.status_code, e)
            return {"status": "error", "message": f"HTTP {e.response.status_code}: {e}"}
        except httpx.RequestError as e:
            logger.error("Telegram 告警推送网络错误: %s", e)
            return {"status": "error", "message": str(e)}
        except Exception as e:
            logger.exception("Telegram 告警推送异常: %s", e)
            return {"status": "error", "message": str(e)}

    async def _push_telegram_async(self, alert: AlertMessage) -> dict[str, Any]:
        """异步推送 Telegram 消息。"""
        if not self._config.has_telegram():
            return {"status": "skipped", "message": "Telegram 未配置"}

        url = f"https://api.telegram.org/bot{self._config.telegram_token}/sendMessage"
        text = alert.to_telegram_text()

        try:
            client = await self._get_async_client()
            response = await client.post(
                url,
                json={
                    "chat_id": self._config.telegram_chat_id,
                    "text": text,
                    "parse_mode": "Markdown",
                },
            )
            response.raise_for_status()
            logger.info("Telegram 告警推送成功: %s", alert.title)
            return {"status": "success", "response": response.json()}
        except httpx.HTTPStatusError as e:
            logger.error("Telegram 告警推送失败 (HTTP %s): %s", e.response.status_code, e)
            return {"status": "error", "message": f"HTTP {e.response.status_code}: {e}"}
        except httpx.RequestError as e:
            logger.error("Telegram 告警推送网络错误: %s", e)
            return {"status": "error", "message": str(e)}
        except Exception as e:
            logger.exception("Telegram 告警推送异常: %s", e)
            return {"status": "error", "message": str(e)}

    def _push_webhook_sync(self, alert: AlertMessage) -> dict[str, Any]:
        """同步推送 Webhook。"""
        if not self._config.has_webhook():
            return {"status": "skipped", "message": "Webhook 未配置"}

        try:
            client = self._get_sync_client()
            response = client.post(
                self._config.webhook_url,
                json=alert.to_webhook_payload(),
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            logger.info("Webhook 告警推送成功: %s", alert.title)
            return {"status": "success", "status_code": response.status_code}
        except httpx.HTTPStatusError as e:
            logger.error("Webhook 告警推送失败 (HTTP %s): %s", e.response.status_code, e)
            return {"status": "error", "message": f"HTTP {e.response.status_code}: {e}"}
        except httpx.RequestError as e:
            logger.error("Webhook 告警推送网络错误: %s", e)
            return {"status": "error", "message": str(e)}
        except Exception as e:
            logger.exception("Webhook 告警推送异常: %s", e)
            return {"status": "error", "message": str(e)}

    async def _push_webhook_async(self, alert: AlertMessage) -> dict[str, Any]:
        """异步推送 Webhook。"""
        if not self._config.has_webhook():
            return {"status": "skipped", "message": "Webhook 未配置"}

        try:
            client = await self._get_async_client()
            response = await client.post(
                self._config.webhook_url,
                json=alert.to_webhook_payload(),
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            logger.info("Webhook 告警推送成功: %s", alert.title)
            return {"status": "success", "status_code": response.status_code}
        except httpx.HTTPStatusError as e:
            logger.error("Webhook 告警推送失败 (HTTP %s): %s", e.response.status_code, e)
            return {"status": "error", "message": f"HTTP {e.response.status_code}: {e}"}
        except httpx.RequestError as e:
            logger.error("Webhook 告警推送网络错误: %s", e)
            return {"status": "error", "message": str(e)}
        except Exception as e:
            logger.exception("Webhook 告警推送异常: %s", e)
            return {"status": "error", "message": str(e)}

    def _push_feishu_sync(self, alert: AlertMessage) -> dict[str, Any]:
        """同步推送到飞书。"""
        try:
            feishu_service = self._get_feishu_service()
            if not feishu_service.enabled:
                return {"status": "skipped", "message": "飞书推送未配置或已禁用"}

            from services.api.app.services.feishu_push_service import (
                FeishuAlertLevel,
                AlertCardMessage,
            )

            # 映射告警级别
            level_map = {
                AlertLevel.INFO: FeishuAlertLevel.INFO,
                AlertLevel.WARNING: FeishuAlertLevel.WARNING,
                AlertLevel.ERROR: FeishuAlertLevel.ERROR,
                AlertLevel.CRITICAL: FeishuAlertLevel.CRITICAL,
            }
            feishu_level = level_map.get(alert.level, FeishuAlertLevel.INFO)

            feishu_alert = AlertCardMessage(
                level=feishu_level,
                title=alert.title,
                message=alert.message,
                details=alert.details,
                timestamp=alert.timestamp,
            )

            success = feishu_service.send_alert(feishu_alert)
            if success:
                logger.info("飞书告警推送成功: %s", alert.title)
                return {"status": "success"}
            else:
                logger.warning("飞书告警推送失败: %s", alert.title)
                return {"status": "error", "message": "飞书推送失败"}

        except Exception as e:
            logger.exception("飞书告警推送异常: %s", e)
            return {"status": "error", "message": str(e)}

    async def _push_feishu_async(self, alert: AlertMessage) -> dict[str, Any]:
        """异步推送到飞书。"""
        try:
            feishu_service = self._get_feishu_service()
            if not feishu_service.enabled:
                return {"status": "skipped", "message": "飞书推送未配置或已禁用"}

            from services.api.app.services.feishu_push_service import (
                FeishuAlertLevel,
                AlertCardMessage,
            )

            # 映射告警级别
            level_map = {
                AlertLevel.INFO: FeishuAlertLevel.INFO,
                AlertLevel.WARNING: FeishuAlertLevel.WARNING,
                AlertLevel.ERROR: FeishuAlertLevel.ERROR,
                AlertLevel.CRITICAL: FeishuAlertLevel.CRITICAL,
            }
            feishu_level = level_map.get(alert.level, FeishuAlertLevel.INFO)

            feishu_alert = AlertCardMessage(
                level=feishu_level,
                title=alert.title,
                message=alert.message,
                details=alert.details,
                timestamp=alert.timestamp,
            )

            success = await feishu_service.send_alert_async(feishu_alert)
            if success:
                logger.info("飞书告警推送成功: %s", alert.title)
                return {"status": "success"}
            else:
                logger.warning("飞书告警推送失败: %s", alert.title)
                return {"status": "error", "message": "飞书推送失败"}

        except Exception as e:
            logger.exception("飞书告警推送异常: %s", e)
            return {"status": "error", "message": str(e)}

    def close(self) -> None:
        """关闭客户端连接。"""
        if self._sync_client:
            self._sync_client.close()
            self._sync_client = None

    async def aclose(self) -> None:
        """异步关闭客户端连接。"""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
        self.close()


# 全局实例
alert_push_service = AlertPushService()


# 便捷函数
def push_trade_alert(
    event_type: AlertEventType,
    level: AlertLevel,
    title: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """同步推送交易告警。"""
    alert = AlertMessage(
        event_type=event_type,
        level=level,
        title=title,
        message=message,
        details=details or {},
    )
    return alert_push_service.push_sync(alert)


async def push_trade_alert_async(
    event_type: AlertEventType,
    level: AlertLevel,
    title: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """异步推送交易告警。"""
    alert = AlertMessage(
        event_type=event_type,
        level=level,
        title=title,
        message=message,
        details=details or {},
    )
    return await alert_push_service.push_async(alert)


def push_open_position_alert(
    symbol: str,
    side: str,
    quantity: str | float,
    price: str | float | None = None,
    strategy_id: int | None = None,
    signal_id: int | None = None,
) -> dict[str, Any]:
    """推送开仓告警。"""
    details: dict[str, Any] = {
        "symbol": symbol,
        "side": side,
        "quantity": str(quantity),
    }
    if price is not None:
        details["price"] = str(price)
    if strategy_id is not None:
        details["strategy_id"] = strategy_id
    if signal_id is not None:
        details["signal_id"] = signal_id

    return push_trade_alert(
        event_type=AlertEventType.OPEN_POSITION,
        level=AlertLevel.INFO,
        title="开仓执行",
        message=f"已执行 {symbol} {side} 开仓，数量: {quantity}",
        details=details,
    )


def push_close_position_alert(
    symbol: str,
    side: str,
    quantity: str | float,
    reason: str | None = None,
    profit_loss: str | float | None = None,
) -> dict[str, Any]:
    """推送平仓告警。"""
    details: dict[str, Any] = {
        "symbol": symbol,
        "side": side,
        "quantity": str(quantity),
    }
    if reason:
        details["reason"] = reason
    if profit_loss is not None:
        details["profit_loss"] = str(profit_loss)

    return push_trade_alert(
        event_type=AlertEventType.CLOSE_POSITION,
        level=AlertLevel.INFO,
        title="平仓执行",
        message=f"已执行 {symbol} 平仓，数量: {quantity}" + (f"，原因: {reason}" if reason else ""),
        details=details,
    )


def push_stop_loss_alert(
    symbol: str,
    trigger_price: str | float,
    current_price: str | float,
    loss_percent: str | float | None = None,
) -> dict[str, Any]:
    """推送止损触发告警。"""
    details: dict[str, Any] = {
        "symbol": symbol,
        "trigger_price": str(trigger_price),
        "current_price": str(current_price),
    }
    if loss_percent is not None:
        details["loss_percent"] = str(loss_percent)

    return push_trade_alert(
        event_type=AlertEventType.STOP_LOSS_TRIGGERED,
        level=AlertLevel.WARNING,
        title="止损触发",
        message=f"{symbol} 止损已触发，触发价: {trigger_price}，当前价: {current_price}",
        details=details,
    )


def push_node_failure_alert(
    node_name: str,
    error_message: str,
    node_type: str | None = None,
) -> dict[str, Any]:
    """推送节点故障告警。"""
    details: dict[str, Any] = {
        "node_name": node_name,
        "error_message": error_message[:200],  # 限制长度
    }
    if node_type:
        details["node_type"] = node_type

    return push_trade_alert(
        event_type=AlertEventType.NODE_FAILURE,
        level=AlertLevel.ERROR,
        title="节点故障",
        message=f"节点 {node_name} 发生故障: {error_message[:100]}",
        details=details,
    )


def push_system_error_alert(
    component: str,
    error_message: str,
    error_type: str | None = None,
    stack_trace: str | None = None,
) -> dict[str, Any]:
    """推送系统异常告警。"""
    details: dict[str, Any] = {
        "component": component,
        "error_message": error_message[:200],
    }
    if error_type:
        details["error_type"] = error_type
    if stack_trace:
        details["stack_trace"] = stack_trace[:500]

    return push_trade_alert(
        event_type=AlertEventType.SYSTEM_ERROR,
        level=AlertLevel.ERROR,
        title="系统异常",
        message=f"{component} 发生异常: {error_message[:100]}",
        details=details,
    )