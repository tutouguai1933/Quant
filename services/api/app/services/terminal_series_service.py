"""终端图表序列服务。

从研究报告读取已有序列，对字段做安全类型转换，不制造假数据。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from services.api.app.services.terminal_view_helpers import build_chart_meta


class TerminalSeriesService:
    """处理终端图表序列的服务类。"""

    def build_training_curve(self, report: dict[str, Any]) -> dict[str, Any]:
        """构建训练曲线。

        从 report.latest_training.training_metrics.training_curve 读取训练曲线数据。

        Args:
            report: 研究报告字典

        Returns:
            包含 series 和 meta 的字典
        """
        latest_training = dict(report.get("latest_training") or {})
        training_metrics = dict(latest_training.get("training_metrics") or {})
        training_curve = list(training_metrics.get("training_curve") or [])

        if not training_curve:
            return {
                "series": [],
                "meta": build_chart_meta(
                    data_quality="empty",
                    warnings=["training_curve_missing"],
                ),
            }

        # 规范化序列字段
        series = []
        for item in training_curve:
            if not isinstance(item, dict):
                continue
            series.append({
                "step": int(item.get("step", 0) or 0),
                "train_score": self._safe_float(item.get("train_score")),
                "validation_score": self._safe_float(item.get("validation_score")),
                "test_score": self._safe_float(item.get("test_score")),
            })

        return {
            "series": series,
            "meta": build_chart_meta(data_quality="real"),
        }

    def build_feature_importance(self, report: dict[str, Any]) -> dict[str, Any]:
        """构建特征重要性数据。

        从 report.latest_training.training_metrics.feature_importance 读取数据。

        Args:
            report: 研究报告字典

        Returns:
            包含 series 和 meta 的字典
        """
        latest_training = dict(report.get("latest_training") or {})
        training_metrics = dict(latest_training.get("training_metrics") or {})
        feature_importance = list(training_metrics.get("feature_importance") or [])

        if not feature_importance:
            return {
                "series": [],
                "meta": build_chart_meta(
                    data_quality="empty",
                    warnings=["feature_importance_missing"],
                ),
            }

        series = []
        for item in feature_importance:
            if not isinstance(item, dict):
                continue
            series.append({
                "factor": str(item.get("factor", "") or ""),
                "category": str(item.get("category", "") or ""),
                "importance": self._safe_float(item.get("importance")),
                "rank": int(item.get("rank", 0) or 0),
            })

        # 按 rank 排序
        series.sort(key=lambda x: x.get("rank", 0))

        return {
            "series": series,
            "meta": build_chart_meta(data_quality="real"),
        }

    def build_backtest_performance_series(
        self,
        report: dict[str, Any],
        *,
        backtest_id: str = "latest",
    ) -> dict[str, Any]:
        """构建回测净值、基准和回撤序列。

        Args:
            report: 研究报告字典
            backtest_id: 回测 ID，"latest" 或 symbol

        Returns:
            包含 series 和 meta 的字典
        """
        backtest_data = self._resolve_backtest_data(report, backtest_id)

        if not backtest_data:
            return {
                "series": [],
                "meta": build_chart_meta(
                    data_quality="empty",
                    warnings=["backtest_series_missing"],
                ),
            }

        series = backtest_data.get("series") or {}
        # series 可能是 dict 或 list，需要安全处理
        if isinstance(series, dict):
            series_data = series.get("performance") or []
        else:
            series_data = []

        if not series_data:
            return {
                "series": [],
                "meta": build_chart_meta(
                    data_quality="empty",
                    warnings=["backtest_series_missing"],
                ),
            }

        series = []
        for item in series_data:
            if not isinstance(item, dict):
                continue
            series.append({
                "date": str(item.get("date", "") or ""),
                "strategy_nav": self._safe_float(item.get("strategy_nav")),
                "benchmark_nav": self._safe_float(item.get("benchmark_nav")),
                "drawdown_pct": self._safe_float(item.get("drawdown_pct")),
                "daily_return_pct": self._safe_float(item.get("daily_return_pct")),
                "turnover": self._safe_float(item.get("turnover")),
            })

        return {
            "series": series,
            "meta": build_chart_meta(data_quality="real"),
        }

    def build_top_candidate_nav_series(
        self,
        report: dict[str, Any],
        *,
        limit: int = 5,
    ) -> dict[str, Any]:
        """构建 Top N 候选净值对比序列。

        Args:
            report: 研究报告字典
            limit: 最多返回多少个候选

        Returns:
            包含 series 和 meta 的字典
        """
        leaderboard = list(report.get("leaderboard") or [])[:limit]

        if not leaderboard:
            return {
                "series": [],
                "meta": build_chart_meta(
                    data_quality="empty",
                    warnings=["candidate_backtest_series_missing"],
                ),
            }

        # 尝试从每个候选中提取净值序列
        # 这里需要将多个候选的净值合并成对比格式
        # 由于当前数据结构可能不包含序列，返回空状态
        return {
            "series": [],
            "meta": build_chart_meta(
                data_quality="empty",
                warnings=["candidate_backtest_series_missing"],
            ),
        }

    def build_factor_ic_series(self, report: dict[str, Any]) -> dict[str, Any]:
        """构建因子 IC 序列。

        Args:
            report: 研究报告字典

        Returns:
            包含 series 和 meta 的字典
        """
        factor_evaluation = dict(report.get("factor_evaluation") or {})
        ic_series = list(factor_evaluation.get("ic_series") or [])

        if not ic_series:
            return {
                "series": [],
                "meta": build_chart_meta(
                    data_quality="empty",
                    warnings=["factor_ic_missing"],
                ),
            }

        series = []
        for item in ic_series:
            if not isinstance(item, dict):
                continue
            series.append({
                "date": str(item.get("date", "") or ""),
                "factor": str(item.get("factor", "") or ""),
                "ic": self._safe_float(item.get("ic")),
                "rank_ic": self._safe_float(item.get("rank_ic")),
                "cumulative_ic": self._safe_float(item.get("cumulative_ic")),
            })

        return {
            "series": series,
            "meta": build_chart_meta(data_quality="real"),
        }

    def build_factor_quantile_nav(self, report: dict[str, Any]) -> dict[str, Any]:
        """构建因子分组收益序列。

        Args:
            report: 研究报告字典

        Returns:
            包含 series 和 meta 的字典
        """
        factor_evaluation = dict(report.get("factor_evaluation") or {})
        quantile_nav = list(factor_evaluation.get("quantile_nav") or [])

        if not quantile_nav:
            return {
                "series": [],
                "meta": build_chart_meta(
                    data_quality="empty",
                    warnings=["factor_quantile_missing"],
                ),
            }

        series = []
        for item in quantile_nav:
            if not isinstance(item, dict):
                continue
            series.append({
                "date": str(item.get("date", "") or ""),
                "q1": self._safe_float(item.get("q1")),
                "q2": self._safe_float(item.get("q2")),
                "q3": self._safe_float(item.get("q3")),
                "q4": self._safe_float(item.get("q4")),
                "q5": self._safe_float(item.get("q5")),
                "long_short": self._safe_float(item.get("long_short")),
            })

        return {
            "series": series,
            "meta": build_chart_meta(data_quality="real"),
        }

    def _resolve_backtest_data(
        self,
        report: dict[str, Any],
        backtest_id: str,
    ) -> dict[str, Any] | None:
        """根据 ID 解析回测数据。"""
        normalized_id = backtest_id.strip().lower() if backtest_id else "latest"

        if normalized_id == "latest" or normalized_id == "":
            training = dict(report.get("latest_training") or {})
            return dict(training.get("backtest") or {})

        leaderboard = list(report.get("leaderboard") or [])
        for item in leaderboard:
            symbol = str(item.get("symbol", "")).strip().upper()
            if symbol == backtest_id.strip().upper():
                return dict(item.get("backtest") or {})

        return None

    @staticmethod
    def _safe_float(value: Any) -> float:
        """安全转换为浮点数。"""
        if value is None:
            return 0.0
        try:
            return float(str(value).replace("%", "").strip())
        except (TypeError, ValueError):
            return 0.0


# 单例实例
terminal_series_service = TerminalSeriesService()
