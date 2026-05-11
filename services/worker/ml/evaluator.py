"""ML 模型评估器。

提供模型评估指标计算，包括 IC、Rank IC、Precision@K、Sharpe 等。
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

import numpy as np

from services.worker.ml.model import MLModel


@dataclass(slots=True)
class EvaluationResult:
    """评估结果数据类。"""

    ic: float
    rank_ic: float
    ic_ir: float
    precision_at_k: dict[int, float]
    recall_at_k: dict[int, float]
    cumulative_return: float
    sharpe: float
    max_drawdown: float
    win_rate: float
    sample_count: int
    metrics: dict[str, float] = field(default_factory=dict)


class ModelEvaluator:
    """模型评估器。

    计算模型的各种评估指标，包括预测能力和交易表现。
    """

    def __init__(
        self,
        k_values: tuple[int, ...] = (1, 3, 5, 10),
    ) -> None:
        """初始化评估器。

        Args:
            k_values: 计算 Precision@K 的 K 值列表
        """
        self._k_values = k_values

    def evaluate(
        self,
        model: MLModel,
        test_rows: list[dict[str, Any]],
        feature_columns: tuple[str, ...],
        label_column: str = "future_return_pct",
    ) -> EvaluationResult:
        """评估模型。

        Args:
            model: 训练好的模型
            test_rows: 测试数据行
            feature_columns: 特征列名
            label_column: 标签列名（未来收益）

        Returns:
            EvaluationResult: 评估结果
        """
        if not test_rows:
            return self._empty_result()

        # 准备数据
        X, y_true, returns = self._prepare_data(test_rows, feature_columns, label_column)

        if len(X) == 0:
            return self._empty_result()

        # 获取预测分数
        y_proba = model.predict_proba(X)[:, 1]

        # 计算 IC 相关指标
        ic = self._calculate_ic(y_proba, returns)
        rank_ic = self._calculate_rank_ic(y_proba, returns)
        ic_ir = self._calculate_ic_ir(y_proba, returns)

        # 计算 Precision@K
        precision_at_k = self._calculate_precision_at_k(y_proba, returns, self._k_values)
        recall_at_k = self._calculate_recall_at_k(y_proba, returns, self._k_values)

        # 计算交易表现
        cumulative_return, sharpe, max_drawdown, win_rate = self._calculate_trading_metrics(
            y_proba, returns
        )

        # 构建完整指标
        metrics = {
            "ic": ic,
            "rank_ic": rank_ic,
            "ic_ir": ic_ir,
            "cumulative_return": cumulative_return,
            "sharpe": sharpe,
            "max_drawdown": max_drawdown,
            "win_rate": win_rate,
            "sample_count": len(test_rows),
            "mean_return": float(np.mean(returns)),
            "std_return": float(np.std(returns)),
            "positive_rate": float(np.mean(returns > 0)),
        }

        return EvaluationResult(
            ic=ic,
            rank_ic=rank_ic,
            ic_ir=ic_ir,
            precision_at_k=precision_at_k,
            recall_at_k=recall_at_k,
            cumulative_return=cumulative_return,
            sharpe=sharpe,
            max_drawdown=max_drawdown,
            win_rate=win_rate,
            sample_count=len(test_rows),
            metrics=metrics,
        )

    def _prepare_data(
        self,
        rows: list[dict[str, Any]],
        feature_columns: tuple[str, ...],
        label_column: str,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """准备评估数据。

        Returns:
            (X, y_true, returns) 元组
        """
        X_list: list[list[float]] = []
        returns_list: list[float] = []

        for row in rows:
            features = [self._to_float(row.get(col)) for col in feature_columns]
            X_list.append(features)
            returns_list.append(self._to_float(row.get(label_column)))

        X = np.array(X_list, dtype=np.float64)
        returns = np.array(returns_list, dtype=np.float64)
        y_true = (returns > 0).astype(int)

        return X, y_true, returns

    def _calculate_ic(self, predictions: np.ndarray, returns: np.ndarray) -> float:
        """计算 Information Coefficient。

        IC = Correlation(predictions, returns)
        """
        if len(predictions) < 2:
            return 0.0

        # 皮尔逊相关系数
        mean_pred = np.mean(predictions)
        mean_ret = np.mean(returns)

        cov = np.sum((predictions - mean_pred) * (returns - mean_ret))
        std_pred = np.sqrt(np.sum((predictions - mean_pred) ** 2))
        std_ret = np.sqrt(np.sum((returns - mean_ret) ** 2))

        if std_pred == 0 or std_ret == 0:
            return 0.0

        return float(cov / (std_pred * std_ret))

    def _calculate_rank_ic(self, predictions: np.ndarray, returns: np.ndarray) -> float:
        """计算 Rank IC。

        Rank IC = Correlation(rank(predictions), rank(returns))
        """
        if len(predictions) < 2:
            return 0.0

        # 使用 Spearman 秩相关
        rank_pred = self._rank(predictions)
        rank_ret = self._rank(returns)

        return self._calculate_ic(rank_pred, rank_ret)

    def _rank(self, arr: np.ndarray) -> np.ndarray:
        """计算秩。"""
        temp = arr.argsort()
        ranks = np.empty_like(temp)
        ranks[temp] = np.arange(len(arr))
        return ranks.astype(float)

    def _calculate_ic_ir(self, predictions: np.ndarray, returns: np.ndarray) -> float:
        """计算 IC Information Ratio。

        IC_IR = IC / std(IC)
        这里简化为 IC 本身，因为单次评估只有一个 IC 值
        """
        ic = self._calculate_ic(predictions, returns)
        # 简化处理，返回 IC 的绝对值作为 IR 的近似
        return abs(ic)

    def _calculate_precision_at_k(
        self,
        predictions: np.ndarray,
        returns: np.ndarray,
        k_values: tuple[int, ...],
    ) -> dict[int, float]:
        """计算 Precision@K。

        选择预测分数最高的 K 个样本，计算其中实际收益为正的比例。
        """
        results = {}

        for k in k_values:
            if k >= len(predictions):
                k = len(predictions)

            if k == 0:
                results[k] = 0.0
                continue

            # 获取预测分数最高的 K 个索引
            top_k_indices = np.argsort(predictions)[-k:]

            # 计算其中收益为正的比例
            positive_count = np.sum(returns[top_k_indices] > 0)
            results[k] = float(positive_count / k)

        return results

    def _calculate_recall_at_k(
        self,
        predictions: np.ndarray,
        returns: np.ndarray,
        k_values: tuple[int, ...],
    ) -> dict[int, float]:
        """计算 Recall@K。

        计算预测分数最高的 K 个样本中，包含实际正样本的比例。
        """
        results = {}
        total_positive = np.sum(returns > 0)

        for k in k_values:
            if k >= len(predictions):
                k = len(predictions)

            if k == 0 or total_positive == 0:
                results[k] = 0.0
                continue

            # 获取预测分数最高的 K 个索引
            top_k_indices = np.argsort(predictions)[-k:]

            # 计算其中正样本占总正样本的比例
            positive_in_top_k = np.sum(returns[top_k_indices] > 0)
            results[k] = float(positive_in_top_k / total_positive)

        return results

    def _calculate_trading_metrics(
        self,
        predictions: np.ndarray,
        returns: np.ndarray,
    ) -> tuple[float, float, float, float]:
        """计算交易表现指标。

        根据预测分数生成交易信号，计算累计收益、Sharpe、最大回撤、胜率。

        Returns:
            (cumulative_return, sharpe, max_drawdown, win_rate)
        """
        # 生成交易信号：预测分数 >= 0.5 做多，否则不交易
        signals = (predictions >= 0.5).astype(int)

        # 计算策略收益
        strategy_returns = signals * returns

        # 累计收益
        cumulative_return = float(np.sum(strategy_returns))

        # Sharpe Ratio
        if len(strategy_returns) > 1 and np.std(strategy_returns) > 0:
            sharpe = float(np.mean(strategy_returns) / np.std(strategy_returns))
        else:
            sharpe = 0.0

        # 最大回撤
        cumulative = np.cumsum(strategy_returns)
        peak = np.maximum.accumulate(cumulative)
        drawdown = cumulative - peak
        max_drawdown = float(np.min(drawdown))

        # 胜率
        traded_returns = strategy_returns[signals == 1]
        if len(traded_returns) > 0:
            win_rate = float(np.mean(traded_returns > 0))
        else:
            win_rate = 0.0

        return cumulative_return, sharpe, max_drawdown, win_rate

    def _empty_result(self) -> EvaluationResult:
        """返回空结果。"""
        return EvaluationResult(
            ic=0.0,
            rank_ic=0.0,
            ic_ir=0.0,
            precision_at_k={k: 0.0 for k in self._k_values},
            recall_at_k={k: 0.0 for k in self._k_values},
            cumulative_return=0.0,
            sharpe=0.0,
            max_drawdown=0.0,
            win_rate=0.0,
            sample_count=0,
            metrics={},
        )

    @staticmethod
    def _to_float(value: Any) -> float:
        """将任意值转换为 float。"""
        if value is None:
            return 0.0
        try:
            return float(Decimal(str(value)))
        except (TypeError, ValueError, InvalidOperation):
            return 0.0
