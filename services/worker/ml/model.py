"""ML 模型封装。

提供 LightGBM 和 XGBoost 模型的统一接口。
"""

from __future__ import annotations

import json
import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np


@dataclass(slots=True)
class TrainingCurve:
    """训练曲线数据。"""

    steps: list[int]
    train_scores: list[float]
    validation_scores: list[float]
    best_step: int
    best_score: float


@dataclass(slots=True)
class FeatureImportance:
    """特征重要性数据。"""

    feature_names: list[str]
    importances: list[float]
    importance_type: str


class MLModel:
    """机器学习模型封装类。

    支持 LightGBM 和 XGBoost 模型，提供统一的训练、预测、保存、加载接口。
    """

    def __init__(
        self,
        model_type: str = "lightgbm",
        params: dict[str, Any] | None = None,
    ) -> None:
        """初始化模型。

        Args:
            model_type: 模型类型，支持 "lightgbm" 或 "xgboost"
            params: 模型参数，如果为 None 则使用默认参数
        """
        self.model_type = model_type.lower()
        self.params = params or self._default_params()
        self.model: Any = None
        self.feature_names: list[str] = []
        self._is_fitted = False

    def _default_params(self) -> dict[str, Any]:
        """返回默认模型参数。"""
        if self.model_type == "lightgbm":
            return {
                "objective": "binary",
                "metric": "auc",
                "boosting_type": "gbdt",
                "num_leaves": 31,
                "learning_rate": 0.05,
                "feature_fraction": 0.8,
                "bagging_fraction": 0.8,
                "bagging_freq": 5,
                "verbose": -1,
                "n_estimators": 100,
                "early_stopping_rounds": 10,
                "random_state": 42,
            }
        elif self.model_type == "xgboost":
            return {
                "objective": "binary:logistic",
                "eval_metric": "auc",
                "max_depth": 6,
                "learning_rate": 0.05,
                "subsample": 0.8,
                "colsample_bytree": 0.8,
                "n_estimators": 100,
                "early_stopping_rounds": 10,
                "random_state": 42,
                "verbosity": 0,
            }
        else:
            raise ValueError(f"不支持的模型类型: {self.model_type}")

    def fit(
        self,
        X: np.ndarray,
        y: np.ndarray,
        feature_names: list[str] | None = None,
        eval_set: tuple[np.ndarray, np.ndarray] | None = None,
    ) -> TrainingCurve:
        """训练模型。

        Args:
            X: 特征矩阵，形状为 (n_samples, n_features)
            y: 目标变量，形状为 (n_samples,)
            feature_names: 特征名称列表
            eval_set: 验证集元组 (X_val, y_val)

        Returns:
            TrainingCurve: 训练曲线数据
        """
        self.feature_names = feature_names or [f"feature_{i}" for i in range(X.shape[1])]

        if self.model_type == "lightgbm":
            return self._fit_lightgbm(X, y, eval_set)
        elif self.model_type == "xgboost":
            return self._fit_xgboost(X, y, eval_set)
        else:
            raise ValueError(f"不支持的模型类型: {self.model_type}")

    def _fit_lightgbm(
        self,
        X: np.ndarray,
        y: np.ndarray,
        eval_set: tuple[np.ndarray, np.ndarray] | None = None,
    ) -> TrainingCurve:
        """训练 LightGBM 模型。"""
        import lightgbm as lgb

        # 创建数据集
        train_data = lgb.Dataset(X, label=y, feature_name=self.feature_names)

        callbacks = []
        eval_result: dict[str, list[float]] = {}

        if eval_set is not None:
            X_val, y_val = eval_set
            valid_data = lgb.Dataset(X_val, label=y_val, reference=train_data)
            callbacks.append(lgb.record_evaluation(eval_result))
            callbacks.append(lgb.early_stopping(int(self.params.get("early_stopping_rounds", 10))))
            fit_params = {"valid_sets": [valid_data]}
        else:
            fit_params = {}

        # 分离 early_stopping_rounds 参数
        params = {k: v for k, v in self.params.items() if k != "early_stopping_rounds"}

        # 训练模型
        self.model = lgb.train(
            params=params,
            train_set=train_data,
            callbacks=callbacks,
            **fit_params,
        )

        self._is_fitted = True

        # 构建训练曲线
        steps = list(range(1, len(eval_result.get("valid_0 auc", [])) + 1))
        train_scores = eval_result.get("training auc", [0.0] * len(steps))
        val_scores = eval_result.get("valid_0 auc", [0.0] * len(steps))

        if steps:
            best_idx = np.argmax(val_scores)
            best_step = steps[best_idx]
            best_score = val_scores[best_idx]
        else:
            best_step = self.model.num_trees()
            best_score = 0.0

        return TrainingCurve(
            steps=steps if steps else [best_step],
            train_scores=train_scores if train_scores else [0.0] * len(steps),
            validation_scores=val_scores if val_scores else [0.0] * len(steps),
            best_step=best_step,
            best_score=best_score,
        )

    def _fit_xgboost(
        self,
        X: np.ndarray,
        y: np.ndarray,
        eval_set: tuple[np.ndarray, np.ndarray] | None = None,
    ) -> TrainingCurve:
        """训练 XGBoost 模型。"""
        import xgboost as xgb

        # 分离 early_stopping_rounds 参数
        params = {k: v for k, v in self.params.items() if k != "early_stopping_rounds"}
        early_stopping_rounds = int(self.params.get("early_stopping_rounds", 10))

        # 创建模型
        self.model = xgb.XGBClassifier(**params)

        # 训练参数
        fit_params: dict[str, Any] = {}
        if eval_set is not None:
            X_val, y_val = eval_set
            fit_params["eval_set"] = [(X_val, y_val)]
            fit_params["verbose"] = False

        # 训练模型
        self.model.fit(
            X,
            y,
            **fit_params,
        )

        self._is_fitted = True

        # 构建训练曲线
        eval_result = self.model.evals_result() if hasattr(self.model, "evals_result") else {}
        if eval_result and "validation_0" in eval_result:
            auc_key = next((k for k in eval_result["validation_0"] if "auc" in k.lower()), None)
            if auc_key:
                val_scores = eval_result["validation_0"][auc_key]
                train_scores = eval_result.get("validation_0", {}).get(auc_key, val_scores)
                steps = list(range(1, len(val_scores) + 1))
                best_idx = np.argmax(val_scores)
                best_step = steps[best_idx]
                best_score = val_scores[best_idx]
            else:
                steps = [self.model.n_estimators]
                train_scores = [0.0]
                val_scores = [0.0]
                best_step = self.model.n_estimators
                best_score = 0.0
        else:
            steps = [self.model.n_estimators]
            train_scores = [0.0]
            val_scores = [0.0]
            best_step = self.model.n_estimators
            best_score = 0.0

        return TrainingCurve(
            steps=steps,
            train_scores=train_scores if isinstance(train_scores, list) else list(train_scores),
            validation_scores=val_scores,
            best_step=best_step,
            best_score=best_score,
        )

    def predict(self, X: np.ndarray) -> np.ndarray:
        """预测类别。

        Args:
            X: 特征矩阵，形状为 (n_samples, n_features)

        Returns:
            预测类别数组
        """
        if not self._is_fitted:
            raise RuntimeError("模型尚未训练，请先调用 fit() 方法")

        if self.model_type == "lightgbm":
            # LightGBM 返回概率，需要转换
            proba = self.model.predict(X)
            return (proba >= 0.5).astype(int)
        else:
            return self.model.predict(X)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """预测概率。

        Args:
            X: 特征矩阵，形状为 (n_samples, n_features)

        Returns:
            预测概率数组，形状为 (n_samples, 2)
        """
        if not self._is_fitted:
            raise RuntimeError("模型尚未训练，请先调用 fit() 方法")

        if self.model_type == "lightgbm":
            # LightGBM 直接返回正类概率
            positive_proba = self.model.predict(X)
            negative_proba = 1 - positive_proba
            return np.column_stack([negative_proba, positive_proba])
        else:
            return self.model.predict_proba(X)

    def get_feature_importance(self, importance_type: str = "gain") -> FeatureImportance:
        """获取特征重要性。

        Args:
            importance_type: 重要性类型，支持 "gain", "split"

        Returns:
            FeatureImportance: 特征重要性数据
        """
        if not self._is_fitted:
            raise RuntimeError("模型尚未训练，请先调用 fit() 方法")

        if self.model_type == "lightgbm":
            importance_dict = dict(zip(
                self.feature_names,
                self.model.feature_importance(importance_type=importance_type),
            ))
        else:
            importance_dict = self.model.get_booster().get_score(importance_type=importance_type)
            # XGBoost 可能返回部分特征，补全
            for name in self.feature_names:
                if name not in importance_dict:
                    importance_dict[name] = 0.0

        importances = [importance_dict.get(name, 0.0) for name in self.feature_names]

        return FeatureImportance(
            feature_names=self.feature_names,
            importances=importances,
            importance_type=importance_type,
        )

    def get_feature_contributions(
        self,
        X: np.ndarray,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """获取每个样本的特征贡献。

        使用特征值 × 特征重要性作为贡献度的近似估计。

        Args:
            X: 特征矩阵，形状为 (n_samples, n_features)
            top_k: 返回贡献最大的前 K 个特征

        Returns:
            每个样本的特征贡献列表，每个元素为 [{"feature": str, "value": float, "contribution": float}, ...]
        """
        if not self._is_fitted:
            raise RuntimeError("模型尚未训练，请先调用 fit() 方法")

        # 获取全局特征重要性
        importance = self.get_feature_importance(importance_type="gain")
        importance_dict = dict(zip(importance.feature_names, importance.importances))

        # 归一化重要性
        total_importance = sum(importance.importances) or 1.0
        normalized_importance = {
            name: imp / total_importance
            for name, imp in importance_dict.items()
        }

        results = []
        for i in range(X.shape[0]):
            sample = X[i]
            contributions = []

            for j, name in enumerate(self.feature_names):
                value = float(sample[j])
                contrib = value * normalized_importance.get(name, 0.0)
                contributions.append({
                    "feature": name,
                    "value": value,
                    "contribution": contrib,
                })

            # 按贡献绝对值排序，取 top_k
            contributions.sort(key=lambda x: abs(x["contribution"]), reverse=True)
            results.append(contributions[:top_k])

        return results

    def save(self, path: Path) -> None:
        """保存模型到文件。

        Args:
            path: 模型保存路径
        """
        if not self._is_fitted:
            raise RuntimeError("模型尚未训练，无法保存")

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        # 保存模型和元数据
        model_data = {
            "model_type": self.model_type,
            "params": self.params,
            "feature_names": self.feature_names,
            "is_fitted": self._is_fitted,
        }

        # 保存元数据
        meta_path = path.with_suffix(".meta.json")
        meta_path.write_text(json.dumps(model_data, ensure_ascii=False, indent=2), encoding="utf-8")

        # 保存模型文件
        if self.model_type == "lightgbm":
            self.model.save_model(str(path.with_suffix(".txt")))
        else:
            self.model.save_model(str(path.with_suffix(".json")))

        # 保存 pickle 作为备份
        pickle_path = path.with_suffix(".pkl")
        with open(pickle_path, "wb") as f:
            pickle.dump(self.model, f)

    @classmethod
    def load(cls, path: Path) -> "MLModel":
        """从文件加载模型。

        Args:
            path: 模型文件路径

        Returns:
            加载的 MLModel 实例
        """
        path = Path(path)

        # 加载元数据
        meta_path = path.with_suffix(".meta.json")
        if meta_path.exists():
            model_data = json.loads(meta_path.read_text(encoding="utf-8"))
        else:
            # 兼容旧格式
            model_data = {
                "model_type": "lightgbm",
                "params": {},
                "feature_names": [],
                "is_fitted": True,
            }

        instance = cls(
            model_type=model_data.get("model_type", "lightgbm"),
            params=model_data.get("params"),
        )
        instance.feature_names = model_data.get("feature_names", [])
        instance._is_fitted = model_data.get("is_fitted", True)

        # 尝试加载模型文件
        if instance.model_type == "lightgbm":
            txt_path = path.with_suffix(".txt")
            if txt_path.exists():
                import lightgbm as lgb
                instance.model = lgb.Booster(model_file=str(txt_path))
            else:
                # 回退到 pickle
                pkl_path = path.with_suffix(".pkl")
                if pkl_path.exists():
                    with open(pkl_path, "rb") as f:
                        instance.model = pickle.load(f)
        else:
            json_path = path.with_suffix(".json")
            if json_path.exists():
                import xgboost as xgb
                instance.model = xgb.XGBClassifier()
                instance.model.load_model(str(json_path))
            else:
                pkl_path = path.with_suffix(".pkl")
                if pkl_path.exists():
                    with open(pkl_path, "rb") as f:
                        instance.model = pickle.load(f)

        return instance

    @property
    def is_fitted(self) -> bool:
        """返回模型是否已训练。"""
        return self._is_fitted

    @property
    def n_features(self) -> int:
        """返回特征数量。"""
        return len(self.feature_names)
