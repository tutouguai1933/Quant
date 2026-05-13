"""ML 模型模块测试。"""

from __future__ import annotations

import math
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import pytest

from services.worker.ml.model import MLModel, TrainingCurve, FeatureImportance
from services.worker.ml.trainer import ModelTrainer, TrainingResult
from services.worker.ml.predictor import ModelPredictor, PredictionResult
from services.worker.ml.evaluator import ModelEvaluator, EvaluationResult


class TestMLModel:
    """测试 MLModel 类。"""

    def test_default_params_lightgbm(self) -> None:
        """测试 LightGBM 默认参数。"""
        model = MLModel(model_type="lightgbm")
        assert model.model_type == "lightgbm"
        assert "objective" in model.params
        assert model.params["objective"] == "binary"

    def test_default_params_xgboost(self) -> None:
        """测试 XGBoost 默认参数。"""
        model = MLModel(model_type="xgboost")
        assert model.model_type == "xgboost"
        assert "objective" in model.params

    def test_fit_and_predict_lightgbm(self) -> None:
        """测试 LightGBM 训练和预测。"""
        pytest.importorskip("lightgbm")

        model = MLModel(model_type="lightgbm", params={
            "n_estimators": 10,
            "verbose": -1,
        })

        # 生成测试数据
        np.random.seed(42)
        X = np.random.randn(100, 5)
        y = (X[:, 0] + X[:, 1] > 0).astype(int)

        feature_names = [f"feature_{i}" for i in range(5)]

        # 训练
        training_curve = model.fit(X, y, feature_names=feature_names)

        assert model.is_fitted
        assert len(training_curve.steps) > 0
        assert len(model.feature_names) == 5

        # 预测
        predictions = model.predict(X[:5])
        assert len(predictions) == 5

        # 概率预测
        proba = model.predict_proba(X[:5])
        assert proba.shape == (5, 2)

    def test_get_feature_importance(self) -> None:
        """测试特征重要性。"""
        pytest.importorskip("lightgbm")

        model = MLModel(model_type="lightgbm", params={
            "n_estimators": 10,
            "verbose": -1,
        })

        np.random.seed(42)
        X = np.random.randn(100, 5)
        y = (X[:, 0] > 0).astype(int)

        model.fit(X, y, feature_names=["a", "b", "c", "d", "e"])

        importance = model.get_feature_importance()
        assert isinstance(importance, FeatureImportance)
        assert len(importance.feature_names) == 5
        assert len(importance.importances) == 5

    def test_get_feature_contributions(self) -> None:
        """测试特征贡献计算。"""
        pytest.importorskip("lightgbm")

        model = MLModel(model_type="lightgbm", params={
            "n_estimators": 10,
            "verbose": -1,
        })

        np.random.seed(42)
        X = np.random.randn(100, 5)
        y = (X[:, 0] > 0).astype(int)

        model.fit(X, y, feature_names=["a", "b", "c", "d", "e"])

        # 获取单个样本的特征贡献
        contributions = model.get_feature_contributions(X[:3], top_k=3)

        assert len(contributions) == 3
        for sample_contrib in contributions:
            assert len(sample_contrib) == 3  # top_k=3
            for item in sample_contrib:
                assert "feature" in item
                assert "value" in item
                assert "contribution" in item

    def test_save_and_load(self) -> None:
        """测试模型保存和加载。"""
        pytest.importorskip("lightgbm")

        with TemporaryDirectory() as tmpdir:
            model_path = Path(tmpdir) / "test_model"

            # 训练模型
            model = MLModel(model_type="lightgbm", params={
                "n_estimators": 10,
                "verbose": -1,
            })
            np.random.seed(42)
            X = np.random.randn(100, 5)
            y = (X[:, 0] > 0).astype(int)
            model.fit(X, y, feature_names=["a", "b", "c", "d", "e"])

            # 保存
            model.save(model_path)

            # 加载
            loaded = MLModel.load(model_path)
            assert loaded.is_fitted
            assert loaded.feature_names == ["a", "b", "c", "d", "e"]


class TestModelTrainer:
    """测试 ModelTrainer 类。"""

    def test_train(self) -> None:
        """测试模型训练。"""
        pytest.importorskip("lightgbm")

        trainer = ModelTrainer(
            model_type="lightgbm",
            model_params={"n_estimators": 10, "verbose": -1},
        )

        # 生成测试数据
        training_rows = [
            {"f1": i * 0.1, "f2": i * 0.05, "future_return_pct": 1.0 if i % 2 == 0 else -0.5}
            for i in range(100)
        ]
        validation_rows = training_rows[-20:]

        result = trainer.train(
            training_rows=training_rows,
            validation_rows=validation_rows,
            feature_columns=("f1", "f2"),
        )

        assert isinstance(result, TrainingResult)
        assert result.model.is_fitted
        assert len(result.training_curve.steps) > 0
        assert len(result.feature_importance.feature_names) == 2


