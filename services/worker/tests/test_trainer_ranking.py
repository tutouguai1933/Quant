"""排序训练器（ModelTrainer ranking 模式）测试。"""

import numpy as np

from services.worker.ml.trainer import ModelTrainer


def _make_rows(n: int, start_ts: int = 0) -> list[dict]:
    """构造 n 行样本：每 4 行一个时间点（4 个币）。"""

    return [
        {
            "symbol": f"S{i % 4}",
            "generated_at": start_ts + i // 4,
            "f1": float(i % 7),
            "f2": float((i * 3) % 11),
            "future_return_pct": str((i % 5) - 2),
        }
        for i in range(n)
    ]


def test_ranking_trainer_builds_groups_and_metrics() -> None:
    """排序训练：输出排序指标（ndcg/top5），且 AUC 正常。"""
    trainer = ModelTrainer(
        model_type="lightgbm",
        model_params={"objective": "lambdarank", "metric": "ndcg", "label_gain": [0, 1, 2]},
        label_column="future_return_pct",
    )
    rows = _make_rows(48)  # 12 个时间点 × 4 币
    result = trainer.train(
        training_rows=rows[:36],
        validation_rows=rows[36:],
        feature_columns=("f1", "f2"),
    )
    assert "val_auc" in result.metrics
    assert "val_ndcg_at_5" in result.metrics
    assert "val_top5_hit_rate" in result.metrics
    assert result.metrics["val_auc"] >= 0.0
    assert 0.0 <= result.metrics["val_ndcg_at_5"] <= 1.0
    assert 0.0 <= result.metrics["val_top5_hit_rate"] <= 1.0


def test_binary_trainer_does_not_output_ranking_metrics() -> None:
    """二分类训练不输出排序指标。"""
    trainer = ModelTrainer(
        model_type="lightgbm",
        model_params={"objective": "binary"},
        label_column="future_return_pct",
    )
    result = trainer.train(
        training_rows=_make_rows(24),
        validation_rows=_make_rows(12, start_ts=1000),
        feature_columns=("f1", "f2"),
    )
    assert "val_ndcg_at_5" not in result.metrics
    assert "val_top5_hit_rate" not in result.metrics
    assert "val_auc" in result.metrics


def test_build_groups_groups_by_timestamp() -> None:
    """_build_groups 按 generated_at 分组，组数和每组行数正确。"""
    trainer = ModelTrainer(model_type="lightgbm", model_params={"objective": "binary"}, label_column="future_return_pct")
    rows = [
        {"generated_at": 100, "f1": 1},
        {"generated_at": 100, "f1": 2},
        {"generated_at": 100, "f1": 3},
        {"generated_at": 200, "f1": 4},
        {"generated_at": 200, "f1": 5},
    ]
    groups = trainer._build_groups(rows)
    assert groups.tolist() == [3, 2]
