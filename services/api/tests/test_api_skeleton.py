from __future__ import annotations

import sys
import threading
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import services.api.app.adapters.freqtrade.client as freqtrade_client_module  # noqa: E402
import services.api.app.routes.auth as auth_route  # noqa: E402
import services.api.app.routes.risk_events as risk_events_route  # noqa: E402
import services.api.app.routes.signals as signals_route  # noqa: E402
import services.api.app.routes.strategies as strategies_route  # noqa: E402
import services.api.app.routes.tasks as tasks_route  # noqa: E402
import services.api.app.services.auth_service as auth_service_module  # noqa: E402
import services.api.app.services.execution_service as execution_service_module  # noqa: E402
import services.api.app.services.risk_service as risk_service_module  # noqa: E402
import services.api.app.services.signal_service as signal_service_module  # noqa: E402
import services.api.app.services.strategy_catalog as strategy_catalog_module  # noqa: E402
import services.api.app.services.strategy_workspace_service as strategy_workspace_module  # noqa: E402
import services.api.app.services.sync_service as sync_service_module  # noqa: E402
import services.api.app.tasks.scheduler as scheduler_module  # noqa: E402
from services.api.app.main import app  # noqa: E402
from services.api.app.routes.accounts import list_accounts  # noqa: E402
from services.api.app.routes.auth import login  # noqa: E402
from services.api.app.routes.health import get_health, get_healthz  # noqa: E402
from services.api.app.routes.risk_events import get_risk_event, list_risk_events  # noqa: E402
from services.api.app.routes.signals import (  # noqa: E402
    get_signal,
    get_research_candidate,
    get_research_candidates,
    ingest_signal,
    list_signals,
    get_latest_research,
    run_research_inference,
    run_research_training,
    run_signal_pipeline,
    run_strategy,
)
from services.api.app.routes.strategies import (  # noqa: E402
    dispatch_latest_signal,
    get_strategy,
    get_strategy_catalog,
    get_strategy_workspace,
    list_strategies,
    pause_strategy,
    start_strategy,
    stop_strategy,
)
from services.api.app.services.auth_service import AuthService  # noqa: E402
from services.api.app.services.risk_service import RiskService  # noqa: E402
from services.api.app.services.signal_service import SignalService  # noqa: E402
from services.api.app.services.strategy_catalog import StrategyCatalogService  # noqa: E402
from services.api.app.services.strategy_workspace_service import StrategyWorkspaceService  # noqa: E402
from services.api.app.adapters.freqtrade.client import FreqtradeClient  # noqa: E402
from services.api.app.tasks.scheduler import TaskScheduler  # noqa: E402
from services.api.app.routes.tasks import get_task, list_tasks  # noqa: E402
from services.api.app.routes.orders import list_orders  # noqa: E402
from services.api.app.routes.positions import list_positions  # noqa: E402


