from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.api.app.services.validation_workflow_service import ValidationWorkflowService  # noqa: E402


class ValidationWorkflowServiceTests(unittest.TestCase):
    def test_build_report_backfills_current_cycle_execution_entries(self) -> None:
        service = ValidationWorkflowService(
            research_reader=_FakeResearchReader(),
            sync_reader=_MatchedSyncReader(),
            scheduler=_MatchedScheduler(),
        )

        with patch("services.api.app.services.validation_workflow_service.automation_service.get_state", return_value={"mode": "auto_dry_run"}), patch(
            "services.api.app.services.validation_workflow_service.automation_service.build_health_summary",
            return_value={},
        ):
            report = service.build_report(limit=5)

        execution_backfill = dict(report["execution_comparison"]["execution_backfill"])
        self.assertEqual(execution_backfill["order"]["freshness"], "current_cycle")
        self.assertEqual(execution_backfill["position"]["freshness"], "current_cycle")
        self.assertEqual(execution_backfill["sync"]["freshness"], "current_cycle")
        self.assertEqual(execution_backfill["order"]["symbol"], "ETHUSDT")
        self.assertEqual(execution_backfill["position"]["symbol"], "ETHUSDT")
        self.assertEqual(execution_backfill["sync"]["sync_status"], "succeeded")

    def test_build_report_marks_stale_or_missing_execution_entries(self) -> None:
        service = ValidationWorkflowService(
            research_reader=_FakeResearchReader(),
            sync_reader=_StaleSyncReader(),
            scheduler=_StaleScheduler(),
        )

        with patch("services.api.app.services.validation_workflow_service.automation_service.get_state", return_value={"mode": "manual"}), patch(
            "services.api.app.services.validation_workflow_service.automation_service.build_health_summary",
            return_value={},
        ):
            report = service.build_report(limit=5)

        execution_backfill = dict(report["execution_comparison"]["execution_backfill"])
        self.assertEqual(report["execution_comparison"]["status"], "attention_required")
        self.assertEqual(execution_backfill["order"]["freshness"], "stale")
        self.assertEqual(execution_backfill["position"]["freshness"], "stale")
        self.assertEqual(execution_backfill["sync"]["freshness"], "current_cycle")
        self.assertEqual(execution_backfill["sync"]["sync_status"], "failed")
        self.assertIn("BTCUSDT", execution_backfill["order"]["detail"])

    def test_build_report_keeps_same_symbol_stale_without_current_sync_anchor(self) -> None:
        service = ValidationWorkflowService(
            research_reader=_FakeResearchReader(),
            sync_reader=_SameSymbolButStaleSyncReader(),
            scheduler=_MissingSyncScheduler(),
        )

        with patch("services.api.app.services.validation_workflow_service.automation_service.get_state", return_value={"mode": "manual"}), patch(
            "services.api.app.services.validation_workflow_service.automation_service.build_health_summary",
            return_value={},
        ):
            report = service.build_report(limit=5)

        execution_backfill = dict(report["execution_comparison"]["execution_backfill"])
        self.assertEqual(report["execution_comparison"]["status"], "unavailable")
        self.assertEqual(execution_backfill["order"]["freshness"], "stale")
        self.assertEqual(execution_backfill["position"]["freshness"], "stale")
        self.assertEqual(execution_backfill["sync"]["freshness"], "stale")
        self.assertIn("旧订单", execution_backfill["order"]["detail"])

    def test_build_report_keeps_same_symbol_stale_when_sync_failed_without_timestamps(self) -> None:
        service = ValidationWorkflowService(
            research_reader=_FakeResearchReader(),
            sync_reader=_SameSymbolFailedWithoutTimestampSyncReader(),
            scheduler=_FailedSameSymbolScheduler(),
        )

        with patch("services.api.app.services.validation_workflow_service.automation_service.get_state", return_value={"mode": "manual"}), patch(
            "services.api.app.services.validation_workflow_service.automation_service.build_health_summary",
            return_value={},
        ):
            report = service.build_report(limit=5)

        execution_backfill = dict(report["execution_comparison"]["execution_backfill"])
        self.assertEqual(report["execution_comparison"]["status"], "unavailable")
        self.assertEqual(execution_backfill["order"]["freshness"], "stale")
        self.assertEqual(execution_backfill["position"]["freshness"], "stale")
        self.assertEqual(execution_backfill["sync"]["freshness"], "current_cycle")
        self.assertEqual(execution_backfill["sync"]["sync_status"], "failed")

    def test_build_report_keeps_same_symbol_stale_when_sync_retrying_without_timestamps(self) -> None:
        service = ValidationWorkflowService(
            research_reader=_FakeResearchReader(),
            sync_reader=_SameSymbolRetryingWithoutTimestampSyncReader(),
            scheduler=_RetryingSameSymbolScheduler(),
        )

        with patch("services.api.app.services.validation_workflow_service.automation_service.get_state", return_value={"mode": "auto_dry_run"}), patch(
            "services.api.app.services.validation_workflow_service.automation_service.build_health_summary",
            return_value={},
        ):
            report = service.build_report(limit=5)

        execution_backfill = dict(report["execution_comparison"]["execution_backfill"])
        self.assertEqual(report["execution_comparison"]["status"], "unavailable")
        self.assertEqual(execution_backfill["order"]["freshness"], "stale")
        self.assertEqual(execution_backfill["position"]["freshness"], "stale")
        self.assertEqual(execution_backfill["sync"]["freshness"], "current_cycle")
        self.assertEqual(execution_backfill["sync"]["sync_status"], "retrying")

    def test_build_report_keeps_timestamped_same_symbol_stale_when_sync_retrying(self) -> None:
        service = ValidationWorkflowService(
            research_reader=_FakeResearchReader(),
            sync_reader=_SameSymbolRetryingWithTimestampSyncReader(),
            scheduler=_RetryingSameSymbolScheduler(),
        )

        with patch("services.api.app.services.validation_workflow_service.automation_service.get_state", return_value={"mode": "auto_dry_run"}), patch(
            "services.api.app.services.validation_workflow_service.automation_service.build_health_summary",
            return_value={},
        ):
            report = service.build_report(limit=5)

        execution_backfill = dict(report["execution_comparison"]["execution_backfill"])
        self.assertEqual(report["execution_comparison"]["status"], "unavailable")
        self.assertEqual(execution_backfill["order"]["freshness"], "stale")
        self.assertEqual(execution_backfill["position"]["freshness"], "stale")
        self.assertEqual(execution_backfill["sync"]["sync_status"], "retrying")

    def test_build_report_prefers_failed_sync_anchor_over_previous_success(self) -> None:
        service = ValidationWorkflowService(
            research_reader=_FakeResearchReader(),
            sync_reader=_SameSymbolFailedAfterPreviousSuccessSyncReader(),
            scheduler=_FailedSameSymbolScheduler(),
        )

        with patch("services.api.app.services.validation_workflow_service.automation_service.get_state", return_value={"mode": "manual"}), patch(
            "services.api.app.services.validation_workflow_service.automation_service.build_health_summary",
            return_value={},
        ):
            report = service.build_report(limit=5)

        execution_backfill = dict(report["execution_comparison"]["execution_backfill"])
        self.assertEqual(report["execution_comparison"]["status"], "unavailable")
        self.assertEqual(execution_backfill["order"]["freshness"], "stale")
        self.assertEqual(execution_backfill["position"]["freshness"], "stale")
        self.assertEqual(execution_backfill["sync"]["finished_at"], "2026-04-11T10:00:00+00:00")


