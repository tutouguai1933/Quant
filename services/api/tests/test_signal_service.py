from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import services.api.app.services.signal_service as signal_service_module  # noqa: E402
from services.api.app.services.signal_service import (  # noqa: E402
    SignalPipelineUnavailableError,
    SignalService,
)


class SignalServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = SignalService()

    def test_mock_pipeline_covers_all_required_stages(self) -> None:
        run = self.service.run_pipeline("mock")

        self.assertEqual(run["source"], "mock")
        self.assertEqual(run["signal_count"], 1)
        self.assertEqual(
            [stage["name"] for stage in run["stages"]],
            [
                "data_preparation",
                "feature_engineering",
                "model_training",
                "signal_output",
            ],
        )

    def test_list_signals_returns_generated_mock_signal(self) -> None:
        items = self.service.list_signals(limit=10)

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["source"], "mock")
        self.assertEqual(items[0]["symbol"], "BTC/USDT")

    def test_ingest_signal_persists_contract_shape(self) -> None:
        created = self.service.ingest_signal(
            {
                "symbol": "ETH/USDT",
                "side": "long",
                "score": "0.730000",
                "confidence": "0.770000",
                "target_weight": "0.150000",
                "generated_at": "2026-04-01T08:00:00+00:00",
                "source": "rule-based",
                "strategy_id": 2,
            }
        )

        self.assertEqual(created["symbol"], "ETH/USDT")
        self.assertEqual(created["source"], "rule-based")
        self.assertIsNotNone(self.service.get_signal(int(created["signal_id"])))

    def test_qlib_pipeline_requires_optional_dependency(self) -> None:
        original_research_service = signal_service_module.research_service
        signal_service_module.research_service = _FailingResearchService()
        try:
            with self.assertRaises(SignalPipelineUnavailableError):
                self.service.run_pipeline("qlib")
        finally:
            signal_service_module.research_service = original_research_service

    def test_qlib_pipeline_persists_strategy_agnostic_signals(self) -> None:
        original_research_service = signal_service_module.research_service
        signal_service_module.research_service = _PassingResearchService()
        try:
            run = self.service.run_pipeline("qlib")
        finally:
            signal_service_module.research_service = original_research_service

        self.assertEqual(run["source"], "qlib")
        items = self.service.list_signals(limit=10)
        self.assertEqual(items[0]["strategy_id"], None)
        self.assertEqual(items[0]["source"], "qlib")
        self.assertEqual(items[0]["payload"]["dry_run_gate"]["status"], "passed")

    def test_executor_strategy_can_claim_latest_qlib_signal(self) -> None:
        original_research_service = signal_service_module.research_service
        signal_service_module.research_service = _PassingResearchService()
        try:
            self.service.run_pipeline("qlib")
            claimed = self.service.claim_latest_dispatchable_signal(1)
        finally:
            signal_service_module.research_service = original_research_service

        self.assertIsNotNone(claimed)
        self.assertEqual(claimed["source"], "qlib")
        self.assertEqual(claimed["strategy_id"], None)

    def test_non_executor_strategy_does_not_claim_strategy_agnostic_qlib_signal(self) -> None:
        original_research_service = signal_service_module.research_service
        signal_service_module.research_service = _PassingResearchService()
        try:
            self.service.run_pipeline("qlib")
            claimed = self.service.claim_latest_dispatchable_signal(2)
        finally:
            signal_service_module.research_service = original_research_service

        self.assertIsNone(claimed)

    def test_executor_strategy_prefers_strategy_bound_signal_over_generic_research_signal(self) -> None:
        original_research_service = signal_service_module.research_service
        signal_service_module.research_service = _PassingResearchService()
        try:
            self.service.run_pipeline("qlib")
        finally:
            signal_service_module.research_service = original_research_service

        created = self.service.ingest_signal(
            {
                "symbol": "BTC/USDT",
                "side": "long",
                "score": "0.800000",
                "confidence": "0.820000",
                "target_weight": "0.250000",
                "generated_at": "2026-04-03T07:00:00+00:00",
                "source": "mock",
                "strategy_id": 1,
            }
        )

        claimed = self.service.claim_latest_dispatchable_signal(1)

        self.assertIsNotNone(claimed)
        self.assertEqual(claimed["signal_id"], created["signal_id"])

    def test_qlib_signal_without_dry_run_gate_is_not_dispatchable(self) -> None:
        self.service.ingest_signal(
            {
                "symbol": "BTCUSDT",
                "side": "long",
                "score": "0.780000",
                "confidence": "0.810000",
                "target_weight": "0.250000",
                "generated_at": "2026-04-03T00:00:00+00:00",
                "source": "qlib",
                "strategy_id": 1,
            }
        )

        claimed = self.service.claim_latest_dispatchable_signal(1)

        self.assertIsNone(claimed)

    def test_qlib_pipeline_blocks_failed_dry_run_candidate(self) -> None:
        original_research_service = signal_service_module.research_service
        signal_service_module.research_service = _BlockedResearchService()
        try:
            self.service.run_pipeline("qlib")
            claimed = self.service.claim_latest_dispatchable_signal(1)
        finally:
            signal_service_module.research_service = original_research_service

        self.assertIsNone(claimed)

    def test_executor_strategy_prefers_ready_research_recommendation(self) -> None:
        original_research_service = signal_service_module.research_service
        signal_service_module.research_service = _MultiCandidateResearchService()
        try:
            self.service.run_pipeline("qlib")
            claimed = self.service.claim_latest_dispatchable_signal(1)
        finally:
            signal_service_module.research_service = original_research_service

        self.assertIsNotNone(claimed)
        self.assertEqual(claimed["symbol"], "BTCUSDT")
        self.assertEqual(claimed["payload"]["recommended_for_execution"], True)