class ApiSkeletonTests(unittest.TestCase):
    def setUp(self) -> None:
        self._reset_singletons()

    @staticmethod
    def _reset_singletons() -> None:
        new_auth_service = AuthService()
        auth_service_module.auth_service = new_auth_service
        auth_route.auth_service = new_auth_service
        strategies_route.auth_service = new_auth_service
        tasks_route.auth_service = new_auth_service
        risk_events_route.auth_service = new_auth_service

        new_freqtrade_client = FreqtradeClient()
        freqtrade_client_module.freqtrade_client = new_freqtrade_client
        sync_service_module.freqtrade_client = new_freqtrade_client
        strategies_route.freqtrade_client = new_freqtrade_client
        execution_service_module.freqtrade_client = new_freqtrade_client

        new_signal_service = SignalService()
        signal_service_module.signal_service = new_signal_service
        signals_route.signal_service = new_signal_service
        sync_service_module.signal_service = new_signal_service
        risk_service_module.signal_service = new_signal_service
        scheduler_module.signal_service = new_signal_service
        strategies_route.signal_service = new_signal_service
        execution_service_module.signal_service = new_signal_service

        new_strategy_catalog_service = StrategyCatalogService()
        strategy_catalog_module.strategy_catalog_service = new_strategy_catalog_service
        strategies_route.strategy_catalog_service = new_strategy_catalog_service

        new_strategy_workspace_service = StrategyWorkspaceService(
            catalog_service=new_strategy_catalog_service,
            signal_store=new_signal_service,
            execution_sync=sync_service_module.sync_service,
        )
        strategy_workspace_module.strategy_workspace_service = new_strategy_workspace_service
        strategies_route.strategy_workspace_service = new_strategy_workspace_service

        new_task_scheduler = TaskScheduler()
        scheduler_module.task_scheduler = new_task_scheduler
        tasks_route.task_scheduler = new_task_scheduler
        strategies_route.task_scheduler = new_task_scheduler

        new_risk_service = RiskService()
        risk_service_module.risk_service = new_risk_service
        risk_events_route.risk_service = new_risk_service
        strategies_route.risk_service = new_risk_service

    @staticmethod
    def _login_token() -> str:
        response = login(username="admin", password="1933")
        return str(response["data"]["item"]["token"])

    def test_main_app_exposes_router_collection(self) -> None:
        self.assertTrue(hasattr(app, "include_router"))

    def test_main_app_includes_auth_router(self) -> None:
        router_prefixes = []
        for router in getattr(app, "routers", []):
            prefix = getattr(router, "prefix", None)
            if prefix is None:
                prefix = getattr(router, "kwargs", {}).get("prefix")
            router_prefixes.append(prefix)
        self.assertIn("/api/v1/auth", router_prefixes)

    def test_health_endpoints_return_success_envelope(self) -> None:
        self.assertEqual(get_health()["error"], None)
        self.assertEqual(get_healthz()["data"]["status"], "ok")

    def test_auth_login_returns_success_envelope(self) -> None:
        response = login(username="admin", password="1933")

        self.assertEqual(set(response.keys()), {"data", "error", "meta"})
        self.assertIsNone(response["error"])
        self.assertEqual(response["data"]["item"]["scope"], "control_plane")

    def test_list_routes_return_consistent_response_shape(self) -> None:
        token = self._login_token()
        responses = [
            list_accounts(),
            list_strategies(token=token),
            list_signals(),
            list_tasks(token=token),
            list_risk_events(token=token),
            list_orders(),
            list_positions(),
        ]

        for response in responses:
            self.assertEqual(set(response.keys()), {"data", "error", "meta"})
            self.assertIsNone(response["error"])
            self.assertIn("items", response["data"])
            self.assertIn("source", response["meta"])

    def test_strategy_catalog_route_returns_consistent_response_shape(self) -> None:
        token = self._login_token()
        response = get_strategy_catalog(token=token)

        self.assertEqual(set(response.keys()), {"data", "error", "meta"})
        self.assertIsNone(response["error"])
        self.assertIn("whitelist", response["data"])
        self.assertIn("strategies", response["data"])
        self.assertEqual(response["meta"]["source"], "strategy-catalog")

    def test_strategy_workspace_route_returns_consistent_response_shape(self) -> None:
        token = self._login_token()
        response = get_strategy_workspace(token=token)

        self.assertEqual(set(response.keys()), {"data", "error", "meta"})
        self.assertIsNone(response["error"])
        self.assertIn("overview", response["data"])
        self.assertIn("whitelist", response["data"])
        self.assertIn("strategies", response["data"])
        self.assertIn("recent_signals", response["data"])
        self.assertIn("recent_orders", response["data"])
        self.assertIn("account_state", response["data"])
        self.assertIn("executor_runtime", response["data"])
        self.assertEqual(response["meta"]["source"], "strategy-workspace")

    def test_detail_routes_return_consistent_response_shape(self) -> None:
        token = self._login_token()
        responses = [
            get_strategy(1, token=token),
            get_signal(2),
            get_task(3, token=token),
            get_risk_event(4, token=token),
        ]

        for response in responses:
            self.assertEqual(set(response.keys()), {"data", "error", "meta"})
            self.assertIsNone(response["error"])
            self.assertIn("item", response["data"])

    def test_signal_pipeline_run_returns_success_envelope(self) -> None:
        response = run_signal_pipeline("mock")

        self.assertEqual(set(response.keys()), {"data", "error", "meta"})
        self.assertIsNone(response["error"])
        self.assertIn("run", response["data"])
        self.assertEqual(response["data"]["run"]["source"], "mock")

    def test_research_routes_return_consistent_response_shape(self) -> None:
        token = self._login_token()
        latest = get_latest_research()
        training = run_research_training(token=token)
        inference = run_research_inference(token=token)

        for response in (latest, training, inference):
            self.assertEqual(set(response.keys()), {"data", "error", "meta"})

    def test_research_candidate_routes_return_consistent_response_shape(self) -> None:
        token = self._login_token()
        run_research_training(token=token)
        run_research_inference(token=token)

        candidates = get_research_candidates()
        candidate = get_research_candidate("BTCUSDT")

        self.assertEqual(set(candidates.keys()), {"data", "error", "meta"})
        self.assertEqual(set(candidate.keys()), {"data", "error", "meta"})
        self.assertIsNone(candidates["error"])
        self.assertIsNone(candidate["error"])
        self.assertIn("items", candidates["data"])
        self.assertIn("summary", candidates["data"])
        self.assertIn("item", candidate["data"])

    def test_strategy_run_route_rejects_missing_symbol(self) -> None:
        response = run_strategy({"strategy_id": "trend_breakout"})

        self.assertEqual(set(response.keys()), {"data", "error", "meta"})
        self.assertEqual(response["error"]["code"], "invalid_request")
        self.assertIn("symbol", response["error"]["message"])

    def test_signal_ingest_returns_created_item(self) -> None:
        response = ingest_signal(
            {
                "symbol": "SOL/USDT",
                "side": "long",
                "score": "0.650000",
                "confidence": "0.710000",
                "target_weight": "0.120000",
                "generated_at": "2026-04-01T09:00:00+00:00",
                "source": "mock",
                "strategy_id": 3,
            }
        )

        self.assertEqual(set(response.keys()), {"data", "error", "meta"})
        self.assertIsNone(response["error"])
        self.assertEqual(response["data"]["item"]["symbol"], "SOL/USDT")

    def test_strategy_control_endpoints_update_status(self) -> None:
        token = self._login_token()
        started = start_strategy(1, token=token)
        paused = pause_strategy(1, token=token)
        stopped = stop_strategy(1, token=token)

        self.assertEqual(started["data"]["item"]["status"], "running")
        self.assertEqual(paused["data"]["item"]["status"], "paused")
        self.assertEqual(stopped["data"]["item"]["status"], "stopped")
        self.assertEqual(started["meta"]["scope"], "executor")

    def test_strategy_control_rejects_non_executor_scope(self) -> None:
        token = self._login_token()

        response = start_strategy(2, token=token)

        self.assertEqual(response["error"]["code"], "unsupported_control_scope")
        self.assertEqual(response["meta"]["scope"], "executor")

    def test_dispatch_latest_signal_creates_execution_feedback(self) -> None:
        token = self._login_token()
        run_signal_pipeline("mock")
        start_strategy(1, token=token)
        response = dispatch_latest_signal(1, token=token)

        self.assertIsNone(response["error"])
        self.assertIn("order", response["data"]["item"])
        self.assertEqual(response["data"]["risk_decision"]["status"], "allow")
        self.assertEqual(response["data"]["sync_task"]["status"], "succeeded")
        self.assertTrue(list_orders()["data"]["items"])
        self.assertTrue(list_positions()["data"]["items"])

    def test_dispatch_latest_signal_returns_structured_error_when_execution_fails(self) -> None:
        token = self._login_token()
        run_signal_pipeline("mock")
        start_strategy(1, token=token)

        original_dispatch = strategies_route.execution_service.dispatch_signal
        strategies_route.execution_service.dispatch_signal = lambda signal_id: (_ for _ in ()).throw(RuntimeError("freqtrade busy"))  # type: ignore[assignment]
        try:
            response = dispatch_latest_signal(1, token=token)
        finally:
            strategies_route.execution_service.dispatch_signal = original_dispatch  # type: ignore[assignment]

        self.assertEqual(response["error"]["code"], "execution_failed")
        self.assertIn("freqtrade busy", response["error"]["message"])

    def test_dispatch_latest_signal_skips_already_dispatched_signal(self) -> None:
        token = self._login_token()
        run_signal_pipeline("mock")
        start_strategy(1, token=token)

        first_response = dispatch_latest_signal(1, token=token)
        second_response = dispatch_latest_signal(1, token=token)

        self.assertIsNone(first_response["error"])
        self.assertEqual(second_response["error"]["code"], "signal_not_ready")
        self.assertIn("pending signal", second_response["error"]["message"])

    def test_dispatch_latest_signal_blocks_concurrent_duplicate_dispatch(self) -> None:
        token = self._login_token()
        run_signal_pipeline("mock")
        start_strategy(1, token=token)

        original_dispatch = strategies_route.execution_service.dispatch_signal
        entered = threading.Event()
        release = threading.Event()
        call_count = {"value": 0}

        def blocking_dispatch(signal_id: int) -> dict[str, object]:
            call_count["value"] += 1
            entered.set()
            release.wait(timeout=2)
            return original_dispatch(signal_id)

        strategies_route.execution_service.dispatch_signal = blocking_dispatch  # type: ignore[assignment]
        responses: list[dict[str, object]] = []
        try:
            thread = threading.Thread(target=lambda: responses.append(dispatch_latest_signal(1, token=token)))
            thread.start()
            entered.wait(timeout=2)
            second_response = dispatch_latest_signal(1, token=token)
            release.set()
            thread.join(timeout=5)
        finally:
            strategies_route.execution_service.dispatch_signal = original_dispatch  # type: ignore[assignment]

        self.assertEqual(call_count["value"], 1)
        self.assertEqual(second_response["error"]["code"], "signal_not_ready")
        self.assertEqual(len(responses), 1)
        self.assertIsNone(responses[0]["error"])

    def test_protected_views_require_token(self) -> None:
        tasks_response = list_tasks()
        risk_response = list_risk_events()
        workspace_response = get_strategy_workspace()

        self.assertEqual(tasks_response["error"]["code"], "unauthorized")
        self.assertEqual(risk_response["error"]["code"], "unauthorized")
        self.assertEqual(workspace_response["error"]["code"], "unauthorized")

    def test_protected_views_accept_bearer_token(self) -> None:
        token = self._login_token()

        tasks_response = list_tasks(authorization=f"Bearer {token}")
        risk_response = list_risk_events(authorization=f"Bearer {token}")

        self.assertIsNone(tasks_response["error"])
        self.assertIsNone(risk_response["error"])


if __name__ == "__main__":
    unittest.main()