class _FakeResearchReader:
    def get_factory_report(self) -> dict[str, object]:
        return {
            "overview": {
                "recommended_symbol": "ETHUSDT",
                "recommended_action": "enter_dry_run",
            },
            "candidates": [
                {
                    "symbol": "ETHUSDT",
                    "backtest": {
                        "net_return_pct": "8.10",
                        "sharpe": "1.12",
                        "win_rate": "0.58",
                    },
                }
            ],
            "reviews": {
                "research": {
                    "result": "candidate_ready",
                    "next_action": "enter_dry_run",
                    "what_happened": "研究已通过",
                }
            },
        }


class _MatchedSyncReader:
    def sync_task_state(self, limit: int = 100) -> dict[str, object]:
        return {
            "balances": [],
            "orders": [
                {
                    "id": "order-eth-1",
                    "symbol": "ETHUSDT",
                    "side": "buy",
                    "status": "filled",
                    "executedQty": "0.01",
                }
            ],
            "positions": [
                {
                    "id": "position-eth-1",
                    "symbol": "ETHUSDT",
                    "side": "long",
                    "quantity": "0.01",
                }
            ],
            "source": "binance-account-sync",
            "truth_source": "binance",
        }

    def get_execution_health_summary(self, *, task_health: dict[str, object] | None = None, automation_state: dict[str, object] | None = None) -> dict[str, object]:
        return {
            "runtime_mode": "dry-run",
            "backend": "memory",
            "connection_status": "connected",
            "latest_sync_status": "succeeded",
            "latest_review_status": "succeeded",
            "latest_successful_sync_at": "2026-04-11T09:00:00+00:00",
            "latest_failed_sync": {},
        }


