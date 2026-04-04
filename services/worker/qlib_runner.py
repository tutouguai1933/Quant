"""Qlib 最小运行入口。

这个文件负责最小训练、最小推理和结果落盘，不让控制平面直接碰内部实现。
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from uuid import uuid4

from services.worker.qlib_backtest import run_backtest
from services.worker.qlib_config import QlibRuntimeConfig
from services.worker.qlib_dataset import DatasetBundle, build_dataset_bundle
from services.worker.qlib_experiment_report import build_experiment_report
from services.worker.qlib_features import FEATURE_COLUMNS
from services.worker.qlib_labels import LABEL_COLUMNS
from services.worker.qlib_ranking import rank_candidates
from services.worker.qlib_rule_gate import evaluate_rule_gate


@dataclass(slots=True)
class TrainingBundle:
    """训练阶段的中间结果。"""

    symbol_bundles: dict[str, DatasetBundle]
    training_rows: list[dict[str, object]]
    validation_rows: list[dict[str, object]]
    backtest_rows: list[dict[str, object]]
    feature_columns: tuple[str, ...]
    label_columns: tuple[str, ...]


class QlibRunner:
    """最小研究层执行器。"""

    def __init__(self, *, config: QlibRuntimeConfig) -> None:
        self._config = config

    def train(self, dataset: dict[str, object]) -> dict[str, object]:
        """执行一次最小训练。"""

        self._config.ensure_ready()
        self._ensure_runtime_directories()
        bundle = self._build_training_bundle(dataset)
        dataset_snapshot_path, dataset_snapshot = self._write_dataset_snapshot(
            symbol_bundles=bundle.symbol_bundles,
            generated_at=_utc_now(),
            snapshot_label="training",
        )
        metrics = self._fit_model(bundle.training_rows)
        validation = self._build_validation_summary(bundle.validation_rows)
        backtest = run_backtest(
            rows=bundle.backtest_rows,
            holding_window="1-3d",
            fee_bps=self._config.backtest_fee_bps,
            slippage_bps=self._config.backtest_slippage_bps,
        )
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
            "dataset_snapshot": dataset_snapshot,
            "dataset_snapshot_path": str(dataset_snapshot_path),
        }
        result["experiment_report"] = build_experiment_report(
            latest_training=result,
            latest_inference=None,
            candidates={"items": []},
            recent_runs=[
                self._build_experiment_entry(run_type="training", payload=result),
            ],
        )
        self._write_run_record("training", run_id, result, self._config.paths.latest_training_path)
        return result

    def infer(self, dataset: dict[str, object]) -> dict[str, object]:
        """执行一次最小推理。"""

        self._config.ensure_ready()
        self._ensure_runtime_directories()
        training_payload = self._read_json(self._config.paths.latest_training_path)
        if not training_payload:
            raise RuntimeError("研究层还没有可用训练结果，不能直接推理")

        signals: list[dict[str, object]] = []
        candidates: list[dict[str, object]] = []
        symbol_bundles: dict[str, DatasetBundle] = {}
        for symbol, market_payload in dataset.items():
            bundle = self._build_symbol_dataset_bundle(symbol=symbol, market_payload=market_payload)
            symbol_bundles[symbol] = bundle
            latest = self._pick_latest_row(bundle)
            if latest is None:
                continue
            score = self._score_signal(latest, dict(training_payload.get("metrics") or {}))
            confidence = max(score, 1 - score)
            signal = _classify_signal(score)
            target_weight = _target_weight(signal, score)
            rule_gate = self._build_rule_gate(latest)
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
                    "backtest": self._build_candidate_backtest(rows=bundle.testing_rows),
                    "rule_gate": rule_gate,
                }
            )

        ranked_candidates = rank_candidates(
            candidates,
            validation=dict(training_payload.get("validation") or {}),
        )
        dataset_snapshot_path, dataset_snapshot = self._write_dataset_snapshot(
            symbol_bundles=symbol_bundles,
            generated_at=_utc_now(),
            snapshot_label="inference",
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
            "candidates": ranked_candidates,
            "warnings": self._build_warnings(),
            "dataset_snapshot": dataset_snapshot,
            "dataset_snapshot_path": str(dataset_snapshot_path),
        }
        result["experiment_report"] = build_experiment_report(
            latest_training=training_payload,
            latest_inference=result,
            candidates=result["candidates"],
            recent_runs=[
                self._build_experiment_entry(run_type="inference", payload=result),
                *self._read_experiment_index(),
            ],
        )
        self._write_run_record("inference", result["run_id"], result, self._config.paths.latest_inference_path)
        return result

    def _build_training_bundle(self, dataset: dict[str, object]) -> TrainingBundle:
        """把输入数据整理成训练样本。"""

        symbol_bundles: dict[str, DatasetBundle] = {}
        training_rows: list[dict[str, object]] = []
        validation_rows: list[dict[str, object]] = []
        backtest_rows: list[dict[str, object]] = []
        for symbol, market_payload in dataset.items():
            bundle = self._build_symbol_dataset_bundle(symbol=symbol, market_payload=market_payload)
            symbol_bundles[symbol] = bundle
            training_rows.extend(bundle.training_rows)
            validation_rows.extend(bundle.validation_rows)
            backtest_rows.extend(bundle.testing_rows)
        if not training_rows:
            raise RuntimeError("研究层没有拿到可训练样本")
        if not validation_rows or not backtest_rows:
            raise RuntimeError("研究层样本不足，无法生成完整验证和回测结果")
        return TrainingBundle(
            symbol_bundles=symbol_bundles,
            training_rows=training_rows,
            validation_rows=validation_rows,
            backtest_rows=backtest_rows,
            feature_columns=FEATURE_COLUMNS,
            label_columns=LABEL_COLUMNS,
        )

    def _build_candidate_backtest(self, *, rows: list[dict[str, object]]) -> dict[str, object]:
        """为单个候选生成独立回测摘要。"""

        return run_backtest(
            rows=rows,
            holding_window="1-3d",
            fee_bps=self._config.backtest_fee_bps,
            slippage_bps=self._config.backtest_slippage_bps,
        )

    def _build_symbol_dataset_bundle(self, *, symbol: str, market_payload: object) -> DatasetBundle:
        """把单个币种的输入统一转换成数据集包。"""

        candles_1h, candles_4h = self._extract_timeframe_candles(market_payload)
        try:
            return build_dataset_bundle(
                symbol=symbol,
                candles_1h=candles_1h,
                candles_4h=candles_4h,
            )
        except RuntimeError as exc:
            if "样本不足以切成训练/验证/测试三段" not in str(exc):
                raise
            raise RuntimeError("研究层样本不足，无法生成完整验证和回测结果") from exc

    def _pick_latest_row(self, bundle: DatasetBundle) -> dict[str, object] | None:
        """优先从测试段挑最新样本，没有则回退到验证和训练。"""

        if bundle.testing_rows:
            return bundle.testing_rows[-1]
        if bundle.validation_rows:
            return bundle.validation_rows[-1]
        if bundle.training_rows:
            return bundle.training_rows[-1]
        return None

    def _build_rule_gate(self, feature_row: dict[str, object]) -> dict[str, object]:
        """把规则门结果统一成候选结构。"""

        decision = evaluate_rule_gate(feature_row)
        if bool(decision.get("allowed")):
            return {"status": "passed", "reasons": []}
        reason = str(decision.get("reason", "")).strip() or "rule_gate_blocked"
        return {"status": "failed", "reasons": [reason]}

    def _extract_timeframe_candles(
        self,
        market_payload: object,
    ) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
        """兼容旧输入和多周期输入。"""

        if isinstance(market_payload, dict):
            candles_1h = list(market_payload.get("candles_1h") or [])
            candles_4h = list(market_payload.get("candles_4h") or [])
            if candles_1h or candles_4h:
                return candles_1h, candles_4h

        candles = list(market_payload) if isinstance(market_payload, list) else []
        if not candles:
            return [], []
        if self._infer_timeframe(candles) == "4h":
            return [], candles
        return candles, []

    @staticmethod
    def _infer_timeframe(candles: list[dict[str, object]]) -> str:
        """根据 K 线时间间隔推断周期。"""

        if len(candles) < 2:
            return "1h"
        first = int(candles[0].get("open_time") or 0)
        second = int(candles[1].get("open_time") or 0)
        step_ms = max(0, second - first)
        if step_ms >= 4 * 60 * 60 * 1000:
            return "4h"
        return "1h"

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
        self._config.paths.dataset_snapshots_dir.mkdir(parents=True, exist_ok=True)
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
        self._append_experiment_index(run_type=run_type, payload=payload)

    def _write_dataset_snapshot(
        self,
        *,
        symbol_bundles: dict[str, DatasetBundle],
        generated_at: datetime,
        snapshot_label: str,
    ) -> tuple[Path, dict[str, object]]:
        """写入最新数据快照和带唯一名的历史快照。"""

        payload = self._build_dataset_snapshot(symbol_bundles=symbol_bundles, generated_at=generated_at)
        snapshot_path = self._config.paths.dataset_snapshots_dir / f"{payload['snapshot_id']}-{snapshot_label}.json"
        self._write_json(snapshot_path, payload)
        self._write_json(self._config.paths.latest_dataset_snapshot_path, payload)
        return snapshot_path, payload

    def _build_dataset_snapshot(
        self,
        *,
        symbol_bundles: dict[str, DatasetBundle],
        generated_at: datetime,
    ) -> dict[str, object]:
        """把当前输入样本压成可复用的数据快照摘要。"""

        symbols: list[dict[str, object]] = []
        total_training = 0
        total_validation = 0
        total_testing = 0
        for symbol, bundle in sorted(symbol_bundles.items()):
            training_count = len(bundle.training_rows)
            validation_count = len(bundle.validation_rows)
            testing_count = len(bundle.testing_rows)
            total_training += training_count
            total_validation += validation_count
            total_testing += testing_count
            symbols.append(
                {
                    "symbol": symbol,
                    "timeframe": bundle.timeframe,
                    "training_count": training_count,
                    "validation_count": validation_count,
                    "testing_count": testing_count,
                    "total_count": training_count + validation_count + testing_count,
                }
            )
        base_payload = {
            "generated_at": generated_at.isoformat(),
            "symbols": symbols,
            "summary": {
                "symbol_count": len(symbols),
                "training_count": total_training,
                "validation_count": total_validation,
                "testing_count": total_testing,
            },
        }
        signature = hashlib.sha256(
            json.dumps(base_payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()[:16]
        return {
            "snapshot_id": f"dataset-{generated_at.strftime('%Y%m%d%H%M%S%f')}",
            **base_payload,
            "signature": signature,
        }

    def _append_experiment_index(self, *, run_type: str, payload: dict[str, object]) -> None:
        """把最近实验账本保持成可直接读取的索引。"""

        current = self._read_experiment_index()
        current.insert(0, self._build_experiment_entry(run_type=run_type, payload=payload))
        self._write_json(self._config.paths.experiment_index_path, {"items": current[:20]})

    def _read_experiment_index(self) -> list[dict[str, object]]:
        """读取最近实验账本。"""

        payload = self._read_json(self._config.paths.experiment_index_path)
        return list((payload or {}).get("items") or [])

    @staticmethod
    def _build_experiment_entry(*, run_type: str, payload: dict[str, object]) -> dict[str, object]:
        """构造统一实验账本条目。"""

        return {
            "run_id": str(payload.get("run_id", "")),
            "run_type": run_type,
            "status": str(payload.get("status", "")),
            "generated_at": str(payload.get("generated_at", "")),
            "model_version": str(payload.get("model_version", "")),
            "dataset_snapshot_path": str(payload.get("dataset_snapshot_path", "")),
            "artifact_path": str(payload.get("artifact_path", "")),
        }

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
