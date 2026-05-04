"""交易日志持久化服务。

记录每笔交易的详细信息，包括：
- 交易对、入场价、出场价
- 盈亏百分比、持仓时间
- 止损原因、信号评分

使用文件持久化存储交易日志数据。
"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from enum import StrEnum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    """返回当前 UTC 时间。"""
    return datetime.now(timezone.utc)


def _parse_decimal(value: object, default: Decimal = Decimal("0")) -> Decimal:
    """安全解析 Decimal。"""
    if value is None:
        return default
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return default


class StopLossReason(StrEnum):
    """止损原因类型。"""

    MANUAL = "manual"  # 手动止损
    SIGNAL = "signal"  # 信号触发止损
    TIME_LIMIT = "time_limit"  # 时间限制止损
    TAKE_PROFIT = "take_profit"  # 止盈触发
    STOP_LOSS = "stop_loss"  # 止损线触发
    TRAILING_STOP = "trailing_stop"  # 移动止损触发
    RISK_LIMIT = "risk_limit"  # 风控限制触发
    UNKNOWN = "unknown"  # 未知原因


@dataclass(slots=True)
class TradeLog:
    """交易日志记录。"""

    trade_id: int
    symbol: str  # 交易对，如 BTC/USDT
    side: str  # buy/sell
    entry_price: Decimal  # 入场价
    exit_price: Decimal | None  # 出场价（未平仓时为 None）
    entry_time: datetime  # 入场时间
    exit_time: datetime | None  # 出场时间（未平仓时为 None）
    quantity: Decimal  # 交易数量
    pnl_percent: Decimal  # 盈亏百分比
    holding_duration: timedelta | None  # 持仓时间（未平仓时为 None）
    stop_loss_reason: StopLossReason | None  # 止损原因
    signal_score: Decimal | None  # 信号评分（0-1）
    strategy_name: str | None  # 策略名称
    notes: str | None  # 备注
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.symbol = self.symbol.strip().upper()
        self.side = self.side.lower()
        if self.side not in ("buy", "sell"):
            raise ValueError(f"side must be 'buy' or 'sell', got {self.side}")
        self.entry_price = _parse_decimal(self.entry_price)
        if self.exit_price is not None:
            self.exit_price = _parse_decimal(self.exit_price)
        self.quantity = _parse_decimal(self.quantity)
        self.pnl_percent = _parse_decimal(self.pnl_percent)
        if self.signal_score is not None:
            self.signal_score = _parse_decimal(self.signal_score)
            if not (Decimal("0") <= self.signal_score <= Decimal("1")):
                self.signal_score = None

    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式。"""
        return {
            "trade_id": self.trade_id,
            "symbol": self.symbol,
            "side": self.side,
            "entry_price": str(self.entry_price),
            "exit_price": str(self.exit_price) if self.exit_price is not None else None,
            "entry_time": self.entry_time.isoformat(),
            "exit_time": self.exit_time.isoformat() if self.exit_time is not None else None,
            "quantity": str(self.quantity),
            "pnl_percent": str(self.pnl_percent),
            "holding_duration_seconds": self.holding_duration.total_seconds() if self.holding_duration is not None else None,
            "stop_loss_reason": self.stop_loss_reason.value if self.stop_loss_reason is not None else None,
            "signal_score": str(self.signal_score) if self.signal_score is not None else None,
            "strategy_name": self.strategy_name,
            "notes": self.notes,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TradeLog":
        """从字典创建 TradeLog 实例。"""
        holding_duration = None
        if data.get("holding_duration_seconds") is not None:
            holding_duration = timedelta(seconds=float(data["holding_duration_seconds"]))

        stop_loss_reason = None
        if data.get("stop_loss_reason"):
            try:
                stop_loss_reason = StopLossReason(data["stop_loss_reason"])
            except ValueError:
                stop_loss_reason = StopLossReason.UNKNOWN

        return cls(
            trade_id=int(data["trade_id"]),
            symbol=data["symbol"],
            side=data["side"],
            entry_price=_parse_decimal(data.get("entry_price")),
            exit_price=_parse_decimal(data.get("exit_price")) if data.get("exit_price") else None,
            entry_time=datetime.fromisoformat(data["entry_time"]),
            exit_time=datetime.fromisoformat(data["exit_time"]) if data.get("exit_time") else None,
            quantity=_parse_decimal(data.get("quantity")),
            pnl_percent=_parse_decimal(data.get("pnl_percent")),
            holding_duration=holding_duration,
            stop_loss_reason=stop_loss_reason,
            signal_score=_parse_decimal(data.get("signal_score")) if data.get("signal_score") else None,
            strategy_name=data.get("strategy_name"),
            notes=data.get("notes"),
            created_at=datetime.fromisoformat(data.get("created_at", utc_now().isoformat())),
            updated_at=datetime.fromisoformat(data.get("updated_at", utc_now().isoformat())),
        )


class TradeLogService:
    """交易日志持久化服务。"""

    def __init__(self) -> None:
        self._trade_logs: dict[int, TradeLog] = {}
        self._next_trade_id: int = 1
        self._lock = threading.Lock()
        self._config_path: Path | None = None

    def set_config_path(self, path: str | Path) -> None:
        """设置配置持久化路径。"""
        self._config_path = Path(path)
        self._load_logs()

    def _load_logs(self) -> None:
        """从文件加载交易日志。"""
        if self._config_path is None or not self._config_path.exists():
            return

        try:
            with open(self._config_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            with self._lock:
                self._trade_logs = {
                    int(k): TradeLog.from_dict(v) for k, v in data.get("trade_logs", {}).items()
                }
                self._next_trade_id = data.get("next_trade_id", 1)

            logger.info("交易日志数据已加载: %s, 共 %d 条", self._config_path, len(self._trade_logs))
        except Exception as e:
            logger.warning("加载交易日志数据失败: %s", e)

    def _save_logs(self) -> None:
        """保存交易日志到文件。"""
        if self._config_path is None:
            return

        try:
            with self._lock:
                data = {
                    "trade_logs": {str(k): v.to_dict() for k, v in self._trade_logs.items()},
                    "next_trade_id": self._next_trade_id,
                    "updated_at": utc_now().isoformat(),
                }

            with open(self._config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

            logger.debug("交易日志数据已保存: %s", self._config_path)
        except Exception as e:
            logger.warning("保存交易日志数据失败: %s", e)

    def record_trade(
        self,
        symbol: str,
        side: str,
        entry_price: Decimal | float | str,
        exit_price: Decimal | float | str | None = None,
        entry_time: datetime | None = None,
        exit_time: datetime | None = None,
        quantity: Decimal | float | str = Decimal("0"),
        pnl_percent: Decimal | float | str = Decimal("0"),
        holding_duration: timedelta | None = None,
        stop_loss_reason: StopLossReason | str | None = None,
        signal_score: Decimal | float | str | None = None,
        strategy_name: str | None = None,
        notes: str | None = None,
    ) -> TradeLog:
        """记录一笔交易日志。

        Args:
            symbol: 交易对，如 BTC/USDT
            side: buy/sell
            entry_price: 入场价格
            exit_price: 出场价格（未平仓时可省略）
            entry_time: 入场时间（默认当前时间）
            exit_time: 出场时间（未平仓时可省略）
            quantity: 交易数量
            pnl_percent: 盈亏百分比
            holding_duration: 持仓时间
            stop_loss_reason: 止损原因
            signal_score: 信号评分（0-1）
            strategy_name: 策略名称
            notes: 备注

        Returns:
            TradeLog: 创建的交易日志记录
        """
        if entry_time is None:
            entry_time = utc_now()

        if isinstance(stop_loss_reason, str):
            try:
                stop_loss_reason = StopLossReason(stop_loss_reason)
            except ValueError:
                stop_loss_reason = StopLossReason.UNKNOWN

        if exit_price is not None and exit_time is not None and holding_duration is None:
            holding_duration = exit_time - entry_time

        with self._lock:
            trade_id = self._next_trade_id
            self._next_trade_id += 1

            trade_log = TradeLog(
                trade_id=trade_id,
                symbol=symbol,
                side=side,
                entry_price=_parse_decimal(entry_price),
                exit_price=_parse_decimal(exit_price) if exit_price else None,
                entry_time=entry_time,
                exit_time=exit_time,
                quantity=_parse_decimal(quantity),
                pnl_percent=_parse_decimal(pnl_percent),
                holding_duration=holding_duration,
                stop_loss_reason=stop_loss_reason,
                signal_score=_parse_decimal(signal_score) if signal_score else None,
                strategy_name=strategy_name,
                notes=notes,
            )

            self._trade_logs[trade_id] = trade_log

        self._save_logs()
        logger.info("记录交易日志: trade_id=%d, symbol=%s, side=%s, pnl=%s%%", trade_id, symbol, side, pnl_percent)

        return trade_log

    def update_trade(
        self,
        trade_id: int,
        exit_price: Decimal | float | str | None = None,
        exit_time: datetime | None = None,
        pnl_percent: Decimal | float | str | None = None,
        stop_loss_reason: StopLossReason | str | None = None,
        notes: str | None = None,
    ) -> TradeLog | None:
        """更新交易日志（主要用于平仓时更新出场信息）。

        Args:
            trade_id: 交易ID
            exit_price: 出场价格
            exit_time: 出场时间（默认当前时间）
            pnl_percent: 盈亏百分比
            stop_loss_reason: 止损原因
            notes: 备注

        Returns:
            TradeLog: 更新后的交易日志，如果不存在则返回 None
        """
        with self._lock:
            trade_log = self._trade_logs.get(trade_id)
            if trade_log is None:
                logger.warning("交易日志不存在: trade_id=%d", trade_id)
                return None

            if exit_price is not None:
                trade_log.exit_price = _parse_decimal(exit_price)
            if exit_time is not None:
                trade_log.exit_time = exit_time
                if trade_log.entry_time:
                    trade_log.holding_duration = exit_time - trade_log.entry_time
            elif trade_log.exit_price is not None and trade_log.exit_time is None:
                trade_log.exit_time = utc_now()
                if trade_log.entry_time:
                    trade_log.holding_duration = trade_log.exit_time - trade_log.entry_time

            if pnl_percent is not None:
                trade_log.pnl_percent = _parse_decimal(pnl_percent)

            if isinstance(stop_loss_reason, str):
                try:
                    trade_log.stop_loss_reason = StopLossReason(stop_loss_reason)
                except ValueError:
                    trade_log.stop_loss_reason = StopLossReason.UNKNOWN
            elif stop_loss_reason is not None:
                trade_log.stop_loss_reason = stop_loss_reason

            if notes is not None:
                trade_log.notes = notes

            trade_log.updated_at = utc_now()

        self._save_logs()
        logger.info("更新交易日志: trade_id=%d, exit_price=%s, pnl=%s%%", trade_id, exit_price, pnl_percent)

        return trade_log

    def get_trade(self, trade_id: int) -> TradeLog | None:
        """获取单条交易日志。"""
        with self._lock:
            return self._trade_logs.get(trade_id)

    def get_trade_history(
        self,
        symbol: str | None = None,
        side: str | None = None,
        strategy_name: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[TradeLog]:
        """查询交易历史。

        Args:
            symbol: 筛选交易对（可选）
            side: 筛选方向 buy/sell（可选）
            strategy_name: 筛选策略名称（可选）
            start_time: 开始时间（可选）
            end_time: 结束时间（可选）
            limit: 返回数量限制
            offset: 偏移量

        Returns:
            list[TradeLog]: 交易日志列表
        """
        with self._lock:
            logs = list(self._trade_logs.values())

        # 应用筛选条件
        if symbol:
            logs = [l for l in logs if l.symbol == symbol.strip().upper()]

        if side:
            logs = [l for l in logs if l.side == side.lower()]

        if strategy_name:
            logs = [l for l in logs if l.strategy_name == strategy_name]

        if start_time:
            logs = [l for l in logs if l.entry_time >= start_time]

        if end_time:
            logs = [l for l in logs if l.entry_time <= end_time]

        # 按时间倒序排列
        logs.sort(key=lambda x: x.entry_time, reverse=True)

        return logs[offset:offset + limit]

    def get_open_positions(self) -> list[TradeLog]:
        """获取当前未平仓的交易。"""
        with self._lock:
            return [l for l in self._trade_logs.values() if l.exit_time is None]

    def get_statistics(
        self,
        symbol: str | None = None,
        strategy_name: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> dict[str, Any]:
        """获取交易统计数据。

        Args:
            symbol: 筛选交易对（可选）
            strategy_name: 筛选策略名称（可选）
            start_time: 开始时间（可选）
            end_time: 结束时间（可选）

        Returns:
            dict: 统计数据
        """
        logs = self.get_trade_history(
            symbol=symbol,
            strategy_name=strategy_name,
            start_time=start_time,
            end_time=end_time,
            limit=10000,
        )

        # 只统计已平仓的交易
        closed_logs = [l for l in logs if l.exit_time is not None and l.pnl_percent is not None]

        if not closed_logs:
            return {
                "total_trades": 0,
                "win_count": 0,
                "loss_count": 0,
                "win_rate": "0",
                "total_pnl_percent": "0",
                "avg_pnl_percent": "0",
                "avg_holding_duration_seconds": None,
                "max_profit_percent": "0",
                "max_loss_percent": "0",
            }

        pnl_values = [l.pnl_percent for l in closed_logs]
        win_count = sum(1 for p in pnl_values if p > 0)
        loss_count = sum(1 for p in pnl_values if p < 0)
        total_pnl = sum(pnl_values)
        avg_pnl = total_pnl / len(pnl_values)
        max_profit = max(pnl_values)
        max_loss = min(pnl_values)

        holding_durations = [l.holding_duration for l in closed_logs if l.holding_duration]
        avg_holding_seconds = None
        if holding_durations:
            avg_holding_seconds = sum(d.total_seconds() for d in holding_durations) / len(holding_durations)

        return {
            "total_trades": len(closed_logs),
            "win_count": win_count,
            "loss_count": loss_count,
            "win_rate": str(Decimal(win_count / len(closed_logs)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)),
            "total_pnl_percent": str(total_pnl.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)),
            "avg_pnl_percent": str(avg_pnl.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)),
            "avg_holding_duration_seconds": avg_holding_seconds,
            "max_profit_percent": str(max_profit.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)),
            "max_loss_percent": str(max_loss.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)),
        }

    def get_service_status(self) -> dict[str, Any]:
        """获取服务状态。"""
        with self._lock:
            return {
                "status": "ready",
                "total_logs": len(self._trade_logs),
                "open_positions": len([l for l in self._trade_logs.values() if l.exit_time is None]),
                "next_trade_id": self._next_trade_id,
                "config_path": str(self._config_path) if self._config_path else None,
            }


# 全局交易日志服务实例
trade_log_service = TradeLogService()

# 设置配置持久化路径
config_dir = Path(__file__).parent.parent.parent.parent.parent / "data" / "config"
config_dir.mkdir(parents=True, exist_ok=True)
trade_log_service.set_config_path(config_dir / "trade_logs.json")