class _StaleSyncReader:
    def sync_task_state(self, limit: int = 100) -> dict[str, object]:
        return {
            "balances": [],
            "orders": [
                {
                    "id": "order-btc-1",
                    "symbol": "BTCUSDT",
                    "side": "buy",
                    "status": "filled",
                    "executedQty": "0.02",
                }
            ],
            "positions": [
                {
                    "id": "position-btc-1",
                    "symbol": "BTCUSDT",
                    "side": "long",
                    "quantity": "0.02",
                }
            ],
            "source": "binance-account-sync",
            "truth_source": "binance",
        }

    def get_execution_health_summary(self, *, task_health: dict[str, object] | None = None, automation_state: dict[str, object] | None = None) -> dict[str, object]:
        return {
            "runtime_mode": "manual",
            "backend": "rest",
            "connection_status": "connected",
            "latest_sync_status": "failed",
            "latest_review_status": "waiting",
            "latest_successful_sync_at": "",
            "latest_failed_sync": {
                "finished_at": "2026-04-11T09:05:00+00:00",
                "error_message": "binance timeout",
            },
        }


class _SameSymbolButStaleSyncReader:
    def sync_task_state(self, limit: int = 100) -> dict[str, object]:
        return {
            "balances": [],
            "orders": [
                {
                    "id": "order-eth-old",
                    "symbol": "ETHUSDT",
                    "side": "buy",
                    "status": "filled",
                    "executedQty": "0.01",
                    "updatedAt": "2026-04-10T09:00:00+00:00",
                }
            ],
            "positions": [
                {
                    "id": "position-eth-old",
                    "symbol": "ETH",
                    "side": "long",
                    "quantity": "0.01",
                }
            ],
            "source": "binance-account-sync",
            "truth_source": "binance",
        }

    def get_execution_health_summary(self, *, task_health: dict[str, object] | None = None, automation_state: dict[str, object] | None = None) -> dict[str, object]:
        return {
            "runtime_mode": "dry-run",
            "backend": "memory",
            "connection_status": "connected",
            "latest_sync_status": "unknown",
            "latest_review_status": "waiting",
            "latest_successful_sync_at": "",
            "latest_failed_sync": {},
        }


