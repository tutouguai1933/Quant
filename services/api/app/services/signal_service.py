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

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from services.api.app.domain.contracts import SignalContract, SignalSide, SignalSource
from services.api.app.services.research_service import research_service


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
        self._next_signal_id = 1
        self._last_run: TrainingRunSummary | None = None

    def list_signals(self, limit: int = 100) -> list[dict[str, object]]:
        self._ensure_seed_data()
        ordered_signals = sorted(self._signals.values(), key=lambda item: item.signal_id or 0, reverse=True)
        return [signal.to_dict() for signal in ordered_signals[:limit]]

    def get_signal(self, signal_id: int) -> dict[str, object] | None:
        self._ensure_seed_data()
        signal = self._signals.get(signal_id)
        return None if signal is None else signal.to_dict()

    def update_signal_status(self, signal_id: int, status: str) -> dict[str, object] | None:
        signal = self._signals.get(signal_id)
        if signal is None:
            return None
        signal.status = status
        return signal.to_dict()

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
        return signal.to_dict()

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

        signal_count = 0
        for item in list(inference.get("signals", [])):
            signal_id = self._allocate_signal_id()
            self._signals[signal_id] = SignalContract(
                signal_id=signal_id,
                strategy_id=None,
                symbol=str(item.get("symbol", "")),
                side=str(item.get("side", "flat")),
                score=str(item.get("score", "0")),
                confidence=str(item.get("confidence", "0")),
                target_weight=str(item.get("target_weight", "0")),
                generated_at=self._parse_timestamp(str(item.get("generated_at", datetime.now(timezone.utc).isoformat()))),
                source=SignalSource.QLIB,
            )
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

    @staticmethod
    def _parse_timestamp(value: str) -> datetime:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("generated_at must be timezone-aware")
        return parsed


signal_service = SignalService()
