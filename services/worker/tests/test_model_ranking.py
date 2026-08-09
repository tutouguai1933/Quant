"""排序学习模式（lambdarank）单元测试。"""

import numpy as np
import pytest

from services.worker.ml.model import MLModel


def test_ranking_model_trains_and_predicts() -> None:
    """LGBMRanker 可训练并输出分数。"""
    model = MLModel(model_type="lightgbm", params={"objective": "lambdarank", "metric": "ndcg", "label_gain": [0, 1, 3]})
    assert model.is_ranking
    # 3 组样本（每组 4 条）
    X = np.random.RandomState(42).rand(12, 5)
    y = np.array([0, 1, 2, 1, 0, 2, 1, 1, 1, 2, 0, 1], dtype=np.int32)
    groups = np.array([4, 4, 4], dtype=np.int32)
    model.fit(X, y, eval_set=(X, y), groups=groups, eval_groups=groups)
    preds = model.predict(X)
    assert preds.shape == (12,)
    assert np.isfinite(preds).all()


def test_ranking_predict_proba_returns_scores() -> None:
    """排序模型 predict_proba 返回原始分数（可排序）。"""
    model = MLModel(model_type="lightgbm", params={"objective": "lambdarank", "metric": "ndcg"})
    X = np.random.RandomState(7).rand(8, 4)
    y = np.array([0, 1, 2, 0, 1, 1, 0, 2], dtype=np.int32)
    model.fit(X, y, groups=np.array([4, 4], dtype=np.int32))
    proba = model.predict_proba(X)
    assert proba.shape == (8,)


def test_binary_model_rejects_groups() -> None:
    """binary 模式不接受 group 参数（防止误用）。"""
    model = MLModel(model_type="lightgbm", params={"objective": "binary"})
    X = np.random.RandomState(1).rand(6, 3)
    y = np.array([0, 1, 0, 1, 0, 1])
    with pytest.raises(ValueError, match="group"):
        model.fit(X, y, groups=np.array([3, 3], dtype=np.int32))