class _SameSymbolFailedWithoutTimestampSyncReader:
    def sync_task_state(self, limit: int = 100) -> dict[str, object]:
        return {
            "balances": [],
            "orders": [
                {
                    "id": "order-eth-failed",
                    "symbol": "ETHUSDT",
                    "side": "buy",
                    "status": "filled",
                    "executedQty": "0.01",
                }
            ],
            "positions": [
                {
                    "id": "position-eth-failed",
                    "symbol": "ETHUSDT",
                    "side": "long",
                    "quantity": "0.01",
                }
            ],
            "source": "binance-account-sync",
            "truth_source": "binance",
        }

    def get_execution_health_summary(self, *, task_health: dict[str, object] | None = None, automation_state: dict[str, object] | None = None) -> dict[str, object]:
        return {
            "runtime_mode": "dry-run",
            "backend": "memory",
            "connection_status": "connected",
            "latest_sync_status": "failed",
            "latest_review_status": "waiting",
            "latest_successful_sync_at": "",
            "latest_failed_sync": {
                "finished_at": "2026-04-11T09:15:00+00:00",
                "error_message": "network timeout",
            },
        }


class _SameSymbolRetryingWithoutTimestampSyncReader:
    def sync_task_state(self, limit: int = 100) -> dict[str, object]:
        return {
            "balances": [],
            "orders": [
                {
                    "id": "order-eth-retrying",
                    "symbol": "ETHUSDT",
                    "side": "buy",
                    "status": "filled",
                    "executedQty": "0.01",
                }
            ],
            "positions": [
                {
                    "id": "position-eth-retrying",
                    "symbol": "ETHUSDT",
                    "side": "long",
                    "quantity": "0.01",
                }
            ],
            "source": "binance-account-sync",
            "truth_source": "binance",
        }

    def get_execution_health_summary(self, *, task_health: dict[str, object] | None = None, automation_state: dict[str, object] | None = None) -> dict[str, object]:
        return {
            "runtime_mode": "dry-run",
            "backend": "memory",
            "connection_status": "connected",
            "latest_sync_status": "retrying",
            "latest_review_status": "waiting",
            "latest_successful_sync_at": "",
            "latest_failed_sync": {},
        }


class _SameSymbolRetryingWithTimestampSyncReader:
    def sync_task_state(self, limit: int = 100) -> dict[str, object]:
        return {
            "balances": [],
            "orders": [
                {
                    "id": "order-eth-retrying-ts",
                    "symbol": "ETHUSDT",
                    "side": "buy",
                    "status": "filled",
                    "executedQty": "0.01",
                    "updatedAt": "2026-04-11T09:20:00+00:00",
                }
            ],
            "positions": [
                {
                    "id": "position-eth-retrying-ts",
                    "symbol": "ETHUSDT",
                    "side": "long",
                    "quantity": "0.01",
                    "updatedAt": "2026-04-11T09:20:00+00:00",
                }
            ],
            "source": "binance-account-sync",
            "truth_source": "binance",
        }

    def get_execution_health_summary(self, *, task_health: dict[str, object] | None = None, automation_state: dict[str, object] | None = None) -> dict[str, object]:
        return {
            "runtime_mode": "dry-run",
            "backend": "memory",
            "connection_status": "connected",
            "latest_sync_status": "retrying",
            "latest_review_status": "waiting",
            "latest_successful_sync_at": "2026-04-11T09:00:00+00:00",
            "latest_failed_sync": {},
        }


class _SameSymbolFailedAfterPreviousSuccessSyncReader:
    def sync_task_state(self, limit: int = 100) -> dict[str, object]:
        return {
            "balances": [],
            "orders": [
                {
                    "id": "order-eth-mixed-anchor",
                    "symbol": "ETHUSDT",
                    "side": "buy",
                    "status": "filled",
                    "executedQty": "0.01",
                    "updatedAt": "2026-04-11T09:10:00+00:00",
                }
            ],
            "positions": [
                {
                    "id": "position-eth-mixed-anchor",
                    "symbol": "ETHUSDT",
                    "side": "long",
                    "quantity": "0.01",
                    "updatedAt": "2026-04-11T09:10:00+00:00",
                }
            ],
            "source": "binance-account-sync",
            "truth_source": "binance",
        }

    def get_execution_health_summary(self, *, task_health: dict[str, object] | None = None, automation_state: dict[str, object] | None = None) -> dict[str, object]:
        return {
            "runtime_mode": "dry-run",
            "backend": "memory",
            "connection_status": "connected",
            "latest_sync_status": "failed",
            "latest_review_status": "waiting",
            "latest_successful_sync_at": "2026-04-11T09:00:00+00:00",
            "latest_failed_sync": {
                "finished_at": "2026-04-11T10:00:00+00:00",
                "error_message": "timeout after success",
            },
        }


