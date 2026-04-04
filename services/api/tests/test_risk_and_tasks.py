from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import services.api.app.routes.auth as auth_route  # noqa: E402
import services.api.app.routes.risk_events as risk_events_route  # noqa: E402
import services.api.app.routes.signals as signals_route  # noqa: E402
import services.api.app.routes.strategies as strategies_route  # noqa: E402
import services.api.app.routes.tasks as tasks_route  # noqa: E402
import services.api.app.services.execution_service as execution_service_module  # noqa: E402
import services.api.app.services.risk_service as risk_service_module  # noqa: E402
import services.api.app.services.sync_service as sync_service_module  # noqa: E402
import services.api.app.tasks.scheduler as scheduler_module  # noqa: E402
from services.api.app.adapters.freqtrade.client import freqtrade_client  # noqa: E402
from services.api.app.routes.auth import login  # noqa: E402
from services.api.app.routes.risk_events import list_risk_events  # noqa: E402
from services.api.app.routes.signals import get_signal, run_signal_pipeline  # noqa: E402
from services.api.app.routes.strategies import dispatch_latest_signal, start_strategy  # noqa: E402
from services.api.app.routes.tasks import get_validation_review, retry_task, run_reconcile_task, run_review_task, run_sync_task  # noqa: E402
from services.api.app.services.auth_service import auth_service  # noqa: E402
from services.api.app.services.risk_service import risk_service  # noqa: E402
from services.api.app.services.signal_service import signal_service  # noqa: E402
from services.api.app.tasks.scheduler import task_scheduler  # noqa: E402


