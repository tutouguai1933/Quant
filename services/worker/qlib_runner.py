"""Qlib 最小运行入口。

这个文件负责最小训练、最小推理和结果落盘，不让控制平面直接碰内部实现。
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from uuid import uuid4

from services.worker.qlib_backtest import run_backtest
from services.worker.qlib_config import QlibRuntimeConfig
from services.worker.qlib_features import FEATURE_COLUMNS, build_feature_rows
from services.worker.qlib_labels import LABEL_COLUMNS, build_label_rows
from services.worker.qlib_ranking import rank_candidates


@dataclass(slots=True)
class TrainingBundle:
    """训练阶段的中间结果。"""

    training_rows: list[dict[str, object]]
    validation_rows: list[dict[str, object]]
    backtest_rows: list[dict[str, object]]
    feature_columns: tuple[str, ...]
    label_columns: tuple[str, ...]


class QlibRunner:
    """最小研究层执行器。"""

    def __init__(self, *, config: QlibRuntimeConfig) -> None:
        self._config = config

    def train(self, dataset: dict[str, list[dict[str, object]]]) -> dict[str, object]:
        """执行一次最小训练。"""

        self._config.ensure_ready()
        self._ensure_runtime_directories()
        bundle = self._build_training_bundle(dataset)
        metrics = self._fit_model(bundle.training_rows)
        validation = self._build_validation_summary(bundle.validation_rows)
        backtest = run_backtest(rows=bundle.backtest_rows, holding_window="1-3d")
        run_id = self._new_run_id("train")
        generated_at = _utc_now()
        model_version = f"qlib-minimal-{generated_at.strftime('%Y%m%d%H%M%S%f')}"
        model_payload = {
            "model_version": model_version,
            "generated_at": generated_at.isoformat(),
            "feature_columns": list(bundle.feature_columns),
            "label_columns": list(bundle.label_columns),
            "metrics": metrics,
            "validation": validation,
            "backtest": backtest,
        }
        artifact_path = self._config.paths.artifacts_dir / f"{model_version}.json"
        self._write_json(artifact_path, model_payload)

        result = {
            "run_id": run_id,
            "status": "completed",
            "backend": self._config.backend,
            "qlib_available": self._config.qlib_available,
            "generated_at": generated_at.isoformat(),
            "model_version": model_version,
            "sample_count": len(bundle.training_rows),
            "feature_columns": list(bundle.feature_columns),
            "label_columns": list(bundle.label_columns),
            "metrics": metrics,
            "validation": validation,
            "backtest": backtest,
            "warnings": self._build_warnings(),
            "artifact_path": str(artifact_path),
        }
        self._write_run_record("training", run_id, result, self._config.paths.latest_training_path)
        return result

    def infer(self, dataset: dict[str, list[dict[str, object]]]) -> dict[str, object]:
        """执行一次最小推理。"""

        self._config.ensure_ready()
        self._ensure_runtime_directories()
        training_payload = self._read_json(self._config.paths.latest_training_path)
        if not training_payload:
            raise RuntimeError("研究层还没有可用训练结果，不能直接推理")

        signals: list[dict[str, object]] = []
        candidates: list[dict[str, object]] = []
        for symbol, candles in dataset.items():
            features = build_feature_rows(symbol, candles)
            if not features:
                continue
            latest = features[-1]
            score = self._score_signal(latest, dict(training_payload.get("metrics") or {}))
            confidence = max(score, 1 - score)
            signal = _classify_signal(score)
            target_weight = _target_weight(signal, score)
            signals.append(
                {
                    "symbol": symbol,
                    "signal": signal,
                    "side": signal,
                    "score": _format_float(score),
                    "confidence": _format_float(confidence),
                    "target_weight": _format_float(target_weight),
                    "explanation": self._build_explanation(latest),
                    "model_version": str(training_payload.get("model_version", "")),
                    "source": "qlib",
                    "generated_at": _utc_now().isoformat(),
                }
            )
            candidates.append(
                {
                    "symbol": symbol,
                    "strategy_template": "trend_breakout_timing",
                    "score": _format_float(score),
                    "backtest": self._build_candidate_backtest(symbol=symbol, candles=candles),
                }
            )

        result = {
            "run_id": self._new_run_id("infer"),
            "status": "completed",
            "backend": self._config.backend,
            "qlib_available": self._config.qlib_available,
            "generated_at": _utc_now().isoformat(),
            "model_version": str(training_payload.get("model_version", "")),
            "signals": signals,
            "summary": {
                "signal_count": len(signals),
                "long_count": sum(1 for item in signals if item["signal"] == "long"),
                "flat_count": sum(1 for item in signals if item["signal"] == "flat"),
                "short_count": sum(1 for item in signals if item["signal"] == "short"),
            },
            "candidates": rank_candidates(candidates),
            "warnings": self._build_warnings(),
        }
        self._write_run_record("inference", result["run_id"], result, self._config.paths.latest_inference_path)
        return result

    def _build_training_bundle(self, dataset: dict[str, list[dict[str, object]]]) -> TrainingBundle:
        """把输入数据整理成训练样本。"""

        training_rows: list[dict[str, object]] = []
        validation_rows: list[dict[str, object]] = []
        backtest_rows: list[dict[str, object]] = []
        for symbol, candles in dataset.items():
            merged_rows = self._build_symbol_rows(symbol, candles)
            symbol_training_rows, symbol_validation_rows, symbol_backtest_rows = self._split_rows(merged_rows)
            training_rows.extend(symbol_training_rows)
            validation_rows.extend(symbol_validation_rows)
            backtest_rows.extend(symbol_backtest_rows)
        if not training_rows:
            raise RuntimeError("研究层没有拿到可训练样本")
        if not validation_rows or not backtest_rows:
            raise RuntimeError("研究层样本不足，无法生成完整验证和回测结果")
        return TrainingBundle(
            training_rows=training_rows,
            validation_rows=validation_rows,
            backtest_rows=backtest_rows,
            feature_columns=FEATURE_COLUMNS,
            label_columns=LABEL_COLUMNS,
        )

    def _build_symbol_rows(self, symbol: str, candles: list[dict[str, object]]) -> list[dict[str, object]]:
        """把单个标的整理成可训练样本。"""

        feature_rows = build_feature_rows(symbol, candles)
        label_rows = build_label_rows(symbol, candles)
        label_rows_by_time = {
            int(label_row["generated_at"]): label_row
            for label_row in label_rows
            if label_row.get("generated_at") is not None
        }
        merged_rows: list[dict[str, object]] = []
        for feature_row in feature_rows:
            label_row = label_rows_by_time.get(int(feature_row["generated_at"]))
            if label_row is None:
                continue
            if not label_row["is_trainable"]:
                continue
            merged_rows.append({**feature_row, **label_row})
        return merged_rows

    def _build_candidate_backtest(self, *, symbol: str, candles: list[dict[str, object]]) -> dict[str, object]:
        """为单个候选生成独立回测摘要。"""

        merged_rows = self._build_symbol_rows(symbol, candles)
        _, _, backtest_rows = self._split_rows(merged_rows)
        return run_backtest(rows=backtest_rows, holding_window="1-3d")

    def _split_rows(
        self,
        rows: list[dict[str, object]],
    ) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
        """把样本按时间切成训练、验证和回测三段。"""

        if len(rows) < 3:
            return rows, [], []

        ordered_rows = sorted(rows, key=lambda item: int(item["generated_at"]))
        train_end = max(1, int(len(ordered_rows) * 0.6))
        valid_end = max(train_end + 1, int(len(ordered_rows) * 0.8))
        if valid_end >= len(ordered_rows):
            valid_end = len(ordered_rows) - 1
        return (
            ordered_rows[:train_end],
            ordered_rows[train_end:valid_end],
            ordered_rows[valid_end:],
        )

    def _fit_model(self, rows: list[dict[str, object]]) -> dict[str, object]:
        """拟合最小启发式模型。"""

        numeric_columns = ("close_return_pct", "range_pct", "body_pct", "volume_ratio", "trend_gap_pct")
        averages: dict[str, float] = {}
        for column in numeric_columns:
            values = [_to_float(item.get(column)) for item in rows]
            averages[column] = sum(values) / len(values)

        future_returns = [_to_float(item.get("future_return_pct")) for item in rows]
        positive_rate = sum(1 for value in future_returns if value > 0) / len(future_returns)
        return {
            "feature_averages": {key: _format_float(value) for key, value in averages.items()},
            "positive_rate": _format_float(positive_rate),
            "avg_future_return_pct": _format_float(sum(future_returns) / len(future_returns)),
        }

    def _build_validation_summary(self, rows: list[dict[str, object]]) -> dict[str, object]:
        """构造最小验证摘要。"""

        future_returns = [_to_float(item.get("future_return_pct")) for item in rows]
        positive_rate = sum(1 for value in future_returns if value > 0) / len(future_returns) if future_returns else 0.0
        return {
            "sample_count": len(rows),
            "positive_rate": _format_float(positive_rate),
            "avg_future_return_pct": _format_float(sum(future_returns) / len(future_returns)) if future_returns else _format_float(0.0),
        }

    def _score_signal(self, feature_row: dict[str, object], metrics: dict[str, object]) -> float:
        """根据特征和训练统计生成分数。"""

        averages = dict(metrics.get("feature_averages") or {})
        raw_score = 0.0
        for key in ("close_return_pct", "range_pct", "body_pct", "volume_ratio", "trend_gap_pct"):
            raw_score += _to_float(feature_row.get(key)) - _to_float(averages.get(key))
        raw_score += _to_float(metrics.get("avg_future_return_pct"))
        normalized = 1 / (1 + math.exp(-(raw_score / 8)))
        return max(0.0, min(normalized, 1.0))

    def _build_explanation(self, feature_row: dict[str, object]) -> str:
        """生成最小解释摘要。"""

        return (
            f"close_return={feature_row['close_return_pct']}%, "
            f"trend_gap={feature_row['trend_gap_pct']}%, "
            f"volume_ratio={feature_row['volume_ratio']}"
        )

    def _ensure_runtime_directories(self) -> None:
        """在已存在根目录下补齐子目录。"""

        self._config.paths.dataset_dir.mkdir(exist_ok=True)
        self._config.paths.artifacts_dir.mkdir(exist_ok=True)
        self._config.paths.runs_dir.mkdir(exist_ok=True)

    def _write_run_record(
        self,
        run_type: str,
        run_id: str,
        payload: dict[str, object],
        latest_path: Path,
    ) -> None:
        """写入运行记录和最新结果。"""

        run_path = self._config.paths.runs_dir / f"{run_id}-{run_type}.json"
        self._write_json(run_path, payload)
        self._write_json(latest_path, payload)

    @staticmethod
    def _new_run_id(prefix: str) -> str:
        """生成运行记录 ID。"""

        return f"{prefix}-{uuid4().hex[:10]}"

    @staticmethod
    def _write_json(path: Path, payload: dict[str, object]) -> None:
        """以 UTF-8 写入 JSON。"""

        temp_path = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
        temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temp_path.replace(path)

    @staticmethod
    def _read_json(path: Path) -> dict[str, object] | None:
        """读取 JSON 文件。"""

        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"研究结果文件暂不可读：{path}") from exc

    def _build_warnings(self) -> list[str]:
        """构造当前运行警告。"""

        if self._config.qlib_available:
            return []
        return ["qlib_not_installed_using_minimal_fallback"]


def _utc_now() -> datetime:
    """返回 UTC 时间。"""

    return datetime.now(timezone.utc)


def _classify_signal(score: float) -> str:
    """把分数转成信号方向。"""

    if score >= 0.6:
        return "long"
    if score <= 0.4:
        return "short"
    return "flat"


def _target_weight(signal: str, score: float) -> float:
    """根据方向给出最小目标权重。"""

    if signal == "long":
        return min(0.35, max(0.1, score - 0.4))
    if signal == "short":
        return max(-0.35, min(-0.1, -(0.6 - score)))
    return 0.0


def _format_float(value: float) -> str:
    """把浮点数转成统一字符串。"""

    return f"{value:.4f}"


def _to_float(value: object) -> float:
    """把任意值尽量转成 float。"""

    try:
        return float(Decimal(str(value)))
    except (TypeError, ValueError, InvalidOperation):
        return 0.0
