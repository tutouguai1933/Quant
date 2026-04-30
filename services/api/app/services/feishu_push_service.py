"""飞书推送服务。

通过飞书机器人 Webhook 推送交易信号、告警和报告。
支持消息卡片格式和文本消息。
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


class FeishuMessageType(str, Enum):
    """飞书消息类型。"""

    TEXT = "text"
    POST = "post"
    INTERACTIVE = "interactive"  # 卡片消息
    IMAGE = "image"


class FeishuAlertLevel(str, Enum):
    """飞书告警级别。"""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class FeishuConfig:
    """飞书推送配置。"""

    webhook_url: str = ""
    app_id: str = ""
    app_secret: str = ""
    enabled: bool = True

    @classmethod
    def from_env(cls) -> "FeishuConfig":
        """从环境变量读取配置。"""
        webhook_url = os.getenv("FEISHU_WEBHOOK_URL", "").strip()
        app_id = os.getenv("FEISHU_APP_ID", "").strip()
        app_secret = os.getenv("FEISHU_APP_SECRET", "").strip()
        enabled = os.getenv("FEISHU_PUSH_ENABLED", "true").strip().lower() == "true"

        return cls(
            webhook_url=webhook_url,
            app_id=app_id,
            app_secret=app_secret,
            enabled=enabled,
        )

    def has_webhook(self) -> bool:
        """检查是否配置了 Webhook。"""
        return bool(self.webhook_url)

    def has_app_credentials(self) -> bool:
        """检查是否配置了应用凭证。"""
        return bool(self.app_id and self.app_secret)


@dataclass
class TradeSignalMessage:
    """交易信号消息。"""

    signal_type: str  # buy, sell
    symbol: str
    price: float | None = None
    quantity: float | None = None
    strategy_name: str | None = None
    confidence: float | None = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_feishu_card(self) -> dict[str, Any]:
        """生成飞书卡片消息格式。"""
        signal_emoji = "\U0001F4C8" if self.signal_type == "buy" else "\U0001F4C9"
        signal_color = "blue" if self.signal_type == "buy" else "red"
        signal_text = "买入" if self.signal_type == "buy" else "卖出"

        elements = [
            {
                "tag": "div",
                "text": {
                    "content": f"{signal_emoji} **{signal_text}信号**",
                    "tag": "lark_md",
                },
            },
            {
                "tag": "div",
                "fields": [
                    {"is_short": True, "text": {"content": f"**币种**: {self.symbol}", "tag": "lark_md"}},
                    {"is_short": True, "text": {"content": f"**价格**: {self.price or 'N/A'}", "tag": "lark_md"}},
                ],
            },
        ]

        if self.quantity:
            elements.append({
                "tag": "div",
                "fields": [
                    {"is_short": True, "text": {"content": f"**数量**: {self.quantity}", "tag": "lark_md"}},
                    {"is_short": True, "text": {"content": f"**策略**: {self.strategy_name or 'N/A'}", "tag": "lark_md"}},
                ],
            })

        if self.confidence:
            elements.append({
                "tag": "div",
                "fields": [
                    {"is_short": True, "text": {"content": f"**置信度**: {self.confidence:.1%}", "tag": "lark_md"}},
                    {"is_short": True, "text": {"content": f"**时间**: {self.timestamp}", "tag": "lark_md"}},
                ],
            })

        return {
            "msg_type": "interactive",
            "card": {
                "config": {"wide_screen_mode": True},
                "elements": elements,
            },
        }


@dataclass
class AlertCardMessage:
    """告警卡片消息。"""

    level: FeishuAlertLevel
    title: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_feishu_card(self) -> dict[str, Any]:
        """生成飞书告警卡片格式。"""
        level_colors = {
            FeishuAlertLevel.INFO: "blue",
            FeishuAlertLevel.WARNING: "orange",
            FeishuAlertLevel.ERROR: "red",
            FeishuAlertLevel.CRITICAL: "red",
        }
        level_emojis = {
            FeishuAlertLevel.INFO: "\U0001F4CA",
            FeishuAlertLevel.WARNING: "⚠️",
            FeishuAlertLevel.ERROR: "❌",
            FeishuAlertLevel.CRITICAL: "\U0001F6A8",
        }

        color = level_colors.get(self.level, "blue")
        emoji = level_emojis.get(self.level, "\U0001F514")

        elements = [
            {
                "tag": "div",
                "text": {
                    "content": f"{emoji} **{self.title}**",
                    "tag": "lark_md",
                },
            },
            {
                "tag": "div",
                "text": {
                    "content": self.message,
                    "tag": "lark_md",
                },
            },
            {
                "tag": "hr",
            },
            {
                "tag": "div",
                "fields": [
                    {"is_short": True, "text": {"content": f"**级别**: {self.level.value.upper()}", "tag": "lark_md"}},
                    {"is_short": True, "text": {"content": f"**时间**: {self.timestamp}", "tag": "lark_md"}},
                ],
            },
        ]

        if self.details:
            detail_fields = []
            for key, value in list(self.details.items())[:4]:  # 最多显示4个详情
                value_str = str(value)[:50]
                detail_fields.append({
                    "is_short": True,
                    "text": {"content": f"**{key}**: {value_str}", "tag": "lark_md"},
                })
            if detail_fields:
                elements.append({
                    "tag": "div",
                    "fields": detail_fields,
                })

        return {
            "msg_type": "interactive",
            "card": {
                "config": {"wide_screen_mode": True},
                "header": {
                    "title": {"tag": "plain_text", "content": self.title},
                    "template": color,
                },
                "elements": elements,
            },
        }


@dataclass
class ReportCardMessage:
    """报告卡片消息。"""

    report_type: str  # daily, weekly, monthly
    summary: str
    metrics: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_feishu_card(self) -> dict[str, Any]:
        """生成飞书报告卡片格式。"""
        report_titles = {
            "daily": "日报",
            "weekly": "周报",
            "monthly": "月报",
        }
        title = report_titles.get(self.report_type, "报告")

        elements = [
            {
                "tag": "div",
                "text": {
                    "content": f"\U0001F4CB **{title}摘要**",
                    "tag": "lark_md",
                },
            },
            {
                "tag": "div",
                "text": {
                    "content": self.summary,
                    "tag": "lark_md",
                },
            },
        ]

        if self.metrics:
            metric_fields = []
            for key, value in list(self.metrics.items())[:6]:
                metric_fields.append({
                    "is_short": True,
                    "text": {"content": f"**{key}**: {value}", "tag": "lark_md"},
                })
            if metric_fields:
                elements.append({
                    "tag": "hr",
                })
                elements.append({
                    "tag": "div",
                    "fields": metric_fields,
                })

        elements.append({
            "tag": "note",
            "elements": [
                {"tag": "plain_text", "content": f"生成时间: {self.timestamp}"},
            ],
        })

        return {
            "msg_type": "interactive",
            "card": {
                "config": {"wide_screen_mode": True},
                "elements": elements,
            },
        }


class FeishuPushService:
    """飞书推送服务。"""

    def __init__(self, config: FeishuConfig | None = None) -> None:
        """初始化飞书推送服务。

        Args:
            config: 飞书配置，默认从环境变量读取
        """
        self._config = config or FeishuConfig.from_env()
        self._http_client: httpx.AsyncClient | None = None
        self._sync_client: httpx.Client | None = None

    @property
    def config(self) -> FeishuConfig:
        """返回当前配置。"""
        return self._config

    @property
    def enabled(self) -> bool:
        """返回是否启用推送。"""
        return self._config.enabled and self._config.has_webhook()

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

    def send_message(self, msg_type: str, content: dict) -> bool:
        """同步发送飞书消息。

        Args:
            msg_type: 消息类型 (text, post, interactive)
            content: 消息内容

        Returns:
            是否发送成功
        """
        if not self.enabled:
            logger.debug("飞书推送已禁用或未配置，跳过推送")
            return False

        payload = {"msg_type": msg_type, "content": content}

        try:
            client = self._get_sync_client()
            response = client.post(
                self._config.webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            result = response.json()
            if result.get("StatusCode") == 0 or result.get("code") == 0:
                logger.info("飞书消息推送成功: msg_type=%s", msg_type)
                return True
            else:
                logger.warning("飞书消息推送返回非成功状态: %s", result)
                return False
        except httpx.HTTPStatusError as e:
            logger.error("飞书推送失败 (HTTP %s): %s", e.response.status_code, e)
            return False
        except httpx.RequestError as e:
            logger.error("飞书推送网络错误: %s", e)
            return False
        except Exception as e:
            logger.exception("飞书推送异常: %s", e)
            return False

    async def send_message_async(self, msg_type: str, content: dict) -> bool:
        """异步发送飞书消息。

        Args:
            msg_type: 消息类型
            content: 消息内容

        Returns:
            是否发送成功
        """
        if not self.enabled:
            logger.debug("飞书推送已禁用或未配置，跳过推送")
            return False

        payload = {"msg_type": msg_type, "content": content}

        try:
            client = await self._get_async_client()
            response = await client.post(
                self._config.webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            result = response.json()
            if result.get("StatusCode") == 0 or result.get("code") == 0:
                logger.info("飞书消息推送成功: msg_type=%s", msg_type)
                return True
            else:
                logger.warning("飞书消息推送返回非成功状态: %s", result)
                return False
        except httpx.HTTPStatusError as e:
            logger.error("飞书推送失败 (HTTP %s): %s", e.response.status_code, e)
            return False
        except httpx.RequestError as e:
            logger.error("飞书推送网络错误: %s", e)
            return False
        except Exception as e:
            logger.exception("飞书推送异常: %s", e)
            return False

    def send_card(self, card_content: dict) -> bool:
        """同步发送飞书卡片消息。

        Args:
            card_content: 卡片内容

        Returns:
            是否发送成功
        """
        if not self.enabled:
            return False

        payload = {"msg_type": "interactive", "card": card_content}

        try:
            client = self._get_sync_client()
            response = client.post(
                self._config.webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            result = response.json()
            if result.get("StatusCode") == 0 or result.get("code") == 0:
                logger.info("飞书卡片推送成功")
                return True
            else:
                logger.warning("飞书卡片推送返回非成功状态: %s", result)
                return False
        except Exception as e:
            logger.error("飞书卡片推送异常: %s", e)
            return False

    async def send_card_async(self, card_content: dict) -> bool:
        """异步发送飞书卡片消息。"""
        if not self.enabled:
            return False

        payload = {"msg_type": "interactive", "card": card_content}

        try:
            client = await self._get_async_client()
            response = await client.post(
                self._config.webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            result = response.json()
            if result.get("StatusCode") == 0 or result.get("code") == 0:
                logger.info("飞书卡片推送成功")
                return True
            else:
                logger.warning("飞书卡片推送返回非成功状态: %s", result)
                return False
        except Exception as e:
            logger.error("飞书卡片推送异常: %s", e)
            return False

    def send_trade_signal(self, signal: TradeSignalMessage) -> bool:
        """推送交易信号。

        Args:
            signal: 交易信号消息

        Returns:
            是否推送成功
        """
        card = signal.to_feishu_card()
        return self.send_card(card.get("card", {}))

    async def send_trade_signal_async(self, signal: TradeSignalMessage) -> bool:
        """异步推送交易信号。"""
        card = signal.to_feishu_card()
        return await self.send_card_async(card.get("card", {}))

    def send_alert(self, alert: AlertCardMessage) -> bool:
        """推送告警。

        Args:
            alert: 告警消息

        Returns:
            是否推送成功
        """
        card = alert.to_feishu_card()
        return self.send_card(card.get("card", {}))

    async def send_alert_async(self, alert: AlertCardMessage) -> bool:
        """异步推送告警。"""
        card = alert.to_feishu_card()
        return await self.send_card_async(card.get("card", {}))

    def send_report(self, report: ReportCardMessage) -> bool:
        """推送报告。

        Args:
            report: 报告消息

        Returns:
            是否推送成功
        """
        card = report.to_feishu_card()
        return self.send_card(card.get("card", {}))

    async def send_report_async(self, report: ReportCardMessage) -> bool:
        """异步推送报告。"""
        card = report.to_feishu_card()
        return await self.send_card_async(card.get("card", {}))

    def send_text(self, text: str) -> bool:
        """发送简单文本消息。

        Args:
            text: 文本内容

        Returns:
            是否发送成功
        """
        return self.send_message("text", {"text": text})

    async def send_text_async(self, text: str) -> bool:
        """异步发送简单文本消息。"""
        return await self.send_message_async("text", {"text": text})

    def test_push(self) -> dict[str, Any]:
        """测试飞书推送。

        Returns:
            测试结果
        """
        if not self._config.has_webhook():
            return {
                "success": False,
                "message": "飞书 Webhook URL 未配置",
                "config": {
                    "webhook_url": "(未配置)",
                    "enabled": self._config.enabled,
                },
            }

        test_text = f"\U0001F4E2 测试消息 - Quant系统飞书推送测试\n时间: {datetime.now(timezone.utc).isoformat()}"

        success = self.send_text(test_text)

        return {
            "success": success,
            "message": "测试消息已发送" if success else "测试消息发送失败",
            "webhook_url": self._config.webhook_url[:50] + "..." if len(self._config.webhook_url) > 50 else self._config.webhook_url,
            "enabled": self._config.enabled,
        }

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
feishu_push_service = FeishuPushService()


# 便捷函数
def send_feishu_alert(
    level: FeishuAlertLevel,
    title: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> bool:
    """发送飞书告警。"""
    alert = AlertCardMessage(
        level=level,
        title=title,
        message=message,
        details=details or {},
    )
    return feishu_push_service.send_alert(alert)


def send_feishu_trade_signal(
    signal_type: str,
    symbol: str,
    price: float | None = None,
    quantity: float | None = None,
    strategy_name: str | None = None,
    confidence: float | None = None,
) -> bool:
    """发送飞书交易信号。"""
    signal = TradeSignalMessage(
        signal_type=signal_type,
        symbol=symbol,
        price=price,
        quantity=quantity,
        strategy_name=strategy_name,
        confidence=confidence,
    )
    return feishu_push_service.send_trade_signal(signal)


def send_feishu_report(
    report_type: str,
    summary: str,
    metrics: dict[str, Any] | None = None,
) -> bool:
    """发送飞书报告。"""
    report = ReportCardMessage(
        report_type=report_type,
        summary=summary,
        metrics=metrics or {},
    )
    return feishu_push_service.send_report(report)