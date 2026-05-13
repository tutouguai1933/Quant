"""多模型集成预测器。

组合 LightGBM 和 XGBoost 预测，通过加权融合提升稳定性。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from services.worker.ml.model import MLModel

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class EnsemblePrediction:
    """集成预测结果。"""

    probability: float
    individual_predictions: dict[str, float]  # 每个模型的预测概率
    weights: dict[str, float]  # 每个模型的权重
    confidence: float  # 模型间一致性指标


class EnsembleModel:
    """多模型集成预测器。

    训练多个异构模型，通过加权平均融合预测结果。
    """

    def __init__(
        self,
        model_types: tuple[str, ...] = ("lightgbm",),
        weights: dict[str, float] | None = None,
    ) -> None:
        self._model_types = list(model_types)
        self._models: dict[str, MLModel] = {}
        self._weights = dict(weights or {})
        self._is_fitted = False

    @property
    def is_fitted(self) -> bool:
        return self._is_fitted

    @property
    def models(self) -> dict[str, MLModel]:
        return dict(self._models)

    def fit(
        self,
        X: np.ndarray,
        y: np.ndarray,
        feature_names: list[str],
        eval_set: tuple[np.ndarray, np.ndarray] | None = None,
        individual_params: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """训练所有模型。

        Returns:
            训练历史字典，key 为模型类型
        """
        histories: dict[str, Any] = {}
        for model_type in self._model_types:
            try:
                params = dict(individual_params.get(model_type, {})) if individual_params else {}
                model = MLModel(model_type=model_type, params=params)
                hist = model.fit(X, y, feature_names=feature_names, eval_set=eval_set)
                self._models[model_type] = model
                histories[model_type] = hist
                logger.info("集成模型 %s 训练完成", model_type)
            except Exception as e:
                logger.warning("集成模型 %s 训练失败: %s", model_type, e)

        if not self._models:
            raise RuntimeError("所有集成模型训练均失败")

        self._is_fitted = True

        # 自动计算权重：基于验证集表现的加权
        if not self._weights:
            self._compute_adaptive_weights(eval_set)

        return histories

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """返回加权融合的正类概率 [n_samples, 2]。"""
        if not self._is_fitted:
            raise RuntimeError("模型尚未训练")
        probas = []
        for model_type, model in self._models.items():
            weight = self._weights.get(model_type, 1.0 / len(self._models))
            proba = model.predict_proba(X)
            probas.append(proba * weight)
        # 加权平均
        fused = sum(probas)
        # 归一化确保列和为1
        fused_sum = np.sum(fused, axis=1, keepdims=True)
        fused_sum[fused_sum == 0] = 1.0
        return fused / fused_sum

    def predict_individual(self, X: np.ndarray) -> list[EnsemblePrediction]:
        """返回每个样本的分解预测。"""
        if not self._is_fitted:
            raise RuntimeError("模型尚未训练")
        results = []
        for i in range(len(X)):
            x = X[i : i + 1]
            individual: dict[str, float] = {}
            for model_type, model in self._models.items():
                proba = model.predict_proba(x)[0]
                individual[model_type] = float(proba[1])
            # 加权融合
            weighted_sum = sum(
                individual[mt] * self._weights.get(mt, 0)
                for mt in self._models
            )
            total_weight = sum(self._weights.get(mt, 0) for mt in self._models)
            probability = weighted_sum / total_weight if total_weight > 0 else 0.5
            # 置信度 = 模型间标准差的反比（越一致越自信）
            values = list(individual.values())
            std = float(np.std(values)) if len(values) > 1 else 0.0
            confidence = 1.0 - min(std * 3, 1.0)  # 标准差越大，置信度越低
            results.append(EnsemblePrediction(
                probability=float(probability),
                individual_predictions=individual,
                weights=dict(self._weights),
                confidence=float(confidence),
            ))
        return results

    def get_feature_importance(self) -> dict[str, Any]:
        """返回所有模型的特征重要性汇总。"""
        result: dict[str, Any] = {}
        for model_type, model in self._models.items():
            fi = model.get_feature_importance()
            result[model_type] = {
                "feature_names": fi.feature_names,
                "importances": fi.importances,
                "importance_type": fi.importance_type,
            }
        # 计算平均重要性
        if result:
            all_features = result[list(result.keys())[0]]["feature_names"]
            avg_importances = []
            for i, feat in enumerate(all_features):
                vals = [
                    result[mt]["importances"][i]
                    for mt in result
                    if i < len(result[mt]["importances"])
                ]
                avg_importances.append(float(np.mean(vals)) if vals else 0.0)
            result["average"] = {
                "feature_names": all_features,
                "importances": avg_importances,
                "importance_type": "ensemble_mean",
            }
        return result

    def save(self, base_path: Path) -> None:
        """保存所有模型。"""
        base_path.mkdir(parents=True, exist_ok=True)
        for model_type, model in self._models.items():
            model_path = base_path / f"{model_type}.pkl"
            model.save(model_path)
        # 保存权重和元数据
        import json
        meta_path = base_path / "ensemble_meta.json"
        meta_path.write_text(json.dumps({
            "model_types": list(self._models.keys()),
            "weights": self._weights,
        }), encoding="utf-8")

    @classmethod
    def load(cls, base_path: Path) -> "EnsembleModel":
        """加载所有模型。"""
        import json
        meta_path = base_path / "ensemble_meta.json"
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            model_types = meta.get("model_types", ["lightgbm"])
            weights = meta.get("weights", {})
        else:
            model_types = ["lightgbm"]
            weights = {}

        ensemble = cls(model_types=tuple(model_types), weights=weights)
        for model_type in model_types:
            model_path = base_path / f"{model_type}.pkl"
            if model_path.exists():
                model = MLModel(model_type=model_type)
                model.load(model_path)
                ensemble._models[model_type] = model
        if ensemble._models:
            ensemble._is_fitted = True
        return ensemble

    def _compute_adaptive_weights(
        self, eval_set: tuple[np.ndarray, np.ndarray] | None
    ) -> None:
        """基于验证集表现自动计算模型权重。"""
        if not eval_set or len(self._models) <= 1:
            self._weights = {mt: 1.0 / len(self._models) for mt in self._models}
            return

        X_val, y_val = eval_set
        scores: dict[str, float] = {}
        for model_type, model in self._models.items():
            try:
                proba = model.predict_proba(X_val)[:, 1]
                from sklearn.metrics import roc_auc_score
                scores[model_type] = float(roc_auc_score(y_val, proba))
            except Exception:
                scores[model_type] = 0.5

        total = sum(scores.values())
        if total > 0:
            self._weights = {mt: s / total for mt, s in scores.items()}
        else:
            self._weights = {mt: 1.0 / len(self._models) for mt in self._models}
        logger.info("自适应权重: %s", self._weights)