class _PassingResearchService:
    def run_training(self) -> dict[str, object]:
        return {"model_version": "qlib-minimal-test", "status": "completed"}

    def run_inference(self) -> dict[str, object]:
        return {
            "backend": "qlib-fallback",
            "signals": [
                {
                    "symbol": "BTCUSDT",
                    "side": "long",
                    "score": "0.7000",
                    "confidence": "0.8000",
                    "target_weight": "0.2000",
                    "generated_at": "2026-04-02T01:00:00+00:00",
                }
            ],
            "candidates": {
                "items": [
                    {
                        "symbol": "BTCUSDT",
                        "allowed_to_dry_run": True,
                        "dry_run_gate": {"status": "passed", "reasons": []},
                    }
                ]
            },
        }


class _BlockedResearchService(_PassingResearchService):
    def run_inference(self) -> dict[str, object]:
        payload = super().run_inference()
        payload["candidates"]["items"][0]["allowed_to_dry_run"] = False
        payload["candidates"]["items"][0]["dry_run_gate"] = {
            "status": "failed",
            "reasons": ["sharpe_too_low"],
        }
        return payload


class _FailingResearchService:
    def run_training(self) -> dict[str, object]:
        raise RuntimeError("qlib unavailable")


class _MultiCandidateResearchService(_PassingResearchService):
    def run_inference(self) -> dict[str, object]:
        return {
            "backend": "qlib-fallback",
            "signals": [
                {
                    "symbol": "BTCUSDT",
                    "side": "long",
                    "score": "0.8100",
                    "confidence": "0.8200",
                    "target_weight": "0.2000",
                    "generated_at": "2026-04-02T01:00:00+00:00",
                },
                {
                    "symbol": "ETHUSDT",
                    "side": "long",
                    "score": "0.7900",
                    "confidence": "0.8100",
                    "target_weight": "0.2000",
                    "generated_at": "2026-04-02T02:00:00+00:00",
                },
            ],
            "candidates": {
                "items": [
                    {
                        "rank": 1,
                        "symbol": "BTCUSDT",
                        "allowed_to_dry_run": True,
                        "dry_run_gate": {"status": "passed", "reasons": []},
                    },
                    {
                        "rank": 2,
                        "symbol": "ETHUSDT",
                        "allowed_to_dry_run": True,
                        "dry_run_gate": {"status": "passed", "reasons": []},
                    },
                ]
            },
        }


if __name__ == "__main__":
    unittest.main()
