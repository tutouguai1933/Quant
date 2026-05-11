"""Optuna 超参数优化器。

提供自动超参数优化功能，支持 LightGBM 和 XGBoost 模型。
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import numpy as np

from services.worker.ml.model import MLModel
from services.worker.ml.trainer import ModelTrainer


@dataclass(slots=True)
class OptimizationResult:
    """优化结果数据类。"""

    study_name: str
    best_params: dict[str, Any]
    best_value: float
    n_trials: int
    duration_seconds: float
    trials: list[dict[str, Any]]
    param_importance: dict[str, float]
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(slots=True)
class OptimizationProgress:
    """优化进度数据类。"""

    status: str  # "idle", "running", "completed", "failed"
    current_trial: int
    total_trials: int
    best_value: float
    best_params: dict[str, Any] | None
    started_at: datetime | None
    elapsed_seconds: float
    message: str


class HyperparameterOptimizer:
    """超参数优化器。

    使用 Optuna 进行超参数自动搜索。
    """

    def __init__(
        self,
        model_type: str = "lightgbm",
        n_trials: int = 50,
        timeout_seconds: int | None = None,
        storage_path: Path | None = None,
    ) -> None:
        """初始化优化器。

        Args:
            model_type: 模型类型，支持 "lightgbm" 或 "xgboost"
            n_trials: 优化轮数
            timeout_seconds: 超时时间（秒）
            storage_path: Optuna 存储路径
        """
        self._model_type = model_type
        self._n_trials = n_trials
        self._timeout_seconds = timeout_seconds
        self._storage_path = storage_path

        self._study: Any = None
        self._is_running = False
        self._progress = OptimizationProgress(
            status="idle",
            current_trial=0,
            total_trials=n_trials,
            best_value=0.0,
            best_params=None,
            started_at=None,
            elapsed_seconds=0.0,
            message="",
        )
        self._lock = threading.Lock()

    def optimize(
        self,
        training_rows: list[dict[str, Any]],
        validation_rows: list[dict[str, Any]],
        feature_columns: tuple[str, ...],
        label_column: str = "future_return_pct",
    ) -> OptimizationResult:
        """执行超参数优化。

        Args:
            training_rows: 训练数据
            validation_rows: 验证数据
            feature_columns: 特征列名
            label_column: 标签列名

        Returns:
            OptimizationResult: 优化结果
        """
        import optuna
        from optuna.samplers import TPESampler

        started_at = datetime.now(timezone.utc)

        with self._lock:
            self._is_running = True
            self._progress = OptimizationProgress(
                status="running",
                current_trial=0,
                total_trials=self._n_trials,
                best_value=0.0,
                best_params=None,
                started_at=started_at,
                elapsed_seconds=0.0,
                message="开始超参数优化",
            )

        study_name = f"{self._model_type}-hyperopt-{started_at.strftime('%Y%m%d%H%M%S')}"

        # 创建存储
        storage = None
        if self._storage_path:
            self._storage_path.parent.mkdir(parents=True, exist_ok=True)
            storage = f"sqlite:///{self._storage_path}"

        # 创建 study
        sampler = TPESampler(seed=42)
        self._study = optuna.create_study(
            study_name=study_name,
            direction="maximize",  # 最大化 AUC
            sampler=sampler,
            storage=storage,
        )

        def objective(trial: optuna.Trial) -> float:
            """优化目标函数。"""
            # 采样超参数
            params = self._sample_params(trial)

            # 训练模型
            trainer = ModelTrainer(
                model_type=self._model_type,
                model_params=params,
                label_column=label_column,
            )

            try:
                result = trainer.train(
                    training_rows=training_rows,
                    validation_rows=validation_rows,
                    feature_columns=feature_columns,
                )

                # 更新进度
                with self._lock:
                    self._progress.current_trial = trial.number + 1
                    if result.metrics.get("val_auc", 0) > self._progress.best_value:
                        self._progress.best_value = result.metrics.get("val_auc", 0)
                        self._progress.best_params = params

                return result.metrics.get("val_auc", 0.0)
            except Exception:
                return 0.0

        # 运行优化
        try:
            self._study.optimize(
                objective,
                n_trials=self._n_trials,
                timeout=self._timeout_seconds,
                show_progress_bar=False,
            )
        except Exception as e:
            with self._lock:
                self._progress.status = "failed"
                self._progress.message = str(e)
            raise
        finally:
            self._is_running = False

        finished_at = datetime.now(timezone.utc)
        duration_seconds = (finished_at - started_at).total_seconds()

        # 收集结果
        trials = [
            {
                "number": trial.number,
                "value": trial.value,
                "params": dict(trial.params),
                "state": trial.state.name,
            }
            for trial in self._study.trials
        ]

        # 计算参数重要性
        param_importance = {}
        try:
            if len(self._study.trials) > 10:
                import optuna.importance
                importance = optuna.importance.get_param_importances(self._study)
                param_importance = {k: float(v) for k, v in importance.items()}
        except Exception:
            pass

        with self._lock:
            self._progress.status = "completed"
            self._progress.message = "优化完成"

        return OptimizationResult(
            study_name=study_name,
            best_params=dict(self._study.best_params),
            best_value=float(self._study.best_value),
            n_trials=len(self._study.trials),
            duration_seconds=duration_seconds,
            trials=trials,
            param_importance=param_importance,
        )

    def get_progress(self) -> OptimizationProgress:
        """获取优化进度。"""
        with self._lock:
            progress = OptimizationProgress(
                status=self._progress.status,
                current_trial=self._progress.current_trial,
                total_trials=self._progress.total_trials,
                best_value=self._progress.best_value,
                best_params=dict(self._progress.best_params) if self._progress.best_params else None,
                started_at=self._progress.started_at,
                elapsed_seconds=self._progress.elapsed_seconds,
                message=self._progress.message,
            )
            if self._progress.started_at:
                progress.elapsed_seconds = (datetime.now(timezone.utc) - self._progress.started_at).total_seconds()
            return progress

    def stop(self) -> None:
        """停止优化。"""
        self._is_running = False

    def _sample_params(self, trial: Any) -> dict[str, Any]:
        """采样超参数。"""
        if self._model_type == "lightgbm":
            return {
                "objective": "binary",
                "metric": "auc",
                "boosting_type": trial.suggest_categorical("boosting_type", ["gbdt", "dart"]),
                "num_leaves": trial.suggest_int("num_leaves", 15, 63),
                "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.2, log=True),
                "feature_fraction": trial.suggest_float("feature_fraction", 0.6, 1.0),
                "bagging_fraction": trial.suggest_float("bagging_fraction", 0.6, 1.0),
                "bagging_freq": trial.suggest_int("bagging_freq", 1, 10),
                "min_child_samples": trial.suggest_int("min_child_samples", 5, 50),
                "reg_alpha": trial.suggest_float("reg_alpha", 1e-8, 10.0, log=True),
                "reg_lambda": trial.suggest_float("reg_lambda", 1e-8, 10.0, log=True),
                "n_estimators": trial.suggest_int("n_estimators", 50, 300),
                "verbose": -1,
                "random_state": 42,
            }
        elif self._model_type == "xgboost":
            return {
                "objective": "binary:logistic",
                "eval_metric": "auc",
                "max_depth": trial.suggest_int("max_depth", 3, 10),
                "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.2, log=True),
                "subsample": trial.suggest_float("subsample", 0.6, 1.0),
                "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 1.0),
                "min_child_weight": trial.suggest_int("min_child_weight", 1, 10),
                "reg_alpha": trial.suggest_float("reg_alpha", 1e-8, 10.0, log=True),
                "reg_lambda": trial.suggest_float("reg_lambda", 1e-8, 10.0, log=True),
                "n_estimators": trial.suggest_int("n_estimators", 50, 300),
                "random_state": 42,
                "verbosity": 0,
            }
        else:
            return {}

    @property
    def is_running(self) -> bool:
        """返回是否正在优化。"""
        return self._is_running


# 全局优化器实例管理
_active_optimizers: dict[str, HyperparameterOptimizer] = {}
_optimizer_results: dict[str, OptimizationResult] = {}


def start_optimization(
    optimizer_id: str,
    training_rows: list[dict[str, Any]],
    validation_rows: list[dict[str, Any]],
    feature_columns: tuple[str, ...],
    model_type: str = "lightgbm",
    n_trials: int = 50,
    timeout_seconds: int | None = None,
) -> None:
    """启动超参数优化（后台运行）。"""
    import threading

    optimizer = HyperparameterOptimizer(
        model_type=model_type,
        n_trials=n_trials,
        timeout_seconds=timeout_seconds,
    )
    _active_optimizers[optimizer_id] = optimizer

    def run():
        try:
            result = optimizer.optimize(
                training_rows=training_rows,
                validation_rows=validation_rows,
                feature_columns=feature_columns,
            )
            _optimizer_results[optimizer_id] = result
        except Exception:
            pass
        finally:
            _active_optimizers.pop(optimizer_id, None)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()


def get_optimization_progress(optimizer_id: str) -> OptimizationProgress | None:
    """获取优化进度。"""
    optimizer = _active_optimizers.get(optimizer_id)
    if optimizer:
        return optimizer.get_progress()

    result = _optimizer_results.get(optimizer_id)
    if result:
        return OptimizationProgress(
            status="completed",
            current_trial=result.n_trials,
            total_trials=result.n_trials,
            best_value=result.best_value,
            best_params=result.best_params,
            started_at=None,
            elapsed_seconds=result.duration_seconds,
            message="优化完成",
        )

    return None


def get_optimization_result(optimizer_id: str) -> OptimizationResult | None:
    """获取优化结果。"""
    return _optimizer_results.get(optimizer_id)


def stop_optimization(optimizer_id: str) -> bool:
    """停止优化。"""
    optimizer = _active_optimizers.get(optimizer_id)
    if optimizer:
        optimizer.stop()
        return True
    return False
