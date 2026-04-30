"""因子分析服务：分析各因子对收益的贡献和有效性。

该服务负责:
- 分析各因子对收益的贡献度
- 计算因子相关性矩阵
- 评估因子有效性评分
- 跟踪因子表现历史
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

from services.api.app.services.scoring import scoring_service, FactorResult, ScoringResult


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
class FactorContribution:
    """单个因子贡献分析结果。"""
    factor_name: str
    weight: float
    avg_score: float
    avg_contribution: float
    contribution_rate: float  # 占总贡献的比例
    impact_count: int  # 影响交易次数
    positive_impact_rate: float  # 正向影响比例
    correlation_with_pnl: float  # 与盈亏的相关性

    def to_dict(self) -> dict[str, Any]:
        return {
            "factor_name": self.factor_name,
            "weight": round(self.weight, 4),
            "avg_score": round(self.avg_score, 4),
            "avg_contribution": round(self.avg_contribution, 4),
            "contribution_rate": round(self.contribution_rate, 4),
            "impact_count": self.impact_count,
            "positive_impact_rate": round(self.positive_impact_rate, 4),
            "correlation_with_pnl": round(self.correlation_with_pnl, 4),
        }


@dataclass(slots=True)
class FactorCorrelationMatrix:
    """因子相关性矩阵。"""
    factors: list[str]
    matrix: list[list[float]]
    timestamp: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "factors": self.factors,
            "matrix": self.matrix,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass(slots=True)
class FactorEffectiveness:
    """因子有效性评估结果。"""
    factor_name: str
    period: str
    effectiveness_score: float  # 0-1
    stability_score: float  # 稳定性评分
    predictive_power: float  # 预测能力
    decay_rate: float  # 衰减率
    recommendation: str  # keep/adjust/remove

    def to_dict(self) -> dict[str, Any]:
        return {
            "factor_name": self.factor_name,
            "period": self.period,
            "effectiveness_score": round(self.effectiveness_score, 4),
            "stability_score": round(self.stability_score, 4),
            "predictive_power": round(self.predictive_power, 4),
            "decay_rate": round(self.decay_rate, 4),
            "recommendation": self.recommendation,
        }


@dataclass(slots=True)
class FactorAnalysisResult:
    """综合因子分析结果。"""
    strategy_id: str
    timestamp: datetime
    contributions: list[FactorContribution]
    total_contribution: float
    top_factors: list[str]
    weak_factors: list[str]
    recommendations: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "timestamp": self.timestamp.isoformat(),
            "contributions": [c.to_dict() for c in self.contributions],
            "total_contribution": round(self.total_contribution, 4),
            "top_factors": self.top_factors,
            "weak_factors": self.weak_factors,
            "recommendations": self.recommendations,
        }


class FactorAnalysisService:
    """因子分析服务，提供因子贡献分析和有效性评估。"""

    def __init__(self) -> None:
        self._factor_history: dict[str, list[dict[str, Any]]] = {}
        self._pnl_records: dict[str, list[Decimal]] = {}
        self._lock = threading.Lock()
        self._config_path: Path | None = None
        self._analysis_cache: dict[str, Any] = {}

    def set_config_path(self, path: str | Path) -> None:
        """设置配置持久化路径。"""
        self._config_path = Path(path)
        self._load_history()

    def _load_history(self) -> None:
        """从文件加载历史数据。"""
        if self._config_path is None or not self._config_path.exists():
            return

        try:
            with open(self._config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            with self._lock:
                self._factor_history = data.get("factor_history", {})
                self._pnl_records = data.get("pnl_records", {})
            logger.info("因子分析历史数据已加载: %s", self._config_path)
        except Exception as e:
            logger.warning("加载因子分析历史数据失败: %s", e)

    def _save_history(self) -> None:
        """保存历史数据到文件。"""
        if self._config_path is None:
            return

        try:
            with self._lock:
                data = {
                    "factor_history": self._factor_history,
                    "pnl_records": self._pnl_records,
                    "updated_at": utc_now().isoformat(),
                }
            with open(self._config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            logger.info("因子分析历史数据已保存: %s", self._config_path)
        except Exception as e:
            logger.warning("保存因子分析历史数据失败: %s", e)

    def record_scoring_result(self, result: ScoringResult, pnl: Decimal = Decimal("0")) -> None:
        """记录评分结果用于后续分析。"""
        symbol = result.symbol
        timestamp = result.timestamp.isoformat()

        with self._lock:
            # 记录因子数据
            if symbol not in self._factor_history:
                self._factor_history[symbol] = []

            factor_data = {
                "timestamp": timestamp,
                "total_score": float(result.total_score),
                "passed_threshold": result.passed_threshold,
                "factors": [f.to_dict() for f in result.factors],
            }
            self._factor_history[symbol].append(factor_data)

            # 限制历史长度
            if len(self._factor_history[symbol]) > 1000:
                self._factor_history[symbol] = self._factor_history[symbol][-1000:]

            # 记录盈亏
            if symbol not in self._pnl_records:
                self._pnl_records[symbol] = []
            self._pnl_records[symbol].append(pnl)

            if len(self._pnl_records[symbol]) > 1000:
                self._pnl_records[symbol] = self._pnl_records[symbol][-1000:]

        self._save_history()

    def analyze_factor_contribution(self, strategy_id: str) -> FactorAnalysisResult:
        """分析各因子对收益的贡献。

        Args:
            strategy_id: 策略标识（可以是symbol或strategy名称）

        Returns:
            FactorAnalysisResult: 因子贡献分析结果
        """
        timestamp = utc_now()

        # 获取评分服务的因子配置
        factors_config = scoring_service.get_factors()
        weights_config = scoring_service.get_factor_weights()
        enabled_factors = set(weights_config.get("enabled_factors", []))

        # 从历史数据中计算贡献
        contributions: list[FactorContribution] = []
        total_contribution = 0.0

        with self._lock:
            # 获取该策略的历史评分数据
            history_key = strategy_id.upper() if strategy_id else ""
            factor_records = self._factor_history.get(history_key, [])
            pnl_records = self._pnl_records.get(history_key, [])

        if not factor_records:
            # 使用评分服务的当前配置生成默认分析
            for factor_info in factors_config:
                if factor_info.get("name") not in enabled_factors:
                    continue

                factor_name = factor_info.get("name", "")
                weight = factor_info.get("weight", 1.0)

                contributions.append(FactorContribution(
                    factor_name=factor_name,
                    weight=weight,
                    avg_score=0.5,
                    avg_contribution=0.5 * weight,
                    contribution_rate=weight / sum(weights_config.get("weights", {}).values()) if weights_config.get("weights") else 0.0,
                    impact_count=0,
                    positive_impact_rate=0.0,
                    correlation_with_pnl=0.0,
                ))

            return FactorAnalysisResult(
                strategy_id=strategy_id,
                timestamp=timestamp,
                contributions=contributions,
                total_contribution=0.0,
                top_factors=[],
                weak_factors=[],
                recommendations=["暂无历史数据，建议积累交易记录后重新分析"],
            )

        # 计算各因子的统计指标
        factor_scores: dict[str, list[float]] = {}
        factor_contributions: dict[str, list[float]] = {}

        for record in factor_records:
            for factor_data in record.get("factors", []):
                name = factor_data.get("name", "")
                if name not in enabled_factors:
                    continue

                if name not in factor_scores:
                    factor_scores[name] = []
                    factor_contributions[name] = []

                factor_scores[name].append(factor_data.get("score", 0.5))
                factor_contributions[name].append(factor_data.get("contribution", 0.0))

        # 计算各因子贡献
        total_weight = sum(weights_config.get("weights", {}).values()) or 1.0

        for factor_info in factors_config:
            factor_name = factor_info.get("name", "")
            if factor_name not in enabled_factors:
                continue

            weight = factor_info.get("weight", 1.0)
            scores = factor_scores.get(factor_name, [])
            contribs = factor_contributions.get(factor_name, [])

            avg_score = sum(scores) / len(scores) if scores else 0.5
            avg_contrib = sum(contribs) / len(contribs) if contribs else weight * 0.5
            contrib_rate = avg_contrib / (sum(sum(c) for c in factor_contributions.values()) or 1.0)

            # 计算正向影响比例（score > 0.5 表示正向）
            positive_count = sum(1 for s in scores if s > 0.5)
            positive_rate = positive_count / len(scores) if scores else 0.0

            # 计算与盈亏的相关性（简化计算）
            pnl_values = [float(p) for p in pnl_records[-len(scores):]] if pnl_records else []
            correlation = self._calculate_correlation(scores, pnl_values)

            contributions.append(FactorContribution(
                factor_name=factor_name,
                weight=weight,
                avg_score=avg_score,
                avg_contribution=avg_contrib,
                contribution_rate=contrib_rate,
                impact_count=len(scores),
                positive_impact_rate=positive_rate,
                correlation_with_pnl=correlation,
            ))

            total_contribution += avg_contrib

        # 排序找出主要因子和弱因子
        sorted_contributions = sorted(contributions, key=lambda c: c.avg_contribution, reverse=True)
        top_factors = [c.factor_name for c in sorted_contributions[:3]]
        weak_factors = [c.factor_name for c in sorted_contributions[-2:] if c.avg_contribution < 0.1]

        # 生成建议
        recommendations = self._generate_recommendations(contributions)

        return FactorAnalysisResult(
            strategy_id=strategy_id,
            timestamp=timestamp,
            contributions=contributions,
            total_contribution=total_contribution,
            top_factors=top_factors,
            weak_factors=weak_factors,
            recommendations=recommendations,
        )

    def calculate_factor_correlation(self) -> FactorCorrelationMatrix:
        """计算因子相关性矩阵。

        Returns:
            FactorCorrelationMatrix: 因子相关性矩阵
        """
        timestamp = utc_now()

        # 获取启用的因子列表
        weights_config = scoring_service.get_factor_weights()
        factors = weights_config.get("enabled_factors", [])

        # 从历史数据中获取各因子的评分序列
        with self._lock:
            all_factor_scores: dict[str, list[float]] = {}

            for symbol_history in self._factor_history.values():
                for record in symbol_history:
                    for factor_data in record.get("factors", []):
                        name = factor_data.get("name", "")
                        if name not in all_factor_scores:
                            all_factor_scores[name] = []
                        all_factor_scores[name].append(factor_data.get("score", 0.5))

        # 计算相关性矩阵
        matrix: list[list[float]] = []

        for i, factor_i in enumerate(factors):
            row: list[float] = []
            scores_i = all_factor_scores.get(factor_i, [])

            for j, factor_j in enumerate(factors):
                if i == j:
                    row.append(1.0)
                else:
                    scores_j = all_factor_scores.get(factor_j, [])
                    correlation = self._calculate_correlation(scores_i, scores_j)
                    row.append(correlation)

            matrix.append(row)

        return FactorCorrelationMatrix(
            factors=factors,
            matrix=matrix,
            timestamp=timestamp,
        )

    def evaluate_factor_effectiveness(self, period: str = "30d") -> list[FactorEffectiveness]:
        """评估因子有效性。

        Args:
            period: 评估周期，如 "7d", "30d", "90d"

        Returns:
            list[FactorEffectiveness]: 各因子有效性评估结果
        """
        # 解析周期
        days = self._parse_period(period)
        cutoff = utc_now() - timedelta(days=days)

        weights_config = scoring_service.get_factor_weights()
        enabled_factors = weights_config.get("enabled_factors", [])

        results: list[FactorEffectiveness] = []

        with self._lock:
            # 收集周期内的因子评分
            period_scores: dict[str, list[float]] = {}
            period_timestamps: dict[str, list[datetime]] = {}

            for symbol_history in self._factor_history.values():
                for record in symbol_history:
                    try:
                        record_time = datetime.fromisoformat(record.get("timestamp", ""))
                        if record_time < cutoff:
                            continue

                        for factor_data in record.get("factors", []):
                            name = factor_data.get("name", "")
                            if name not in enabled_factors:
                                continue

                            if name not in period_scores:
                                period_scores[name] = []
                                period_timestamps[name] = []

                            period_scores[name].append(factor_data.get("score", 0.5))
                            period_timestamps[name].append(record_time)
                    except (ValueError, TypeError):
                        continue

        for factor_name in enabled_factors:
            scores = period_scores.get(factor_name, [])

            if not scores:
                # 无数据时使用默认值
                results.append(FactorEffectiveness(
                    factor_name=factor_name,
                    period=period,
                    effectiveness_score=0.5,
                    stability_score=0.5,
                    predictive_power=0.5,
                    decay_rate=0.0,
                    recommendation="insufficient_data",
                ))
                continue

            # 计算有效性评分（平均评分）
            avg_score = sum(scores) / len(scores)

            # 计算稳定性（标准差越低越稳定）
            variance = sum((s - avg_score) ** 2 for s in scores) / len(scores)
            std_dev = variance ** 0.5
            stability = max(0.0, 1.0 - std_dev * 2)  # 标准差映射到稳定性

            # 计算预测能力（高分时的盈亏表现）
            predictive_power = self._estimate_predictive_power(factor_name, scores)

            # 计算衰减率（最近评分与早期评分的差异）
            decay_rate = self._calculate_decay_rate(scores)

            # 生成建议
            recommendation = self._get_effectiveness_recommendation(
                avg_score, stability, predictive_power, decay_rate
            )

            results.append(FactorEffectiveness(
                factor_name=factor_name,
                period=period,
                effectiveness_score=avg_score,
                stability_score=stability,
                predictive_power=predictive_power,
                decay_rate=decay_rate,
                recommendation=recommendation,
            ))

        return results

    def _calculate_correlation(self, series1: list[float], series2: list[float]) -> float:
        """计算两个序列的相关系数。"""
        if not series1 or not series2:
            return 0.0

        # 取较短序列的长度
        n = min(len(series1), len(series2))
        if n < 2:
            return 0.0

        s1 = series1[:n]
        s2 = series2[:n]

        mean1 = sum(s1) / n
        mean2 = sum(s2) / n

        cov = sum((s1[i] - mean1) * (s2[i] - mean2) for i in range(n)) / n

        var1 = sum((x - mean1) ** 2 for x in s1) / n
        var2 = sum((x - mean2) ** 2 for x in s2) / n

        if var1 == 0 or var2 == 0:
            return 0.0

        return cov / (var1 ** 0.5 * var2 ** 0.5)

    def _parse_period(self, period: str) -> int:
        """解析周期字符串为天数。"""
        try:
            if period.endswith("d"):
                return int(period[:-1])
            elif period.endswith("w"):
                return int(period[:-1]) * 7
            elif period.endswith("m"):
                return int(period[:-1]) * 30
            else:
                return int(period)
        except (ValueError, TypeError):
            return 30

    def _estimate_predictive_power(self, factor_name: str, scores: list[float]) -> float:
        """估算因子的预测能力。"""
        # 简化估算：高分样本的比例
        high_score_count = sum(1 for s in scores if s > 0.6)
        return high_score_count / len(scores) if scores else 0.5

    def _calculate_decay_rate(self, scores: list[float]) -> float:
        """计算因子评分衰减率。"""
        if len(scores) < 10:
            return 0.0

        # 比较最近10个和之前10个的平均值
        recent_avg = sum(scores[-10:]) / 10
        earlier_avg = sum(scores[:10]) / 10

        if earlier_avg == 0:
            return 0.0

        return max(0.0, (earlier_avg - recent_avg) / earlier_avg)

    def _generate_recommendations(self, contributions: list[FactorContribution]) -> list[str]:
        """根据贡献分析生成优化建议。"""
        recommendations: list[str] = []

        # 分析高贡献因子
        high_contrib_factors = [c for c in contributions if c.avg_contribution > 0.5]
        if high_contrib_factors:
            names = ", ".join([c.factor_name for c in high_contrib_factors[:3]])
            recommendations.append(f"高贡献因子: {names}，建议保持当前权重")

        # 分析低贡献因子
        low_contrib_factors = [c for c in contributions if c.avg_contribution < 0.1]
        if low_contrib_factors:
            names = ", ".join([c.factor_name for c in low_contrib_factors])
            recommendations.append(f"低贡献因子: {names}，建议降低权重或禁用")

        # 分析相关性
        high_corr_factors = [c for c in contributions if c.correlation_with_pnl > 0.3]
        if high_corr_factors:
            names = ", ".join([c.factor_name for c in high_corr_factors])
            recommendations.append(f"与盈亏正相关因子: {names}，可适当增加权重")

        # 分析负相关因子
        neg_corr_factors = [c for c in contributions if c.correlation_with_pnl < -0.2]
        if neg_corr_factors:
            names = ", ".join([c.factor_name for c in neg_corr_factors])
            recommendations.append(f"与盈亏负相关因子: {names}，需要重新评估计算逻辑")

        return recommendations

    def _get_effectiveness_recommendation(
        self,
        effectiveness: float,
        stability: float,
        predictive_power: float,
        decay_rate: float,
    ) -> str:
        """根据有效性指标生成建议。"""
        if effectiveness > 0.7 and stability > 0.6:
            return "keep"

        if decay_rate > 0.3:
            return "adjust"

        if effectiveness < 0.3 or stability < 0.3:
            return "remove"

        if predictive_power > 0.6:
            return "keep"

        return "adjust"

    def get_factor_performance_summary(self) -> dict[str, Any]:
        """获取因子表现汇总。"""
        weights_config = scoring_service.get_factor_weights()

        with self._lock:
            total_records = sum(len(h) for h in self._factor_history.values())
            symbols_count = len(self._factor_history)

        return {
            "status": "ready",
            "total_records": total_records,
            "symbols_count": symbols_count,
            "enabled_factors_count": len(weights_config.get("enabled_factors", [])),
            "last_updated": utc_now().isoformat(),
        }


# 全局因子分析服务实例
factor_analysis_service = FactorAnalysisService()

# 设置配置持久化路径
config_dir = Path(__file__).parent.parent.parent.parent.parent / "data" / "config"
config_dir.mkdir(parents=True, exist_ok=True)
factor_analysis_service.set_config_path(config_dir / "factor_analysis_history.json")