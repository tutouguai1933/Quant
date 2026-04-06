from __future__ import annotations

import sys
import threading
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import services.api.app.adapters.freqtrade.client as freqtrade_client_module  # noqa: E402
import services.api.app.routes.auth as auth_route  # noqa: E402
import services.api.app.routes.risk_events as risk_events_route  # noqa: E402
import services.api.app.routes.signals as signals_route  # noqa: E402
import services.api.app.routes.strategies as strategies_route  # noqa: E402
import services.api.app.routes.tasks as tasks_route  # noqa: E402
import services.api.app.routes.workbench_config as workbench_config_route  # noqa: E402
import services.api.app.services.automation_service as automation_service_module  # noqa: E402
import services.api.app.services.automation_workflow_service as automation_workflow_module  # noqa: E402
import services.api.app.services.auth_service as auth_service_module  # noqa: E402
import services.api.app.services.execution_service as execution_service_module  # noqa: E402
import services.api.app.services.risk_service as risk_service_module  # noqa: E402
import services.api.app.services.signal_service as signal_service_module  # noqa: E402
import services.api.app.services.strategy_dispatch_service as strategy_dispatch_module  # noqa: E402
import services.api.app.services.strategy_catalog as strategy_catalog_module  # noqa: E402
import services.api.app.services.strategy_workspace_service as strategy_workspace_module  # noqa: E402
import services.api.app.services.sync_service as sync_service_module  # noqa: E402
import services.api.app.services.validation_workflow_service as validation_workflow_module  # noqa: E402
import services.api.app.tasks.scheduler as scheduler_module  # noqa: E402
from services.api.app.main import app  # noqa: E402
from services.api.app.routes.accounts import list_accounts  # noqa: E402
from services.api.app.routes.auth import login  # noqa: E402
from services.api.app.routes.backtest_workspace import get_backtest_workspace  # noqa: E402
from services.api.app.routes.data_workspace import get_data_workspace  # noqa: E402
from services.api.app.routes.evaluation_workspace import get_evaluation_workspace  # noqa: E402
from services.api.app.routes.feature_workspace import get_feature_workspace  # noqa: E402
from services.api.app.routes.health import get_health, get_healthz  # noqa: E402
from services.api.app.routes.research_workspace import get_research_workspace  # noqa: E402
from services.api.app.routes.workbench_config import get_workbench_config, update_workbench_config  # noqa: E402
from services.api.app.routes.risk_events import get_risk_event, list_risk_events  # noqa: E402
from services.api.app.routes.signals import (  # noqa: E402
    get_signal,
    get_research_candidate,
    get_research_candidates,
    get_research_report,
    get_research_runtime,
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
from services.api.app.services.automation_service import AutomationService  # noqa: E402
from services.api.app.services.automation_workflow_service import AutomationWorkflowService  # noqa: E402
from services.api.app.services.risk_service import RiskService  # noqa: E402
from services.api.app.services.signal_service import SignalService  # noqa: E402
from services.api.app.services.strategy_dispatch_service import StrategyDispatchService  # noqa: E402
from services.api.app.services.strategy_catalog import StrategyCatalogService  # noqa: E402
from services.api.app.services.strategy_workspace_service import StrategyWorkspaceService  # noqa: E402
from services.api.app.services.validation_workflow_service import ValidationWorkflowService  # noqa: E402
from services.api.app.adapters.freqtrade.client import FreqtradeClient  # noqa: E402
from services.api.app.tasks.scheduler import TaskScheduler  # noqa: E402
from services.api.app.routes.tasks import get_task, get_validation_review, list_tasks, run_review_task, run_train_task  # noqa: E402
from services.api.app.routes.tasks import get_automation_status, set_automation_mode, halt_automation, resume_automation, run_automation_cycle, enable_dry_run_only, trigger_kill_switch  # noqa: E402
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
        workbench_config_route.auth_service = new_auth_service

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

        new_automation_service = AutomationService()
        automation_service_module.automation_service = new_automation_service
        tasks_route.automation_service = new_automation_service
        validation_workflow_module.automation_service = new_automation_service

        strategy_dispatch_module.signal_service = new_signal_service
        strategy_dispatch_module.task_scheduler = new_task_scheduler
        strategy_dispatch_module.sync_service = sync_service_module.sync_service
        strategy_dispatch_module.risk_service = new_risk_service
        strategy_dispatch_module.execution_service = execution_service_module.execution_service
        new_strategy_dispatch_service = StrategyDispatchService()
        strategy_dispatch_module.strategy_dispatch_service = new_strategy_dispatch_service

        new_validation_workflow_service = ValidationWorkflowService(
            research_reader=signals_route.research_service,
            sync_reader=sync_service_module.sync_service,
            scheduler=new_task_scheduler,
        )
        validation_workflow_module.validation_workflow_service = new_validation_workflow_service

        new_automation_workflow_service = AutomationWorkflowService(
            scheduler=new_task_scheduler,
            automation=new_automation_service,
            research=signals_route.research_service,
            signals=new_signal_service,
            dispatcher=new_strategy_dispatch_service,
            reviewer=new_validation_workflow_service,
            syncer=sync_service_module.sync_service,
        )
        automation_workflow_module.automation_workflow_service = new_automation_workflow_service
        tasks_route.automation_workflow_service = new_automation_workflow_service
        strategies_route.automation_workflow_service = new_automation_workflow_service

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
        self.assertIn("/api/v1/backtest", router_prefixes)
        self.assertIn("/api/v1/data", router_prefixes)
        self.assertIn("/api/v1/evaluation", router_prefixes)
        self.assertIn("/api/v1/features", router_prefixes)
        self.assertIn("/api/v1/research", router_prefixes)
        self.assertIn("/api/v1/workbench", router_prefixes)

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
        self.assertIn("research_recommendation", response["data"])
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

    def test_train_task_route_now_records_research_training(self) -> None:
        token = self._login_token()
        response = run_train_task(token=token)

        self.assertIsNone(response["error"])
        self.assertEqual(response["meta"]["action"], "research-train")
        self.assertEqual(response["data"]["item"]["task_type"], "research_train")

    def test_data_workspace_route_returns_consistent_response_shape(self) -> None:
        response = get_data_workspace(symbol="BTCUSDT", interval="4h", limit=120)

        self.assertEqual(set(response.keys()), {"data", "error", "meta"})
        self.assertIsNone(response["error"])
        self.assertIn("item", response["data"])
        self.assertEqual(response["meta"]["source"], "data-workspace")

    def test_backtest_workspace_route_returns_consistent_response_shape(self) -> None:
        response = get_backtest_workspace()

        self.assertEqual(set(response.keys()), {"data", "error", "meta"})
        self.assertIsNone(response["error"])
        self.assertIn("item", response["data"])
        self.assertEqual(response["meta"]["source"], "backtest-workspace")

    def test_evaluation_workspace_route_returns_consistent_response_shape(self) -> None:
        response = get_evaluation_workspace()

        self.assertEqual(set(response.keys()), {"data", "error", "meta"})
        self.assertIsNone(response["error"])
        self.assertIn("item", response["data"])
        self.assertEqual(response["meta"]["source"], "evaluation-workspace")

    def test_feature_workspace_route_returns_consistent_response_shape(self) -> None:
        response = get_feature_workspace()

        self.assertEqual(set(response.keys()), {"data", "error", "meta"})
        self.assertIsNone(response["error"])
        self.assertIn("item", response["data"])
        self.assertEqual(response["meta"]["source"], "feature-workspace")

    def test_research_workspace_route_returns_consistent_response_shape(self) -> None:
        response = get_research_workspace()

        self.assertEqual(set(response.keys()), {"data", "error", "meta"})
        self.assertIsNone(response["error"])
        self.assertIn("item", response["data"])

    def test_workbench_config_routes_return_consistent_response_shape(self) -> None:
        response = get_workbench_config()

        self.assertEqual(set(response.keys()), {"data", "error", "meta"})
        self.assertIsNone(response["error"])
        self.assertIn("item", response["data"])
        token = self._login_token()
        updated = update_workbench_config(
            {"section": "backtest", "values": {"fee_bps": "12", "slippage_bps": "6"}},
            token=token,
        )
        self.assertIsNone(updated["error"])
        self.assertEqual(updated["data"]["item"]["backtest"]["fee_bps"], "12")
        self.assertEqual(response["meta"]["source"], "workbench-config")

    def test_research_routes_return_consistent_response_shape(self) -> None:
        token = self._login_token()
        latest = get_latest_research()
        runtime = get_research_runtime()
        training = run_research_training(token=token)
        inference = run_research_inference(token=token)

        for response in (latest, runtime, training, inference):
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

    def test_research_report_route_returns_consistent_response_shape(self) -> None:
        token = self._login_token()
        run_research_training(token=token)
        run_research_inference(token=token)

        report = get_research_report()

        self.assertEqual(set(report.keys()), {"data", "error", "meta"})
        self.assertIsNone(report["error"])
        self.assertIn("item", report["data"])
        self.assertIn("overview", report["data"]["item"])
        self.assertIn("experiments", report["data"]["item"])

    def test_validation_review_routes_return_consistent_response_shape(self) -> None:
        token = self._login_token()
        review = run_review_task(token=token)
        report = get_validation_review(token=token)

        self.assertEqual(set(review.keys()), {"data", "error", "meta"})
        self.assertEqual(set(report.keys()), {"data", "error", "meta"})
        self.assertIsNone(review["error"])
        self.assertIsNone(report["error"])
        self.assertIn("item", review["data"])

    def test_automation_routes_return_consistent_response_shape(self) -> None:
        token = self._login_token()

        status = get_automation_status(token=token)
        switched = set_automation_mode(mode="auto_dry_run", token=token)
        dry_run_only = enable_dry_run_only(token=token)
        halted = halt_automation(reason="manual", token=token)
        resumed = resume_automation(mode="manual", token=token)
        killed = trigger_kill_switch(token=token)
        with mock.patch.object(
            tasks_route.task_scheduler,
            "run_named_task",
            return_value={"id": 1, "task_type": "automation_cycle", "status": "succeeded", "result": {"status": "completed"}},
        ):
            cycled = run_automation_cycle(token=token)

        for response in (status, switched, dry_run_only, halted, resumed, killed, cycled):
            self.assertEqual(set(response.keys()), {"data", "error", "meta"})
            self.assertIsNone(response["error"])
            self.assertIn("item", response["data"])
        self.assertIn("state", status["data"]["item"])
        self.assertIn("health", status["data"]["item"])
        self.assertIn("daily_summary", status["data"]["item"])
        self.assertIn("scheduler_plan", status["data"]["item"])
        self.assertIn("status", cycled["data"]["item"])

    def test_validation_review_http_route_is_not_shadowed_by_task_id_route(self) -> None:
        token = self._login_token()
        run_review_task(token=token)
        payload = get_validation_review(token=token)
        self.assertIsNone(payload["error"])
        self.assertIn("overview", payload["data"]["item"])

    def test_research_report_route_stays_unavailable_without_results(self) -> None:
        original_research_service = signals_route.research_service

        class _UnavailableResearchService:
            @staticmethod
            def get_factory_report() -> dict[str, object]:
                return {
                    "status": "unavailable",
                    "overview": {},
                    "experiments": {
                        "training": {"status": "unavailable"},
                        "inference": {"status": "unavailable"},
                        "recent_runs": [],
                    },
                    "candidates": [],
                    "leaderboard": [],
                    "screening": {},
                }

        signals_route.research_service = _UnavailableResearchService()
        try:
            report = get_research_report()
        finally:
            signals_route.research_service = original_research_service

        self.assertEqual(set(report.keys()), {"data", "error", "meta"})
        self.assertIsNone(report["error"])
        self.assertEqual(report["data"]["item"]["status"], "unavailable")
        self.assertEqual(report["data"]["item"]["experiments"]["training"]["status"], "unavailable")
        self.assertEqual(report["data"]["item"]["experiments"]["inference"]["status"], "unavailable")

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

        original_dispatch = strategies_route.strategy_dispatch_service.dispatch_latest_signal
        strategies_route.strategy_dispatch_service.dispatch_latest_signal = lambda strategy_id, source="system": {  # type: ignore[assignment]
            "status": "failed",
            "error_code": "execution_failed",
            "message": "freqtrade busy",
            "risk_task": None,
            "sync_task": None,
        }
        try:
            response = dispatch_latest_signal(1, token=token)
        finally:
            strategies_route.strategy_dispatch_service.dispatch_latest_signal = original_dispatch  # type: ignore[assignment]

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

        original_dispatch = strategy_dispatch_module.execution_service.dispatch_signal
        entered = threading.Event()
        release = threading.Event()
        call_count = {"value": 0}

        def blocking_dispatch(signal_id: int, strategy_context_id: int | None = None) -> dict[str, object]:
            call_count["value"] += 1
            entered.set()
            release.wait(timeout=2)
            return original_dispatch(signal_id, strategy_context_id=strategy_context_id)

        strategy_dispatch_module.execution_service.dispatch_signal = blocking_dispatch  # type: ignore[assignment]
        responses: list[dict[str, object]] = []
        try:
            thread = threading.Thread(target=lambda: responses.append(dispatch_latest_signal(1, token=token)))
            thread.start()
            entered.wait(timeout=2)
            second_response = dispatch_latest_signal(1, token=token)
            release.set()
            thread.join(timeout=5)
        finally:
            strategy_dispatch_module.execution_service.dispatch_signal = original_dispatch  # type: ignore[assignment]

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
