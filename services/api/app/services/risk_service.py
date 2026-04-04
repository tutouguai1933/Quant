"""Minimal risk gate for Quant phase 1."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from services.api.app.domain.contracts import RiskDecisionContract, RiskDecisionStatus, RiskLevel
from services.api.app.services.signal_service import signal_service
from services.api.app.services.sync_service import sync_service


@dataclass(slots=True)
class RiskEventRecord:
    id: int
    signal_id: int | None
    strategy_id: int | None
    rule_name: str
    level: str
    decision: str
    reason: str
    event_time: str
    resolved_at: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "signal_id": self.signal_id,
            "strategy_id": self.strategy_id,
            "rule_name": self.rule_name,
            "level": self.level,
            "decision": self.decision,
            "reason": self.reason,
            "event_time": self.event_time,
            "resolved_at": self.resolved_at,
        }


class RiskService:
    """Implements the first set of hard risk rules required by Task 7."""

    def __init__(self) -> None:
        self.global_pause = False
        self.max_symbol_exposure = Decimal("0.35")
        self.account_total_risk_threshold = Decimal("0.80")
        self.warn_total_risk_threshold = Decimal("0.70")
        self._events: dict[int, RiskEventRecord] = {}
        self._next_event_id = 1

    def evaluate_signal(self, signal_id: int, strategy_context_id: int | None = None) -> dict[str, object]:
        signal = signal_service.get_signal(signal_id)
        if signal is None:
            raise ValueError(f"signal {signal_id} not found")

        strategy_id = signal.get("strategy_id")
        effective_strategy_id = strategy_id if strategy_id is not None else strategy_context_id
        strategy = sync_service.get_strategy(int(effective_strategy_id)) if effective_strategy_id is not None else None

        decision = self._apply_rules(signal, strategy, effective_strategy_id)
        if decision["status"] in {"warn", "block"}:
            self._record_event(
                signal_id=signal_id,
                strategy_id=effective_strategy_id,
                rule_name=str(decision["rule_name"]),
                level=str(decision["level"]),
                decision=str(decision["status"]),
                reason=str(decision["reason"]),
                event_time=str(decision["evaluated_at"]),
            )

        if decision["status"] == "block":
            signal_service.update_signal_status(signal_id, "rejected")
        else:
            signal_service.update_signal_status(signal_id, "accepted")

        return decision

    def list_events(self, limit: int = 100) -> list[dict[str, object]]:
        ordered = sorted(self._events.values(), key=lambda item: item.id, reverse=True)
        return [item.to_dict() for item in ordered[:limit]]

    def get_event(self, event_id: int) -> dict[str, object] | None:
        event = self._events.get(event_id)
        return None if event is None else event.to_dict()

    def set_global_pause(self, paused: bool) -> dict[str, object]:
        self.global_pause = paused
        return {"global_pause": self.global_pause}

    def _apply_rules(
        self,
        signal: dict[str, object],
        strategy: dict[str, object] | None,
        strategy_context_id: int | None,
    ) -> dict[str, object]:
        if self.global_pause:
            return self._decision(
                "block",
                "global pause is enabled",
                "global_pause_guard",
                "critical",
                signal,
                strategy_context_id,
            )

        if strategy is None:
            return self._decision(
                "block",
                "strategy not found",
                "strategy_exists_guard",
                "high",
                signal,
                strategy_context_id,
            )

        if strategy["status"] != "running":
            return self._decision(
                "block",
                "strategy is not running",
                "strategy_status_guard",
                "high",
                signal,
                strategy_context_id,
            )

        target_weight = Decimal(str(signal["target_weight"])).copy_abs()
        if target_weight > self.max_symbol_exposure:
            return self._decision(
                "block",
                f"target weight {target_weight} exceeds symbol exposure limit {self.max_symbol_exposure}",
                "max_symbol_exposure_guard",
                "high",
                signal,
                strategy_context_id,
            )

        current_risk = Decimal(len(sync_service.list_positions(limit=100))) * Decimal("0.25")
        projected_risk = current_risk + target_weight
        if projected_risk > self.account_total_risk_threshold:
            return self._decision(
                "block",
                f"projected risk {projected_risk} exceeds account threshold {self.account_total_risk_threshold}",
                "account_total_risk_guard",
                "high",
                signal,
                strategy_context_id,
            )
        if projected_risk > self.warn_total_risk_threshold:
            return self._decision(
                "warn",
                f"projected risk {projected_risk} is near account threshold {self.account_total_risk_threshold}",
                "account_total_risk_warn",
                "medium",
                signal,
                strategy_context_id,
            )
        return self._decision("allow", "risk checks passed", "default_allow", "low", signal, strategy_context_id)

    def _decision(
        self,
        status: str,
        reason: str,
        rule_name: str,
        level: str,
        signal: dict[str, object],
        strategy_context_id: int | None = None,
    ) -> dict[str, object]:
        contract = RiskDecisionContract(
            status=RiskDecisionStatus(status),
            reason=reason,
            rule_name=rule_name,
            evaluated_at=signal_service._parse_timestamp(str(signal["received_at"])),
            level=RiskLevel(level),
            source_signal_id=signal.get("signal_id"),
            strategy_id=signal.get("strategy_id") or strategy_context_id,
        )
        return contract.to_dict()

    def _record_event(
        self,
        signal_id: int | None,
        strategy_id: int | None,
        rule_name: str,
        level: str,
        decision: str,
        reason: str,
        event_time: str,
    ) -> dict[str, object]:
        event = RiskEventRecord(
            id=self._next_event_id,
            signal_id=signal_id,
            strategy_id=strategy_id,
            rule_name=rule_name,
            level=level,
            decision=decision,
            reason=reason,
            event_time=event_time,
        )
        self._events[event.id] = event
        self._next_event_id += 1
        return event.to_dict()


risk_service = RiskService()
