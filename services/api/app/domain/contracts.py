"""Core contracts for the Quant phase-1 control plane.

The module stays stdlib-only so the repository can define stable contracts
before dependency management is approved by the user.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any

try:
    from enum import StrEnum as BaseStrEnum
except ImportError:
    class BaseStrEnum(str, Enum):
        """Python 3.10 compatible fallback for StrEnum."""


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


def _serialize_value(value: object) -> object:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, BaseStrEnum):
        return value.value
    if isinstance(value, dict):
        return {key: _serialize_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_serialize_value(item) for item in value]
    return value


def _ensure_aware(timestamp: datetime, field_name: str) -> None:
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


def _coerce_decimal(value: Decimal | int | float | str, field_name: str) -> Decimal:
    try:
        return Decimal(str(value))
    except Exception as exc:  # pragma: no cover - defensive conversion guard
        raise ValueError(f"{field_name} must be decimal-compatible") from exc


def _coerce_positive_int(value: int | None, field_name: str) -> int | None:
    if value is not None and value <= 0:
        raise ValueError(f"{field_name} must be greater than 0 when provided")
    return value


def _normalize_symbol(symbol: str) -> str:
    normalized = symbol.strip().upper()
    if not normalized:
        raise ValueError("symbol must not be empty")
    return normalized


def _serialize_dict(data: dict[str, Any]) -> dict[str, object]:
    return {key: _serialize_value(value) for key, value in data.items()}


class StrategyStatus(BaseStrEnum):
    DRAFT = "draft"
    STOPPED = "stopped"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"


class TaskStatus(BaseStrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    RETRYING = "retrying"
    CANCELLED = "cancelled"


class RiskLevel(BaseStrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SignalSource(BaseStrEnum):
    MOCK = "mock"
    QLIB = "qlib"
    RULE_BASED = "rule-based"


class SignalSide(BaseStrEnum):
    LONG = "long"
    SHORT = "short"
    FLAT = "flat"


class SignalStatus(BaseStrEnum):
    RECEIVED = "received"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    DISPATCHED = "dispatched"
    EXPIRED = "expired"
    SYNCED = "synced"


class ExecutionActionType(BaseStrEnum):
    OPEN_POSITION = "open_position"
    CLOSE_POSITION = "close_position"
    REBALANCE_POSITION = "rebalance_position"


class RiskDecisionStatus(BaseStrEnum):
    ALLOW = "allow"
    WARN = "warn"
    BLOCK = "block"


@dataclass(slots=True)
class SignalContract:
    symbol: str
    side: SignalSide
    score: Decimal
    confidence: Decimal
    target_weight: Decimal
    generated_at: datetime
    source: SignalSource
    strategy_id: int | None = None
    status: SignalStatus = SignalStatus.RECEIVED
    signal_id: int | None = None
    received_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.symbol = _normalize_symbol(self.symbol)
        self.side = SignalSide(self.side)
        self.source = SignalSource(self.source)
        self.status = SignalStatus(self.status)
        self.score = _coerce_decimal(self.score, "score")
        self.confidence = _coerce_decimal(self.confidence, "confidence")
        self.target_weight = _coerce_decimal(self.target_weight, "target_weight")
        _ensure_aware(self.generated_at, "generated_at")
        _ensure_aware(self.received_at, "received_at")
        self.strategy_id = _coerce_positive_int(self.strategy_id, "strategy_id")
        self.signal_id = _coerce_positive_int(self.signal_id, "signal_id")
        if self.score < Decimal("0"):
            raise ValueError("score must be greater than or equal to 0")
        if not (Decimal("0") <= self.confidence <= Decimal("1")):
            raise ValueError("confidence must be between 0 and 1")
        if not (Decimal("-1") <= self.target_weight <= Decimal("1")):
            raise ValueError("target_weight must be between -1 and 1")

    def to_dict(self) -> dict[str, object]:
        return _serialize_dict(asdict(self))


@dataclass(slots=True)
class ExecutionActionContract:
    action_type: ExecutionActionType
    symbol: str
    side: SignalSide
    quantity: Decimal
    source_signal_id: int
    strategy_id: int | None = None
    account_id: int | None = None
    execution_engine: str = "freqtrade"
    venue: str = "binance"
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.action_type = ExecutionActionType(self.action_type)
        self.symbol = _normalize_symbol(self.symbol)
        self.side = SignalSide(self.side)
        self.quantity = _coerce_decimal(self.quantity, "quantity")
        _ensure_aware(self.created_at, "created_at")
        _coerce_positive_int(self.source_signal_id, "source_signal_id")
        self.strategy_id = _coerce_positive_int(self.strategy_id, "strategy_id")
        self.account_id = _coerce_positive_int(self.account_id, "account_id")
        if self.quantity <= 0:
            raise ValueError("quantity must be greater than 0")
        if self.execution_engine != "freqtrade":
            raise ValueError("execution_engine must be 'freqtrade' in phase 1")
        if self.venue != "binance":
            raise ValueError("venue must be 'binance' in phase 1")

    def to_dict(self) -> dict[str, object]:
        return _serialize_dict(asdict(self))


@dataclass(slots=True)
class RiskDecisionContract:
    status: RiskDecisionStatus
    reason: str
    rule_name: str
    evaluated_at: datetime
    level: RiskLevel | None = None
    source_signal_id: int | None = None
    strategy_id: int | None = None

    def __post_init__(self) -> None:
        self.status = RiskDecisionStatus(self.status)
        if self.level is None:
            self.level = RiskLevel.MEDIUM
        else:
            self.level = RiskLevel(self.level)
        _ensure_aware(self.evaluated_at, "evaluated_at")
        self.reason = self.reason.strip()
        self.rule_name = self.rule_name.strip()
        self.source_signal_id = _coerce_positive_int(self.source_signal_id, "source_signal_id")
        self.strategy_id = _coerce_positive_int(self.strategy_id, "strategy_id")
        if not self.reason:
            raise ValueError("reason must not be empty")
        if not self.rule_name:
            raise ValueError("rule_name must not be empty")

    def to_dict(self) -> dict[str, object]:
        return _serialize_dict(asdict(self))
