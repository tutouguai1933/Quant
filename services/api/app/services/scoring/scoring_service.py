"""评分服务：多因子加权评分模型的核心服务。

提供评分计算、因子管理、阈值设置等功能。
"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from services.api.app.services.scoring.factors import (
    DEFAULT_FACTORS,
    FactorBase,
    create_factor,
    RSIFactor,
    MACDFactor,
    VolumeFactor,
    VolatilityFactor,
    TrendFactor,
    MomentumFactor,
)


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class FactorResult:
    """单个因子的计算结果。"""

    name: str
    weight: float
    score: float
    contribution: float  # score * weight

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "weight": self.weight,
            "score": round(self.score, 4),
            "contribution": round(self.contribution, 4),
        }


@dataclass(slots=True)
class ScoringResult:
    """综合评分结果。"""

    symbol: str
    total_score: float
    weighted_sum: float
    total_weight: float
    factors: list[FactorResult]
    timestamp: datetime
    passed_threshold: bool
    threshold: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "total_score": round(self.total_score, 4),
            "weighted_sum": round(self.weighted_sum, 4),
            "total_weight": round(self.total_weight, 4),
            "factors": [f.to_dict() for f in self.factors],
            "timestamp": self.timestamp.isoformat(),
            "passed_threshold": self.passed_threshold,
            "threshold": self.threshold,
        }


@dataclass
class ScoringConfig:
    """评分配置，持久化存储。"""

    min_entry_score: float = 0.60
    factor_weights: dict[str, float] = field(default_factory=lambda: {
        "rsi": 1.0,
        "macd": 1.0,
        "volume": 0.8,
        "volatility": 0.6,
        "trend": 1.2,
        "momentum": 0.8,
    })
    enabled_factors: list[str] = field(default_factory=lambda: [
        "rsi", "macd", "volume", "volatility", "trend", "momentum"
    ])

    def to_dict(self) -> dict[str, Any]:
        return {
            "min_entry_score": self.min_entry_score,
            "factor_weights": dict(self.factor_weights),
            "enabled_factors": list(self.enabled_factors),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ScoringConfig":
        return cls(
            min_entry_score=float(data.get("min_entry_score", 0.60)),
            factor_weights=dict(data.get("factor_weights", {})),
            enabled_factors=list(data.get("enabled_factors", [])),
        )


class ScoringService:
    """多因子加权评分服务。

    主要功能：
    1. 计算综合评分
    2. 获取/设置因子权重
    3. 设置入场阈值
    4. 动态添加/删除因子
    5. 配置持久化
    """

    def __init__(self) -> None:
        self._factors: list[FactorBase] = list(DEFAULT_FACTORS)
        self._config: ScoringConfig = ScoringConfig()
        self._config_lock = threading.Lock()
        self._config_path: Path | None = None
        self._last_scores: dict[str, ScoringResult] = {}
        self._score_history: dict[str, list[ScoringResult]] = {}

    def set_config_path(self, path: str | Path) -> None:
        """设置配置持久化路径。"""
        self._config_path = Path(path)
        self._load_config()

    def _load_config(self) -> None:
        """从文件加载配置。"""
        if self._config_path is None or not self._config_path.exists():
            return

        try:
            with open(self._config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            with self._config_lock:
                self._config = ScoringConfig.from_dict(data)
                self._apply_config_weights()
            logger.info("评分配置已加载: %s", self._config_path)
        except Exception as e:
            logger.warning("加载评分配置失败: %s", e)

    def _save_config(self) -> None:
        """保存配置到文件。"""
        if self._config_path is None:
            return

        try:
            with self._config_lock:
                data = self._config.to_dict()
            with open(self._config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            logger.info("评分配置已保存: %s", self._config_path)
        except Exception as e:
            logger.warning("保存评分配置失败: %s", e)

    def _apply_config_weights(self) -> None:
        """应用配置中的权重到因子。"""
        for factor in self._factors:
            weight = self._config.factor_weights.get(factor.name, factor.weight)
            factor.weight = weight

    def calculate_score(self, symbol: str, data: dict[str, Any]) -> ScoringResult:
        """计算综合评分。

        Args:
            symbol: 交易标的符号
            data: 市场数据字典，包含各因子所需的输入

        Returns:
            ScoringResult: 评分结果
        """
        timestamp = datetime.now(timezone.utc)
        threshold = self._config.min_entry_score

        factor_results: list[FactorResult] = []
        weighted_sum = 0.0
        total_weight = 0.0

        with self._config_lock:
            enabled_factors = set(self._config.enabled_factors)

        for factor in self._factors:
            if factor.name not in enabled_factors:
                continue

            try:
                score = factor.calculate(data)
                weight = factor.weight
                contribution = score * weight

                factor_results.append(FactorResult(
                    name=factor.name,
                    weight=weight,
                    score=score,
                    contribution=contribution,
                ))

                weighted_sum += contribution
                total_weight += weight
            except Exception as e:
                logger.warning("因子 %s 计算失败: %s", factor.name, e)
                # 使用中性值
                factor_results.append(FactorResult(
                    name=factor.name,
                    weight=factor.weight,
                    score=0.5,
                    contribution=0.5 * factor.weight,
                ))
                weighted_sum += 0.5 * factor.weight
                total_weight += factor.weight

        if total_weight > 0:
            total_score = weighted_sum / total_weight
        else:
            total_score = 0.5

        result = ScoringResult(
            symbol=symbol.strip().upper(),
            total_score=total_score,
            weighted_sum=weighted_sum,
            total_weight=total_weight,
            factors=factor_results,
            timestamp=timestamp,
            passed_threshold=total_score >= threshold,
            threshold=threshold,
        )

        # 缓存结果
        self._last_scores[result.symbol] = result
        history = self._score_history.setdefault(result.symbol, [])
        history.append(result)
        # 保留最近100条历史
        if len(history) > 100:
            history = history[-100:]
            self._score_history[result.symbol] = history

        return result

    def get_current_score(self, symbol: str) -> ScoringResult | None:
        """获取指定标的的最新评分。"""
        return self._last_scores.get(symbol.strip().upper())

    def get_score_history(self, symbol: str, limit: int = 10) -> list[ScoringResult]:
        """获取指定标的的评分历史。"""
        history = self._score_history.get(symbol.strip().upper(), [])
        return history[-limit:]

    def get_factor_weights(self) -> dict[str, Any]:
        """获取各因子权重配置。"""
        with self._config_lock:
            return {
                "weights": dict(self._config.factor_weights),
                "enabled_factors": list(self._config.enabled_factors),
                "min_entry_score": self._config.min_entry_score,
            }

    def set_factor_weights(self, weights: dict[str, float]) -> bool:
        """设置各因子权重。

        Args:
            weights: 因子名称到权重的映射

        Returns:
            bool: 设置是否成功
        """
        # 验证权重值
        for name, weight in weights.items():
            if not isinstance(weight, (int, float)):
                return False
            if weight < 0 or weight > 5.0:  # 权重范围限制
                return False

        with self._config_lock:
            for name, weight in weights.items():
                self._config.factor_weights[name] = float(weight)
            self._apply_config_weights()

        self._save_config()
        return True

    def set_min_entry_score(self, threshold: float) -> bool:
        """设置入场阈值。

        Args:
            threshold: 最小入场评分阈值（0-1范围）

        Returns:
            bool: 设置是否成功
        """
        if not isinstance(threshold, (int, float)):
            return False
        if threshold < 0 or threshold > 1.0:
            return False

        with self._config_lock:
            self._config.min_entry_score = float(threshold)

        self._save_config()
        return True

    def get_min_entry_score(self) -> float:
        """获取当前入场阈值。"""
        with self._config_lock:
            return self._config.min_entry_score

    def enable_factor(self, factor_name: str) -> bool:
        """启用指定因子。"""
        with self._config_lock:
            if factor_name not in self._config.enabled_factors:
                self._config.enabled_factors.append(factor_name)
        self._save_config()
        return True

    def disable_factor(self, factor_name: str) -> bool:
        """禁用指定因子。"""
        with self._config_lock:
            if factor_name in self._config.enabled_factors:
                self._config.enabled_factors.remove(factor_name)
        self._save_config()
        return True

    def add_factor(self, factor_type: str, weight: float = 1.0, **kwargs) -> bool:
        """动态添加因子。

        Args:
            factor_type: 因子类型
            weight: 因子权重
            **kwargs: 因子配置参数

        Returns:
            bool: 添加是否成功
        """
        new_factor = create_factor(factor_type, weight, **kwargs)
        if new_factor is None:
            return False

        # 检查是否已存在同名因子
        for factor in self._factors:
            if factor.name == new_factor.name:
                # 更新权重
                factor.weight = weight
                with self._config_lock:
                    self._config.factor_weights[new_factor.name] = weight
                self._save_config()
                return True

        self._factors.append(new_factor)
        with self._config_lock:
            self._config.factor_weights[new_factor.name] = weight
            if new_factor.name not in self._config.enabled_factors:
                self._config.enabled_factors.append(new_factor.name)
        self._save_config()
        return True

    def remove_factor(self, factor_name: str) -> bool:
        """移除因子。

        Args:
            factor_name: 因子名称

        Returns:
            bool: 移除是否成功
        """
        # 不允许移除核心因子
        core_factors = {"rsi", "macd", "volume", "volatility", "trend", "momentum"}
        if factor_name in core_factors:
            # 只能禁用，不能移除
            return self.disable_factor(factor_name)

        self._factors = [f for f in self._factors if f.name != factor_name]
        with self._config_lock:
            if factor_name in self._config.enabled_factors:
                self._config.enabled_factors.remove(factor_name)
            if factor_name in self._config.factor_weights:
                del self._config.factor_weights[factor_name]
        self._save_config()
        return True

    def get_factors(self) -> list[dict[str, Any]]:
        """获取所有因子配置信息。"""
        with self._config_lock:
            enabled = set(self._config.enabled_factors)

        return [
            {
                **factor.to_dict(),
                "enabled": factor.name in enabled,
            }
            for factor in self._factors
        ]

    def should_enter(self, symbol: str, data: dict[str, Any]) -> tuple[bool, ScoringResult]:
        """判断是否应该入场。

        Args:
            symbol: 交易标的符号
            data: 市场数据

        Returns:
            tuple[bool, ScoringResult]: 是否入场和评分结果
        """
        result = self.calculate_score(symbol, data)
        return result.passed_threshold, result

    def get_config(self) -> dict[str, Any]:
        """获取完整配置。"""
        with self._config_lock:
            return self._config.to_dict()


# 全局评分服务实例
scoring_service = ScoringService()

# 设置配置持久化路径
config_dir = Path(__file__).parent.parent.parent.parent.parent / "data" / "config"
config_dir.mkdir(parents=True, exist_ok=True)
scoring_service.set_config_path(config_dir / "scoring_config.json")