class RiskAndTaskTests(unittest.TestCase):
    def setUp(self) -> None:
        auth_service.__init__()
        freqtrade_client.__init__()
        signal_service.__init__()
        risk_service.__init__()
        task_scheduler.__init__()
        auth_route.auth_service = auth_service
        signals_route.signal_service = signal_service
        risk_events_route.auth_service = auth_service
        strategies_route.signal_service = signal_service
        strategies_route.risk_service = risk_service
        strategies_route.freqtrade_client = freqtrade_client
        strategies_route.auth_service = auth_service
        strategies_route.task_scheduler = task_scheduler
        tasks_route.auth_service = auth_service
        tasks_route.task_scheduler = task_scheduler
        risk_events_route.risk_service = risk_service
        risk_service_module.signal_service = signal_service
        sync_service_module.freqtrade_client = freqtrade_client
        execution_service_module.freqtrade_client = freqtrade_client
        execution_service_module.signal_service = signal_service
        scheduler_module.signal_service = signal_service

    @staticmethod
    def _login_token() -> str:
        response = login(username="admin", password="1933")
        return str(response["data"]["item"]["token"])

    def test_blocked_dispatch_creates_risk_event_and_rejects_signal(self) -> None:
        token = self._login_token()
        run_signal_pipeline("mock")

        response = dispatch_latest_signal(1, token=token)

        self.assertEqual(response["error"]["code"], "risk_blocked")
        self.assertEqual(list_risk_events(token=token)["data"]["items"][0]["rule_name"], "strategy_status_guard")
        self.assertEqual(get_signal(1)["data"]["item"]["status"], "rejected")

    def test_allowed_dispatch_runs_sync_and_marks_signal_synced(self) -> None:
        token = self._login_token()
        run_signal_pipeline("mock")
        start_strategy(1, token=token)

        response = dispatch_latest_signal(1, token=token)

        self.assertIsNone(response["error"])
        self.assertEqual(response["data"]["risk_task"]["status"], "succeeded")
        self.assertEqual(response["data"]["sync_task"]["status"], "succeeded")
        self.assertEqual(get_signal(1)["data"]["item"]["status"], "synced")

    def test_retry_task_keeps_retrying_history_visible(self) -> None:
        token = self._login_token()
        failed = run_reconcile_task(simulate_failure=True, token=token)
        task_id = failed["data"]["item"]["id"]

        retried = retry_task(task_id, clear_failure=True, token=token)

        self.assertEqual(failed["data"]["item"]["status"], "failed")
        self.assertEqual(retried["data"]["item"]["status"], "succeeded")
        self.assertIn("retrying", retried["data"]["item"]["status_history"])

    def test_live_sync_task_uses_binance_account_snapshot(self) -> None:
        class ExplodingFreqtradeClient:
            def get_snapshot(self) -> dict[str, object]:
                raise TimeoutError("timed out")

        class FakeAccountSyncService:
            def list_balances(self, limit: int = 100) -> list[dict[str, object]]:
                return [{"asset": "USDT", "available": "19.00000000", "locked": "0.00000000"}]

            def list_orders(self, limit: int = 100, symbols: tuple[str, ...] | None = None) -> list[dict[str, object]]:
                return [{"id": "14136461324", "symbol": "DOGEUSDT", "status": "FILLED"}]

            def list_positions(self, limit: int = 100) -> list[dict[str, object]]:
                return [{"id": "position-DOGE", "symbol": "DOGE", "side": "long", "quantity": "12.00000000"}]

        token = self._login_token()
        with patch.dict(
            os.environ,
            {"QUANT_RUNTIME_MODE": "live", "BINANCE_API_KEY": "k", "BINANCE_API_SECRET": "s"},
            clear=False,
        ), patch.object(sync_service_module, "freqtrade_client", ExplodingFreqtradeClient()), patch.object(
            sync_service_module, "account_sync_service", FakeAccountSyncService()
        ), patch.object(scheduler_module, "sync_service", sync_service_module.sync_service):
            response = run_sync_task(token=token)

        self.assertEqual(response["data"]["item"]["status"], "succeeded")
        self.assertEqual(response["data"]["item"]["result"]["orders"][0]["symbol"], "DOGEUSDT")
        self.assertEqual(response["data"]["item"]["result"]["positions"][0]["symbol"], "DOGE")

    def test_live_dispatch_marks_signal_synced_when_expected_order_is_confirmed(self) -> None:
        class FakeAccountSyncService:
            def list_balances(self, limit: int = 100) -> list[dict[str, object]]:
                return [{"asset": "USDT", "available": "19.00000000", "locked": "0.00000000"}]

            def list_orders(self, limit: int = 100, symbols: tuple[str, ...] | None = None) -> list[dict[str, object]]:
                return [
                    {
                        "id": "14136461324",
                        "symbol": "DOGEUSDT",
                        "status": "FILLED",
                        "side": "buy",
                        "updateTime": 1712044800000,
                    }
                ]

            def list_positions(self, limit: int = 100) -> list[dict[str, object]]:
                return [{"id": "position-DOGE", "symbol": "DOGE", "side": "long", "quantity": "12.00000000"}]

        token = self._login_token()
        run_signal_pipeline("mock")
        start_strategy(1, token=token)

        fake_dispatch_result = {
            "action": {"symbol": "DOGE/USDT", "side": "long"},
            "order": {
                "id": "trade-1",
                "venueOrderId": "14136461324",
                "symbol": "DOGE/USDT",
                "status": "closed",
                "runtimeMode": "live",
                "updatedAt": "2026-04-02T00:00:00+00:00",
            },
            "runtime": {"mode": "live", "backend": "rest", "connection_status": "connected"},
        }
        with patch.dict(
            os.environ,
            {
                "QUANT_RUNTIME_MODE": "live",
                "BINANCE_API_KEY": "k",
                "BINANCE_API_SECRET": "s",
                "QUANT_LIVE_ALLOWED_SYMBOLS": "DOGEUSDT",
            },
            clear=False,
        ), patch.object(sync_service_module, "account_sync_service", FakeAccountSyncService()), patch.object(
            scheduler_module, "sync_service", sync_service_module.sync_service
        ), patch.object(
            strategies_route.execution_service, "dispatch_signal", return_value=fake_dispatch_result
        ):
            response = dispatch_latest_signal(1, token=token)

        self.assertIsNone(response["error"])
        self.assertEqual(response["data"]["sync_task"]["status"], "succeeded")
        self.assertEqual(response["data"]["sync_task"]["result"]["orders"][0]["status"], "FILLED")
        self.assertEqual(get_signal(1)["data"]["item"]["status"], "synced")

    def test_live_dispatch_keeps_signal_dispatched_when_expected_order_is_missing(self) -> None:
        class FakeAccountSyncService:
            def list_balances(self, limit: int = 100) -> list[dict[str, object]]:
                return [{"asset": "USDT", "available": "19.00000000", "locked": "0.00000000"}]

            def list_orders(self, limit: int = 100, symbols: tuple[str, ...] | None = None) -> list[dict[str, object]]:
                return [
                    {
                        "id": "99999999999",
                        "symbol": "DOGEUSDT",
                        "status": "FILLED",
                        "side": "buy",
                        "updateTime": 1712044800000,
                    }
                ]

            def list_positions(self, limit: int = 100) -> list[dict[str, object]]:
                return [{"id": "position-DOGE", "symbol": "DOGE", "side": "long", "quantity": "12.00000000"}]

        token = self._login_token()
        run_signal_pipeline("mock")
        start_strategy(1, token=token)

        fake_dispatch_result = {
            "action": {"symbol": "DOGE/USDT", "side": "long"},
            "order": {
                "id": "trade-1",
                "venueOrderId": "14136461324",
                "symbol": "DOGE/USDT",
                "status": "closed",
                "runtimeMode": "live",
                "updatedAt": "2026-04-02T00:00:00+00:00",
            },
            "runtime": {"mode": "live", "backend": "rest", "connection_status": "connected"},
        }
        with patch.dict(
            os.environ,
            {
                "QUANT_RUNTIME_MODE": "live",
                "BINANCE_API_KEY": "k",
                "BINANCE_API_SECRET": "s",
                "QUANT_LIVE_ALLOWED_SYMBOLS": "DOGEUSDT",
            },
            clear=False,
        ), patch.object(sync_service_module, "account_sync_service", FakeAccountSyncService()), patch.object(
            scheduler_module, "sync_service", sync_service_module.sync_service
        ), patch.object(
            strategies_route.execution_service, "dispatch_signal", return_value=fake_dispatch_result
        ):
            response = dispatch_latest_signal(1, token=token)

        self.assertIsNone(response["error"])
        self.assertEqual(response["data"]["sync_task"]["status"], "failed")
        self.assertIn("14136461324", response["data"]["sync_task"]["error_message"])
        self.assertEqual(get_signal(1)["data"]["item"]["status"], "dispatched")

    def test_live_dispatch_rejects_similar_recent_order_when_expected_order_id_differs(self) -> None:
        class FakeAccountSyncService:
            def list_balances(self, limit: int = 100) -> list[dict[str, object]]:
                return [{"asset": "USDT", "available": "19.00000000", "locked": "0.00000000"}]

            def list_orders(self, limit: int = 100, symbols: tuple[str, ...] | None = None) -> list[dict[str, object]]:
                return [
                    {
                        "id": "99999999999",
                        "symbol": "DOGEUSDT",
                        "status": "FILLED",
                        "side": "buy",
                        "executedQty": "12.00000000",
                        "updateTime": 1775088005000,
                    }
                ]

            def list_positions(self, limit: int = 100) -> list[dict[str, object]]:
                return [{"id": "position-DOGE", "symbol": "DOGE", "side": "long", "quantity": "12.00000000"}]

        token = self._login_token()
        run_signal_pipeline("mock")
        start_strategy(1, token=token)

        fake_dispatch_result = {
            "action": {"symbol": "DOGE/USDT", "side": "long"},
            "order": {
                "id": "trade-1",
                "venueOrderId": "14136461324",
                "symbol": "DOGE/USDT",
                "status": "closed",
                "runtimeMode": "live",
                "executedQty": "12.00000000",
                "updatedAt": "2026-04-02T00:00:00+00:00",
            },
            "runtime": {"mode": "live", "backend": "rest", "connection_status": "connected"},
        }
        with patch.dict(
            os.environ,
            {
                "QUANT_RUNTIME_MODE": "live",
                "BINANCE_API_KEY": "k",
                "BINANCE_API_SECRET": "s",
                "QUANT_LIVE_ALLOWED_SYMBOLS": "DOGEUSDT",
            },
            clear=False,
        ), patch.object(sync_service_module, "account_sync_service", FakeAccountSyncService()), patch.object(
            scheduler_module, "sync_service", sync_service_module.sync_service
        ), patch.object(
            strategies_route.execution_service, "dispatch_signal", return_value=fake_dispatch_result
        ):
            response = dispatch_latest_signal(1, token=token)

        self.assertEqual(response["data"]["sync_task"]["status"], "failed")
        self.assertIn("14136461324", response["data"]["sync_task"]["error_message"])
        self.assertEqual(get_signal(1)["data"]["item"]["status"], "dispatched")

    def test_retry_sync_task_marks_signal_synced_after_confirmation_recovers(self) -> None:
        class FakeAccountSyncService:
            def __init__(self) -> None:
                self._calls = 0

            def list_balances(self, limit: int = 100) -> list[dict[str, object]]:
                return [{"asset": "USDT", "available": "19.00000000", "locked": "0.00000000"}]

            def list_orders(self, limit: int = 100, symbols: tuple[str, ...] | None = None) -> list[dict[str, object]]:
                self._calls += 1
                if self._calls == 1:
                    return []
                return [
                    {
                        "id": "14136461324",
                        "symbol": "DOGEUSDT",
                        "status": "FILLED",
                        "side": "buy",
                        "updateTime": 1775088005000,
                    }
                ]

            def list_positions(self, limit: int = 100) -> list[dict[str, object]]:
                return [{"id": "position-DOGE", "symbol": "DOGE", "side": "long", "quantity": "12.00000000"}]

        token = self._login_token()
        run_signal_pipeline("mock")
        start_strategy(1, token=token)

        fake_dispatch_result = {
            "action": {"symbol": "DOGE/USDT", "side": "long", "source_signal_id": 1},
            "order": {
                "id": "trade-1",
                "venueOrderId": "14136461324",
                "symbol": "DOGE/USDT",
                "status": "closed",
                "runtimeMode": "live",
                "updatedAt": "2026-04-02T00:00:00+00:00",
            },
            "runtime": {"mode": "live", "backend": "rest", "connection_status": "connected"},
        }
        fake_account_sync_service = FakeAccountSyncService()
        with patch.dict(
            os.environ,
            {
                "QUANT_RUNTIME_MODE": "live",
                "BINANCE_API_KEY": "k",
                "BINANCE_API_SECRET": "s",
                "QUANT_LIVE_ALLOWED_SYMBOLS": "DOGEUSDT",
            },
            clear=False,
        ), patch.object(sync_service_module, "account_sync_service", fake_account_sync_service), patch.object(
            scheduler_module, "sync_service", sync_service_module.sync_service
        ), patch.object(
            strategies_route.execution_service, "dispatch_signal", return_value=fake_dispatch_result
        ):
            response = dispatch_latest_signal(1, token=token)
            task_id = int(response["data"]["sync_task"]["id"])
            retry_response = retry_task(task_id, token=token)

        self.assertEqual(response["data"]["sync_task"]["status"], "failed")
        self.assertEqual(retry_response["data"]["item"]["status"], "succeeded")
        self.assertEqual(get_signal(1)["data"]["item"]["status"], "synced")

    def test_review_task_returns_validation_workflow_report(self) -> None:
        token = self._login_token()
        run_signal_pipeline("mock")
        run_sync_task(token=token)

        review_response = run_review_task(token=token)
        report_response = get_validation_review(token=token)

        self.assertEqual(review_response["data"]["item"]["status"], "succeeded")
        self.assertIn("overview", review_response["data"]["item"]["result"])
        self.assertIn("steps", review_response["data"]["item"]["result"])
        self.assertIn("task_health", review_response["data"]["item"]["result"])
        self.assertIn("execution_health", report_response["data"]["item"])
        self.assertIn("recent_tasks", report_response["data"]["item"])


if __name__ == "__main__":
    unittest.main()
