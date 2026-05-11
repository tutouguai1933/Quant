"""ML 模型推理器。

提供模型推理和信号生成功能。
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import numpy as np

from services.worker.ml.model import MLModel


@dataclass(slots=True)
class PredictionResult:
    """推理结果数据类。"""

    symbol: str
    score: float
    signal: str
    confidence: float
    feature_values: dict[str, float]
    model_version: str


class ModelPredictor:
    """模型推理器。

    负责加载模型、准备特征、执行推理、生成信号。
    """

    def __init__(
        self,
        model_path: Path | None = None,
        confidence_floor: float = 0.55,
    ) -> None:
        """初始化推理器。

        Args:
            model_path: 模型文件路径（基础路径，不带后缀）
            confidence_floor: 信号置信度阈值，大于此值为 long，小于 (1-threshold) 为 short
        """
        self._model: MLModel | None = None
        self._model_path = model_path
        self._confidence_floor = confidence_floor
        self._model_version = ""

        if model_path is not None:
            # 检查是否存在模型文件（.txt 或 .meta.json 或 .pkl）
            path = Path(model_path)
            txt_path = Path(str(path) + ".txt")
            meta_path = Path(str(path) + ".meta.json")
            pkl_path = Path(str(path) + ".pkl")
            if txt_path.exists() or meta_path.exists() or pkl_path.exists():
                self._load_model(path)

    def _load_model(self, path: Path) -> None:
        """加载模型。"""
        self._model = MLModel.load(path)
        # 从元数据中获取模型版本
        meta_path = path.with_suffix(".meta.json")
        if meta_path.exists():
            import json
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            self._model_version = meta.get("model_version", "")
        else:
            self._model_version = path.stem

    def load_model(self, path: Path) -> None:
        """加载模型文件。

        Args:
            path: 模型文件路径
        """
        self._load_model(path)

    def predict(
        self,
        feature_row: dict[str, Any],
        feature_columns: tuple[str, ...],
        symbol: str = "",
    ) -> PredictionResult:
        """执行推理。

        Args:
            feature_row: 特征数据行
            feature_columns: 特征列名
            symbol: 币种符号

        Returns:
            PredictionResult: 推理结果
        """
        if self._model is None:
            raise RuntimeError("模型尚未加载，请先调用 load_model() 方法")

        # 准备特征向量
        X = self._prepare_features(feature_row, feature_columns)

        # 获取预测概率
        proba = self._model.predict_proba(X.reshape(1, -1))[0]
        score = float(proba[1])  # 正类概率

        # 计算置信度
        confidence = max(score, 1 - score)

        # 生成信号
        signal = self._classify_signal(score)

        # 记录特征值
        feature_values = {
            col: self._to_float(feature_row.get(col))
            for col in feature_columns
        }

        return PredictionResult(
            symbol=symbol,
            score=score,
            signal=signal,
            confidence=confidence,
            feature_values=feature_values,
            model_version=self._model_version,
        )

    def predict_batch(
        self,
        feature_rows: list[dict[str, Any]],
        feature_columns: tuple[str, ...],
        symbols: list[str] | None = None,
    ) -> list[PredictionResult]:
        """批量推理 - 使用向量化提高性能。

        Args:
            feature_rows: 特征数据行列表
            feature_columns: 特征列名
            symbols: 币种符号列表

        Returns:
            推理结果列表
        """
        if self._model is None:
            raise RuntimeError("模型尚未加载，请先调用 load_model() 方法")

        if not feature_rows:
            return []

        if symbols is None:
            symbols = [""] * len(feature_rows)

        # 准备特征矩阵 - 向量化
        X = np.array([
            [self._to_float(row.get(col)) for col in feature_columns]
            for row in feature_rows
        ], dtype=np.float64)

        # 批量预测
        probas = self._model.predict_proba(X)[:, 1]  # 正类概率

        # 生成结果
        results = []
        for i, (row, proba) in enumerate(zip(feature_rows, probas)):
            score = float(proba)
            confidence = max(score, 1 - score)
            signal = self._classify_signal(score)

            feature_values = {
                col: self._to_float(row.get(col))
                for col in feature_columns
            }

            results.append(PredictionResult(
                symbol=symbols[i] if i < len(symbols) else "",
                score=score,
                signal=signal,
                confidence=confidence,
                feature_values=feature_values,
                model_version=self._model_version,
            ))

        return results

    def _prepare_features(
        self,
        feature_row: dict[str, Any],
        feature_columns: tuple[str, ...],
    ) -> np.ndarray:
        """准备特征向量。"""
        features = []
        for col in feature_columns:
            value = feature_row.get(col)
            features.append(self._to_float(value))
        return np.array(features, dtype=np.float64)

    def _classify_signal(self, score: float) -> str:
        """根据分数生成信号。"""
        if score >= self._confidence_floor:
            return "long"
        if score <= (1 - self._confidence_floor):
            return "short"
        return "flat"

    @property
    def model_version(self) -> str:
        """返回当前加载的模型版本。"""
        return self._model_version

    @property
    def is_loaded(self) -> bool:
        """返回模型是否已加载。"""
        return self._model is not None

    @staticmethod
    def _to_float(value: Any) -> float:
        """将任意值转换为 float。"""
        if value is None:
            return 0.0
        try:
            return float(Decimal(str(value)))
        except (TypeError, ValueError, InvalidOperation):
            return 0.0
