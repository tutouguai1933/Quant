"""数据分析服务，提供交易统计和归因分析。

该服务负责:
- 每日/每周交易统计
- 盈亏归因分析
- 策略表现对比
- 交易历史查询
"""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

from services.api.app.core.settings import Settings
from services.api.app.services.sync_service import sync_service
from services.api.app.services.signal_service import signal_service


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


def _parse_timestamp(value: object) -> datetime | None:
    """安全解析时间戳。"""
    if value is None:
        return None
    try:
        raw = str(value).strip().replace("Z", "+00:00")
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def _start_of_day(dt: datetime) -> datetime:
    """返回当天的零点。"""
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)


def _start_of_week(dt: datetime) -> datetime:
    """返回当周周一零点。"""
    weekday = dt.weekday()
    return _start_of_day(dt - timedelta(days=weekday))


@dataclass(slots=True)
class TradeRecord:
    """单笔交易记录。"""
    trade_id: str
    symbol: str
    side: str  # buy/sell
    quantity: Decimal
    price: Decimal
    pnl: Decimal
    executed_at: datetime
    strategy_id: int | None = None
    signal_id: int | None = None
    source: str = "freqtrade"

    def to_dict(self) -> dict[str, object]:
        return {
            "trade_id": self.trade_id,
            "symbol": self.symbol,
            "side": self.side,
            "quantity": str(self.quantity),
            "price": str(self.price),
            "pnl": str(self.pnl),
            "executed_at": self.executed_at.isoformat(),
            "strategy_id": self.strategy_id,
            "signal_id": self.signal_id,
            "source": self.source,
        }


@dataclass(slots=True)
class DailySummary:
    """每日统计汇总。"""
    date: str  # YYYY-MM-DD
    trade_count: int
    buy_count: int
    sell_count: int
    total_pnl: Decimal
    win_count: int
    loss_count: int
    win_rate: Decimal
    avg_pnl: Decimal
    max_profit: Decimal
    max_loss: Decimal
    symbols: list[str]

    def to_dict(self) -> dict[str, object]:
        return {
            "date": self.date,
            "trade_count": self.trade_count,
            "buy_count": self.buy_count,
            "sell_count": self.sell_count,
            "total_pnl": str(self.total_pnl),
            "win_count": self.win_count,
            "loss_count": self.loss_count,
            "win_rate": str(self.win_rate),
            "avg_pnl": str(self.avg_pnl),
            "max_profit": str(self.max_profit),
            "max_loss": str(self.max_loss),
            "symbols": self.symbols,
        }


@dataclass(slots=True)
class WeeklySummary:
    """每周统计汇总。"""
    week_start: str  # YYYY-MM-DD (周一)
    week_end: str  # YYYY-MM-DD (周日)
    trade_count: int
    total_pnl: Decimal
    win_count: int
    loss_count: int
    win_rate: Decimal
    daily_breakdown: list[dict[str, object]]
    best_day: str  # date of best performance
    worst_day: str  # date of worst performance

    def to_dict(self) -> dict[str, object]:
        return {
            "week_start": self.week_start,
            "week_end": self.week_end,
            "trade_count": self.trade_count,
            "total_pnl": str(self.total_pnl),
            "win_count": self.win_count,
            "loss_count": self.loss_count,
            "win_rate": str(self.win_rate),
            "daily_breakdown": self.daily_breakdown,
            "best_day": self.best_day,
            "worst_day": self.worst_day,
        }


@dataclass(slots=True)
class PnlAttribution:
    """盈亏归因分析。"""
    by_symbol: dict[str, dict[str, object]]
    by_strategy: dict[str, dict[str, object]]
    by_time_period: dict[str, dict[str, object]]
    top_profit_symbols: list[dict[str, object]]
    top_loss_symbols: list[dict[str, object]]

    def to_dict(self) -> dict[str, object]:
        return {
            "by_symbol": self.by_symbol,
            "by_strategy": self.by_strategy,
            "by_time_period": self.by_time_period,
            "top_profit_symbols": self.top_profit_symbols,
            "top_loss_symbols": self.top_loss_symbols,
        }


