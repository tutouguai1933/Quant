"""异常订单告警服务。

检测交易异常并发送飞书告警：
1. 单笔亏损 > 5%：大额亏损告警
2. 入场价格偏离市场价 > 3%：异常价格告警
3. 连续3笔亏损：连续亏损告警
4. 单日总亏损 > 10%：日亏损超标告警

与 Freqtrade 交易回调集成，实时监控交易风险。
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Optional

from services.api.app.services.feishu_push_service import (
    FeishuPushService,
    FeishuAlertLevel,
    AlertCardMessage,
    feishu_push_service,
)

logger = logging.getLogger(__name__)


class TradeAlertType(str, Enum):
    """交易告警类型。"""

    LARGE_LOSS = "large_loss"  # 单笔大额亏损
    PRICE_DEVIATION = "price_deviation"  # 入场价格偏离
    CONSECUTIVE_LOSS = "consecutive_loss"  # 连续亏损
    DAILY_LOSS_LIMIT = "daily_loss_limit"  # 日亏损超标


class TradeAlertLevel(str, Enum):
    """交易告警级别。"""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class TradeAlertConfig:
    """交易告警配置。"""

    # 单笔亏损阈值（百分比）
    large_loss_threshold: float = 0.05  # 5%

    # 入场价格偏离阈值（百分比）
    price_deviation_threshold: float = 0.03  # 3%

    # 连续亏损次数阈值
    consecutive_loss_count: int = 3

    # 日亏损阈值（百分比）
    daily_loss_threshold: float = 0.10  # 10%

    # 告警冷却时间（秒），避免重复告警
    alert_cooldown_seconds: int = 300  # 5分钟

    # 是否启用告警
    enabled: bool = True

    @classmethod
    def from_env(cls) -> "TradeAlertConfig":
        """从环境变量读取配置。"""
        import os

        large_loss_threshold = float(os.getenv("QUANT_TRADE_ALERT_LARGE_LOSS", "0.05"))
        price_deviation_threshold = float(os.getenv("QUANT_TRADE_ALERT_PRICE_DEVIATION", "0.03"))
        consecutive_loss_count = int(os.getenv("QUANT_TRADE_ALERT_CONSECUTIVE_LOSS", "3"))
        daily_loss_threshold = float(os.getenv("QUANT_TRADE_ALERT_DAILY_LOSS", "0.10"))
        alert_cooldown_seconds = int(os.getenv("QUANT_TRADE_ALERT_COOLDOWN", "300"))
        enabled = os.getenv("QUANT_TRADE_ALERT_ENABLED", "true").lower() == "true"

        return cls(
            large_loss_threshold=large_loss_threshold,
            price_deviation_threshold=price_deviation_threshold,
            consecutive_loss_count=consecutive_loss_count,
            daily_loss_threshold=daily_loss_threshold,
            alert_cooldown_seconds=alert_cooldown_seconds,
            enabled=enabled,
        )


@dataclass
class TradeRecord:
    """交易记录。"""

    trade_id: str
    symbol: str
    entry_price: float
    exit_price: Optional[float] = None
    entry_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    exit_time: Optional[datetime] = None
    profit_ratio: Optional[float] = None  # 盈亏比例
    is_loss: bool = False
    amount: float = 0.0
    side: str = "long"


@dataclass
class TradeAlertMessage:
    """交易告警消息。"""

    alert_type: TradeAlertType
    level: TradeAlertLevel
    title: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_feishu_card(self) -> dict[str, Any]:
        """生成飞书告警卡片。"""
        level_map = {
            TradeAlertLevel.INFO: FeishuAlertLevel.INFO,
            TradeAlertLevel.WARNING: FeishuAlertLevel.WARNING,
            TradeAlertLevel.ERROR: FeishuAlertLevel.ERROR,
            TradeAlertLevel.CRITICAL: FeishuAlertLevel.CRITICAL,
        }
        feishu_level = level_map.get(self.level, FeishuAlertLevel.WARNING)

        alert = AlertCardMessage(
            level=feishu_level,
            title=self.title,
            message=self.message,
            details=self.details,
            timestamp=self.timestamp,
        )
        return alert.to_feishu_card()


class TradeAlertService:
    """交易告警服务。

    检测交易异常并发送告警。
    """

    def __init__(
        self,
        config: TradeAlertConfig | None = None,
        feishu_service: FeishuPushService | None = None,
    ) -> None:
        """初始化交易告警服务。

        Args:
            config: 告警配置
            feishu_service: 飞书推送服务
        """
        self._config = config or TradeAlertConfig.from_env()
        self._feishu_service = feishu_service or feishu_push_service

        # 交易历史追踪
        self._trade_history: dict[str, list[TradeRecord]] = defaultdict(list)

        # 日亏损追踪
        self._daily_loss_tracker: dict[str, dict] = {}

        # 告警冷却追踪（避免重复告警）
        self._alert_cooldown: dict[str, datetime] = {}

        # 连续亏损计数
        self._consecutive_loss_count: dict[str, int] = defaultdict(int)

    @property
    def config(self) -> TradeAlertConfig:
        """返回当前配置。"""
        return self._config

    @property
    def enabled(self) -> bool:
        """返回是否启用告警。"""
        return self._config.enabled

    def _is_in_cooldown(self, alert_key: str) -> bool:
        """检查告警是否在冷却期内。"""
        if alert_key not in self._alert_cooldown:
            return False

        last_alert_time = self._alert_cooldown[alert_key]
        cooldown_end = last_alert_time + timedelta(seconds=self._config.alert_cooldown_seconds)
        return datetime.now(timezone.utc) < cooldown_end

    def _set_cooldown(self, alert_key: str) -> None:
        """设置告警冷却。"""
        self._alert_cooldown[alert_key] = datetime.now(timezone.utc)

    def _send_alert(self, alert: TradeAlertMessage) -> bool:
        """发送告警到飞书。"""
        if not self.enabled:
            logger.debug("交易告警已禁用，跳过: %s", alert.title)
            return False

        alert_key = f"{alert.alert_type.value}:{alert.details.get('symbol', 'unknown')}"

        if self._is_in_cooldown(alert_key):
            logger.debug("告警冷却中，跳过: %s", alert_key)
            return False

        try:
            card = alert.to_feishu_card()
            success = self._feishu_service.send_card(card.get("card", {}))

            if success:
                self._set_cooldown(alert_key)
                logger.info("交易告警发送成功: %s", alert.title)
            else:
                logger.warning("交易告警发送失败: %s", alert.title)

            return success
        except Exception as e:
            logger.exception("交易告警发送异常: %s", e)
            return False

    async def _send_alert_async(self, alert: TradeAlertMessage) -> bool:
        """异步发送告警到飞书。"""
        if not self.enabled:
            logger.debug("交易告警已禁用，跳过: %s", alert.title)
            return False

        alert_key = f"{alert.alert_type.value}:{alert.details.get('symbol', 'unknown')}"

        if self._is_in_cooldown(alert_key):
            logger.debug("告警冷却中，跳过: %s", alert_key)
            return False

        try:
            card = alert.to_feishu_card()
            success = await self._feishu_service.send_card_async(card.get("card", {}))

            if success:
                self._set_cooldown(alert_key)
                logger.info("交易告警发送成功: %s", alert.title)
            else:
                logger.warning("交易告警发送失败: %s", alert.title)

            return success
        except Exception as e:
            logger.exception("交易告警发送异常: %s", e)
            return False

    def check_large_loss(
        self,
        symbol: str,
        profit_ratio: float,
        entry_price: float,
        exit_price: float,
        trade_id: str | None = None,
    ) -> bool:
        """检查单笔大额亏损。

        Args:
            symbol: 币种符号
            profit_ratio: 盈亏比例（负数表示亏损）
            entry_price: 入场价格
            exit_price: 出场价格
            trade_id: 交易ID

        Returns:
            是否触发了告警
        """
        loss_percent = abs(profit_ratio)

        if loss_percent <= self._config.large_loss_threshold:
            return False

        alert = TradeAlertMessage(
            alert_type=TradeAlertType.LARGE_LOSS,
            level=TradeAlertLevel.ERROR,
            title="大额亏损告警",
            message=f"币种 {symbol} 单笔亏损 {loss_percent:.2%}，超过阈值 {self._config.large_loss_threshold:.2%}",
            details={
                "symbol": symbol,
                "loss_percent": f"{loss_percent:.2%}",
                "threshold": f"{self._config.large_loss_threshold:.2%}",
                "entry_price": str(entry_price),
                "exit_price": str(exit_price),
                "trade_id": trade_id or "unknown",
                "time": datetime.now(timezone.utc).isoformat(),
            },
        )

        return self._send_alert(alert)

    def check_price_deviation(
        self,
        symbol: str,
        entry_price: float,
        market_price: float,
        trade_id: str | None = None,
    ) -> bool:
        """检查入场价格偏离。

        Args:
            symbol: 币种符号
            entry_price: 入场价格
            market_price: 市场价格
            trade_id: 交易ID

        Returns:
            是否触发了告警
        """
        if market_price <= 0:
            return False

        deviation = abs(entry_price - market_price) / market_price

        if deviation <= self._config.price_deviation_threshold:
            return False

        alert = TradeAlertMessage(
            alert_type=TradeAlertType.PRICE_DEVIATION,
            level=TradeAlertLevel.WARNING,
            title="异常价格告警",
            message=f"币种 {symbol} 入场价格偏离市场价 {deviation:.2%}，超过阈值 {self._config.price_deviation_threshold:.2%}",
            details={
                "symbol": symbol,
                "deviation": f"{deviation:.2%}",
                "threshold": f"{self._config.price_deviation_threshold:.2%}",
                "entry_price": str(entry_price),
                "market_price": str(market_price),
                "trade_id": trade_id or "unknown",
                "time": datetime.now(timezone.utc).isoformat(),
            },
        )

        return self._send_alert(alert)

    def check_consecutive_loss(
        self,
        symbol: str,
        is_loss: bool,
        profit_ratio: float,
        trade_id: str | None = None,
    ) -> bool:
        """检查连续亏损。

        Args:
            symbol: 币种符号
            is_loss: 是否亏损
            profit_ratio: 盈亏比例
            trade_id: 交易ID

        Returns:
            是否触发了告警
        """
        if is_loss:
            self._consecutive_loss_count[symbol] += 1
        else:
            self._consecutive_loss_count[symbol] = 0
            return False

        count = self._consecutive_loss_count[symbol]

        if count < self._config.consecutive_loss_count:
            return False

        alert = TradeAlertMessage(
            alert_type=TradeAlertType.CONSECUTIVE_LOSS,
            level=TradeAlertLevel.WARNING,
            title="连续亏损告警",
            message=f"币种 {symbol} 已连续亏损 {count} 笔，达到告警阈值 {self._config.consecutive_loss_count} 笔",
            details={
                "symbol": symbol,
                "consecutive_count": str(count),
                "threshold": str(self._config.consecutive_loss_count),
                "last_loss_ratio": f"{abs(profit_ratio):.2%}",
                "trade_id": trade_id or "unknown",
                "time": datetime.now(timezone.utc).isoformat(),
            },
        )

        result = self._send_alert(alert)
        # 发送告警后重置计数
        if result:
            self._consecutive_loss_count[symbol] = 0

        return result

    def check_daily_loss_limit(
        self,
        strategy_id: str,
        daily_profit_ratio: float,
        total_trades: int,
        loss_trades: int,
    ) -> bool:
        """检查日亏损限制。

        Args:
            strategy_id: 策略ID
            daily_profit_ratio: 日盈亏比例（负数表示亏损）
            total_trades: 总交易次数
            loss_trades: 亏损交易次数

        Returns:
            是否触发了告警
        """
        daily_loss = abs(daily_profit_ratio)

        if daily_loss <= self._config.daily_loss_threshold:
            return False

        # 检查是否当天已经告警过
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        alert_key = f"daily_loss:{strategy_id}:{today}"

        if self._is_in_cooldown(alert_key):
            return False

        alert = TradeAlertMessage(
            alert_type=TradeAlertType.DAILY_LOSS_LIMIT,
            level=TradeAlertLevel.CRITICAL,
            title="日亏损超标告警",
            message=f"策略 {strategy_id} 日亏损 {daily_loss:.2%}，超过阈值 {self._config.daily_loss_threshold:.2%}",
            details={
                "strategy_id": strategy_id,
                "daily_loss": f"{daily_loss:.2%}",
                "threshold": f"{self._config.daily_loss_threshold:.2%}",
                "total_trades": str(total_trades),
                "loss_trades": str(loss_trades),
                "loss_rate": f"{loss_trades/total_trades:.2%}" if total_trades > 0 else "0%",
                "date": today,
                "time": datetime.now(timezone.utc).isoformat(),
            },
        )

        return self._send_alert(alert)

    def record_trade(
        self,
        symbol: str,
        entry_price: float,
        exit_price: float,
        profit_ratio: float,
        trade_id: str,
        side: str = "long",
        amount: float = 0.0,
    ) -> dict[str, bool]:
        """记录交易并检查所有告警条件。

        Args:
            symbol: 币种符号
            entry_price: 入场价格
            exit_price: 出场价格
            profit_ratio: 盈亏比例
            trade_id: 交易ID
            side: 交易方向
            amount: 交易数量

        Returns:
            各类告警触发结果
        """
        is_loss = profit_ratio < 0

        trade = TradeRecord(
            trade_id=trade_id,
            symbol=symbol,
            entry_price=entry_price,
            exit_price=exit_price,
            exit_time=datetime.now(timezone.utc),
            profit_ratio=profit_ratio,
            is_loss=is_loss,
            side=side,
            amount=amount,
        )

        # 记录交易历史
        self._trade_history[symbol].append(trade)

        # 检查各类告警
        results = {
            "large_loss": False,
            "consecutive_loss": False,
        }

        # 检查单笔大额亏损
        if is_loss:
            results["large_loss"] = self.check_large_loss(
                symbol=symbol,
                profit_ratio=profit_ratio,
                entry_price=entry_price,
                exit_price=exit_price,
                trade_id=trade_id,
            )

            # 检查连续亏损
            results["consecutive_loss"] = self.check_consecutive_loss(
                symbol=symbol,
                is_loss=is_loss,
                profit_ratio=profit_ratio,
                trade_id=trade_id,
            )

        return results

    def check_entry(
        self,
        symbol: str,
        entry_price: float,
        market_price: float,
        trade_id: str | None = None,
    ) -> bool:
        """检查入场时的价格偏离。

        Args:
            symbol: 币种符号
            entry_price: 入场价格
            market_price: 当前市场价格
            trade_id: 交易ID

        Returns:
            是否触发了告警
        """
        return self.check_price_deviation(
            symbol=symbol,
            entry_price=entry_price,
            market_price=market_price,
            trade_id=trade_id,
        )

    def get_trade_stats(self, symbol: str) -> dict[str, Any]:
        """获取交易统计。

        Args:
            symbol: 币种符号

        Returns:
            交易统计信息
        """
        trades = self._trade_history.get(symbol, [])
        if not trades:
            return {
                "symbol": symbol,
                "total_trades": 0,
                "win_trades": 0,
                "loss_trades": 0,
                "win_rate": 0,
                "total_profit": 0,
                "avg_profit": 0,
                "consecutive_losses": self._consecutive_loss_count.get(symbol, 0),
            }

        total_trades = len(trades)
        win_trades = sum(1 for t in trades if not t.is_loss)
        loss_trades = total_trades - win_trades
        total_profit = sum(t.profit_ratio or 0 for t in trades)
        avg_profit = total_profit / total_trades if total_trades > 0 else 0

        return {
            "symbol": symbol,
            "total_trades": total_trades,
            "win_trades": win_trades,
            "loss_trades": loss_trades,
            "win_rate": win_trades / total_trades if total_trades > 0 else 0,
            "total_profit": total_profit,
            "avg_profit": avg_profit,
            "consecutive_losses": self._consecutive_loss_count.get(symbol, 0),
        }

    def reset_daily_stats(self) -> None:
        """重置日统计数据（每日开始时调用）。"""
        # 保持交易历史但重置连续亏损计数
        self._consecutive_loss_count.clear()
        logger.info("交易告警日统计数据已重置")


# 全局实例
trade_alert_service = TradeAlertService()


# 便捷函数
def check_trade_exit_alert(
    symbol: str,
    entry_price: float,
    exit_price: float,
    profit_ratio: float,
    trade_id: str | None = None,
) -> dict[str, bool]:
    """检查交易出场告警。

    Args:
        symbol: 币种符号
        entry_price: 入场价格
        exit_price: 出场价格
        profit_ratio: 盈亏比例
        trade_id: 交易ID

    Returns:
        各类告警触发结果
    """
    return trade_alert_service.record_trade(
        symbol=symbol,
        entry_price=entry_price,
        exit_price=exit_price,
        profit_ratio=profit_ratio,
        trade_id=trade_id or "unknown",
    )


def check_trade_entry_alert(
    symbol: str,
    entry_price: float,
    market_price: float,
    trade_id: str | None = None,
) -> bool:
    """检查交易入场告警。

    Args:
        symbol: 币种符号
        entry_price: 入场价格
        market_price: 市场价格
        trade_id: 交易ID

    Returns:
        是否触发了告警
    """
    return trade_alert_service.check_entry(
        symbol=symbol,
        entry_price=entry_price,
        market_price=market_price,
        trade_id=trade_id,
    )