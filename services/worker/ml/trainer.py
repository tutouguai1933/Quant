"""ML 模型训练器。

提供完整的模型训练流程，包括数据准备、特征工程、模型训练、评估。
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import numpy as np

from services.worker.ml.model import MLModel, TrainingCurve, FeatureImportance


@dataclass(slots=True)
class TrainingResult:
    """训练结果数据类。"""

    model: MLModel
    model_version: str
    training_curve: TrainingCurve
    feature_importance: FeatureImportance
    metrics: dict[str, float]
    training_context: dict[str, Any]
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class ModelTrainer:
    """模型训练器。

    负责将原始数据转换为模型输入，训练模型，并返回完整的训练结果。
    """

    def __init__(
        self,
        model_type: str = "lightgbm",
        model_params: dict[str, Any] | None = None,
        label_column: str = "future_return_pct",
        label_threshold: float = 0.0,
    ) -> None:
        """初始化训练器。

        Args:
            model_type: 模型类型，支持 "lightgbm" 或 "xgboost"
            model_params: 模型参数
            label_column: 标签列名
            label_threshold: 正样本阈值，大于此值为正样本
        """
        self.model_type = model_type
        self.model_params = model_params
        self.label_column = label_column
        self.label_threshold = label_threshold

    def train(
        self,
        training_rows: list[dict[str, Any]],
        validation_rows: list[dict[str, Any]],
        feature_columns: tuple[str, ...],
        label_column: str | None = None,
        model_params: dict[str, Any] | None = None,
    ) -> TrainingResult:
        """训练模型。

        Args:
            training_rows: 训练数据行
            validation_rows: 验证数据行
            feature_columns: 特征列名
            label_column: 标签列名，如果为 None 则使用初始化时的值
            model_params: 模型参数，如果为 None 则使用初始化时的值

        Returns:
            TrainingResult: 训练结果
        """
        effective_label_column = label_column or self.label_column
        effective_model_params = model_params or self.model_params

        # 准备特征矩阵
        X_train, y_train = self._prepare_data(
            training_rows,
            feature_columns,
            effective_label_column,
        )
        X_val, y_val = self._prepare_data(
            validation_rows,
            feature_columns,
            effective_label_column,
        )

        # 创建模型
        model = MLModel(
            model_type=self.model_type,
            params=effective_model_params,
        )

        # 训练模型
        training_curve = model.fit(
            X_train,
            y_train,
            feature_names=list(feature_columns),
            eval_set=(X_val, y_val) if len(X_val) > 0 else None,
        )

        # 获取特征重要性
        feature_importance = model.get_feature_importance()

        # 计算评估指标
        metrics = self._calculate_metrics(model, X_train, y_train, X_val, y_val)

        # 生成模型版本
        model_version = self._generate_model_version()

        # 构建训练上下文
        training_context = {
            "model_type": self.model_type,
            "model_params": effective_model_params,
            "feature_columns": list(feature_columns),
            "label_column": effective_label_column,
            "label_threshold": self.label_threshold,
            "training_samples": len(training_rows),
            "validation_samples": len(validation_rows),
            "training_positive_rate": float(np.mean(y_train)) if len(y_train) > 0 else 0.0,
            "validation_positive_rate": float(np.mean(y_val)) if len(y_val) > 0 else 0.0,
        }

        return TrainingResult(
            model=model,
            model_version=model_version,
            training_curve=training_curve,
            feature_importance=feature_importance,
            metrics=metrics,
            training_context=training_context,
        )

    def _prepare_data(
        self,
        rows: list[dict[str, Any]],
        feature_columns: tuple[str, ...],
        label_column: str,
    ) -> tuple[np.ndarray, np.ndarray]:
        """准备训练数据。

        Args:
            rows: 数据行
            feature_columns: 特征列名
            label_column: 标签列名

        Returns:
            (X, y) 元组
        """
        if not rows:
            return np.array([]).reshape(0, len(feature_columns)), np.array([])

        X_list: list[list[float]] = []
        y_list: list[int] = []

        for row in rows:
            # 提取特征
            features = []
            for col in feature_columns:
                value = row.get(col)
                features.append(self._to_float(value))
            X_list.append(features)

            # 提取标签并转换为二分类
            label_value = self._to_float(row.get(label_column))
            y_list.append(1 if label_value > self.label_threshold else 0)

        X = np.array(X_list, dtype=np.float64)
        y = np.array(y_list, dtype=np.int32)

        return X, y

    def _calculate_metrics(
        self,
        model: MLModel,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: np.ndarray,
        y_val: np.ndarray,
    ) -> dict[str, float]:
        """计算评估指标。

        Args:
            model: 训练好的模型
            X_train: 训练特征
            y_train: 训练标签
            X_val: 验证特征
            y_val: 验证标签

        Returns:
            评估指标字典
        """
        metrics: dict[str, float] = {}

        # 训练集指标
        if len(X_train) > 0:
            train_proba = model.predict_proba(X_train)[:, 1]
            train_pred = (train_proba >= 0.5).astype(int)
            metrics["train_auc"] = self._calculate_auc(y_train, train_proba)
            metrics["train_accuracy"] = float(np.mean(train_pred == y_train))
            metrics["train_precision"] = self._calculate_precision(y_train, train_pred)
            metrics["train_recall"] = self._calculate_recall(y_train, train_pred)
            metrics["train_f1"] = self._calculate_f1(
                metrics["train_precision"],
                metrics["train_recall"],
            )

        # 验证集指标
        if len(X_val) > 0:
            val_proba = model.predict_proba(X_val)[:, 1]
            val_pred = (val_proba >= 0.5).astype(int)
            metrics["val_auc"] = self._calculate_auc(y_val, val_proba)
            metrics["val_accuracy"] = float(np.mean(val_pred == y_val))
            metrics["val_precision"] = self._calculate_precision(y_val, val_pred)
            metrics["val_recall"] = self._calculate_recall(y_val, val_pred)
            metrics["val_f1"] = self._calculate_f1(
                metrics["val_precision"],
                metrics["val_recall"],
            )

        return metrics

    def _calculate_auc(self, y_true: np.ndarray, y_proba: np.ndarray) -> float:
        """计算 AUC。"""
        try:
            from sklearn.metrics import roc_auc_score
            return float(roc_auc_score(y_true, y_proba))
        except (ImportError, ValueError):
            # 简化版 AUC 计算
            return self._simple_auc(y_true, y_proba)

    def _simple_auc(self, y_true: np.ndarray, y_proba: np.ndarray) -> float:
        """简化版 AUC 计算 - 使用向量化实现 O(n log n) 复杂度。"""
        positive_mask = y_true == 1
        negative_mask = y_true == 0

        if not np.any(positive_mask) or not np.any(negative_mask):
            return 0.5

        positive_scores = y_proba[positive_mask]
        negative_scores = y_proba[negative_mask]

        n_pos = len(positive_scores)
        n_neg = len(negative_scores)

        # 使用广播进行向量化计算
        # 比较矩阵：positive_scores[:, None] > negative_scores[None, :]
        comparisons = positive_scores[:, None] > negative_scores[None, :]
        ties = positive_scores[:, None] == negative_scores[None, :]

        # AUC = (大于的数量 + 0.5 * 等于的数量) / (n_pos * n_neg)
        correct = np.sum(comparisons) + 0.5 * np.sum(ties)

        return float(correct / (n_pos * n_neg))

    def _calculate_precision(self, y_true: np.ndarray, y_pred: np.ndarray) -> float:
        """计算精确率。"""
        tp = np.sum((y_pred == 1) & (y_true == 1))
        fp = np.sum((y_pred == 1) & (y_true == 0))
        return float(tp / (tp + fp)) if (tp + fp) > 0 else 0.0

    def _calculate_recall(self, y_true: np.ndarray, y_pred: np.ndarray) -> float:
        """计算召回率。"""
        tp = np.sum((y_pred == 1) & (y_true == 1))
        fn = np.sum((y_pred == 0) & (y_true == 1))
        return float(tp / (tp + fn)) if (tp + fn) > 0 else 0.0

    def _calculate_f1(self, precision: float, recall: float) -> float:
        """计算 F1 分数。"""
        if precision + recall == 0:
            return 0.0
        return 2 * precision * recall / (precision + recall)

    def _generate_model_version(self) -> str:
        """生成模型版本号。"""
        now = datetime.now(timezone.utc)
        return f"{self.model_type}-{now.strftime('%Y%m%d%H%M%S')}"

    @staticmethod
    def _to_float(value: Any) -> float:
        """将任意值转换为 float。"""
        if value is None:
            return 0.0
        try:
            return float(Decimal(str(value)))
        except (TypeError, ValueError, InvalidOperation):
            return 0.0
