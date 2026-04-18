"""Minimal signal production service for Quant phase 1.

Task 5 requires a smallest-possible signal pipeline that covers:
- data preparation
- feature generation
- training
- signal output

The implementation stays stdlib-only so the repo can advance without changing
dependency declarations. Mock data is the default executable path. A qlib path
is defined as an optional runtime path and becomes available once the user
approves installing qlib later.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from services.api.app.domain.contracts import SignalContract, SignalSide, SignalSource, SignalStatus
from services.api.app.services.research_service import research_service
from services.api.app.services.strategy_catalog import strategy_catalog_service


@dataclass(slots=True)
class PipelineStage:
    name: str
    status: str
    detail: str

    def to_dict(self) -> dict[str, str]:
        return {"name": self.name, "status": self.status, "detail": self.detail}


@dataclass(slots=True)
class TrainingRunSummary:
    source: str
    backend: str
    stages: list[PipelineStage]
    signal_count: int

    def to_dict(self) -> dict[str, object]:
        return {
            "source": self.source,
            "backend": self.backend,
            "signal_count": self.signal_count,
            "stages": [stage.to_dict() for stage in self.stages],
        }


class SignalPipelineUnavailableError(RuntimeError):
    """Raised when an optional pipeline backend is not available."""


class SignalService:
    """Owns a minimal in-memory signal flow for the phase-1 skeleton."""

    def __init__(self) -> None:
        self._signals: dict[int, SignalContract] = {}
        self._signal_metadata: dict[int, dict[str, object]] = {}
        self._next_signal_id = 1
        self._last_run: TrainingRunSummary | None = None
        self._dispatch_lock = threading.Lock()
        self._dispatch_claims: set[int] = set()

    def list_signals(self, limit: int = 100) -> list[dict[str, object]]:
        self._ensure_seed_data()
        ordered_signals = sorted(self._signals.values(), key=lambda item: item.signal_id or 0, reverse=True)
        return [self._serialize_signal(signal) for signal in ordered_signals[:limit]]

    def get_signal(self, signal_id: int) -> dict[str, object] | None:
        self._ensure_seed_data()
        signal = self._signals.get(signal_id)
        return None if signal is None else self._serialize_signal(signal)

    def update_signal_status(self, signal_id: int, status: str) -> dict[str, object] | None:
        with self._dispatch_lock:
            signal = self._signals.get(signal_id)
            if signal is None:
                return None
            signal.status = status
            return self._serialize_signal(signal)

    def claim_latest_dispatchable_signal(self, strategy_id: int) -> dict[str, object] | None:
        """原子地认领一条可派发信号，避免并发重复派发。"""

        self._ensure_seed_data()
        dispatchable_statuses = {SignalStatus.RECEIVED.value, SignalStatus.ACCEPTED.value}
        with self._dispatch_lock:
            ordered_signals = sorted(self._signals.values(), key=lambda item: item.signal_id or 0, reverse=True)
            latest_pending_qlib_signal_id = self._latest_pending_qlib_signal_id(ordered_signals, dispatchable_statuses)
            for signal in ordered_signals:
                signal_id = signal.signal_id or 0
                if signal.source != SignalSource.QLIB and 0 < signal_id < latest_pending_qlib_signal_id:
                    continue
                if signal.strategy_id != strategy_id:
                    continue
                if signal.status not in dispatchable_statuses:
                    continue
                if not self._is_dispatchable_signal(signal):
                    continue
                if signal_id in self._dispatch_claims:
                    continue
                self._dispatch_claims.add(signal_id)
                return self._serialize_signal(signal)

            generic_candidates: list[SignalContract] = []
            for signal in ordered_signals:
                signal_id = signal.signal_id or 0
                if signal.source != SignalSource.QLIB and 0 < signal_id < latest_pending_qlib_signal_id:
                    continue
                if signal.strategy_id is not None:
                    continue
                if str(signal.side) == SignalSide.FLAT.value:
                    continue
                if signal.status not in dispatchable_statuses:
                    continue
                if not self._is_dispatchable_signal(signal):
                    continue
                if signal_id in self._dispatch_claims:
                    continue
                generic_candidates.append(signal)
            if generic_candidates:
                matched_candidates = [
                    signal
                    for signal in generic_candidates
                    if self._matches_strategy_context(signal=signal, strategy_id=strategy_id)
                ]
                if strategy_id == 1:
                    source_candidates = matched_candidates or generic_candidates
                else:
                    source_candidates = matched_candidates
                if not source_candidates:
                    return None
                chosen = sorted(source_candidates, key=self._dispatch_sort_key)[0]
                chosen_id = chosen.signal_id or 0
                self._dispatch_claims.add(chosen_id)
                return self._serialize_signal(chosen)
        return None

    def _latest_pending_qlib_signal_id(
        self,
        ordered_signals: list[SignalContract],
        dispatchable_statuses: set[str],
    ) -> int:
        """返回当前待处理研究信号里的最新编号。"""

        for signal in ordered_signals:
            signal_id = signal.signal_id or 0
            if signal.source != SignalSource.QLIB:
                continue
            if signal.status not in dispatchable_statuses:
                continue
            if signal_id in self._dispatch_claims:
                continue
            return signal_id
        return 0

    def release_dispatch_claim(self, signal_id: int) -> None:
        """释放派发认领，允许后续状态继续推进。"""

        with self._dispatch_lock:
            self._dispatch_claims.discard(signal_id)

    def ingest_signal(self, payload: dict[str, object]) -> dict[str, object]:
        signal = SignalContract(
            signal_id=self._allocate_signal_id(),
            symbol=str(payload["symbol"]),
            side=payload["side"],
            score=payload["score"],
            confidence=payload["confidence"],
            target_weight=payload["target_weight"],
            generated_at=self._parse_timestamp(str(payload["generated_at"])),
            source=payload["source"],
            strategy_id=payload.get("strategy_id"),
        )
        self._signals[signal.signal_id] = signal
        self._signal_metadata[signal.signal_id] = dict(payload.get("payload") or {})
        return self._serialize_signal(signal)

    def run_pipeline(self, source: str = SignalSource.MOCK.value) -> dict[str, object]:
        requested_source = SignalSource(source)
        if requested_source == SignalSource.QLIB:
            summary = self._run_optional_qlib_pipeline()
        elif requested_source == SignalSource.RULE_BASED:
            summary = self._run_mock_pipeline(requested_source, backend="rule-based-simplified")
        else:
            summary = self._run_mock_pipeline(requested_source, backend="mock")

        self._last_run = summary
        return summary.to_dict()

    def refresh_qlib_signals_from_latest_result(self) -> dict[str, object]:
        """把最近一次研究推理结果写回信号主链。"""

        latest = research_service.get_latest_result()
        training = dict(latest.get("latest_training") or {})
        inference = dict(latest.get("latest_inference") or {})
        if not training or not inference:
            raise SignalPipelineUnavailableError("研究层还没有可写入信号主链的训练和推理结果")
        summary = self._store_qlib_pipeline_result(training=training, inference=inference)
        self._last_run = summary
        return summary.to_dict()

    def get_last_run(self) -> dict[str, object] | None:
        return None if self._last_run is None else self._last_run.to_dict()

    def _ensure_seed_data(self) -> None:
        if not self._signals:
            self.run_pipeline(SignalSource.MOCK.value)

    def _run_mock_pipeline(self, source: SignalSource, backend: str) -> TrainingRunSummary:
        dataset = self._prepare_mock_dataset()
        features = self._build_mock_features(dataset)
        model_summary = self._train_mock_model(features)
        signals = self._generate_mock_signals(features, source)

        for signal in signals:
            self._signals[signal.signal_id] = signal

        stages = [
            PipelineStage("data_preparation", "completed", f"{len(dataset)} rows prepared"),
            PipelineStage("feature_engineering", "completed", f"{len(features)} feature rows built"),
            PipelineStage("model_training", "completed", model_summary),
            PipelineStage("signal_output", "completed", f"{len(signals)} signals emitted"),
        ]
        return TrainingRunSummary(
            source=source.value,
            backend=backend,
            stages=stages,
            signal_count=len(signals),
        )

    def _run_optional_qlib_pipeline(self) -> TrainingRunSummary:
        try:
            training = research_service.run_training()
            inference = research_service.run_inference()
        except Exception as exc:
            raise SignalPipelineUnavailableError(str(exc)) from exc

        return self._store_qlib_pipeline_result(training=training, inference=inference)

    def _store_qlib_pipeline_result(
        self,
        *,
        training: dict[str, object],
        inference: dict[str, object],
    ) -> TrainingRunSummary:
        """把研究层结果写进信号主链。"""

        self._expire_pending_qlib_signals()

        signal_count = 0
        candidate_items = list((inference.get("candidates") or {}).get("items", []))
        recommended_symbol = self._resolve_recommended_symbol(candidate_items)
        candidate_by_symbol = {
            str(item.get("symbol", "")).strip().upper(): dict(item)
            for item in candidate_items
            if str(item.get("symbol", "")).strip()
        }
        for item in list(inference.get("signals", [])):
            signal_id = self._allocate_signal_id()
            normalized_symbol = str(item.get("symbol", "")).strip().upper()
            self._signals[signal_id] = SignalContract(
                signal_id=signal_id,
                strategy_id=None,
                symbol=normalized_symbol,
                side=str(item.get("side", "flat")),
                score=str(item.get("score", "0")),
                confidence=str(item.get("confidence", "0")),
                target_weight=str(item.get("target_weight", "0")),
                generated_at=self._parse_timestamp(str(item.get("generated_at", datetime.now(timezone.utc).isoformat()))),
                source=SignalSource.QLIB,
            )
            candidate = candidate_by_symbol.get(normalized_symbol, {})
            self._signal_metadata[signal_id] = {
                "candidate": candidate,
                "dry_run_gate": dict(candidate.get("dry_run_gate") or {}),
                "allowed_to_dry_run": bool(candidate.get("allowed_to_dry_run")),
                "forced_for_validation": bool(candidate.get("forced_for_validation")),
                "forced_reason": str(candidate.get("forced_reason", "")),
                "review_status": str(candidate.get("review_status", "")),
                "next_action": str(candidate.get("next_action", "")),
                "execution_priority": candidate.get("execution_priority"),
                "strategy_template": str(candidate.get("strategy_template", "")),
                "recommended_for_execution": normalized_symbol == recommended_symbol,
            }
            signal_count += 1

        return TrainingRunSummary(
            source=SignalSource.QLIB.value,
            backend=str(inference.get("backend", "qlib-fallback")),
            stages=[
                PipelineStage("data_preparation", "completed", "研究层市场样本已准备"),
                PipelineStage("feature_engineering", "completed", "最小特征和标签已生成"),
                PipelineStage("model_training", "completed", str(training.get("model_version", "unknown"))),
                PipelineStage("signal_output", "completed", f"{signal_count} 条研究信号已输出"),
            ],
            signal_count=signal_count,
        )

    def _expire_pending_qlib_signals(self) -> None:
        """把旧的待处理研究信号标成过期，避免重复派发。"""

        for signal in self._signals.values():
            if signal.source != SignalSource.QLIB:
                continue
            if signal.status not in {SignalStatus.RECEIVED.value, SignalStatus.ACCEPTED.value}:
                continue
            signal.status = SignalStatus.EXPIRED

    def _prepare_mock_dataset(self) -> list[dict[str, object]]:
        anchor = datetime(2026, 4, 1, 6, 0, tzinfo=timezone.utc)
        closes = [Decimal("84000"), Decimal("84500"), Decimal("85200"), Decimal("86000")]
        return [
            {"symbol": "BTC/USDT", "timestamp": anchor + timedelta(hours=index), "close": close}
            for index, close in enumerate(closes)
        ]

    def _build_mock_features(self, dataset: list[dict[str, object]]) -> list[dict[str, object]]:
        feature_rows: list[dict[str, object]] = []
        previous_close: Decimal | None = None
        for row in dataset:
            close = row["close"]
            momentum = Decimal("0") if previous_close is None else close - previous_close
            feature_rows.append(
                {
                    "symbol": row["symbol"],
                    "generated_at": row["timestamp"],
                    "close": close,
                    "momentum": momentum,
                }
            )
            previous_close = close
        return feature_rows

    def _train_mock_model(self, features: list[dict[str, object]]) -> str:
        positive_momentum = sum(1 for item in features if item["momentum"] > 0)
        return f"mock momentum model fitted on {len(features)} rows with {positive_momentum} positive moves"

    def _generate_mock_signals(
        self,
        features: list[dict[str, object]],
        source: SignalSource,
    ) -> list[SignalContract]:
        latest = features[-1]
        score = Decimal("0.780000")
        confidence = Decimal("0.810000")
        side = SignalSide.LONG if latest["momentum"] >= 0 else SignalSide.SHORT
        return [
            SignalContract(
                signal_id=self._allocate_signal_id(),
                strategy_id=1,
                symbol=str(latest["symbol"]),
                side=side,
                score=score,
                confidence=confidence,
                target_weight=Decimal("0.250000"),
                generated_at=latest["generated_at"],
                source=source,
            )
        ]

    def _allocate_signal_id(self) -> int:
        signal_id = self._next_signal_id
        self._next_signal_id += 1
        return signal_id

    def _serialize_signal(self, signal: SignalContract) -> dict[str, object]:
        """把信号和内部元数据一起返回。"""

        payload = signal.to_dict()
        payload["payload"] = dict(self._signal_metadata.get(signal.signal_id or 0, {}))
        return payload

    @staticmethod
    def _parse_timestamp(value: str) -> datetime:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("generated_at must be valid ISO 8601 timestamp") from exc
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("generated_at must be timezone-aware")
        return parsed

    def _is_dispatchable_signal(self, signal: SignalContract) -> bool:
        """判断当前信号是否允许进入派发。"""

        if signal.source != SignalSource.QLIB:
            return True
        metadata = dict(self._signal_metadata.get(signal.signal_id or 0, {}))
        if bool(metadata.get("forced_for_validation")):
            return True
        gate = dict(metadata.get("dry_run_gate") or {})
        if gate:
            return str(gate.get("status", "")).strip() == "passed"
        return bool(metadata.get("allowed_to_dry_run"))

    def _matches_strategy_context(self, *, signal: SignalContract, strategy_id: int) -> bool:
        """判断一条通用研究信号是否适合当前策略实例。"""

        if strategy_id == 1:
            return True
        metadata = dict(self._signal_metadata.get(signal.signal_id or 0, {}))
        strategy_template = str(metadata.get("strategy_template", "")).strip()
        if not strategy_template:
            return False
        resolved_strategy_id = strategy_catalog_service.resolve_strategy_id(strategy_template)
        return resolved_strategy_id == strategy_id

    def _dispatch_sort_key(self, signal: SignalContract) -> tuple[int, int, int]:
        """给通用研究信号排序，优先推荐候选，其次看候选 rank。"""

        metadata = dict(self._signal_metadata.get(signal.signal_id or 0, {}))
        candidate = dict(metadata.get("candidate") or {})
        recommended = 0 if bool(metadata.get("recommended_for_execution")) else 1
        execution_priority = self._parse_rank(metadata.get("execution_priority"))
        rank = self._parse_rank(candidate.get("rank"))
        return recommended, execution_priority, rank, -(signal.signal_id or 0)

    @staticmethod
    def _resolve_recommended_symbol(candidate_items: list[dict[str, object]]) -> str:
        """从研究候选里挑出当前优先进入执行链的币种。"""

        ready_items = [
            item
            for item in candidate_items
            if bool(item.get("allowed_to_dry_run")) and str(item.get("next_action", "") or "enter_dry_run") == "enter_dry_run"
        ]
        if not ready_items:
            return ""
        chosen = sorted(
            ready_items,
            key=lambda item: (
                SignalService._parse_rank(item.get("execution_priority")),
                SignalService._parse_rank(item.get("rank")),
                str(item.get("symbol", "")),
            ),
        )[0]
        return str(chosen.get("symbol", "")).strip().upper()

    @staticmethod
    def _parse_rank(value: object) -> int:
        """把候选 rank 转成可排序的整数。"""

        try:
            return int(value)
        except (TypeError, ValueError):
            return 999999


signal_service = SignalService()