class TestModelPredictor:
    """测试 ModelPredictor 类。"""

    def test_predict(self) -> None:
        """测试模型推理。"""
        pytest.importorskip("lightgbm")

        # 先训练模型
        trainer = ModelTrainer(
            model_type="lightgbm",
            model_params={"n_estimators": 10, "verbose": -1},
        )
        training_rows = [
            {"f1": i * 0.1, "f2": i * 0.05, "future_return_pct": 1.0 if i % 2 == 0 else -0.5}
            for i in range(100)
        ]
        result = trainer.train(
            training_rows=training_rows,
            validation_rows=[],
            feature_columns=("f1", "f2"),
        )

        with TemporaryDirectory() as tmpdir:
            # 使用不带后缀的基础路径，save() 会自动添加 .txt/.meta.json 等
            model_base_path = Path(tmpdir) / "test_model"
            result.model.save(model_base_path)

            # 确保文件存在
            txt_path = Path(str(model_base_path) + ".txt")
            meta_path = Path(str(model_base_path) + ".meta.json")
            assert txt_path.exists() or (Path(str(model_base_path) + ".pkl")).exists()

            # 加载并预测 - 使用相同的基础路径
            predictor = ModelPredictor(model_path=model_base_path)
            assert predictor.is_loaded, f"模型应该已加载，检查文件: {txt_path}, {meta_path}"

            prediction = predictor.predict(
                feature_row={"f1": 0.5, "f2": 0.25},
                feature_columns=("f1", "f2"),
                symbol="TESTUSDT",
            )

            assert isinstance(prediction, PredictionResult)
            assert prediction.symbol == "TESTUSDT"
            assert 0.0 <= prediction.score <= 1.0
            assert prediction.signal in ("long", "short", "flat")

    def test_predict_with_contributions(self) -> None:
        """测试带特征贡献的推理。"""
        pytest.importorskip("lightgbm")

        trainer = ModelTrainer(
            model_type="lightgbm",
            model_params={"n_estimators": 10, "verbose": -1},
        )
        training_rows = [
            {"f1": i * 0.1, "f2": i * 0.05, "future_return_pct": 1.0 if i % 2 == 0 else -0.5}
            for i in range(100)
        ]
        result = trainer.train(
            training_rows=training_rows,
            validation_rows=[],
            feature_columns=("f1", "f2"),
        )

        with TemporaryDirectory() as tmpdir:
            model_base_path = Path(tmpdir) / "test_model"
            result.model.save(model_base_path)

            predictor = ModelPredictor(model_path=model_base_path)

            prediction = predictor.predict(
                feature_row={"f1": 0.5, "f2": 0.25},
                feature_columns=("f1", "f2"),
                symbol="TESTUSDT",
                include_contributions=True,
            )

            assert prediction.feature_contributions is not None
            assert len(prediction.feature_contributions) <= 2  # top_k=5, but only 2 features
            for item in prediction.feature_contributions:
                assert "feature" in item
                assert "value" in item
                assert "contribution" in item


class TestModelEvaluator:
    """测试 ModelEvaluator 类。"""

    def test_evaluate(self) -> None:
        """测试模型评估。"""
        pytest.importorskip("lightgbm")

        # 训练模型
        trainer = ModelTrainer(
            model_type="lightgbm",
            model_params={"n_estimators": 10, "verbose": -1},
        )
        training_rows = [
            {"f1": i * 0.1, "f2": i * 0.05, "future_return_pct": 1.0 if i % 2 == 0 else -0.5}
            for i in range(100)
        ]
        result = trainer.train(
            training_rows=training_rows,
            validation_rows=[],
            feature_columns=("f1", "f2"),
        )

        # 评估
        test_rows = [
            {"f1": i * 0.1, "f2": i * 0.05, "future_return_pct": 1.0 if i % 3 == 0 else -0.3}
            for i in range(50)
        ]

        evaluator = ModelEvaluator(k_values=(1, 3, 5))
        eval_result = evaluator.evaluate(
            model=result.model,
            test_rows=test_rows,
            feature_columns=("f1", "f2"),
        )

        assert isinstance(eval_result, EvaluationResult)
        assert eval_result.sample_count == 50
        assert isinstance(eval_result.ic, float)
        assert isinstance(eval_result.rank_ic, float)
        assert isinstance(eval_result.sharpe, float)
        assert len(eval_result.precision_at_k) == 3