@dataclass(slots=True)
class StrategyPerformance:
    """策略表现对比。"""
    strategy_id: int | None
    strategy_name: str
    trade_count: int
    total_pnl: Decimal
    win_rate: Decimal
    avg_pnl: Decimal
    max_profit: Decimal
    max_loss: Decimal
    sharpe_ratio: Decimal | None

    def to_dict(self) -> dict[str, object]:
        return {
            "strategy_id": self.strategy_id,
            "strategy_name": self.strategy_name,
            "trade_count": self.trade_count,
            "total_pnl": str(self.total_pnl),
            "win_rate": str(self.win_rate),
            "avg_pnl": str(self.avg_pnl),
            "max_profit": str(self.max_profit),
            "max_loss": str(self.max_loss),
            "sharpe_ratio": str(self.sharpe_ratio) if self.sharpe_ratio is not None else None,
        }


class AnalyticsService:
    """数据分析服务，聚合交易数据并提供统计功能。"""

    def __init__(self) -> None:
        self._trade_history: dict[str, TradeRecord] = {}
        self._trade_lock = threading.Lock()
        self._history_days: int = self._load_history_days()
        self._last_sync_at: datetime | None = None

    def _load_history_days(self) -> int:
        """读取历史天数配置。"""
        raw = os.getenv("QUANT_ANALYTICS_HISTORY_DAYS", "30").strip()
        try:
            days = int(raw)
            return max(1, min(days, 365))
        except ValueError:
            return 30

    @property
    def history_days(self) -> int:
        """返回历史查询天数。"""
        return self._history_days

    def refresh_trade_history(self) -> dict[str, object]:
        """从执行器同步最新的交易记录。"""
        settings = Settings.from_env()
        try:
            snapshot = sync_service.sync_execution_state()
            orders = list(snapshot.get("orders", []))
            positions = list(snapshot.get("positions", []))
        except Exception:
            orders = []
            positions = []

        with self._trade_lock:
            # 清理过期记录
            cutoff = utc_now() - timedelta(days=self._history_days)
            expired_ids = [
                trade_id
                for trade_id, trade in self._trade_history.items()
                if trade.executed_at < cutoff
            ]
            for trade_id in expired_ids:
                self._trade_history.pop(trade_id, None)

            # 从订单记录更新
            for order in orders:
                self._ingest_order_as_trade(order)

            # 从持仓记录更新 PnL
            for position in positions:
                self._update_position_pnl(position)

            self._last_sync_at = utc_now()

        return {
            "status": "synced",
            "trade_count": len(self._trade_history),
            "history_days": self._history_days,
            "last_sync_at": self._last_sync_at.isoformat() if self._last_sync_at else None,
        }

    def _ingest_order_as_trade(self, order: dict[str, object]) -> None:
        """将订单记录转换为交易记录。"""
        order_id = str(order.get("id") or order.get("venueOrderId") or "")
        if not order_id:
            return

        # 跳过已存在的记录
        if order_id in self._trade_history:
            return

        executed_at = _parse_timestamp(order.get("updatedAt") or order.get("time"))
        if executed_at is None:
            executed_at = utc_now()

        # 检查是否在历史范围内
        cutoff = utc_now() - timedelta(days=self._history_days)
        if executed_at < cutoff:
            return

        symbol = str(order.get("symbol", "")).strip().upper()
        side = str(order.get("side", "")).strip().lower()
        quantity = _parse_decimal(order.get("executedQty") or order.get("quantity"))
        price = _parse_decimal(order.get("avgPrice") or order.get("price"))

        strategy_id = None
        raw_strategy_id = order.get("strategyId")
        if raw_strategy_id is not None:
            try:
                strategy_id = int(raw_strategy_id)
            except (TypeError, ValueError):
                pass

        signal_id = None
        raw_signal_id = order.get("sourceSignalId")
        if raw_signal_id is not None:
            try:
                signal_id = int(raw_signal_id)
            except (TypeError, ValueError):
                pass

        # 计算 PnL（简化版，仅对卖出计算）
        pnl = Decimal("0")
        if side == "sell":
            # 查找对应的买入记录来计算 PnL
            pnl = self._estimate_sell_pnl(symbol, quantity, price)

        trade = TradeRecord(
            trade_id=order_id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
            pnl=pnl,
            executed_at=executed_at,
            strategy_id=strategy_id,
            signal_id=signal_id,
            source="freqtrade",
        )
        self._trade_history[order_id] = trade

    def _estimate_sell_pnl(self, symbol: str, quantity: Decimal, sell_price: Decimal) -> Decimal:
        """估算卖出交易的盈亏。"""
        buy_trades = [
            trade for trade in self._trade_history.values()
            if trade.symbol == symbol and trade.side == "buy"
        ]
        if not buy_trades:
            return Decimal("0")

        # 使用最早的买入价格作为参考
        earliest_buy = min(buy_trades, key=lambda t: t.executed_at)
        buy_price = earliest_buy.price
        pnl = (sell_price - buy_price) * quantity
        return pnl.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)

    def _update_position_pnl(self, position: dict[str, object]) -> None:
        """从持仓记录更新未实现盈亏。"""
        symbol = str(position.get("symbol", "")).strip().upper()
        unrealized_pnl = _parse_decimal(position.get("unrealizedPnl"))
        # 暂不处理未实现盈亏，仅记录已实现盈亏

    def get_daily_summary(self, date: str | None = None) -> DailySummary:
        """获取每日交易统计。

        Args:
            date: YYYY-MM-DD 格式的日期，默认为今天
        """
        if date is None:
            target_date = _start_of_day(utc_now())
        else:
            try:
                parsed = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                target_date = _start_of_day(parsed)
            except ValueError:
                target_date = _start_of_day(utc_now())

        next_date = target_date + timedelta(days=1)

        with self._trade_lock:
            day_trades = [
                trade for trade in self._trade_history.values()
                if target_date <= trade.executed_at < next_date
            ]

        if not day_trades:
            return DailySummary(
                date=target_date.strftime("%Y-%m-%d"),
                trade_count=0,
                buy_count=0,
                sell_count=0,
                total_pnl=Decimal("0"),
                win_count=0,
                loss_count=0,
                win_rate=Decimal("0"),
                avg_pnl=Decimal("0"),
                max_profit=Decimal("0"),
                max_loss=Decimal("0"),
                symbols=[],
            )

        buy_count = sum(1 for t in day_trades if t.side == "buy")
        sell_count = sum(1 for t in day_trades if t.side == "sell")
        pnls = [t.pnl for t in day_trades]
        total_pnl = sum(pnls)
        win_count = sum(1 for pnl in pnls if pnl > 0)
        loss_count = sum(1 for pnl in pnls if pnl < 0)
        total_with_pnl = win_count + loss_count
        win_rate = Decimal(win_count) / Decimal(total_with_pnl) if total_with_pnl > 0 else Decimal("0")
        avg_pnl = total_pnl / Decimal(len(day_trades)) if day_trades else Decimal("0")
        max_profit = max(pnls) if pnls else Decimal("0")
        max_loss = min(pnls) if pnls else Decimal("0")
        symbols = sorted(set(t.symbol for t in day_trades if t.symbol))

        return DailySummary(
            date=target_date.strftime("%Y-%m-%d"),
            trade_count=len(day_trades),
            buy_count=buy_count,
            sell_count=sell_count,
            total_pnl=total_pnl.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP),
            win_count=win_count,
            loss_count=loss_count,
            win_rate=win_rate.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP),
            avg_pnl=avg_pnl.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP),
            max_profit=max_profit.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP),
            max_loss=max_loss.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP),
            symbols=symbols,
        )

    def get_weekly_summary(self, week_start: str | None = None) -> WeeklySummary:
        """获取每周交易统计。

        Args:
            week_start: YYYY-MM-DD 格式的周一日期，默认为本周
        """
        if week_start is None:
            target_week = _start_of_week(utc_now())
        else:
            try:
                parsed = datetime.strptime(week_start, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                target_week = _start_of_week(parsed)
            except ValueError:
                target_week = _start_of_week(utc_now())

        week_end = target_week + timedelta(days=6)
        week_end_next = target_week + timedelta(days=7)

        daily_summaries: list[dict[str, object]] = []
        for day_offset in range(7):
            day_date = target_week + timedelta(days=day_offset)
            summary = self.get_daily_summary(day_date.strftime("%Y-%m-%d"))
            daily_summaries.append(summary.to_dict())

        with self._trade_lock:
            week_trades = [
                trade for trade in self._trade_history.values()
                if target_week <= trade.executed_at < week_end_next
            ]

        if not week_trades:
            return WeeklySummary(
                week_start=target_week.strftime("%Y-%m-%d"),
                week_end=week_end.strftime("%Y-%m-%d"),
                trade_count=0,
                total_pnl=Decimal("0"),
                win_count=0,
                loss_count=0,
                win_rate=Decimal("0"),
                daily_breakdown=daily_summaries,
                best_day="",
                worst_day="",
            )

        pnls = [t.pnl for t in week_trades]
        total_pnl = sum(pnls)
        win_count = sum(1 for pnl in pnls if pnl > 0)
        loss_count = sum(1 for pnl in pnls if pnl < 0)
        total_with_pnl = win_count + loss_count
        win_rate = Decimal(win_count) / Decimal(total_with_pnl) if total_with_pnl > 0 else Decimal("0")

        # 找出最佳和最差日
        best_day = ""
        worst_day = ""
        best_pnl = Decimal("-999999999")
        worst_pnl = Decimal("999999999")
        for day_summary in daily_summaries:
            day_pnl = _parse_decimal(day_summary.get("total_pnl"))
            day_date = str(day_summary.get("date", ""))
            if day_pnl > best_pnl:
                best_pnl = day_pnl
                best_day = day_date
            if day_pnl < worst_pnl:
                worst_pnl = day_pnl
                worst_day = day_date

        return WeeklySummary(
            week_start=target_week.strftime("%Y-%m-%d"),
            week_end=week_end.strftime("%Y-%m-%d"),
            trade_count=len(week_trades),
            total_pnl=total_pnl.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP),
            win_count=win_count,
            loss_count=loss_count,
            win_rate=win_rate.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP),
            daily_breakdown=daily_summaries,
            best_day=best_day,
            worst_day=worst_day,
        )

    def get_pnl_attribution(self, days: int | None = None) -> PnlAttribution:
        """盈亏归因分析。

        Args:
            days: 分析天数，默认使用配置的历史天数
        """
        if days is None:
            days = self._history_days
        cutoff = utc_now() - timedelta(days=days)

        with self._trade_lock:
            relevant_trades = [
                trade for trade in self._trade_history.values()
                if trade.executed_at >= cutoff
            ]

        # 按标的分组
        by_symbol: dict[str, dict[str, object]] = {}
        for trade in relevant_trades:
            symbol = trade.symbol
            if symbol not in by_symbol:
                by_symbol[symbol] = {
                    "symbol": symbol,
                    "trade_count": 0,
                    "total_pnl": Decimal("0"),
                    "buy_count": 0,
                    "sell_count": 0,
                }
            by_symbol[symbol]["trade_count"] += 1
            by_symbol[symbol]["total_pnl"] += trade.pnl
            if trade.side == "buy":
                by_symbol[symbol]["buy_count"] += 1
            else:
                by_symbol[symbol]["sell_count"] += 1

        # 转换 Decimal 到字符串
        for symbol_data in by_symbol.values():
            symbol_data["total_pnl"] = str(symbol_data["total_pnl"].quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP))

        # 按策略分组
        by_strategy: dict[str, dict[str, object]] = {}
        for trade in relevant_trades:
            strategy_key = str(trade.strategy_id) if trade.strategy_id is not None else "unknown"
            strategy_name = self._resolve_strategy_name(trade.strategy_id)
            if strategy_key not in by_strategy:
                by_strategy[strategy_key] = {
                    "strategy_id": trade.strategy_id,
                    "strategy_name": strategy_name,
                    "trade_count": 0,
                    "total_pnl": Decimal("0"),
                }
            by_strategy[strategy_key]["trade_count"] += 1
            by_strategy[strategy_key]["total_pnl"] += trade.pnl

        for strategy_data in by_strategy.values():
            strategy_data["total_pnl"] = str(strategy_data["total_pnl"].quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP))

        # 按时段分组（上午/下午/夜间 UTC）
        by_time_period: dict[str, dict[str, object]] = {
            "morning": {"period": "06:00-12:00 UTC", "trade_count": 0, "total_pnl": Decimal("0")},
            "afternoon": {"period": "12:00-18:00 UTC", "trade_count": 0, "total_pnl": Decimal("0")},
            "evening": {"period": "18:00-24:00 UTC", "trade_count": 0, "total_pnl": Decimal("0")},
            "night": {"period": "00:00-06:00 UTC", "trade_count": 0, "total_pnl": Decimal("0")},
        }
        for trade in relevant_trades:
            hour = trade.executed_at.hour
            if 6 <= hour < 12:
                by_time_period["morning"]["trade_count"] += 1
                by_time_period["morning"]["total_pnl"] += trade.pnl
            elif 12 <= hour < 18:
                by_time_period["afternoon"]["trade_count"] += 1
                by_time_period["afternoon"]["total_pnl"] += trade.pnl
            elif 18 <= hour < 24:
                by_time_period["evening"]["trade_count"] += 1
                by_time_period["evening"]["total_pnl"] += trade.pnl
            else:
                by_time_period["night"]["trade_count"] += 1
                by_time_period["night"]["total_pnl"] += trade.pnl

        for period_data in by_time_period.values():
            period_data["total_pnl"] = str(period_data["total_pnl"].quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP))

        # 排序得出最佳和最差标的
        symbol_pnls = [
            {"symbol": symbol, "total_pnl": _parse_decimal(data["total_pnl"])}
            for symbol, data in by_symbol.items()
        ]
        top_profit_symbols = sorted(
            [s for s in symbol_pnls if s["total_pnl"] > 0],
            key=lambda x: x["total_pnl"],
            reverse=True,
        )[:5]
        for s in top_profit_symbols:
            s["total_pnl"] = str(s["total_pnl"])

        top_loss_symbols = sorted(
            [s for s in symbol_pnls if s["total_pnl"] < 0],
            key=lambda x: x["total_pnl"],
        )[:5]
        for s in top_loss_symbols:
            s["total_pnl"] = str(s["total_pnl"])

        return PnlAttribution(
            by_symbol=by_symbol,
            by_strategy=by_strategy,
            by_time_period=by_time_period,
            top_profit_symbols=top_profit_symbols,
            top_loss_symbols=top_loss_symbols,
        )

    def get_strategy_performance(self, strategy_id: int | None = None) -> list[StrategyPerformance]:
        """策略表现对比。

        Args:
            strategy_id: 可选的策略ID，用于筛选单个策略
        """
        cutoff = utc_now() - timedelta(days=self._history_days)

        with self._trade_lock:
            relevant_trades = [
                trade for trade in self._trade_history.values()
                if trade.executed_at >= cutoff
            ]

        # 按策略分组
        strategy_trades: dict[int | None, list[TradeRecord]] = {}
        for trade in relevant_trades:
            key = trade.strategy_id
            if strategy_id is not None and key != strategy_id:
                continue
            if key not in strategy_trades:
                strategy_trades[key] = []
            strategy_trades[key].append(trade)

        performances: list[StrategyPerformance] = []
        for st_id, trades in strategy_trades.items():
            if not trades:
                continue

            strategy_name = self._resolve_strategy_name(st_id)
            pnls = [t.pnl for t in trades]
            total_pnl = sum(pnls)
            win_count = sum(1 for pnl in pnls if pnl > 0)
            loss_count = sum(1 for pnl in pnls if pnl < 0)
            total_with_pnl = win_count + loss_count
            win_rate = Decimal(win_count) / Decimal(total_with_pnl) if total_with_pnl > 0 else Decimal("0")
            avg_pnl = total_pnl / Decimal(len(trades)) if trades else Decimal("0")
            max_profit = max(pnls) if pnls else Decimal("0")
            max_loss = min(pnls) if pnls else Decimal("0")

            # 简化计算 Sharpe（需要更多历史数据）
            sharpe_ratio = None
            if len(pnls) >= 5:
                avg = avg_pnl
                variance = sum((pnl - avg) ** 2 for pnl in pnls) / Decimal(len(pnls))
                std_dev = variance.sqrt() if variance > 0 else Decimal("0")
                if std_dev > 0:
                    sharpe_ratio = avg / std_dev

            performances.append(StrategyPerformance(
                strategy_id=st_id,
                strategy_name=strategy_name,
                trade_count=len(trades),
                total_pnl=total_pnl.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP),
                win_rate=win_rate.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP),
                avg_pnl=avg_pnl.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP),
                max_profit=max_profit.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP),
                max_loss=max_loss.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP),
                sharpe_ratio=sharpe_ratio,
            ))

        # 按总盈亏排序
        performances.sort(key=lambda p: p.total_pnl, reverse=True)
        return performances

    def get_trade_history(
        self,
        limit: int = 100,
        symbol: str | None = None,
        side: str | None = None,
        strategy_id: int | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[dict[str, object]]:
        """交易历史查询。

        Args:
            limit: 返回记录数量上限
            symbol: 标的筛选
            side: 方向筛选（buy/sell）
            strategy_id: 策略筛选
            start_date: 开始日期（YYYY-MM-DD）
            end_date: 结束日期（YYYY-MM-DD）
        """
        cutoff = utc_now() - timedelta(days=self._history_days)

        # 解析日期筛选
        start_dt = None
        end_dt = None
        if start_date:
            try:
                start_dt = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except ValueError:
                pass
        if end_date:
            try:
                end_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=timezone.utc) + timedelta(days=1)
            except ValueError:
                pass

        with self._trade_lock:
            trades = list(self._trade_history.values())

        # 应用筛选条件
        filtered_trades: list[TradeRecord] = []
        for trade in trades:
            if trade.executed_at < cutoff:
                continue
            if symbol and trade.symbol != symbol.strip().upper():
                continue
            if side and trade.side != side.strip().lower():
                continue
            if strategy_id is not None and trade.strategy_id != strategy_id:
                continue
            if start_dt and trade.executed_at < start_dt:
                continue
            if end_dt and trade.executed_at >= end_dt:
                continue
            filtered_trades.append(trade)

        # 按时间倒序排列
        filtered_trades.sort(key=lambda t: t.executed_at, reverse=True)

        # 返回限制数量
        return [trade.to_dict() for trade in filtered_trades[:limit]]

    def _resolve_strategy_name(self, strategy_id: int | None) -> str:
        """解析策略名称。"""
        if strategy_id is None:
            return "Unknown Strategy"
        strategy_names = {
            1: "BTC Trend",
            2: "ETH Momentum",
            3: "Multi-Asset",
        }
        return strategy_names.get(strategy_id, f"Strategy {strategy_id}")

    def get_service_status(self) -> dict[str, object]:
        """返回服务状态。"""
        with self._trade_lock:
            trade_count = len(self._trade_history)
        return {
            "status": "ready",
            "history_days": self._history_days,
            "trade_count": trade_count,
            "last_sync_at": self._last_sync_at.isoformat() if self._last_sync_at else None,
        }


# 单例实例
analytics_service = AnalyticsService()