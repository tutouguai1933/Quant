from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import services.api.app.routes.signals as signals_route  # noqa: E402
import services.api.app.services.research_runtime_service as research_runtime_module  # noqa: E402
import services.api.app.services.research_service as research_service_module  # noqa: E402
from services.api.app.services.auth_service import auth_service  # noqa: E402
from services.api.app.services.research_runtime_service import ResearchRuntimeService  # noqa: E402
from services.api.app.services.research_service import ResearchService  # noqa: E402


class ResearchServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.runtime_root = Path(self._temp_dir.name)
        self.runtime_root.mkdir(exist_ok=True)
        self.token = str(auth_service.login("admin", "1933")["token"])
        self.service = ResearchService(
            config_loader=self._load_config,
            market_reader=_FakeMarketReader(),
            whitelist_provider=lambda: ["BTCUSDT", "ETHUSDT"],
        )
        research_service_module.research_service = self.service
        signals_route.research_service = self.service
        runtime_service = ResearchRuntimeService(
            config_loader=self._load_config,
            research_service_instance=self.service,
            signal_service_instance=signals_route.signal_service,
            async_runner=lambda fn: fn(),
        )
        research_runtime_module.research_runtime_service = runtime_service
        signals_route.research_runtime_service = runtime_service

    def tearDown(self) -> None:
        self._temp_dir.cleanup()

    def _load_config(self):
        return research_service_module.load_qlib_config(
            env={"QUANT_QLIB_RUNTIME_ROOT": str(self.runtime_root)},
            require_explicit=True,
        )

    def test_research_service_reads_latest_result(self) -> None:
        self.service.run_training()
        self.service.run_inference()

        latest = self.service.get_latest_result()

        self.assertEqual(latest["status"], "ready")
        self.assertIn("latest_training", latest)
        self.assertIn("latest_inference", latest)
        self.assertTrue(latest["symbols"])
        self.assertTrue(latest["recent_runs"])

    def test_research_service_returns_ranked_candidates(self) -> None:
        self.service.run_training()
        self.service.run_inference()

        snapshot = self.service.get_factory_snapshot()

        self.assertEqual(snapshot["status"], "ready")
        self.assertIn("candidates", snapshot)
        self.assertIn("summary", snapshot)
        self.assertTrue(snapshot["candidates"])
        self.assertEqual(snapshot["summary"]["candidate_count"], len(snapshot["candidates"]))

    def test_research_service_empty_runtime_stays_unavailable(self) -> None:
        latest = self.service.get_latest_result()
        report = self.service.get_factory_report()
        snapshot = self.service.get_factory_snapshot()

        self.assertEqual(latest["status"], "unavailable")
        self.assertEqual(report["status"], "unavailable")
        self.assertEqual(snapshot["status"], "unavailable")
        self.assertEqual(snapshot["candidates"], [])
        self.assertEqual(snapshot["summary"]["candidate_count"], 0)
        self.assertEqual(report["experiments"]["training"]["status"], "unavailable")
        self.assertEqual(report["experiments"]["inference"]["status"], "unavailable")

    def test_research_service_returns_symbol_candidate_summary(self) -> None:
        self.service.run_training()
        self.service.run_inference()

        item = self.service.get_factory_symbol("BTCUSDT")

        self.assertIsNotNone(item)
        self.assertEqual(item["symbol"], "BTCUSDT")
        self.assertIn("allowed_to_dry_run", item)

    def test_research_service_returns_unified_report(self) -> None:
        self.service.run_training()
        self.service.run_inference()

        report = self.service.get_factory_report()

        self.assertEqual(report["status"], "ready")
        self.assertIn("overview", report)
        self.assertIn("latest_training", report)
        self.assertIn("latest_inference", report)
        self.assertIn("candidates", report)
        self.assertIn("experiments", report)
        self.assertEqual(report["overview"]["candidate_count"], len(report["candidates"]))
        self.assertIn("blocked_count", report["overview"])
        self.assertIn("pass_rate_pct", report["overview"])
        self.assertIn("top_candidate_symbol", report["overview"])
        self.assertIn("recommended_symbol", report["overview"])
        self.assertIn("recommended_action", report["overview"])
        self.assertEqual(report["experiments"]["training"]["status"], "completed")
        self.assertEqual(report["experiments"]["inference"]["status"], "completed")
        self.assertIn("leaderboard", report)
        self.assertIn("screening", report)
        self.assertTrue(report["experiments"]["recent_runs"])
        self.assertIn("factor_protocol", report)
        self.assertIn("primary_feature_columns", report["factor_protocol"])
        self.assertIn("auxiliary_feature_columns", report["factor_protocol"])
        self.assertIn("evaluation", report)
        self.assertIn("reviews", report)
        self.assertIn("training_context", report["latest_training"])
        self.assertIn("inference_context", report["latest_inference"])
        self.assertEqual(report["experiments"]["training"]["dataset_snapshot"]["data_states"]["current"], "feature-ready")
        self.assertIn("cache", report["experiments"]["training"]["dataset_snapshot"])
        self.assertIn("snapshots", report)
        self.assertEqual(report["snapshots"]["training"]["active_data_state"], "feature-ready")
        self.assertEqual(
            report["snapshots"]["training"]["cache_signature"],
            report["snapshots"]["inference"]["cache_signature"],
        )

    def test_research_service_report_uses_worker_experiment_builder(self) -> None:
        self.service.run_training()
        self.service.run_inference()

        with patch(
            "services.api.app.services.research_factory_service.build_experiment_report",
            return_value={
                "overview": {"candidate_count": 7, "ready_count": 3, "signal_count": 5},
                "latest_training": {"model_version": "patched-model"},
                "latest_inference": {"run_id": "infer-patched"},
                "candidates": [{"symbol": "BTCUSDT", "allowed_to_dry_run": True}],
                "leaderboard": [{"symbol": "BTCUSDT", "next_action": "enter_dry_run"}],
                "screening": {"blocked_reason_counts": {"drawdown_too_large": 1}},
                "experiments": {
                    "training": {"status": "completed", "model_version": "patched-model"},
                    "inference": {"status": "completed", "model_version": "patched-model"},
                },
            },
        ) as report_builder:
            report = self.service.get_factory_report()

        report_builder.assert_called_once()
        self.assertEqual(report["overview"]["candidate_count"], 7)
        self.assertEqual(report["latest_training"]["model_version"], "patched-model")
        self.assertEqual(report["candidates"][0]["symbol"], "BTCUSDT")
        self.assertEqual(report["leaderboard"][0]["symbol"], "BTCUSDT")

    def test_research_service_prepares_both_1h_and_4h_samples_for_runner(self) -> None:
        self.service.run_training()

        self.assertIn(("BTCUSDT", "1h", 120), self.service._market_reader.calls)
        self.assertIn(("BTCUSDT", "4h", 120), self.service._market_reader.calls)
        self.assertIn(("ETHUSDT", "1h", 120), self.service._market_reader.calls)
        self.assertIn(("ETHUSDT", "4h", 120), self.service._market_reader.calls)

    def test_research_service_reuses_cached_kline_batch_between_training_and_inference(self) -> None:
        training_result = self.service.run_training()
        inference_result = self.service.run_inference()

        self.assertEqual(len(self.service._market_reader.calls), 4)
        self.assertEqual(training_result["market_cache"]["reused_count"], 0)
        self.assertEqual(inference_result["market_cache"]["reused_count"], 4)
        self.assertEqual(training_result["dataset_snapshot"]["cache_signature"], inference_result["dataset_snapshot"]["cache_signature"])

    def test_research_report_uses_signal_list_when_summary_missing(self) -> None:
        self._write_json(
            self.runtime_root / "latest_training.json",
            {
                "run_id": "train-1",
                "status": "completed",
                "generated_at": "2026-04-03T10:00:00+00:00",
                "model_version": "qlib-minimal-1",
                "artifact_path": "/tmp/model.json",
            },
        )
        self._write_json(
            self.runtime_root / "latest_inference.json",
            {
                "run_id": "infer-1",
                "status": "completed",
                "generated_at": "2026-04-03T11:00:00+00:00",
                "model_version": "qlib-minimal-1",
                "signals": [
                    {"symbol": "BTCUSDT", "signal": "long", "score": "0.7300"},
                    {"symbol": "ETHUSDT", "signal": "flat", "score": "0.5100"},
                ],
                "candidates": {"items": [], "summary": {"candidate_count": 0, "ready_count": 0}},
            },
        )

        report = self.service.get_factory_report()

        self.assertEqual(report["status"], "ready")
        self.assertEqual(report["overview"]["signal_count"], 2)
        self.assertEqual(report["experiments"]["inference"]["signal_count"], 2)

    def test_research_snapshot_hides_stale_candidates_when_status_is_unavailable(self) -> None:
        self._write_json(
            self.runtime_root / "latest_inference.json",
            {
                "run_id": "infer-1",
                "status": "completed",
                "generated_at": "2026-04-03T11:00:00+00:00",
                "model_version": "qlib-minimal-1",
                "signals": [{"symbol": "BTCUSDT", "signal": "long", "score": "0.7300"}],
                "candidates": {
                    "items": [
                        {
                            "symbol": "BTCUSDT",
                            "score": "0.7300",
                            "allowed_to_dry_run": True,
                        }
                    ],
                    "summary": {"candidate_count": 1, "ready_count": 1},
                },
            },
        )

        snapshot = self.service.get_factory_snapshot()
        report = self.service.get_factory_report()

        self.assertEqual(snapshot["status"], "unavailable")
        self.assertEqual(snapshot["candidates"], [])
        self.assertEqual(snapshot["summary"]["candidate_count"], 0)
        self.assertEqual(report["candidates"], [])
        self.assertEqual(report["overview"]["candidate_count"], 0)

    def test_research_snapshot_repairs_candidate_summary_drift(self) -> None:
        self._write_json(
            self.runtime_root / "latest_training.json",
            {
                "run_id": "train-1",
                "status": "completed",
                "generated_at": "2026-04-03T10:00:00+00:00",
                "model_version": "qlib-minimal-1",
                "artifact_path": "/tmp/model.json",
            },
        )
        self._write_json(
            self.runtime_root / "latest_inference.json",
            {
                "run_id": "infer-1",
                "status": "completed",
                "generated_at": "2026-04-03T11:00:00+00:00",
                "model_version": "qlib-minimal-1",
                "signals": [{"symbol": "BTCUSDT", "signal": "long", "score": "0.7300"}],
                "candidates": {
                    "items": [
                        {
                            "rank": 1,
                            "symbol": "BTCUSDT",
                            "strategy_template": "trend_breakout_timing",
                            "score": "0.7300",
                            "backtest": {"metrics": {}},
                            "dry_run_gate": {"status": "passed", "reasons": []},
                            "allowed_to_dry_run": True,
                        },
                        {
                            "rank": 2,
                            "symbol": "ETHUSDT",
                            "strategy_template": "trend_pullback_timing",
                            "score": "0.6100",
                            "backtest": {"metrics": {}},
                            "dry_run_gate": {"status": "failed", "reasons": ["drawdown_too_large"]},
                            "allowed_to_dry_run": False,
                        },
                    ],
                    "summary": {"candidate_count": 1, "ready_count": 0},
                },
            },
        )

        snapshot = self.service.get_factory_snapshot()
        report = self.service.get_factory_report()

        self.assertEqual(snapshot["summary"]["candidate_count"], 2)
        self.assertEqual(snapshot["summary"]["ready_count"], 1)
        self.assertEqual(report["overview"]["candidate_count"], 2)
        self.assertEqual(report["overview"]["ready_count"], 1)

    def test_research_recommendation_falls_back_to_continue_research_when_no_ready_candidate(self) -> None:
        self._write_json(
            self.runtime_root / "latest_training.json",
            {
                "run_id": "train-1",
                "status": "completed",
                "generated_at": "2026-04-03T10:00:00+00:00",
                "model_version": "qlib-minimal-1",
                "artifact_path": "/tmp/model.json",
            },
        )
        self._write_json(
            self.runtime_root / "latest_inference.json",
            {
                "run_id": "infer-1",
                "status": "completed",
                "generated_at": "2026-04-03T11:00:00+00:00",
                "model_version": "qlib-minimal-1",
                "signals": [{"symbol": "BTCUSDT", "signal": "long", "score": "0.7300"}],
                "candidates": {
                    "items": [
                        {
                            "rank": 1,
                            "symbol": "BTCUSDT",
                            "strategy_template": "trend_breakout_timing",
                            "score": "0.7300",
                            "backtest": {"metrics": {}},
                            "dry_run_gate": {"status": "failed", "reasons": ["drawdown_too_large"]},
                            "allowed_to_dry_run": False,
                            "review_status": "needs_research_iteration",
                            "next_action": "continue_research",
                            "execution_priority": 100,
                        }
                    ],
                    "summary": {"candidate_count": 1, "ready_count": 0},
                },
            },
        )

        recommendation = self.service.get_research_recommendation()

        self.assertIsNotNone(recommendation)
        assert recommendation is not None
        self.assertEqual(recommendation["symbol"], "BTCUSDT")
        self.assertFalse(recommendation["allowed_to_dry_run"])
        self.assertEqual(recommendation["next_action"], "continue_research")

    def test_research_recommendation_exposes_forced_validation_candidate(self) -> None:
        self._write_json(
            self.runtime_root / "latest_training.json",
            {
                "run_id": "train-1",
                "status": "completed",
                "generated_at": "2026-04-03T10:00:00+00:00",
                "model_version": "qlib-minimal-1",
                "artifact_path": "/tmp/model.json",
            },
        )
        self._write_json(
            self.runtime_root / "latest_inference.json",
            {
                "run_id": "infer-1",
                "status": "completed",
                "generated_at": "2026-04-03T11:00:00+00:00",
                "model_version": "qlib-minimal-1",
                "signals": [{"symbol": "ETHUSDT", "signal": "long", "score": "0.8300"}],
                "candidates": {
                    "items": [
                        {
                            "rank": 1,
                            "symbol": "ETHUSDT",
                            "strategy_template": "trend_breakout_timing",
                            "score": "0.8300",
                            "backtest": {"metrics": {}},
                            "dry_run_gate": {"status": "failed", "reasons": ["drawdown_too_large"]},
                            "allowed_to_dry_run": True,
                            "forced_for_validation": True,
                            "forced_reason": "force_top_candidate_for_validation",
                            "review_status": "forced_validation",
                            "next_action": "enter_dry_run",
                            "execution_priority": 0,
                        }
                    ],
                    "summary": {"candidate_count": 1, "ready_count": 1},
                },
            },
        )

        recommendation = self.service.get_research_recommendation()
        report = self.service.get_factory_report()

        self.assertIsNotNone(recommendation)
        assert recommendation is not None
        self.assertTrue(recommendation["allowed_to_dry_run"])
        self.assertTrue(recommendation["forced_for_validation"])
        self.assertEqual(recommendation["review_status"], "forced_validation")
        self.assertTrue(report["overview"]["forced_validation"])
        self.assertEqual(report["overview"]["forced_symbol"], "ETHUSDT")

    def test_signals_route_returns_unified_research_report(self) -> None:
        self.service.run_training()
        self.service.run_inference()

        response = signals_route.get_research_report()

        self.assertIsNone(response["error"])
        self.assertEqual(response["data"]["item"]["status"], "ready")
        self.assertIn("overview", response["data"]["item"])
        self.assertIn("experiments", response["data"]["item"])

    def test_signals_routes_trigger_training_and_inference(self) -> None:
        training_response = signals_route.run_research_training(token=self.token)
        inference_response = signals_route.run_research_inference(token=self.token)

        self.assertIsNone(training_response["error"])
        self.assertIsNone(inference_response["error"])
        self.assertEqual(training_response["data"]["item"]["status"], "succeeded")
        self.assertEqual(inference_response["data"]["item"]["status"], "succeeded")
        runtime_response = signals_route.get_research_runtime()
        self.assertEqual(runtime_response["data"]["item"]["status"], "succeeded")

    def test_research_routes_require_login_for_write_actions(self) -> None:
        training_response = signals_route.run_research_training()
        inference_response = signals_route.run_research_inference()

        self.assertEqual(training_response["error"]["code"], "unauthorized")
        self.assertEqual(inference_response["error"]["code"], "unauthorized")

    @staticmethod
    def _write_json(path: Path, payload: dict[str, object]) -> None:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


class _FakeMarketReader:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, int]] = []

    def get_symbol_chart(
        self,
        symbol: str,
        interval: str = "1h",
        limit: int = 120,
        allowed_symbols: tuple[str, ...] | None = None,
    ) -> dict[str, object]:
        self.calls.append((symbol, interval, limit))
        base_price = 100 if symbol == "BTCUSDT" else 50
        items = []
        step_ms = 4 * 3600000 if interval == "4h" else 3600000
        for index in range(120):
            close = base_price + index * 0.8
            items.append(
                {
                    "open_time": 1712016000000 + (index * step_ms),
                    "open": str(close - 1),
                    "high": str(close + 2),
                    "low": str(close - 2),
                    "close": str(close),
                    "volume": str(1000 + (index * 100)),
                    "close_time": 1712019599999 + (index * step_ms),
                }
            )
        return {"items": items, "overlays": {}, "markers": {"signals": [], "entries": [], "stops": []}}


if __name__ == "__main__":
    unittest.main()
