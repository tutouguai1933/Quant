from __future__ import annotations

import sys
import unittest
from pathlib import Path


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
from services.api.app.routes.tasks import retry_task, run_reconcile_task  # noqa: E402
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


if __name__ == "__main__":
    unittest.main()
