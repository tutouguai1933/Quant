from __future__ import annotations

import sys
import unittest
import enum
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

if not hasattr(enum, "StrEnum"):
    class StrEnum(str, enum.Enum):
        pass

    enum.StrEnum = StrEnum

from services.api.app.domain.contracts import (  # noqa: E402
    ExecutionActionContract,
    ExecutionActionType,
    RiskDecisionContract,
    RiskDecisionStatus,
    RiskLevel,
    SignalContract,
    SignalSide,
    SignalSource,
    SignalStatus,
    StrategyStatus,
    TaskStatus,
)


class ContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.generated_at = datetime(2026, 4, 1, 6, 0, tzinfo=timezone.utc)

    def test_signal_contract_can_be_instantiated(self) -> None:
        signal = SignalContract(
            symbol="btc/usdt",
            side="long",
            score="0.870000",
            confidence="0.920000",
            target_weight="0.250000",
            generated_at=self.generated_at,
            source="qlib",
            strategy_id=1,
        )

        self.assertEqual(signal.symbol, "BTC/USDT")
        self.assertEqual(signal.side, SignalSide.LONG)
        self.assertEqual(signal.status, SignalStatus.RECEIVED)
        self.assertEqual(signal.source, SignalSource.QLIB)
        self.assertEqual(signal.to_dict()["confidence"], "0.920000")

    def test_signal_contract_rejects_invalid_confidence(self) -> None:
        with self.assertRaises(ValueError):
            SignalContract(
                symbol="BTC/USDT",
                side=SignalSide.LONG,
                score=Decimal("0.870000"),
                confidence=Decimal("1.200000"),
                target_weight=Decimal("0.250000"),
                generated_at=self.generated_at,
                source=SignalSource.QLIB,
            )

    def test_execution_action_contract_can_be_instantiated(self) -> None:
        action = ExecutionActionContract(
            action_type="open_position",
            symbol="BTC/USDT",
            side="long",
            quantity="0.0100000000",
            source_signal_id=1001,
            strategy_id=1,
            account_id=1,
        )

        self.assertEqual(action.action_type, ExecutionActionType.OPEN_POSITION)
        self.assertEqual(action.execution_engine, "freqtrade")
        self.assertEqual(action.venue, "binance")

    def test_execution_action_contract_requires_positive_quantity(self) -> None:
        with self.assertRaises(ValueError):
            ExecutionActionContract(
                action_type=ExecutionActionType.OPEN_POSITION,
                symbol="BTC/USDT",
                side=SignalSide.LONG,
                quantity=Decimal("0"),
                source_signal_id=1001,
            )

    def test_risk_decision_contract_can_be_instantiated(self) -> None:
        decision = RiskDecisionContract(
            status="block",
            reason=" strategy is paused ",
            rule_name=" strategy_status_guard ",
            evaluated_at=self.generated_at,
            level="high",
            source_signal_id=1001,
            strategy_id=1,
        )

        self.assertEqual(decision.status, RiskDecisionStatus.BLOCK)
        self.assertEqual(decision.level, RiskLevel.HIGH)
        self.assertEqual(decision.rule_name, "strategy_status_guard")

    def test_risk_decision_requires_timezone_aware_timestamp(self) -> None:
        with self.assertRaises(ValueError):
            RiskDecisionContract(
                status=RiskDecisionStatus.BLOCK,
                reason="strategy is paused",
                rule_name="strategy_status_guard",
                evaluated_at=datetime(2026, 4, 1, 6, 1),
                level=RiskLevel.HIGH,
            )

    def test_key_enum_values_match_documented_contracts(self) -> None:
        self.assertEqual(
            {item.value for item in StrategyStatus},
            {"draft", "stopped", "running", "paused", "error"},
        )
        self.assertEqual(
            {item.value for item in TaskStatus},
            {"queued", "running", "succeeded", "failed", "retrying", "cancelled"},
        )
        self.assertEqual(
            {item.value for item in RiskLevel},
            {"low", "medium", "high", "critical"},
        )
        self.assertEqual(
            {item.value for item in SignalSource},
            {"mock", "qlib", "rule-based"},
        )
        self.assertEqual(
            {item.value for item in SignalSide},
            {"long", "short", "flat"},
        )
        self.assertEqual(
            {item.value for item in SignalStatus},
            {"received", "accepted", "rejected", "dispatched", "expired", "synced"},
        )
        self.assertEqual(
            {item.value for item in ExecutionActionType},
            {"open_position", "close_position", "rebalance_position"},
        )
        self.assertEqual(
            {item.value for item in RiskDecisionStatus},
            {"allow", "warn", "block"},
        )

    def test_to_dict_contains_core_fields(self) -> None:
        signal = SignalContract(
            symbol="BTC/USDT",
            side=SignalSide.LONG,
            score=Decimal("0.870000"),
            confidence=Decimal("0.920000"),
            target_weight=Decimal("0.250000"),
            generated_at=self.generated_at,
            source=SignalSource.QLIB,
            strategy_id=1,
        )
        action = ExecutionActionContract(
            action_type=ExecutionActionType.OPEN_POSITION,
            symbol="BTC/USDT",
            side=SignalSide.LONG,
            quantity=Decimal("0.0100000000"),
            source_signal_id=1001,
            strategy_id=1,
            account_id=1,
        )
        decision = RiskDecisionContract(
            status=RiskDecisionStatus.BLOCK,
            reason="strategy is paused",
            rule_name="strategy_status_guard",
            evaluated_at=self.generated_at,
            level=RiskLevel.HIGH,
            source_signal_id=1001,
            strategy_id=1,
        )

        signal_dict = signal.to_dict()
        action_dict = action.to_dict()
        decision_dict = decision.to_dict()

        self.assertTrue(
            {"symbol", "side", "score", "confidence", "target_weight", "generated_at", "source"}.issubset(
                signal_dict
            )
        )
        self.assertEqual(signal_dict["generated_at"], "2026-04-01T06:00:00+00:00")
        self.assertTrue(
            {"action_type", "symbol", "side", "quantity", "source_signal_id"}.issubset(
                action_dict
            )
        )
        self.assertTrue(
            {"status", "reason", "rule_name", "evaluated_at"}.issubset(
                decision_dict
            )
        )


if __name__ == "__main__":
    unittest.main()
