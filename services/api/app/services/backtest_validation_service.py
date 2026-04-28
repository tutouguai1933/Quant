"""回测验证服务 - 用历史数据验证策略有效性。

提供历史数据加载、模拟交易执行、指标计算和策略对比功能。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from services.api.app.adapters.binance.market_client import BinanceMarketClient


@dataclass
class Trade:
    """模拟交易记录。"""

    entry_time: int
    exit_time: int
    entry_price: Decimal
    exit_price: Decimal
    quantity: Decimal
    side: str  # "long" or "short"
    pnl: Decimal = Decimal("0")
    pnl_pct: Decimal = Decimal("0")
    reason: str = ""


@dataclass
class BacktestConfig:
    """回测配置。"""

    symbol: str
    strategy_type: str  # "trend_breakout" or "trend_pullback"
    timeframe: str = "4h"
    lookback_bars: int = 20
    initial_capital: Decimal = Decimal("10000")
    fee_bps: int = 10  # 手续费基点
    slippage_bps: int = 5  # 滑点基点
    position_size_pct: Decimal = Decimal("100")  # 仓位比例
    stop_loss_pct: Decimal = Decimal("5")  # 止损百分比
    take_profit_pct: Decimal = Decimal("10")  # 止盈百分比
    breakout_buffer_pct: Decimal = Decimal("0.5")  # 突破缓冲
    pullback_depth_pct: Decimal = Decimal("3")  # 回调深度


@dataclass
class BacktestMetrics:
    """回测指标。"""

    total_return: Decimal = Decimal("0")
    total_return_pct: Decimal = Decimal("0")
    annualized_return_pct: Decimal = Decimal("0")
    sharpe_ratio: Decimal = Decimal("0")
    max_drawdown: Decimal = Decimal("0")
    max_drawdown_pct: Decimal = Decimal("0")
    win_rate: Decimal = Decimal("0")
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    avg_profit: Decimal = Decimal("0")
    avg_loss: Decimal = Decimal("0")
    profit_factor: Decimal = Decimal("0")
    avg_trade_duration_hours: Decimal = Decimal("0")
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0


@dataclass
class BacktestResult:
    """回测结果。"""

    config: BacktestConfig
    metrics: BacktestMetrics
    trades: list[Trade] = field(default_factory=list)
    equity_curve: list[dict[str, Any]] = field(default_factory=list)
    start_time: int = 0
    end_time: int = 0
    status: str = "pending"
    error: str = ""


class BacktestValidationService:
    """回测验证服务。"""

    def __init__(
        self,
        market_client: BinanceMarketClient | None = None,
        max_klines_limit: int = 1000,
    ) -> None:
        self._client = market_client or BinanceMarketClient()
        self._max_klines_limit = max_klines_limit

    def load_historical_data(
        self,
        symbol: str,
        days: int = 30,
        interval: str = "4h",
    ) -> list[dict[str, Any]]:
        """加载历史K线数据。

        Args:
            symbol: 交易对符号，如 BTCUSDT
            days: 历史数据天数
            interval: K线间隔

        Returns:
            标准化的K线数据列表
        """
        normalized_symbol = symbol.strip().upper()

        # 根据间隔计算需要的K线数量
        intervals_per_day = self._get_intervals_per_day(interval)
        limit = min(days * intervals_per_day, self._max_klines_limit)

        raw_klines = self._client.get_klines(
            symbol=normalized_symbol,
            interval=interval,
            limit=limit,
        )

        klines = self._normalize_klines(raw_klines)
        return klines

    def simulate_trades(
        self,
        config: BacktestConfig,
        klines: list[dict[str, Any]] | None = None,
    ) -> BacktestResult:
        """模拟策略执行。

        Args:
            config: 回测配置
            klines: 可选的K线数据，如未提供则自动加载

        Returns:
            回测结果
        """
        result = BacktestResult(config=config, metrics=BacktestMetrics())

        try:
            # 加载历史数据
            if klines is None:
                klines = self.load_historical_data(
                    symbol=config.symbol,
                    days=30,
                    interval=config.timeframe,
                )

            if len(klines) < config.lookback_bars + 2:
                result.status = "error"
                result.error = f"Insufficient data: need {config.lookback_bars + 2}, got {len(klines)}"
                return result

            result.start_time = klines[0].get("open_time", 0)
            result.end_time = klines[-1].get("close_time", 0)

            # 根据策略类型执行模拟
            if config.strategy_type == "trend_breakout":
                trades = self._simulate_trend_breakout(config, klines)
            elif config.strategy_type == "trend_pullback":
                trades = self._simulate_trend_pullback(config, klines)
            else:
                result.status = "error"
                result.error = f"Unknown strategy type: {config.strategy_type}"
                return result

            result.trades = trades
            result.metrics = self.calculate_metrics(trades, config)

            # 构建权益曲线
            result.equity_curve = self._build_equity_curve(trades, config)

            result.status = "completed"
            return result

        except Exception as e:
            result.status = "error"
            result.error = str(e)
            return result

    def calculate_metrics(
        self,
        trades: list[Trade],
        config: BacktestConfig,
    ) -> BacktestMetrics:
        """计算回测指标。

        Args:
            trades: 交易列表
            config: 回测配置

        Returns:
            回测指标
        """
        metrics = BacktestMetrics()
        metrics.total_trades = len(trades)

        if not trades:
            return metrics

        # 计算盈亏
        total_pnl = Decimal("0")
        total_profit = Decimal("0")
        total_loss = Decimal("0")
        winning_trades = 0
        losing_trades = 0
        total_duration = Decimal("0")

        for trade in trades:
            total_pnl += trade.pnl
            total_duration += Decimal(str(trade.exit_time - trade.entry_time))

            if trade.pnl > 0:
                winning_trades += 1
                total_profit += trade.pnl
            else:
                losing_trades += 1
                total_loss += abs(trade.pnl)

        metrics.winning_trades = winning_trades
        metrics.losing_trades = losing_trades

        # 总收益率
        metrics.total_return = total_pnl
        metrics.total_return_pct = (total_pnl / config.initial_capital) * Decimal("100")

        # 年化收益率
        if trades:
            start_time = trades[0].entry_time
            end_time = trades[-1].exit_time
            duration_days = Decimal(str(end_time - start_time)) / Decimal("86400000")
            if duration_days > 0:
                annualized_return = metrics.total_return_pct * (Decimal("365") / duration_days)
                metrics.annualized_return_pct = annualized_return

        # 胜率
        metrics.win_rate = Decimal(str(winning_trades)) / Decimal(str(metrics.total_trades)) * Decimal("100")

        # 平均盈亏
        if winning_trades > 0:
            metrics.avg_profit = total_profit / Decimal(str(winning_trades))
        if losing_trades > 0:
            metrics.avg_loss = total_loss / Decimal(str(losing_trades))

        # 盈亏比
        if total_loss > 0:
            metrics.profit_factor = total_profit / total_loss
        elif total_profit > 0:
            metrics.profit_factor = Decimal("999")

        # 平均持仓时间（小时）
        if trades:
            metrics.avg_trade_duration_hours = (total_duration / Decimal(str(len(trades)))) / Decimal("3600000")

        # 最大回撤
        metrics.max_drawdown, metrics.max_drawdown_pct = self._calculate_max_drawdown(trades, config)

        # 夏普比率
        metrics.sharpe_ratio = self._calculate_sharpe_ratio(trades)

        # 最大连续盈亏
        metrics.max_consecutive_wins, metrics.max_consecutive_losses = self._calculate_consecutive(trades)

        return metrics

    def compare_strategies(
        self,
        configs: list[BacktestConfig],
        klines: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        """对比不同策略配置。

        Args:
            configs: 策略配置列表
            klines: 可选的共享K线数据

        Returns:
            对比结果列表
        """
        results = []

        for config in configs:
            result = self.simulate_trades(config, klines)
            results.append(
                {
                    "symbol": config.symbol,
                    "strategy_type": config.strategy_type,
                    "timeframe": config.timeframe,
                    "lookback_bars": config.lookback_bars,
                    "status": result.status,
                    "total_return_pct": str(result.metrics.total_return_pct),
                    "sharpe_ratio": str(result.metrics.sharpe_ratio),
                    "max_drawdown_pct": str(result.metrics.max_drawdown_pct),
                    "win_rate": str(result.metrics.win_rate),
                    "total_trades": result.metrics.total_trades,
                    "avg_profit": str(result.metrics.avg_profit),
                    "avg_loss": str(result.metrics.avg_loss),
                    "profit_factor": str(result.metrics.profit_factor),
                    "error": result.error,
                }
            )

        # 按总收益率排序
        results.sort(key=lambda x: Decimal(x["total_return_pct"]), reverse=True)

        return results

    def _simulate_trend_breakout(
        self,
        config: BacktestConfig,
        klines: list[dict[str, Any]],
    ) -> list[Trade]:
        """模拟趋势突破策略。"""
        trades: list[Trade] = []
        position: dict[str, Any] | None = None

        for i in range(config.lookback_bars, len(klines)):
            current_candle = klines[i]
            historical_candles = klines[i - config.lookback_bars : i]

            if position is None:
                # 检查买入信号
                signal = self._check_breakout_signal(
                    current_candle,
                    historical_candles,
                    config.breakout_buffer_pct,
                )

                if signal:
                    # 开仓
                    entry_price = signal["entry_price"]
                    position = {
                        "entry_time": current_candle["open_time"],
                        "entry_price": entry_price,
                        "quantity": (config.initial_capital * config.position_size_pct / Decimal("100")) / entry_price,
                        "stop_loss": entry_price * (Decimal("1") - config.stop_loss_pct / Decimal("100")),
                        "take_profit": entry_price * (Decimal("1") + config.take_profit_pct / Decimal("100")),
                    }
            else:
                # 检查卖出信号
                close_price = Decimal(str(current_candle["close"]))
                low_price = Decimal(str(current_candle["low"]))

                exit_reason = ""
                exit_price = None

                if low_price <= position["stop_loss"]:
                    exit_price = position["stop_loss"]
                    exit_reason = "stop_loss"
                elif close_price >= position["take_profit"]:
                    exit_price = position["take_profit"]
                    exit_reason = "take_profit"
                elif self._check_breakdown_signal(current_candle, historical_candles, config.breakout_buffer_pct):
                    exit_price = close_price
                    exit_reason = "breakdown"

                if exit_price:
                    # 计算盈亏（扣除手续费和滑点）
                    fee = exit_price * Decimal(str(config.fee_bps)) / Decimal("10000")
                    slippage = exit_price * Decimal(str(config.slippage_bps)) / Decimal("10000")
                    effective_exit = exit_price - fee - slippage

                    pnl = (effective_exit - position["entry_price"]) * position["quantity"]
                    pnl_pct = (effective_exit - position["entry_price"]) / position["entry_price"] * Decimal("100")

                    trades.append(
                        Trade(
                            entry_time=position["entry_time"],
                            exit_time=current_candle["close_time"],
                            entry_price=position["entry_price"],
                            exit_price=exit_price,
                            quantity=position["quantity"],
                            side="long",
                            pnl=pnl,
                            pnl_pct=pnl_pct,
                            reason=exit_reason,
                        )
                    )
                    position = None

        return trades

    def _simulate_trend_pullback(
        self,
        config: BacktestConfig,
        klines: list[dict[str, Any]],
    ) -> list[Trade]:
        """模拟趋势回调策略。"""
        trades: list[Trade] = []
        position: dict[str, Any] | None = None

        for i in range(config.lookback_bars, len(klines)):
            current_candle = klines[i]
            historical_candles = klines[i - config.lookback_bars : i]

            if position is None:
                # 检查买入信号
                signal = self._check_pullback_signal(
                    current_candle,
                    historical_candles,
                    config.pullback_depth_pct,
                )

                if signal:
                    entry_price = signal["entry_price"]
                    position = {
                        "entry_time": current_candle["open_time"],
                        "entry_price": entry_price,
                        "quantity": (config.initial_capital * config.position_size_pct / Decimal("100")) / entry_price,
                        "stop_loss": signal["invalidation_level"],
                        "take_profit": entry_price * (Decimal("1") + config.take_profit_pct / Decimal("100")),
                    }
            else:
                # 检查卖出信号
                close_price = Decimal(str(current_candle["close"]))
                low_price = Decimal(str(current_candle["low"]))

                exit_reason = ""
                exit_price = None

                if low_price <= position["stop_loss"]:
                    exit_price = position["stop_loss"]
                    exit_reason = "invalidation"
                elif close_price >= position["take_profit"]:
                    exit_price = position["take_profit"]
                    exit_reason = "take_profit"
                elif self._check_trend_reversal(current_candle, historical_candles):
                    exit_price = close_price
                    exit_reason = "trend_reversal"

                if exit_price:
                    fee = exit_price * Decimal(str(config.fee_bps)) / Decimal("10000")
                    slippage = exit_price * Decimal(str(config.slippage_bps)) / Decimal("10000")
                    effective_exit = exit_price - fee - slippage

                    pnl = (effective_exit - position["entry_price"]) * position["quantity"]
                    pnl_pct = (effective_exit - position["entry_price"]) / position["entry_price"] * Decimal("100")

                    trades.append(
                        Trade(
                            entry_time=position["entry_time"],
                            exit_time=current_candle["close_time"],
                            entry_price=position["entry_price"],
                            exit_price=exit_price,
                            quantity=position["quantity"],
                            side="long",
                            pnl=pnl,
                            pnl_pct=pnl_pct,
                            reason=exit_reason,
                        )
                    )
                    position = None

        return trades

    def _check_breakout_signal(
        self,
        current_candle: dict[str, Any],
        historical_candles: list[dict[str, Any]],
        buffer_pct: Decimal,
    ) -> dict[str, Any] | None:
        """检查趋势突破买入信号。"""
        if not historical_candles:
            return None

        recent_high = max(Decimal(str(c["high"])) for c in historical_candles)
        close_price = Decimal(str(current_candle["close"]))
        breakout_threshold = recent_high * (Decimal("1") + buffer_pct / Decimal("100"))

        if close_price > breakout_threshold:
            return {
                "entry_price": close_price,
                "breakout_level": breakout_threshold,
            }
        return None

    def _check_breakdown_signal(
        self,
        current_candle: dict[str, Any],
        historical_candles: list[dict[str, Any]],
        buffer_pct: Decimal,
    ) -> bool:
        """检查趋势突破卖出信号（价格跌破区间低点）。"""
        if not historical_candles:
            return False

        recent_low = min(Decimal(str(c["low"])) for c in historical_candles)
        close_price = Decimal(str(current_candle["close"]))
        breakdown_threshold = recent_low * (Decimal("1") - buffer_pct / Decimal("100"))

        return close_price < breakdown_threshold

    def _check_pullback_signal(
        self,
        current_candle: dict[str, Any],
        historical_candles: list[dict[str, Any]],
        pullback_depth_pct: Decimal,
    ) -> dict[str, Any] | None:
        """检查趋势回调买入信号。"""
        if not historical_candles:
            return None

        recent_high = max(Decimal(str(c["high"])) for c in historical_candles)
        recent_low = min(Decimal(str(c["low"])) for c in historical_candles)
        close_price = Decimal(str(current_candle["close"]))
        low_price = Decimal(str(current_candle["low"]))

        pullback_level = recent_high * (Decimal("1") - pullback_depth_pct / Decimal("100"))

        # 检查是否触及回调位并企稳
        if low_price <= pullback_level and close_price >= pullback_level:
            return {
                "entry_price": close_price,
                "pullback_level": pullback_level,
                "invalidation_level": recent_low,
            }
        return None

    def _check_trend_reversal(
        self,
        current_candle: dict[str, Any],
        historical_candles: list[dict[str, Any]],
    ) -> bool:
        """检查趋势反转信号。"""
        if len(historical_candles) < 3:
            return False

        # 简单判断：连续3根阴线
        last_3 = historical_candles[-3:] + [current_candle]
        for candle in last_3:
            open_price = Decimal(str(candle["open"]))
            close_price = Decimal(str(candle["close"]))
            if close_price >= open_price:
                return False
        return True

    def _calculate_max_drawdown(
        self,
        trades: list[Trade],
        config: BacktestConfig,
    ) -> tuple[Decimal, Decimal]:
        """计算最大回撤。"""
        if not trades:
            return Decimal("0"), Decimal("0")

        peak = config.initial_capital
        capital = config.initial_capital
        max_dd = Decimal("0")
        max_dd_pct = Decimal("0")

        for trade in trades:
            capital += trade.pnl
            if capital > peak:
                peak = capital
            dd = peak - capital
            dd_pct = dd / peak * Decimal("100") if peak > 0 else Decimal("0")
            if dd > max_dd:
                max_dd = dd
                max_dd_pct = dd_pct

        return max_dd, max_dd_pct

    def _calculate_sharpe_ratio(
        self,
        trades: list[Trade],
    ) -> Decimal:
        """计算夏普比率。"""
        if len(trades) < 2:
            return Decimal("0")

        # 计算收益率序列
        returns = [float(trade.pnl_pct) for trade in trades]

        # 计算平均收益率
        avg_return = sum(returns) / len(returns)

        # 计算标准差
        if len(returns) < 2:
            return Decimal("0")

        variance = sum((r - avg_return) ** 2 for r in returns) / (len(returns) - 1)
        std_dev = variance**0.5

        if std_dev == 0:
            return Decimal("0")

        # 年化夏普比率（假设每年252个交易日，每4小时约63个交易周期）
        risk_free_rate = 0.0
        sharpe = (avg_return - risk_free_rate) / std_dev
        annualized_sharpe = sharpe * (63**0.5)  # 年化

        return Decimal(str(round(annualized_sharpe, 2)))

    def _calculate_consecutive(
        self,
        trades: list[Trade],
    ) -> tuple[int, int]:
        """计算最大连续盈亏次数。"""
        max_wins = 0
        max_losses = 0
        current_wins = 0
        current_losses = 0

        for trade in trades:
            if trade.pnl > 0:
                current_wins += 1
                current_losses = 0
                max_wins = max(max_wins, current_wins)
            else:
                current_losses += 1
                current_wins = 0
                max_losses = max(max_losses, current_losses)

        return max_wins, max_losses

    def _build_equity_curve(
        self,
        trades: list[Trade],
        config: BacktestConfig,
    ) -> list[dict[str, Any]]:
        """构建权益曲线。"""
        curve = []
        capital = config.initial_capital

        for trade in trades:
            capital += trade.pnl
            curve.append(
                {
                    "time": trade.exit_time,
                    "equity": str(capital),
                    "pnl": str(trade.pnl),
                    "pnl_pct": str(trade.pnl_pct),
                }
            )

        return curve

    def _normalize_klines(
        self,
        raw_klines: list[list[Any]],
    ) -> list[dict[str, Any]]:
        """标准化K线数据。"""
        klines = []
        for row in raw_klines:
            if len(row) < 7:
                continue
            try:
                klines.append(
                    {
                        "open_time": int(row[0]),
                        "open": str(row[1]),
                        "high": str(row[2]),
                        "low": str(row[3]),
                        "close": str(row[4]),
                        "volume": str(row[5]),
                        "close_time": int(row[6]),
                    }
                )
            except (TypeError, ValueError, IndexError):
                continue
        return klines

    def _get_intervals_per_day(self, interval: str) -> int:
        """获取每天的K线数量。"""
        mapping = {
            "1m": 1440,
            "3m": 480,
            "5m": 288,
            "15m": 96,
            "30m": 48,
            "1h": 24,
            "2h": 12,
            "4h": 6,
            "6h": 4,
            "8h": 3,
            "12h": 2,
            "1d": 1,
            "3d": 1 // 3,
            "1w": 1 // 7,
        }
        return mapping.get(interval, 6)


# 单例实例
backtest_validation_service = BacktestValidationService()