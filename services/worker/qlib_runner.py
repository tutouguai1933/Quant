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
from services.worker.qlib_dataset import (
    DATA_STATE_NAMES,
    DatasetBundle,
    build_dataset_bundle,
    deserialize_dataset_bundle,
    serialize_dataset_bundle,
)
from services.worker.qlib_experiment_report import build_experiment_report
from services.worker.qlib_experiment_report import _build_dataset_snapshot_summary
from services.worker.qlib_features import (
    AUXILIARY_FEATURE_COLUMNS,
    FEATURE_PROTOCOL,
    FACTOR_METADATA,
    MISSING_POLICY_LABELS,
    NORMALIZATION_POLICY_LABELS,
    OUTLIER_POLICY_LABELS,
    PRIMARY_FEATURE_COLUMNS,
    TIMEFRAME_PROFILES,
)
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
    auxiliary_feature_columns: tuple[str, ...]
    label_columns: tuple[str, ...]
    factor_protocol: dict[str, object]


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
            holding_window=self._config.holding_window_label,
            fee_bps=self._config.backtest_fee_bps,
            slippage_bps=self._config.backtest_slippage_bps,
            cost_model=self._config.backtest_cost_model,
        )
        run_id = self._new_run_id("train")
        generated_at = _utc_now()
        model_version = f"qlib-minimal-{generated_at.strftime('%Y%m%d%H%M%S%f')}"
        model_payload = {
            "model_version": model_version,
            "generated_at": generated_at.isoformat(),
            "feature_columns": list(bundle.feature_columns),
            "auxiliary_feature_columns": list(bundle.auxiliary_feature_columns),
            "label_columns": list(bundle.label_columns),
            "factor_protocol": dict(bundle.factor_protocol),
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
            "auxiliary_feature_columns": list(bundle.auxiliary_feature_columns),
            "label_columns": list(bundle.label_columns),
            "factor_protocol": dict(bundle.factor_protocol),
            "metrics": metrics,
            "validation": validation,
            "backtest": backtest,
            "warnings": self._build_warnings(),
            "artifact_path": str(artifact_path),
            "dataset_snapshot": dataset_snapshot,
            "dataset_snapshot_path": str(dataset_snapshot_path),
            "training_context": self._build_training_context(bundle=bundle, dataset_snapshot=dataset_snapshot),
        }
        result["backtest"]["data_snapshot"] = {
            "snapshot_id": str(dataset_snapshot.get("snapshot_id", "")),
            "cache_signature": str(dataset_snapshot.get("cache_signature", "")),
            "active_data_state": str(dataset_snapshot.get("active_data_state", "")),
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
            signal = self._classify_signal(score)
            target_weight = self._target_weight(signal, score)
            rule_gate = self._build_rule_gate(latest)
            recommendation_context = self._build_recommendation_context(feature_row=latest)
            strategy_template = self._resolve_strategy_template(feature_row=latest)
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
                    "strategy_template": strategy_template,
                    "score": _format_float(score),
                    "backtest": self._build_candidate_backtest(rows=bundle.testing_rows),
                    "rule_gate": rule_gate,
                    "recommendation_context": recommendation_context,
                }
            )

        ranked_candidates = rank_candidates(
            candidates,
            validation=dict(training_payload.get("validation") or {}),
            training_metrics=dict(training_payload.get("metrics") or {}),
            force_validation_top_candidate=self._config.force_validation_top_candidate,
            research_template=self._config.research_template,
            thresholds={
                "dry_run_min_score": self._config.dry_run_min_score,
                "dry_run_min_positive_rate": self._config.dry_run_min_positive_rate,
                "dry_run_min_net_return_pct": self._config.dry_run_min_net_return_pct,
                "dry_run_min_sharpe": self._config.dry_run_min_sharpe,
                "dry_run_max_drawdown_pct": self._config.dry_run_max_drawdown_pct,
                "dry_run_max_loss_streak": self._config.dry_run_max_loss_streak,
                "dry_run_min_win_rate": self._config.dry_run_min_win_rate,
                "dry_run_max_turnover": self._config.dry_run_max_turnover,
                "dry_run_min_sample_count": self._config.dry_run_min_sample_count,
                "validation_min_sample_count": self._config.validation_min_sample_count,
                "validation_min_avg_future_return_pct": self._config.validation_min_avg_future_return_pct,
                "consistency_max_validation_backtest_return_gap_pct": self._config.consistency_max_validation_backtest_return_gap_pct,
                "consistency_max_training_validation_positive_rate_gap": self._config.consistency_max_training_validation_positive_rate_gap,
                "consistency_max_training_validation_return_gap_pct": self._config.consistency_max_training_validation_return_gap_pct,
                "rule_min_ema20_gap_pct": self._config.rule_min_ema20_gap_pct,
                "rule_min_ema55_gap_pct": self._config.rule_min_ema55_gap_pct,
                "rule_max_atr_pct": self._config.rule_max_atr_pct,
                "rule_min_volume_ratio": self._config.rule_min_volume_ratio,
                "enable_rule_gate": self._config.enable_rule_gate,
                "enable_validation_gate": self._config.enable_validation_gate,
                "enable_backtest_gate": self._config.enable_backtest_gate,
                "enable_consistency_gate": self._config.enable_consistency_gate,
                "enable_live_gate": self._config.enable_live_gate,
                "live_min_score": self._config.live_min_score,
                "live_min_positive_rate": self._config.live_min_positive_rate,
                "live_min_net_return_pct": self._config.live_min_net_return_pct,
                "live_min_win_rate": self._config.live_min_win_rate,
                "live_max_turnover": self._config.live_max_turnover,
                "live_min_sample_count": self._config.live_min_sample_count,
            },
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
            "feature_columns": list(self._active_primary_feature_columns()),
            "auxiliary_feature_columns": list(self._active_auxiliary_feature_columns()),
            "factor_protocol": dict(training_payload.get("factor_protocol") or self._build_factor_protocol()),
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
            "inference_context": self._build_inference_context(
                symbol_bundles=symbol_bundles,
                signals=signals,
                candidates=ranked_candidates,
                training_payload=training_payload,
                dataset_snapshot=dataset_snapshot,
            ),
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
            feature_columns=self._active_primary_feature_columns(),
            auxiliary_feature_columns=self._active_auxiliary_feature_columns(),
            label_columns=LABEL_COLUMNS,
            factor_protocol=self._build_factor_protocol(),
        )

    def _build_candidate_backtest(self, *, rows: list[dict[str, object]]) -> dict[str, object]:
        """为单个候选生成独立回测摘要。"""

        return run_backtest(
            rows=rows,
            holding_window=self._config.holding_window_label,
            fee_bps=self._config.backtest_fee_bps,
            slippage_bps=self._config.backtest_slippage_bps,
            cost_model=self._config.backtest_cost_model,
        )

    def _build_symbol_dataset_bundle(self, *, symbol: str, market_payload: object) -> DatasetBundle:
        """把单个币种的输入统一转换成数据集包。"""

        candles_1h, candles_4h = self._extract_timeframe_candles(market_payload)
        cache_key = self._build_dataset_cache_key(symbol=symbol, candles_1h=candles_1h, candles_4h=candles_4h)
        cache_path = self._config.paths.dataset_cache_dir / f"{cache_key}.json"
        cached_payload = self._read_json(cache_path)
        if cached_payload:
            bundle = deserialize_dataset_bundle(cached_payload)
            bundle.cache = {
                "key": cache_key,
                "status": "hit",
                "path": str(cache_path),
            }
            return bundle
        try:
            build_kwargs = {
                "symbol": symbol,
                "candles_1h": candles_1h,
                "candles_4h": candles_4h,
                "label_mode": self._config.label_mode,
                "trigger_basis": self._config.label_trigger_basis,
                "missing_policy": self._config.missing_policy,
                "outlier_policy": self._config.outlier_policy,
                "normalization_policy": self._config.normalization_policy,
                "label_target_pct": self._config.label_target_pct,
                "label_stop_pct": self._config.label_stop_pct,
                "min_window_days": self._config.holding_window_min_days,
                "max_window_days": self._config.holding_window_max_days,
                "holding_window_label": self._config.holding_window_label,
                "lookback_days": self._config.lookback_days,
                "window_mode": self._config.window_mode,
                "start_date": self._config.start_date,
                "end_date": self._config.end_date,
                "train_split_ratio": self._config.train_split_ratio,
                "validation_split_ratio": self._config.validation_split_ratio,
                "test_split_ratio": self._config.test_split_ratio,
            }
            if self._config.timeframe_profiles != TIMEFRAME_PROFILES:
                build_kwargs["timeframe_profiles"] = self._config.timeframe_profiles
            bundle = build_dataset_bundle(
                **build_kwargs,
            )
        except RuntimeError as exc:
            if "样本不足以切成训练/验证/测试三段" not in str(exc):
                raise
            raise RuntimeError("研究层样本不足，无法生成完整验证和回测结果") from exc
        bundle.cache = {
            "key": cache_key,
            "status": "miss",
            "path": str(cache_path),
        }
        self._write_json(cache_path, serialize_dataset_bundle(bundle))
        return bundle

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

        decision = evaluate_rule_gate(
            feature_row,
            research_template=self._config.research_template,
            thresholds={
                "rule_min_ema20_gap_pct": self._config.rule_min_ema20_gap_pct,
                "rule_min_ema55_gap_pct": self._config.rule_min_ema55_gap_pct,
                "rule_max_atr_pct": self._config.rule_max_atr_pct,
                "rule_min_volume_ratio": self._config.rule_min_volume_ratio,
                "strict_rule_min_ema20_gap_pct": self._config.strict_rule_min_ema20_gap_pct,
                "strict_rule_min_ema55_gap_pct": self._config.strict_rule_min_ema55_gap_pct,
                "strict_rule_max_atr_pct": self._config.strict_rule_max_atr_pct,
                "strict_rule_min_volume_ratio": self._config.strict_rule_min_volume_ratio,
            },
        )
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

    def _build_dataset_cache_key(
        self,
        *,
        symbol: str,
        candles_1h: list[dict[str, object]],
        candles_4h: list[dict[str, object]],
    ) -> str:
        """根据输入 K 线构造稳定缓存键。"""

        payload = {
            "symbol": symbol.strip().upper(),
            "candles_1h": candles_1h,
            "candles_4h": candles_4h,
            "label_config": {
                "research_template": self._config.research_template,
                "label_mode": self._config.label_mode,
                "target_pct": str(self._config.label_target_pct),
                "stop_pct": str(self._config.label_stop_pct),
                "min_days": self._config.holding_window_min_days,
                "max_days": self._config.holding_window_max_days,
                "holding_window_label": self._config.holding_window_label,
                "lookback_days": self._config.lookback_days,
                "window_mode": self._config.window_mode,
                "start_date": self._config.start_date,
                "end_date": self._config.end_date,
            },
            "feature_config": {
                "missing_policy": self._config.missing_policy,
                "outlier_policy": self._config.outlier_policy,
                "normalization_policy": self._config.normalization_policy,
            },
        }
        return hashlib.sha256(
            json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()[:16]

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

        numeric_columns = self._active_primary_feature_columns()
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
        primary_columns = self._active_primary_feature_columns()
        model_key = str(self._config.model_key or "heuristic_v1")
        if model_key == "trend_bias_v2":
            for key in primary_columns:
                delta = _to_float(feature_row.get(key)) - _to_float(averages.get(key))
                weight = self._feature_weight(key)
                raw_score += delta * weight
            for key in self._active_auxiliary_feature_columns():
                raw_score += _to_float(feature_row.get(key)) * self._feature_weight(key) * 0.05
            raw_score += _to_float(metrics.get("avg_future_return_pct")) * 1.2
            raw_score += _to_float(metrics.get("positive_rate")) * 0.8
        elif model_key == "momentum_drive_v4":
            for key in primary_columns:
                delta = _to_float(feature_row.get(key)) - _to_float(averages.get(key))
                raw_score += delta * self._feature_weight(key) * 0.65
            raw_score += _to_float(feature_row.get("breakout_strength")) * float(self._config.momentum_weight) * 1.4
            raw_score += _to_float(feature_row.get("close_return_pct")) * float(self._config.momentum_weight) * 0.9
            raw_score += _to_float(feature_row.get("roc6")) * float(self._config.momentum_weight) * 0.7
            raw_score += _to_float(feature_row.get("body_pct")) * float(self._config.momentum_weight) * 0.5
            raw_score += max(0.0, _to_float(feature_row.get("volume_ratio")) - 1.0) * float(self._config.volume_weight) * 1.2
            raw_score += _to_float(metrics.get("avg_future_return_pct")) * 1.0
            raw_score += _to_float(metrics.get("positive_rate")) * 0.7
            raw_score -= max(0.0, _to_float(feature_row.get("atr_pct")) - 6.0) * float(self._config.volatility_weight) * 0.3
        elif model_key == "balanced_v3":
            for key in primary_columns:
                delta = _to_float(feature_row.get(key)) - _to_float(averages.get(key))
                raw_score += delta * self._feature_weight(key) * 0.9
            for key in self._active_auxiliary_feature_columns():
                raw_score += (_to_float(feature_row.get(key)) - _to_float(averages.get(key))) * self._feature_weight(key) * 0.08
            raw_score += _to_float(metrics.get("avg_future_return_pct")) * 1.1
            raw_score += _to_float(metrics.get("positive_rate")) * 0.9
            raw_score -= max(0.0, _to_float(metrics.get("max_loss_streak")) - 2.0) * 0.4
        elif model_key == "stability_guard_v5":
            for key in primary_columns:
                delta = _to_float(feature_row.get(key)) - _to_float(averages.get(key))
                raw_score += delta * self._feature_weight(key) * 0.75
            for key in self._active_auxiliary_feature_columns():
                raw_score += (_to_float(feature_row.get(key)) - _to_float(averages.get(key))) * self._feature_weight(key) * 0.05
            raw_score += max(0.0, _to_float(feature_row.get("ema20_gap_pct"))) * float(self._config.trend_weight) * 0.5
            raw_score += max(0.0, _to_float(feature_row.get("ema55_gap_pct"))) * float(self._config.trend_weight) * 0.4
            raw_score += max(0.0, _to_float(feature_row.get("volume_ratio")) - 1.0) * float(self._config.volume_weight) * 0.6
            raw_score += _to_float(metrics.get("avg_future_return_pct")) * 1.15
            raw_score += _to_float(metrics.get("positive_rate")) * 1.0
            raw_score -= max(0.0, _to_float(metrics.get("max_loss_streak")) - 1.0) * 0.8
            raw_score -= max(0.0, _to_float(feature_row.get("range_pct")) - 4.0) * float(self._config.volatility_weight) * 0.15
            raw_score -= max(0.0, _to_float(feature_row.get("atr_pct")) - 4.5) * float(self._config.volatility_weight) * 0.45
        else:
            for key in primary_columns:
                raw_score += (_to_float(feature_row.get(key)) - _to_float(averages.get(key))) * self._feature_weight(key)
            raw_score += _to_float(metrics.get("avg_future_return_pct"))
        if self._config.research_template == "single_asset_timing_strict":
            penalty_weight = float(self._config.strict_penalty_weight)
            raw_score -= max(0.0, 1.2 - _to_float(feature_row.get("ema20_gap_pct"))) * 0.8 * penalty_weight
            raw_score -= max(0.0, 1.8 - _to_float(feature_row.get("ema55_gap_pct"))) * 0.8 * penalty_weight
            raw_score -= max(0.0, _to_float(feature_row.get("atr_pct")) - 4.5) * 0.5 * penalty_weight
            raw_score -= max(0.0, 1.05 - _to_float(feature_row.get("volume_ratio"))) * 1.0 * penalty_weight
        normalized = 1 / (1 + math.exp(-(raw_score / 8)))
        return max(0.0, min(normalized, 1.0))

    def _build_explanation(self, feature_row: dict[str, object]) -> str:
        """生成最小解释摘要。"""

        parts: list[str] = []
        for key in (*self._active_primary_feature_columns()[:3], *self._active_auxiliary_feature_columns()[:1]):
            metadata = FACTOR_METADATA.get(key) or {}
            label = str(metadata.get("name", key))
            parts.append(f"{label}={feature_row.get(key, 'n/a')}")
        return ", ".join(parts)

    def _build_training_context(self, *, bundle: TrainingBundle, dataset_snapshot: dict[str, object]) -> dict[str, object]:
        """整理训练阶段的实验元数据。"""

        return {
            "feature_version": str(bundle.factor_protocol.get("version", "")),
            "holding_window": self._config.holding_window_label,
            "symbols": sorted(bundle.symbol_bundles.keys()),
            "timeframes": sorted({item.timeframe for item in bundle.symbol_bundles.values()}),
            "sample_window": self._build_sample_window(bundle=bundle),
            "parameters": {
                "backtest_fee_bps": str(self._config.backtest_fee_bps),
                "backtest_slippage_bps": str(self._config.backtest_slippage_bps),
                "backtest_cost_model": str(self._config.backtest_cost_model),
                "force_validation_top_candidate": bool(self._config.force_validation_top_candidate),
                "research_preset_key": str(self._config.research_preset_key),
                "label_preset_key": str(self._config.label_preset_key),
                "research_template": str(self._config.research_template),
                "model_key": str(self._config.model_key),
                "label_mode": str(self._config.label_mode),
                "label_trigger_basis": str(self._config.label_trigger_basis),
                "holding_window_label": str(self._config.holding_window_label),
                "label_target_pct": str(self._config.label_target_pct),
                "label_stop_pct": str(self._config.label_stop_pct),
                "holding_window_min_days": self._config.holding_window_min_days,
                "holding_window_max_days": self._config.holding_window_max_days,
                "outlier_policy": str(self._config.outlier_policy),
                "normalization_policy": str(self._config.normalization_policy),
                "missing_policy": str(self._config.missing_policy),
                "timeframe_profiles": {
                    str(interval): dict(profile)
                    for interval, profile in self._config.timeframe_profiles.items()
                },
                "sample_limit": self._config.sample_limit,
                "lookback_days": self._config.lookback_days,
                "window_mode": str(self._config.window_mode),
                "start_date": str(self._config.start_date),
                "end_date": str(self._config.end_date),
                "signal_confidence_floor": str(self._config.signal_confidence_floor),
                "trend_weight": str(self._config.trend_weight),
                "momentum_weight": str(self._config.momentum_weight),
                "volume_weight": str(self._config.volume_weight),
                "oscillator_weight": str(self._config.oscillator_weight),
                "volatility_weight": str(self._config.volatility_weight),
                "strict_penalty_weight": str(self._config.strict_penalty_weight),
                "validation_min_avg_future_return_pct": str(self._config.validation_min_avg_future_return_pct),
                "consistency_max_validation_backtest_return_gap_pct": str(
                    self._config.consistency_max_validation_backtest_return_gap_pct
                ),
                "consistency_max_training_validation_positive_rate_gap": str(
                    self._config.consistency_max_training_validation_positive_rate_gap
                ),
                "consistency_max_training_validation_return_gap_pct": str(
                    self._config.consistency_max_training_validation_return_gap_pct
                ),
                "rule_min_ema20_gap_pct": str(self._config.rule_min_ema20_gap_pct),
                "rule_min_ema55_gap_pct": str(self._config.rule_min_ema55_gap_pct),
                "rule_max_atr_pct": str(self._config.rule_max_atr_pct),
                "rule_min_volume_ratio": str(self._config.rule_min_volume_ratio),
                "strict_rule_min_ema20_gap_pct": str(self._config.strict_rule_min_ema20_gap_pct),
                "strict_rule_min_ema55_gap_pct": str(self._config.strict_rule_min_ema55_gap_pct),
                "strict_rule_max_atr_pct": str(self._config.strict_rule_max_atr_pct),
                "strict_rule_min_volume_ratio": str(self._config.strict_rule_min_volume_ratio),
                "primary_factors": list(self._config.primary_feature_columns),
                "auxiliary_factors": list(self._config.auxiliary_feature_columns),
            },
            "dataset_snapshot_id": str(dataset_snapshot.get("snapshot_id", "")),
        }

    def _build_inference_context(
        self,
        *,
        symbol_bundles: dict[str, DatasetBundle],
        signals: list[dict[str, object]],
        candidates: dict[str, object],
        training_payload: dict[str, object],
        dataset_snapshot: dict[str, object],
    ) -> dict[str, object]:
        """整理推理阶段输入和输出摘要。"""

        candidate_items = list(candidates.get("items") or [])
        return {
            "feature_version": str((training_payload.get("factor_protocol") or {}).get("version", "")),
            "symbol_count": len(symbol_bundles),
            "input_summary": {
                "symbols": sorted(symbol_bundles.keys()),
                "timeframes": sorted({item.timeframe for item in symbol_bundles.values()}),
                "dataset_snapshot_id": str(dataset_snapshot.get("snapshot_id", "")),
                "research_preset_key": str(self._config.research_preset_key),
                "label_preset_key": str(self._config.label_preset_key),
                "model_key": str(self._config.model_key),
                "research_template": str(self._config.research_template),
                "label_mode": str(self._config.label_mode),
                "label_trigger_basis": str(self._config.label_trigger_basis),
                "outlier_policy": str(self._config.outlier_policy),
                "normalization_policy": str(self._config.normalization_policy),
                "missing_policy": str(self._config.missing_policy),
                "timeframe_profiles": {
                    str(interval): dict(profile)
                    for interval, profile in self._config.timeframe_profiles.items()
                },
                "sample_limit": str(self._config.sample_limit),
                "lookback_days": str(self._config.lookback_days),
                "window_mode": str(self._config.window_mode),
                "start_date": str(self._config.start_date),
                "end_date": str(self._config.end_date),
                "holding_window_label": str(self._config.holding_window_label),
                "backtest_cost_model": str(self._config.backtest_cost_model),
                "train_split_ratio": str(self._config.train_split_ratio),
                "validation_split_ratio": str(self._config.validation_split_ratio),
                "test_split_ratio": str(self._config.test_split_ratio),
                "dry_run_min_score": str(self._config.dry_run_min_score),
                "dry_run_min_positive_rate": str(self._config.dry_run_min_positive_rate),
                "dry_run_min_net_return_pct": str(self._config.dry_run_min_net_return_pct),
                "dry_run_min_sharpe": str(self._config.dry_run_min_sharpe),
                "dry_run_max_drawdown_pct": str(self._config.dry_run_max_drawdown_pct),
                "dry_run_max_loss_streak": str(self._config.dry_run_max_loss_streak),
                "dry_run_min_win_rate": str(self._config.dry_run_min_win_rate),
                "dry_run_max_turnover": str(self._config.dry_run_max_turnover),
                "dry_run_min_sample_count": str(self._config.dry_run_min_sample_count),
                "validation_min_sample_count": str(self._config.validation_min_sample_count),
                "validation_min_avg_future_return_pct": str(self._config.validation_min_avg_future_return_pct),
                "consistency_max_validation_backtest_return_gap_pct": str(
                    self._config.consistency_max_validation_backtest_return_gap_pct
                ),
                "consistency_max_training_validation_positive_rate_gap": str(
                    self._config.consistency_max_training_validation_positive_rate_gap
                ),
                "consistency_max_training_validation_return_gap_pct": str(
                    self._config.consistency_max_training_validation_return_gap_pct
                ),
                "rule_min_ema20_gap_pct": str(self._config.rule_min_ema20_gap_pct),
                "rule_min_ema55_gap_pct": str(self._config.rule_min_ema55_gap_pct),
                "rule_max_atr_pct": str(self._config.rule_max_atr_pct),
                "rule_min_volume_ratio": str(self._config.rule_min_volume_ratio),
                "strict_rule_min_ema20_gap_pct": str(self._config.strict_rule_min_ema20_gap_pct),
                "strict_rule_min_ema55_gap_pct": str(self._config.strict_rule_min_ema55_gap_pct),
                "strict_rule_max_atr_pct": str(self._config.strict_rule_max_atr_pct),
                "strict_rule_min_volume_ratio": str(self._config.strict_rule_min_volume_ratio),
                "enable_rule_gate": self._config.enable_rule_gate,
                "enable_validation_gate": self._config.enable_validation_gate,
                "enable_backtest_gate": self._config.enable_backtest_gate,
                "enable_consistency_gate": self._config.enable_consistency_gate,
                "enable_live_gate": self._config.enable_live_gate,
                "live_min_score": str(self._config.live_min_score),
                "live_min_positive_rate": str(self._config.live_min_positive_rate),
                "live_min_net_return_pct": str(self._config.live_min_net_return_pct),
                "live_min_win_rate": str(self._config.live_min_win_rate),
                "live_max_turnover": str(self._config.live_max_turnover),
                "live_min_sample_count": str(self._config.live_min_sample_count),
                "signal_confidence_floor": str(self._config.signal_confidence_floor),
                "trend_weight": str(self._config.trend_weight),
                "momentum_weight": str(self._config.momentum_weight),
                "volume_weight": str(self._config.volume_weight),
                "oscillator_weight": str(self._config.oscillator_weight),
                "volatility_weight": str(self._config.volatility_weight),
                "strict_penalty_weight": str(self._config.strict_penalty_weight),
            },
            "output_summary": {
                "signal_count": len(signals),
                "ready_count": sum(1 for item in candidate_items if bool(item.get("allowed_to_dry_run"))),
                "blocked_count": sum(1 for item in candidate_items if not bool(item.get("allowed_to_dry_run"))),
                "top_symbol": str(candidate_items[0].get("symbol", "")) if candidate_items else "",
            },
        }

    @staticmethod
    def _build_sample_window(*, bundle: TrainingBundle) -> dict[str, object]:
        """把训练、验证、回测的样本窗口压成统一结构。"""

        def _window(rows: list[dict[str, object]]) -> dict[str, object]:
            timestamps = [int(item.get("generated_at") or 0) for item in rows if item.get("generated_at") is not None]
            if not timestamps:
                return {"start": 0, "end": 0, "count": 0}
            return {"start": min(timestamps), "end": max(timestamps), "count": len(rows)}

        return {
            "training": _window(bundle.training_rows),
            "validation": _window(bundle.validation_rows),
            "backtest": _window(bundle.backtest_rows),
        }

    def _build_recommendation_context(self, *, feature_row: dict[str, object]) -> dict[str, str]:
        """根据当前因子状态补充市场形态和主要依赖指标。"""

        regime = "trend"
        rsi = _to_float(feature_row.get("rsi14"))
        cci = _to_float(feature_row.get("cci20"))
        if 40 <= rsi <= 60 and abs(cci) < 80:
            regime = "range"
        indicator_mix = "trend+momentum+volume" if regime == "trend" else "oscillator+volume"
        return {
            "regime": regime,
            "indicator_mix": indicator_mix,
            "research_template": str(self._config.research_template),
        }

    def _resolve_strategy_template(self, *, feature_row: dict[str, object]) -> str:
        """根据研究模板和当前市场状态选择执行策略模板。"""

        if self._config.research_template == "single_asset_timing_strict":
            return "trend_pullback_timing"
        breakout_strength = _to_float(feature_row.get("breakout_strength"))
        trend_gap_pct = _to_float(feature_row.get("trend_gap_pct"))
        volume_ratio = _to_float(feature_row.get("volume_ratio"))
        if breakout_strength > 0 and trend_gap_pct >= 0 and volume_ratio >= 1:
            return "trend_breakout_timing"
        return "trend_pullback_timing"

    def _active_primary_feature_columns(self) -> tuple[str, ...]:
        """返回当前启用的主判断因子。"""

        return self._config.primary_feature_columns

    def _active_auxiliary_feature_columns(self) -> tuple[str, ...]:
        """返回当前启用的辅助因子。"""

        return self._config.auxiliary_feature_columns

    def _build_factor_protocol(self) -> dict[str, object]:
        """把当前启用因子写回协议摘要。"""

        enabled_primary = set(self._active_primary_feature_columns())
        enabled_auxiliary = set(self._active_auxiliary_feature_columns())
        factors = []
        for item in list(FEATURE_PROTOCOL.get("factors") or []):
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", ""))
            enabled = name in enabled_primary or name in enabled_auxiliary
            factors.append({**item, "enabled": enabled})
        categories: dict[str, list[str]] = {}
        for name, items in dict(FEATURE_PROTOCOL.get("categories") or {}).items():
            categories[str(name)] = [
                str(item)
                for item in list(items or [])
                if str(item) in enabled_primary or str(item) in enabled_auxiliary
            ]
        return {
            **FEATURE_PROTOCOL,
            "categories": categories,
            "preprocessing": {
                **dict(FEATURE_PROTOCOL.get("preprocessing") or {}),
                "missing_policy": MISSING_POLICY_LABELS.get(
                    self._config.missing_policy,
                    self._config.missing_policy,
                ),
                "outlier_policy": OUTLIER_POLICY_LABELS.get(self._config.outlier_policy, self._config.outlier_policy),
                "normalization_policy": NORMALIZATION_POLICY_LABELS.get(
                    self._config.normalization_policy,
                    self._config.normalization_policy,
                ),
            },
            "roles": {
                "primary": list(self._active_primary_feature_columns()),
                "auxiliary": list(self._active_auxiliary_feature_columns()),
            },
            "factors": factors,
        }

    def _feature_weight(self, name: str) -> float:
        """按因子类别给简单权重。"""

        category = str((FACTOR_METADATA.get(name) or {}).get("category", ""))
        if category == "trend":
            return float(self._config.trend_weight)
        if category == "momentum":
            return float(self._config.momentum_weight)
        if category == "volume":
            return float(self._config.volume_weight)
        if category == "oscillator":
            return float(self._config.oscillator_weight)
        if category == "volatility":
            return float(self._config.volatility_weight)
        return 1.0

    def _classify_signal(self, score: float) -> str:
        """按当前置信度门槛把分数转成信号方向。"""

        floor = float(self._config.signal_confidence_floor)
        if score >= floor:
            return "long"
        if score <= (1 - floor):
            return "short"
        return "flat"

    def _target_weight(self, signal: str, score: float) -> float:
        """根据方向给出最小目标权重。"""

        floor = float(self._config.signal_confidence_floor)
        if signal == "long":
            return min(0.35, max(0.1, score - max(0.2, floor - 0.15)))
        if signal == "short":
            return max(-0.35, min(-0.1, -((1 - max(0.2, floor - 0.15)) - score)))
        return 0.0

    def _ensure_runtime_directories(self) -> None:
        """在已存在根目录下补齐子目录。"""

        self._config.paths.dataset_dir.mkdir(exist_ok=True)
        self._config.paths.dataset_snapshots_dir.mkdir(parents=True, exist_ok=True)
        self._config.paths.dataset_cache_dir.mkdir(parents=True, exist_ok=True)
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

        payload = self._build_dataset_snapshot(symbol_bundles=symbol_bundles, generated_at=generated_at, snapshot_label=snapshot_label)
        snapshot_path = self._config.paths.dataset_snapshots_dir / f"{payload['snapshot_id']}.json"
        if snapshot_path.exists():
            existing_payload = self._read_json(snapshot_path) or {}
            payload["cache_status"] = "reused"
            if existing_payload.get("generated_at"):
                payload["generated_at"] = str(existing_payload.get("generated_at"))
        self._write_json(snapshot_path, payload)
        self._write_json(self._config.paths.latest_dataset_snapshot_path, payload)
        return snapshot_path, payload

    def _build_dataset_snapshot(
        self,
        *,
        symbol_bundles: dict[str, DatasetBundle],
        generated_at: datetime,
        snapshot_label: str,
    ) -> dict[str, object]:
        """把当前输入样本压成可复用的数据快照摘要。"""

        symbols: list[dict[str, object]] = []
        total_training = 0
        total_validation = 0
        total_testing = 0
        aggregated_states = {
            state: {"symbol_count": 0, "row_count": 0}
            for state in DATA_STATE_NAMES
        }
        cache_hit_count = 0
        cache_miss_count = 0
        cache_signatures: list[str] = []
        for symbol, bundle in sorted(symbol_bundles.items()):
            training_count = len(bundle.training_rows)
            validation_count = len(bundle.validation_rows)
            testing_count = len(bundle.testing_rows)
            total_training += training_count
            total_validation += validation_count
            total_testing += testing_count
            symbol_states = dict(bundle.data_states or {})
            for state in DATA_STATE_NAMES:
                state_payload = dict(symbol_states.get(state) or {})
                aggregated_states[state]["symbol_count"] += int(state_payload.get("symbol_count", 0) or 0)
                aggregated_states[state]["row_count"] += int(state_payload.get("row_count", 0) or 0)
            cache_payload = dict(bundle.cache or {})
            if str(cache_payload.get("status", "")) == "hit":
                cache_hit_count += 1
            else:
                cache_miss_count += 1
            if str(cache_payload.get("key", "")).strip():
                cache_signatures.append(str(cache_payload.get("key", "")).strip())
            symbols.append(
                {
                    "symbol": symbol,
                    "timeframe": bundle.timeframe,
                    "training_count": training_count,
                    "validation_count": validation_count,
                    "testing_count": testing_count,
                    "total_count": training_count + validation_count + testing_count,
                    "data_layers": symbol_states,
                    "cache": cache_payload,
                }
            )
        stable_signature_payload = {
            "active_data_state": self._config.research_data_layer,
            "data_states": aggregated_states,
            "symbols": [
                {
                    "symbol": item["symbol"],
                    "timeframe": item["timeframe"],
                    "training_count": item["training_count"],
                    "validation_count": item["validation_count"],
                    "testing_count": item["testing_count"],
                    "total_count": item["total_count"],
                    "data_layers": item["data_layers"],
                    "cache_key": dict(item.get("cache") or {}).get("key", ""),
                }
                for item in symbols
            ],
            "summary": {
                "symbol_count": len(symbols),
                "training_count": total_training,
                "validation_count": total_validation,
                "testing_count": total_testing,
            },
        }
        signature = hashlib.sha256(
            json.dumps(stable_signature_payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()[:16]
        base_payload = {
            "generated_at": generated_at.isoformat(),
            "active_data_state": self._config.research_data_layer,
            "data_states": aggregated_states,
            "symbols": symbols,
            "summary": {
                "symbol_count": len(symbols),
                "training_count": total_training,
                "validation_count": total_validation,
                "testing_count": total_testing,
                "data_states": {
                    "current": self._config.research_data_layer,
                    **aggregated_states,
                },
                "cache": {
                    "hit_count": cache_hit_count,
                    "miss_count": cache_miss_count,
                    "scope": "runtime-dataset-cache",
                    "refresh_rule": "change_input_signature",
                },
            },
        }
        return {
            "snapshot_id": f"dataset-{signature}",
            **base_payload,
            "snapshot_label": snapshot_label,
            "cache_signature": signature,
            "signature": signature,
            "cache_status": "created",
            "cache_signatures": sorted(set(cache_signatures)),
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
            "signal_count": str(payload.get("signal_count", dict(payload.get("summary") or {}).get("signal_count", ""))),
            "dataset_snapshot_path": str(payload.get("dataset_snapshot_path", "")),
            "dataset_snapshot": _build_dataset_snapshot_summary(payload),
            "backtest": _build_experiment_backtest_snapshot(payload.get("backtest")),
            "training_context": dict(payload.get("training_context") or {}),
            "inference_context": dict(payload.get("inference_context") or {}),
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


def _build_experiment_backtest_snapshot(value: object) -> dict[str, str]:
    """抽取实验账本需要的最小回测摘要。"""

    payload = dict(value or {}) if isinstance(value, dict) else {}
    metrics = dict(payload.get("metrics") or {})
    return {
        "net_return_pct": str(metrics.get("net_return_pct", metrics.get("total_return_pct", ""))),
        "max_drawdown_pct": str(metrics.get("max_drawdown_pct", "")),
        "sharpe": str(metrics.get("sharpe", "")),
        "win_rate": str(metrics.get("win_rate", "")),
    }


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
