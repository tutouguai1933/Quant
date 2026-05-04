"""交易报告服务：生成日报、周报和定时报告调度。

该服务负责:
- 生成每日交易报告（每日6:00 UTC自动生成）
- 生成每周交易报告（每周一6:00 UTC自动生成）
- 报告历史存储和查询
- 定时任务调度（使用threading.Timer）
- 推送飞书 webhook
"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any

from services.api.app.services.analytics_service import analytics_service
from services.api.app.services.factor_analysis_service import factor_analysis_service
from services.api.app.services.scoring import scoring_service
from services.api.app.services.feishu_push_service import (
    feishu_push_service,
    ReportCardMessage,
)


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


@dataclass(slots=True)
class DailyReport:
    """每日交易报告。"""
    date: str  # YYYY-MM-DD
    generated_at: datetime
    trade_summary: dict[str, Any]
    pnl_summary: dict[str, Any]
    position_status: dict[str, Any]
    risk_metrics: dict[str, Any]
    factor_analysis: dict[str, Any]
    markdown_content: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "date": self.date,
            "generated_at": self.generated_at.isoformat(),
            "trade_summary": self.trade_summary,
            "pnl_summary": self.pnl_summary,
            "position_status": self.position_status,
            "risk_metrics": self.risk_metrics,
            "factor_analysis": self.factor_analysis,
            "markdown_content": self.markdown_content,
        }


@dataclass(slots=True)
class WeeklyReport:
    """每周交易报告。"""
    week_start: str  # YYYY-MM-DD (周一)
    week_end: str  # YYYY-MM-DD (周日)
    generated_at: datetime
    strategy_performance: dict[str, Any]
    risk_analysis: dict[str, Any]
    factor_analysis: dict[str, Any]
    daily_breakdown: list[dict[str, Any]]
    recommendations: list[str]
    markdown_content: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "week_start": self.week_start,
            "week_end": self.week_end,
            "generated_at": self.generated_at.isoformat(),
            "strategy_performance": self.strategy_performance,
            "risk_analysis": self.risk_analysis,
            "factor_analysis": self.factor_analysis,
            "daily_breakdown": self.daily_breakdown,
            "recommendations": self.recommendations,
            "markdown_content": self.markdown_content,
        }


class ReportService:
    """交易报告服务。"""

    def __init__(self) -> None:
        self._report_history: dict[str, list[dict[str, Any]]] = {}
        self._daily_reports: dict[str, DailyReport] = {}
        self._weekly_reports: dict[str, WeeklyReport] = {}
        self._lock = threading.Lock()
        self._config_path: Path | None = None
        self._timer: threading.Timer | None = None
        self._schedule_active: bool = False
        self._schedule_interval_minutes: int = 60
        # 新增：定时报告调度器（每日6:00和每周一6:00）
        self._scheduled_report_timer: threading.Timer | None = None
        self._scheduled_report_active: bool = False
        self._last_daily_report_date: str | None = None
        self._last_weekly_report_week: str | None = None

    def set_config_path(self, path: str | Path) -> None:
        """设置配置持久化路径。"""
        self._config_path = Path(path)
        self._load_history()

    def _load_history(self) -> None:
        """从文件加载历史报告。"""
        if self._config_path is None or not self._config_path.exists():
            return

        try:
            with open(self._config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            with self._lock:
                self._report_history = data.get("report_history", {})
            logger.info("报告历史数据已加载: %s", self._config_path)
        except Exception as e:
            logger.warning("加载报告历史数据失败: %s", e)

    def _save_history(self) -> None:
        """保存历史报告到文件。"""
        if self._config_path is None:
            return

        try:
            with self._lock:
                data = {
                    "report_history": self._report_history,
                    "daily_reports": {k: v.to_dict() for k, v in self._daily_reports.items()},
                    "weekly_reports": {k: v.to_dict() for k, v in self._weekly_reports.items()},
                    "updated_at": utc_now().isoformat(),
                }
            with open(self._config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            logger.info("报告历史数据已保存: %s", self._config_path)
        except Exception as e:
            logger.warning("保存报告历史数据失败: %s", e)

    def generate_daily_report(self, date: str | None = None) -> DailyReport:
        """生成每日交易报告。

        Args:
            date: YYYY-MM-DD 格式的日期，默认为今天

        Returns:
            DailyReport: 日报内容
        """
        generated_at = utc_now()

        # 获取交易汇总
        daily_summary = analytics_service.get_daily_summary(date=date)
        target_date = daily_summary.date

        # 构建交易汇总
        trade_summary = {
            "trade_count": daily_summary.trade_count,
            "buy_count": daily_summary.buy_count,
            "sell_count": daily_summary.sell_count,
            "symbols": daily_summary.symbols,
        }

        # 构建盈亏汇总
        pnl_summary = {
            "total_pnl": str(daily_summary.total_pnl),
            "win_count": daily_summary.win_count,
            "loss_count": daily_summary.loss_count,
            "win_rate": str(daily_summary.win_rate),
            "avg_pnl": str(daily_summary.avg_pnl),
            "max_profit": str(daily_summary.max_profit),
            "max_loss": str(daily_summary.max_loss),
        }

        # 构建持仓状态（简化版）
        position_status = {
            "open_positions": 0,
            "unrealized_pnl": "0",
            "largest_position": None,
            "notes": "暂无持仓数据",
        }

        # 构建风险指标
        risk_metrics = {
            "daily_pnl_ratio": float(daily_summary.total_pnl) if daily_summary.trade_count > 0 else 0.0,
            "max_single_loss": float(daily_summary.max_loss),
            "trade_frequency": daily_summary.trade_count,
            "risk_level": "low" if daily_summary.trade_count < 10 else "medium",
        }

        # 获取因子分析
        factor_analysis_result = factor_analysis_service.analyze_factor_contribution("default")
        factor_analysis = {
            "top_factors": factor_analysis_result.top_factors,
            "weak_factors": factor_analysis_result.weak_factors,
            "recommendations": factor_analysis_result.recommendations[:3],
        }

        # 生成 Markdown 内容
        markdown_content = self._generate_daily_markdown(
            target_date, trade_summary, pnl_summary, position_status, risk_metrics, factor_analysis
        )

        report = DailyReport(
            date=target_date,
            generated_at=generated_at,
            trade_summary=trade_summary,
            pnl_summary=pnl_summary,
            position_status=position_status,
            risk_metrics=risk_metrics,
            factor_analysis=factor_analysis,
            markdown_content=markdown_content,
        )

        # 缓存报告
        with self._lock:
            self._daily_reports[target_date] = report
            if "daily" not in self._report_history:
                self._report_history["daily"] = []
            self._report_history["daily"].append({
                "date": target_date,
                "generated_at": generated_at.isoformat(),
                "trade_count": daily_summary.trade_count,
                "total_pnl": str(daily_summary.total_pnl),
            })
            # 限制历史长度
            if len(self._report_history["daily"]) > 90:
                self._report_history["daily"] = self._report_history["daily"][-90:]

        self._save_history()

        return report

    def generate_weekly_report(self, week_start: str | None = None) -> WeeklyReport:
        """生成每周交易报告。

        Args:
            week_start: YYYY-MM-DD 格式的周一日期，默认为本周

        Returns:
            WeeklyReport: 周报内容
        """
        generated_at = utc_now()

        # 获取周汇总
        weekly_summary = analytics_service.get_weekly_summary(week_start=week_start)
        target_week_start = weekly_summary.week_start
        target_week_end = weekly_summary.week_end

        # 获取策略表现
        strategy_performances = analytics_service.get_strategy_performance()
        strategy_performance = {
            "strategies": [p.to_dict() for p in strategy_performances],
            "best_strategy": strategy_performances[0].strategy_name if strategy_performances else None,
            "total_strategies": len(strategy_performances),
        }

        # 构建风险分析
        risk_analysis = {
            "week_pnl": str(weekly_summary.total_pnl),
            "win_rate": str(weekly_summary.win_rate),
            "best_day": weekly_summary.best_day,
            "worst_day": weekly_summary.worst_day,
            "pnl_volatility": self._calculate_pnl_volatility(weekly_summary.daily_breakdown),
        }

        # 获取因子分析
        factor_effectiveness = factor_analysis_service.evaluate_factor_effectiveness("7d")
        factor_analysis = {
            "effectiveness": [f.to_dict() for f in factor_effectiveness],
            "recommendations": self._summarize_factor_recommendations(factor_effectiveness),
        }

        # 生成建议
        recommendations = self._generate_weekly_recommendations(
            weekly_summary, strategy_performances, factor_effectiveness
        )

        # 生成 Markdown 内容
        markdown_content = self._generate_weekly_markdown(
            target_week_start, target_week_end,
            strategy_performance, risk_analysis, factor_analysis,
            weekly_summary.daily_breakdown, recommendations
        )

        report = WeeklyReport(
            week_start=target_week_start,
            week_end=target_week_end,
            generated_at=generated_at,
            strategy_performance=strategy_performance,
            risk_analysis=risk_analysis,
            factor_analysis=factor_analysis,
            daily_breakdown=weekly_summary.daily_breakdown,
            recommendations=recommendations,
            markdown_content=markdown_content,
        )

        # 缓存报告
        with self._lock:
            self._weekly_reports[target_week_start] = report
            if "weekly" not in self._report_history:
                self._report_history["weekly"] = []
            self._report_history["weekly"].append({
                "week_start": target_week_start,
                "week_end": target_week_end,
                "generated_at": generated_at.isoformat(),
                "trade_count": weekly_summary.trade_count,
                "total_pnl": str(weekly_summary.total_pnl),
            })
            # 限制历史长度
            if len(self._report_history["weekly"]) > 52:
                self._report_history["weekly"] = self._report_history["weekly"][-52:]

        self._save_history()

        return report

    def get_report_history(self, report_type: str = "daily", limit: int = 10) -> list[dict[str, Any]]:
        """获取报告历史。

        Args:
            report_type: 报告类型 (daily/weekly)
            limit: 返回数量限制

        Returns:
            list: 报告历史列表
        """
        with self._lock:
            history = self._report_history.get(report_type, [])

        return history[-limit:]

    def get_cached_daily_report(self, date: str) -> DailyReport | None:
        """获取缓存的日报。"""
        with self._lock:
            return self._daily_reports.get(date)

    def get_cached_weekly_report(self, week_start: str) -> WeeklyReport | None:
        """获取缓存的周报。"""
        with self._lock:
            return self._weekly_reports.get(week_start)

    def schedule_report_generation(self) -> dict[str, Any]:
        """启动定时报告生成调度。

        使用 threading.Timer 实现定时任务。
        """
        if self._schedule_active:
            return {
                "success": False,
                "message": "报告调度已在运行",
                "interval_minutes": self._schedule_interval_minutes,
            }

        self._schedule_active = True
        self._run_schedule_cycle()
        logger.info("报告生成调度已启动，间隔 %d 分钟", self._schedule_interval_minutes)

        return {
            "success": True,
            "message": "报告生成调度已启动",
            "interval_minutes": self._schedule_interval_minutes,
        }

    def stop_schedule(self) -> dict[str, Any]:
        """停止定时报告生成调度。"""
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None

        self._schedule_active = False
        logger.info("报告生成调度已停止")

        return {
            "success": True,
            "message": "报告生成调度已停止",
        }

    def _run_schedule_cycle(self) -> None:
        """执行调度周期。"""
        if not self._schedule_active:
            return

        try:
            # 同步交易数据
            analytics_service.refresh_trade_history()

            # 检查是否需要生成日报（每天一次）
            now = utc_now()
            today = now.strftime("%Y-%m-%d")

            with self._lock:
                today_report_exists = today in self._daily_reports

            if not today_report_exists:
                logger.info("定时生成日报: %s", today)
                self.generate_daily_report(today)

            # 检查是否需要生成周报（每周一）
            weekday = now.weekday()
            if weekday == 0:  # 周一
                week_start = today
                with self._lock:
                    week_report_exists = week_start in self._weekly_reports

                if not week_report_exists:
                    logger.info("定时生成周报: %s", week_start)
                    self.generate_weekly_report(week_start)

        except Exception as e:
            logger.warning("定时报告生成失败: %s", e)

        # 设置下一次调度
        if self._schedule_active:
            self._timer = threading.Timer(
                self._schedule_interval_minutes * 60,
                self._run_schedule_cycle,
            )
            self._timer.start()

    def _generate_daily_markdown(
        self,
        date: str,
        trade_summary: dict[str, Any],
        pnl_summary: dict[str, Any],
        position_status: dict[str, Any],
        risk_metrics: dict[str, Any],
        factor_analysis: dict[str, Any],
    ) -> str:
        """生成日报 Markdown 内容。"""
        lines: list[str] = [
            f"# 交易日报 - {date}",
            "",
            "## 交易汇总",
            f"- 总交易次数: {trade_summary['trade_count']}",
            f"- 买入次数: {trade_summary['buy_count']}",
            f"- 卖出次数: {trade_summary['sell_count']}",
            f"- 涉及标的: {', '.join(trade_summary['symbols']) if trade_summary['symbols'] else '无'}",
            "",
            "## 盈亏统计",
            f"- 总盈亏: {pnl_summary['total_pnl']}",
            f"- 盈利次数: {pnl_summary['win_count']}",
            f"- 亏损次数: {pnl_summary['loss_count']}",
            f"- 胜率: {pnl_summary['win_rate']}",
            f"- 平均盈亏: {pnl_summary['avg_pnl']}",
            f"- 最大盈利: {pnl_summary['max_profit']}",
            f"- 最大亏损: {pnl_summary['max_loss']}",
            "",
            "## 持仓状态",
            f"- 开仓数量: {position_status['open_positions']}",
            f"- 未实现盈亏: {position_status['unrealized_pnl']}",
            "",
            "## 风险指标",
            f"- 日盈亏比率: {risk_metrics['daily_pnl_ratio']}",
            f"- 最大单笔亏损: {risk_metrics['max_single_loss']}",
            f"- 交易频率: {risk_metrics['trade_frequency']}",
            f"- 风险等级: {risk_metrics['risk_level']}",
            "",
            "## 因子分析",
            f"- 主要因子: {', '.join(factor_analysis['top_factors']) if factor_analysis['top_factors'] else '暂无'}",
            f"- 弱因子: {', '.join(factor_analysis['weak_factors']) if factor_analysis['weak_factors'] else '暂无'}",
        ]

        if factor_analysis["recommendations"]:
            lines.append("- 建议:")
            for rec in factor_analysis["recommendations"]:
                lines.append(f"  - {rec}")

        lines.append("")
        lines.append("---")
        lines.append(f"生成时间: {utc_now().isoformat()}")

        return "\n".join(lines)

    def _generate_weekly_markdown(
        self,
        week_start: str,
        week_end: str,
        strategy_performance: dict[str, Any],
        risk_analysis: dict[str, Any],
        factor_analysis: dict[str, Any],
        daily_breakdown: list[dict[str, Any]],
        recommendations: list[str],
    ) -> str:
        """生成周报 Markdown 内容。"""
        lines: list[str] = [
            f"# 交易周报 - {week_start} 至 {week_end}",
            "",
            "## 策略表现",
            f"- 活跃策略数: {strategy_performance['total_strategies']}",
            f"- 最佳策略: {strategy_performance['best_strategy'] or '暂无数据'}",
            "",
        ]

        if strategy_performance["strategies"]:
            lines.append("### 策略详情")
            for strat in strategy_performance["strategies"]:
                lines.append(f"- **{strat['strategy_name']}**")
                lines.append(f"  - 交易次数: {strat['trade_count']}")
                lines.append(f"  - 总盈亏: {strat['total_pnl']}")
                lines.append(f"  - 胜率: {strat['win_rate']}")

        lines.extend([
            "",
            "## 风险分析",
            f"- 本周盈亏: {risk_analysis['week_pnl']}",
            f"- 胜率: {risk_analysis['win_rate']}",
            f"- 最佳交易日: {risk_analysis['best_day'] or '暂无'}",
            f"- 最差交易日: {risk_analysis['worst_day'] or '暂无'}",
            f"- 盈亏波动: {risk_analysis['pnl_volatility']}",
            "",
            "## 每日明细",
        ])

        for day in daily_breakdown:
            lines.append(f"- {day.get('date', '')}: PnL={day.get('total_pnl', '0')}, 交易={day.get('trade_count', 0)}")

        lines.extend([
            "",
            "## 因子分析",
        ])

        if factor_analysis["effectiveness"]:
            lines.append("### 因子有效性")
            for eff in factor_analysis["effectiveness"]:
                lines.append(f"- **{eff['factor_name']}**")
                lines.append(f"  - 有效性: {eff['effectiveness_score']}")
                lines.append(f"  - 稳定性: {eff['stability_score']}")
                lines.append(f"  - 建议: {eff['recommendation']}")

        lines.extend([
            "",
            "## 本周建议",
        ])

        for rec in recommendations:
            lines.append(f"- {rec}")

        lines.append("")
        lines.append("---")
        lines.append(f"生成时间: {utc_now().isoformat()}")

        return "\n".join(lines)

    def _calculate_pnl_volatility(self, daily_breakdown: list[dict[str, Any]]) -> str:
        """计算盈亏波动率。"""
        pnls = [_parse_decimal(d.get("total_pnl", "0")) for d in daily_breakdown if d.get("trade_count", 0) > 0]

        if not pnls:
            return "0"

        mean_pnl = sum(pnls) / len(pnls)
        variance = sum((p - mean_pnl) ** 2 for p in pnls) / len(pnls)
        volatility = variance.sqrt() if variance > 0 else Decimal("0")

        return str(volatility.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP))

    def _summarize_factor_recommendations(self, effectiveness: list[Any]) -> list[str]:
        """汇总因子建议。"""
        keep_factors = [f.factor_name for f in effectiveness if f.recommendation == "keep"]
        adjust_factors = [f.factor_name for f in effectiveness if f.recommendation == "adjust"]

        recommendations: list[str] = []

        if keep_factors:
            recommendations.append(f"保持因子: {', '.join(keep_factors)}")
        if adjust_factors:
            recommendations.append(f"调整因子: {', '.join(adjust_factors)}")

        return recommendations

    def _generate_weekly_recommendations(
        self,
        weekly_summary: Any,
        strategy_performances: list[Any],
        factor_effectiveness: list[Any],
    ) -> list[str]:
        """生成周报建议。"""
        recommendations: list[str] = []

        # 基于盈亏的建议
        total_pnl = _parse_decimal(str(weekly_summary.total_pnl))
        if total_pnl > 0:
            recommendations.append("本周盈利，建议保持当前策略配置")
        elif total_pnl < 0:
            recommendations.append("本周亏损，建议复盘策略参数和市场环境")

        # 基于胜率的建议
        win_rate = _parse_decimal(str(weekly_summary.win_rate))
        if win_rate > Decimal("0.6"):
            recommendations.append(f"胜率较高({win_rate})，可考虑增加仓位")
        elif win_rate < Decimal("0.4"):
            recommendations.append(f"胜率偏低({win_rate})，建议优化入场条件")

        # 基于因子的建议
        weak_factors = [f.factor_name for f in factor_effectiveness if f.effectiveness_score < 0.4]
        if weak_factors:
            recommendations.append(f"弱效因子({', '.join(weak_factors)})需要重新评估")

        return recommendations[:5]  # 最多返回5条建议

    def get_service_status(self) -> dict[str, Any]:
        """获取服务状态。"""
        with self._lock:
            daily_count = len(self._daily_reports)
            weekly_count = len(self._weekly_reports)
            history_count = sum(len(h) for h in self._report_history.values())

        return {
            "status": "ready",
            "schedule_active": self._schedule_active,
            "schedule_interval_minutes": self._schedule_interval_minutes,
            "scheduled_report_active": self._scheduled_report_active,
            "daily_reports_cached": daily_count,
            "weekly_reports_cached": weekly_count,
            "history_records": history_count,
            "last_daily_report_date": self._last_daily_report_date,
            "last_weekly_report_week": self._last_weekly_report_week,
        }

    def start_scheduled_reports(self) -> dict[str, Any]:
        """启动定时报告生成（每日6:00 UTC和每周一6:00 UTC）。

        使用 threading.Timer 实现精确时间调度。
        报告生成后自动推送飞书 webhook。
        """
        if self._scheduled_report_active:
            return {
                "success": False,
                "message": "定时报告调度已在运行",
                "last_daily": self._last_daily_report_date,
                "last_weekly": self._last_weekly_report_week,
            }

        self._scheduled_report_active = True
        self._schedule_next_report()
        logger.info("定时报告生成已启动（每日6:00 UTC日报，每周一6:00 UTC周报）")

        return {
            "success": True,
            "message": "定时报告生成已启动",
            "schedule": {
                "daily": "06:00 UTC",
                "weekly": "Monday 06:00 UTC",
            },
        }

    def stop_scheduled_reports(self) -> dict[str, Any]:
        """停止定时报告生成。"""
        if self._scheduled_report_timer is not None:
            self._scheduled_report_timer.cancel()
            self._scheduled_report_timer = None

        self._scheduled_report_active = False
        logger.info("定时报告生成已停止")

        return {
            "success": True,
            "message": "定时报告生成已停止",
        }

    def _schedule_next_report(self) -> None:
        """计算并调度下一次报告生成时间。"""
        if not self._scheduled_report_active:
            return

        now = utc_now()
        target_hour = 6  # 6:00 UTC

        # 计算下一个6:00 UTC
        next_daily = now.replace(hour=target_hour, minute=0, second=0, microsecond=0)
        if now.hour >= target_hour:
            next_daily = next_daily + timedelta(days=1)

        # 计算下周一6:00 UTC
        days_until_monday = (7 - now.weekday()) % 7
        if now.weekday() == 0 and now.hour < target_hour:
            days_until_monday = 0  # 今天是周一且还没到6点
        elif now.weekday() == 0 and now.hour >= target_hour:
            days_until_monday = 7  # 今天是周一但已过了6点
        next_monday = now + timedelta(days=days_until_monday)
        next_monday = next_monday.replace(hour=target_hour, minute=0, second=0, microsecond=0)

        # 选择最近的调度时间
        next_schedule = min(next_daily, next_monday)
        wait_seconds = (next_schedule - now).total_seconds()

        logger.info("下一次报告调度时间: %s (等待 %.0f 秒)", next_schedule.isoformat(), wait_seconds)

        self._scheduled_report_timer = threading.Timer(wait_seconds, self._execute_scheduled_report)
        self._scheduled_report_timer.start()

    def _execute_scheduled_report(self) -> None:
        """执行定时报告生成并推送飞书。"""
        if not self._scheduled_report_active:
            return

        now = utc_now()
        today = now.strftime("%Y-%m-%d")
        weekday = now.weekday()

        try:
            # 检查是否需要生成日报
            if self._last_daily_report_date != today:
                logger.info("定时生成日报: %s", today)
                daily_report = self.generate_daily_report(today)
                self._last_daily_report_date = today
                self._push_daily_report_to_feishu(daily_report)

            # 检查是否需要生成周报（周一）
            if weekday == 0 and self._last_weekly_report_week != today:
                logger.info("定时生成周报: %s", today)
                weekly_report = self.generate_weekly_report(today)
                self._last_weekly_report_week = today
                self._push_weekly_report_to_feishu(weekly_report)

        except Exception as e:
            logger.warning("定时报告生成失败: %s", e)

        # 调度下一次
        self._schedule_next_report()

    def _push_daily_report_to_feishu(self, report: DailyReport) -> bool:
        """推送日报到飞书。"""
        if not feishu_push_service.enabled:
            logger.debug("飞书推送未启用，跳过日报推送")
            return False

        # 构建摘要文本
        summary_lines = [
            f"总交易: {report.trade_summary.get('trade_count', 0)}笔",
            f"盈亏: {report.pnl_summary.get('total_pnl', '0')}",
            f"胜率: {report.pnl_summary.get('win_rate', '0')}",
        ]
        summary = "\n".join(summary_lines)

        # 构建指标字典
        metrics = {
            "交易次数": str(report.trade_summary.get("trade_count", 0)),
            "盈亏": report.pnl_summary.get("total_pnl", "0"),
            "胜率": report.pnl_summary.get("win_rate", "0"),
            "最大盈利": report.pnl_summary.get("max_profit", "0"),
            "最大亏损": report.pnl_summary.get("max_loss", "0"),
            "风险等级": report.risk_metrics.get("risk_level", "N/A"),
        }

        feishu_report = ReportCardMessage(
            report_type="daily",
            summary=summary,
            metrics=metrics,
        )

        success = feishu_push_service.send_report(feishu_report)
        if success:
            logger.info("日报已推送飞书: %s", report.date)
        else:
            logger.warning("日报推送飞书失败: %s", report.date)

        return success

    def _push_weekly_report_to_feishu(self, report: WeeklyReport) -> bool:
        """推送周报到飞书。"""
        if not feishu_push_service.enabled:
            logger.debug("飞书推送未启用，跳过周报推送")
            return False

        # 构建摘要文本
        summary_lines = [
            f"周盈亏: {report.risk_analysis.get('week_pnl', '0')}",
            f"胜率: {report.risk_analysis.get('win_rate', '0')}",
            f"活跃策略: {report.strategy_performance.get('total_strategies', 0)}个",
        ]
        summary = "\n".join(summary_lines)

        # 构建指标字典
        metrics = {
            "累计盈亏": report.risk_analysis.get("week_pnl", "0"),
            "胜率": report.risk_analysis.get("win_rate", "0"),
            "最佳策略": report.strategy_performance.get("best_strategy", "N/A"),
            "最佳交易日": report.risk_analysis.get("best_day", "N/A"),
            "最差交易日": report.risk_analysis.get("worst_day", "N/A"),
        }

        feishu_report = ReportCardMessage(
            report_type="weekly",
            summary=summary,
            metrics=metrics,
        )

        success = feishu_push_service.send_report(feishu_report)
        if success:
            logger.info("周报已推送飞书: %s - %s", report.week_start, report.week_end)
        else:
            logger.warning("周报推送飞书失败: %s - %s", report.week_start, report.week_end)

        return success

    def generate_and_push_daily_report(self, date: str | None = None) -> dict[str, Any]:
        """手动生成日报并推送飞书。"""
        report = self.generate_daily_report(date)
        push_success = self._push_daily_report_to_feishu(report)

        return {
            "report": report.to_dict(),
            "feishu_push": push_success,
            "date": report.date,
        }

    def generate_and_push_weekly_report(self, week_start: str | None = None) -> dict[str, Any]:
        """手动生成周报并推送飞书。"""
        report = self.generate_weekly_report(week_start)
        push_success = self._push_weekly_report_to_feishu(report)

        return {
            "report": report.to_dict(),
            "feishu_push": push_success,
            "week_start": report.week_start,
            "week_end": report.week_end,
        }


# 全局报告服务实例
report_service = ReportService()

# 设置配置持久化路径
config_dir = Path(__file__).parent.parent.parent.parent.parent / "data" / "config"
config_dir.mkdir(parents=True, exist_ok=True)
report_service.set_config_path(config_dir / "report_history.json")