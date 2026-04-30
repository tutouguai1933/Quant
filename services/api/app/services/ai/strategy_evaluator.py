"""策略评估服务。

计算夏普比率、最大回撤、胜率等评估指标。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class EvaluationPeriod(Enum):
    """评估周期。"""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"


@dataclass
class TradeRecord:
    """交易记录数据结构。"""

    symbol: str
    entry_time: datetime
    exit_time: datetime | None = None
    entry_price: float = 0.0
    exit_price: float = 0.0
    position_size: float = 0.0
    pnl: float = 0.0
    pnl_pct: float = 0.0
    direction: str = "long"  # long/short
    fees: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "entry_time": self.entry_time.isoformat(),
            "exit_time": self.exit_time.isoformat() if self.exit_time else None,
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "position_size": self.position_size,
            "pnl": self.pnl,
            "pnl_pct": self.pnl_pct,
            "direction": self.direction,
            "fees": self.fees,
        }


@dataclass
class EvaluationResult:
    """评估结果数据结构。"""

    strategy_id: str
    period: EvaluationPeriod
    start_time: datetime
    end_time: datetime
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_pnl: float = 0.0
    total_pnl_pct: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown: float = 0.0
    calmar_ratio: float = 0.0
    omega_ratio: float = 0.0
    avg_holding_period: float = 0.0
    health_score: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "period": self.period.value,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "total_pnl": self.total_pnl,
            "total_pnl_pct": self.total_pnl_pct,
            "win_rate": self.win_rate,
            "profit_factor": self.profit_factor,
            "avg_win": self.avg_win,
            "avg_loss": self.avg_loss,
            "sharpe_ratio": self.sharpe_ratio,
            "sortino_ratio": self.sortino_ratio,
            "max_drawdown": self.max_drawdown,
            "calmar_ratio": self.calmar_ratio,
            "omega_ratio": self.omega_ratio,
            "avg_holding_period": self.avg_holding_period,
            "health_score": self.health_score,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class ComparisonResult:
    """策略对比结果。"""

    baseline_id: str | None
    strategies: list[dict[str, Any]] = field(default_factory=list)
    rankings: list[tuple[str, float]] = field(default_factory=list)  # (strategy_id, score)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "baseline_id": self.baseline_id,
            "strategies": self.strategies,
            "rankings": [(id, score) for id, score in self.rankings],
            "timestamp": self.timestamp.isoformat(),
        }


# 评估周期配置
EVALUATION_CONFIG = {
    EvaluationPeriod.DAILY: {
        "min_trades": 3,
        "metrics": ["pnl", "win_rate", "total_trades"],
    },
    EvaluationPeriod.WEEKLY: {
        "min_trades": 10,
        "metrics": ["sharpe", "max_drawdown", "win_rate", "profit_factor"],
    },
    EvaluationPeriod.MONTHLY: {
        "min_trades": 30,
        "metrics": ["sharpe", "calmar", "omega", "sortino", "max_drawdown", "win_rate"],
    },
    EvaluationPeriod.QUARTERLY: {
        "min_trades": 100,
        "metrics": "all",
    },
    EvaluationPeriod.YEARLY: {
        "min_trades": 300,
        "metrics": "all",
    },
}


class StrategyEvaluatorService:
    """策略评估服务。

    功能：
    1. 计算各种评估指标
    2. 按周期评估策略表现
    3. 对比多个策略
    4. 计算健康度评分
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self._config = config or {}
        self._evaluation_history: dict[str, list[EvaluationResult]] = {}
        self._risk_free_rate = self._config.get("risk_free_rate", 0.02)  # 年化无风险利率
        self._trading_days_per_year = self._config.get("trading_days_per_year", 252)

    def evaluate_strategy(
        self,
        strategy_id: str,
        period: EvaluationPeriod,
        trades: list[TradeRecord],
        equity_curve: list[float] | None = None,
    ) -> EvaluationResult:
        """评估策略表现。

        Args:
            strategy_id: 策略ID
            period: 评估周期
            trades: 交易记录列表
            equity_curve: 资金曲线（可选）

        Returns:
            EvaluationResult: 评估结果
        """
        now = datetime.now(timezone.utc)
        start_time, end_time = self._get_period_range(period, now)

        # 过滤时间范围内的交易
        period_trades = self._filter_trades_by_period(trades, start_time, end_time)

        # 计算基础指标
        metrics = self.calculate_metrics(period_trades, equity_curve)

        # 构建评估结果
        result = EvaluationResult(
            strategy_id=strategy_id,
            period=period,
            start_time=start_time,
            end_time=end_time,
            total_trades=metrics["total_trades"],
            winning_trades=metrics["winning_trades"],
            losing_trades=metrics["losing_trades"],
            total_pnl=metrics["total_pnl"],
            total_pnl_pct=metrics["total_pnl_pct"],
            win_rate=metrics["win_rate"],
            profit_factor=metrics["profit_factor"],
            avg_win=metrics["avg_win"],
            avg_loss=metrics["avg_loss"],
            sharpe_ratio=metrics["sharpe_ratio"],
            sortino_ratio=metrics["sortino_ratio"],
            max_drawdown=metrics["max_drawdown"],
            calmar_ratio=metrics["calmar_ratio"],
            omega_ratio=metrics["omega_ratio"],
            avg_holding_period=metrics["avg_holding_period"],
        )

        # 计算健康度评分
        result.health_score = self._calculate_health_score(metrics)

        # 存储历史
        history = self._evaluation_history.setdefault(strategy_id, [])
        history.append(result)
        if len(history) > 100:
            history = history[-100:]
            self._evaluation_history[strategy_id] = history

        return result

    def _get_period_range(
        self,
        period: EvaluationPeriod,
        now: datetime,
    ) -> tuple[datetime, datetime]:
        """获取评估周期的时间范围。"""
        if period == EvaluationPeriod.DAILY:
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end = now
        elif period == EvaluationPeriod.WEEKLY:
            days_since_monday = now.weekday()
            start = now - timedelta(days=days_since_monday)
            start = start.replace(hour=0, minute=0, second=0, microsecond=0)
            end = now
        elif period == EvaluationPeriod.MONTHLY:
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            end = now
        elif period == EvaluationPeriod.QUARTERLY:
            quarter_month = ((now.month - 1) // 3) * 3 + 1
            start = now.replace(month=quarter_month, day=1, hour=0, minute=0, second=0, microsecond=0)
            end = now
        else:  # YEARLY
            start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            end = now

        return start, end

    def _filter_trades_by_period(
        self,
        trades: list[TradeRecord],
        start_time: datetime,
        end_time: datetime,
    ) -> list[TradeRecord]:
        """过滤时间范围内的交易。"""
        filtered = []
        for trade in trades:
            if trade.exit_time is None:
                continue
            if trade.exit_time >= start_time and trade.exit_time <= end_time:
                filtered.append(trade)
        return filtered

    def calculate_metrics(
        self,
        trades: list[TradeRecord],
        equity_curve: list[float] | None = None,
    ) -> dict[str, float]:
        """计算所有评估指标。

        Args:
            trades: 交易记录
            equity_curve: 资金曲线

        Returns:
            dict: 指标字典
        """
        metrics: dict[str, float] = {}

        # 基础统计
        metrics["total_trades"] = len(trades)
        metrics["winning_trades"] = sum(1 for t in trades if t.pnl > 0)
        metrics["losing_trades"] = sum(1 for t in trades if t.pnl <= 0)

        # 盈亏统计
        wins = [t.pnl for t in trades if t.pnl > 0]
        losses = [abs(t.pnl) for t in trades if t.pnl <= 0]

        metrics["total_pnl"] = sum(t.pnl for t in trades)
        metrics["avg_win"] = sum(wins) / len(wins) if wins else 0.0
        metrics["avg_loss"] = sum(losses) / len(losses) if losses else 0.0

        # 初始资金（用于计算百分比）
        initial_capital = 100000.0  # 默认假设
        metrics["total_pnl_pct"] = metrics["total_pnl"] / initial_capital

        # 胜率
        if metrics["total_trades"] > 0:
            metrics["win_rate"] = metrics["winning_trades"] / metrics["total_trades"]
        else:
            metrics["win_rate"] = 0.0

        # 盈亏比
        if metrics["avg_loss"] > 0:
            metrics["profit_factor"] = metrics["avg_win"] / metrics["avg_loss"]
        else:
            metrics["profit_factor"] = float("inf") if metrics["avg_win"] > 0 else 0.0

        # 平均持仓周期
        holding_periods = []
        for trade in trades:
            if trade.exit_time and trade.entry_time:
                period = (trade.exit_time - trade.entry_time).total_seconds() / 3600  # 小时
                holding_periods.append(period)

        metrics["avg_holding_period"] = sum(holding_periods) / len(holding_periods) if holding_periods else 0.0

        # 收益率序列（用于风险指标）
        returns = [t.pnl_pct for t in trades if t.pnl_pct != 0]

        # 夏普比率
        metrics["sharpe_ratio"] = self._calculate_sharpe(returns)

        # Sortino比率
        metrics["sortino_ratio"] = self._calculate_sortino(returns)

        # 最大回撤
        if equity_curve:
            metrics["max_drawdown"] = self._calculate_max_drawdown(equity_curve)
        else:
            # 从交易估算回撤（简化）
            metrics["max_drawdown"] = self._estimate_max_drawdown(trades)

        # 卡玛比率
        if metrics["max_drawdown"] > 0:
            annual_return = self._annualize_return(metrics["total_pnl_pct"], metrics["avg_holding_period"])
            metrics["calmar_ratio"] = annual_return / metrics["max_drawdown"]
        else:
            metrics["calmar_ratio"] = float("inf") if metrics["total_pnl"] > 0 else 0.0

        # Omega比率
        metrics["omega_ratio"] = self._calculate_omega(returns)

        return metrics

    def _calculate_sharpe(self, returns: list[float]) -> float:
        """计算夏普比率。"""
        if len(returns) < 2:
            return 0.0

        avg_return = sum(returns) / len(returns)

        # 计算标准差
        variance = sum((r - avg_return) ** 2 for r in returns) / len(returns)
        std_dev = variance ** 0.5

        if std_dev == 0:
            return 0.0

        # 年化调整（假设交易频率）
        annual_avg_return = avg_return * self._trading_days_per_year
        annual_std_dev = std_dev * (self._trading_days_per_year ** 0.5)

        # 夏普比率 = (收益率 - 无风险利率) / 波动率
        sharpe = (annual_avg_return - self._risk_free_rate) / annual_std_dev

        return sharpe

    def _calculate_sortino(self, returns: list[float]) -> float:
        """计算Sortino比率（只考虑下行波动）。"""
        if len(returns) < 2:
            return 0.0

        avg_return = sum(returns) / len(returns)

        # 计算下行偏差（只考虑负收益）
        negative_returns = [r for r in returns if r < 0]
        if not negative_returns:
            return float("inf") if avg_return > 0 else 0.0

        downside_variance = sum(r ** 2 for r in negative_returns) / len(negative_returns)
        downside_dev = downside_variance ** 0.5

        if downside_dev == 0:
            return 0.0

        # 年化调整
        annual_avg_return = avg_return * self._trading_days_per_year
        annual_downside_dev = downside_dev * (self._trading_days_per_year ** 0.5)

        sortino = (annual_avg_return - self._risk_free_rate) / annual_downside_dev

        return sortino

    def _calculate_max_drawdown(self, equity_curve: list[float]) -> float:
        """计算最大回撤。"""
        if len(equity_curve) < 2:
            return 0.0

        peak = equity_curve[0]
        max_dd = 0.0

        for value in equity_curve:
            if value > peak:
                peak = value

            dd = (peak - value) / peak if peak > 0 else 0.0
            max_dd = max(max_dd, dd)

        return max_dd

    def _estimate_max_drawdown(self, trades: list[TradeRecord]) -> float:
        """从交易记录估算最大回撤（简化方法）。"""
        if not trades:
            return 0.0

        # 模拟资金曲线
        initial_capital = 100000.0
        equity = initial_capital
        equity_curve = [equity]

        for trade in trades:
            equity += trade.pnl
            equity_curve.append(equity)

        return self._calculate_max_drawdown(equity_curve)

    def _annualize_return(self, total_pct: float, avg_holding_hours: float) -> float:
        """年化收益率。"""
        if avg_holding_hours <= 0:
            return total_pct * self._trading_days_per_year

        # 估算年化收益
        trades_per_year = (365 * 24) / avg_holding_hours
        annual_return = total_pct * trades_per_year

        # 合理范围限制
        return max(-1.0, min(1.0, annual_return))

    def _calculate_omega(self, returns: list[float], threshold: float = 0.0) -> float:
        """计算Omega比率。"""
        if not returns:
            return 1.0

        gains = sum(r - threshold for r in returns if r > threshold)
        losses = sum(threshold - r for r in returns if r < threshold)

        if losses == 0:
            return float("inf") if gains > 0 else 1.0

        return gains / losses

    def _calculate_health_score(self, metrics: dict[str, float]) -> float:
        """计算策略健康度评分 (0-100)。"""
        weights = {
            "sharpe": 0.25,
            "max_drawdown": 0.20,
            "win_rate": 0.15,
            "profit_factor": 0.15,
            "trade_frequency": 0.10,
            "consistency": 0.15,
        }

        # 归一化各指标
        sharpe_norm = self._normalize_sharpe(metrics.get("sharpe_ratio", 0))
        dd_norm = 1.0 - min(metrics.get("max_drawdown", 0) / 0.2, 1.0)  # 回撤越大分数越低
        win_norm = metrics.get("win_rate", 0)
        pf_norm = self._normalize_profit_factor(metrics.get("profit_factor", 0))

        # 交易频率评分（需要足够交易）
        trades = metrics.get("total_trades", 0)
        if trades >= 30:
            freq_norm = 1.0
        elif trades >= 10:
            freq_norm = 0.7
        else:
            freq_norm = 0.4

        # 稳定性（简化：基于胜率和盈亏比的一致性）
        consistency = (win_norm + pf_norm) / 2

        # 加权总分
        score = (
            sharpe_norm * weights["sharpe"]
            + dd_norm * weights["max_drawdown"]
            + win_norm * weights["win_rate"]
            + pf_norm * weights["profit_factor"]
            + freq_norm * weights["trade_frequency"]
            + consistency * weights["consistency"]
        )

        return score * 100

    def _normalize_sharpe(self, sharpe: float) -> float:
        """归一化夏普比率。"""
        # 夏普比率范围假设为 -1 到 3
        if sharpe >= 3:
            return 1.0
        elif sharpe <= -1:
            return 0.0
        else:
            return (sharpe + 1) / 4

    def _normalize_profit_factor(self, pf: float) -> float:
        """归一化盈亏比。"""
        # 盈亏比范围假设为 0 到 3
        if pf >= 3:
            return 1.0
        elif pf <= 0:
            return 0.0
        else:
            return pf / 3

    def compare_strategies(
        self,
        strategy_results: dict[str, EvaluationResult],
        baseline_id: str | None = None,
    ) -> ComparisonResult:
        """对比多个策略表现。

        Args:
            strategy_results: 策略ID到评估结果的映射
            baseline_id: 基准策略ID（可选）

        Returns:
            ComparisonResult: 对比结果
        """
        strategies_list = []
        rankings = []

        for strategy_id, result in strategy_results.items():
            strategies_list.append(result.to_dict())
            rankings.append((strategy_id, result.health_score))

        # 按健康度评分排序
        rankings.sort(key=lambda x: x[1], reverse=True)

        return ComparisonResult(
            baseline_id=baseline_id,
            strategies=strategies_list,
            rankings=rankings,
        )

    def get_evaluation_history(
        self,
        strategy_id: str,
        limit: int = 10,
    ) -> list[EvaluationResult]:
        """获取评估历史。"""
        history = self._evaluation_history.get(strategy_id, [])
        return history[-limit:]

    def should_trigger_fallback(
        self,
        result: EvaluationResult,
        thresholds: dict[str, float] | None = None,
    ) -> bool:
        """检查是否需要触发降级。

        Args:
            result: 评估结果
            thresholds: 阈值配置（可选）

        Returns:
            bool: 是否需要降级
        """
        default_thresholds = {
            "win_rate": 0.45,
            "max_drawdown": 0.20,
            "sharpe_ratio": 0.5,
            "health_score": 50.0,
        }

        thresholds = thresholds or default_thresholds

        conditions = [
            result.win_rate < thresholds["win_rate"],
            result.max_drawdown > thresholds["max_drawdown"],
            result.sharpe_ratio < thresholds["sharpe_ratio"],
            result.health_score < thresholds["health_score"],
        ]

        return any(conditions)

    def get_min_trades_required(self, period: EvaluationPeriod) -> int:
        """获取指定周期所需的最少交易数。"""
        return EVALUATION_CONFIG.get(period, {}).get("min_trades", 0)

    def generate_report(
        self,
        strategy_id: str,
        period: EvaluationPeriod,
        trades: list[TradeRecord],
        equity_curve: list[float] | None = None,
    ) -> dict[str, Any]:
        """生成完整评估报告。

        Args:
            strategy_id: 策略ID
            period: 评估周期
            trades: 交易记录
            equity_curve: 资金曲线

        Returns:
            dict: 评估报告
        """
        result = self.evaluate_strategy(strategy_id, period, trades, equity_curve)

        # 构建报告
        report = {
            "summary": result.to_dict(),
            "performance_analysis": {
                "profitability": {
                    "total_pnl": result.total_pnl,
                    "total_pnl_pct": result.total_pnl_pct,
                    "profit_factor": result.profit_factor,
                },
                "risk": {
                    "max_drawdown": result.max_drawdown,
                    "sharpe_ratio": result.sharpe_ratio,
                    "sortino_ratio": result.sortino_ratio,
                },
                "consistency": {
                    "win_rate": result.win_rate,
                    "avg_win": result.avg_win,
                    "avg_loss": result.avg_loss,
                },
            },
            "recommendations": self._generate_recommendations(result),
            "fallback_triggered": self.should_trigger_fallback(result),
        }

        return report

    def _generate_recommendations(self, result: EvaluationResult) -> list[str]:
        """生成改进建议。"""
        recommendations = []

        if result.win_rate < 0.5:
            recommendations.append("胜率偏低，建议优化入场条件或止损策略")

        if result.max_drawdown > 0.15:
            recommendations.append("最大回撤过大，建议收紧仓位或改进风控")

        if result.profit_factor < 1.5:
            recommendations.append("盈亏比偏低，建议优化止盈策略或过滤低质量信号")

        if result.sharpe_ratio < 1.0:
            recommendations.append("夏普比率偏低，整体风险调整后收益不佳")

        if result.avg_holding_period > 24:
            recommendations.append("持仓周期偏长，可能错过及时止损/止盈机会")

        if not recommendations:
            recommendations.append("策略表现良好，继续保持当前参数")

        return recommendations


# 全局策略评估服务实例
strategy_evaluator_service = StrategyEvaluatorService()