class _MatchedScheduler:
    def list_tasks(self, limit: int = 10) -> list[dict[str, object]]:
        return [
            {
                "task_type": "sync",
                "status": "succeeded",
                "finished_at": "2026-04-11T09:00:00+00:00",
                "payload": {},
                "result": {"status": "succeeded"},
            },
            {
                "task_type": "review",
                "status": "succeeded",
                "finished_at": "2026-04-11T09:02:00+00:00",
                "payload": {},
                "result": {"status": "succeeded"},
            },
        ][:limit]

    def get_health_summary(self) -> dict[str, object]:
        return {
            "latest_status_by_type": {
                "sync": "succeeded",
                "review": "succeeded",
            },
            "latest_success_by_type": {
                "sync": "2026-04-11T09:00:00+00:00",
                "review": "2026-04-11T09:02:00+00:00",
            },
            "latest_failure_by_type": {},
        }


class _StaleScheduler:
    def list_tasks(self, limit: int = 10) -> list[dict[str, object]]:
        return [
            {
                "task_type": "sync",
                "status": "failed",
                "finished_at": "2026-04-11T09:05:00+00:00",
                "payload": {},
                "result": {"status": "failed", "detail": "binance timeout"},
                "error_message": "binance timeout",
            },
            {
                "task_type": "review",
                "status": "waiting",
                "finished_at": "",
                "payload": {},
                "result": {"status": "waiting"},
            },
        ][:limit]

    def get_health_summary(self) -> dict[str, object]:
        return {
            "latest_status_by_type": {
                "sync": "failed",
                "review": "waiting",
            },
            "latest_success_by_type": {},
            "latest_failure_by_type": {
                "sync": {
                    "finished_at": "2026-04-11T09:05:00+00:00",
                    "error_message": "binance timeout",
                }
            },
        }


class _MissingSyncScheduler:
    def list_tasks(self, limit: int = 10) -> list[dict[str, object]]:
        return [
            {
                "task_type": "review",
                "status": "waiting",
                "finished_at": "",
                "payload": {},
                "result": {"status": "waiting"},
            }
        ][:limit]

    def get_health_summary(self) -> dict[str, object]:
        return {
            "latest_status_by_type": {
                "sync": "unknown",
                "review": "waiting",
            },
            "latest_success_by_type": {},
            "latest_failure_by_type": {},
        }


class _FailedSameSymbolScheduler:
    def list_tasks(self, limit: int = 10) -> list[dict[str, object]]:
        return [
            {
                "task_type": "sync",
                "status": "failed",
                "finished_at": "2026-04-11T09:15:00+00:00",
                "payload": {},
                "result": {"status": "failed", "detail": "network timeout"},
                "error_message": "network timeout",
            }
        ][:limit]

    def get_health_summary(self) -> dict[str, object]:
        return {
            "latest_status_by_type": {
                "sync": "failed",
                "review": "waiting",
            },
            "latest_success_by_type": {},
            "latest_failure_by_type": {
                "sync": {
                    "finished_at": "2026-04-11T09:15:00+00:00",
                    "error_message": "network timeout",
                }
            },
        }


class _RetryingSameSymbolScheduler:
    def list_tasks(self, limit: int = 10) -> list[dict[str, object]]:
        return [
            {
                "task_type": "sync",
                "status": "retrying",
                "finished_at": "",
                "payload": {},
                "result": {"status": "retrying", "detail": "retry in progress"},
            }
        ][:limit]

    def get_health_summary(self) -> dict[str, object]:
        return {
            "latest_status_by_type": {
                "sync": "retrying",
                "review": "waiting",
            },
            "latest_success_by_type": {},
            "latest_failure_by_type": {},
        }


if __name__ == "__main__":
    unittest.main()
