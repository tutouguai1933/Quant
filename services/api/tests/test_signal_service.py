from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone
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

    def test_matching_strategy_can_claim_generic_qlib_signal_with_template(self) -> None:
        original_research_service = signal_service_module.research_service
        signal_service_module.research_service = _TemplateMatchedResearchService()
        try:
            self.service.run_pipeline("qlib")
            claimed = self.service.claim_latest_dispatchable_signal(2)
        finally:
            signal_service_module.research_service = original_research_service

        self.assertIsNotNone(claimed)
        assert claimed is not None
        self.assertEqual(claimed["symbol"], "ETHUSDT")
        self.assertEqual(claimed["payload"]["strategy_template"], "trend_pullback_timing")

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

    def test_executor_strategy_does_not_fall_back_to_mock_when_pending_qlib_candidates_are_blocked(self) -> None:
        self.service.run_pipeline("mock")
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

    def test_qlib_pipeline_keeps_recommendation_metadata_for_blocked_candidate(self) -> None:
        original_research_service = signal_service_module.research_service
        signal_service_module.research_service = _BlockedRecommendationResearchService()
        try:
            self.service.run_pipeline("qlib")
            items = self.service.list_signals(limit=10)
        finally:
            signal_service_module.research_service = original_research_service

        self.assertEqual(items[0]["payload"]["next_action"], "continue_research")
        self.assertEqual(items[0]["payload"]["review_status"], "needs_research_iteration")
        self.assertEqual(items[0]["payload"]["recommended_for_execution"], False)

    def test_forced_validation_without_model_admission_is_blocked(self) -> None:
        """强制研究验证不能绕过生产模型与实时行情准入。"""
        original_research_service = signal_service_module.research_service
        signal_service_module.research_service = _ForcedValidationResearchService()
        try:
            self.service.run_pipeline("qlib")
            claimed = self.service.claim_latest_dispatchable_signal(1)
        finally:
            signal_service_module.research_service = original_research_service
        self.assertIsNone(claimed)

    def test_admitted_forced_validation_candidate_can_be_claimed(self) -> None:
        """合格模型的强制研究验证可被认领，实盘执行仍由独立执行准入检查。"""
        original_research_service = signal_service_module.research_service
        signal_service_module.research_service = _AdmittedForcedValidationResearchService()
        try:
            self.service.run_pipeline("qlib")
            claimed = self.service.claim_latest_dispatchable_signal(1)
        finally:
            signal_service_module.research_service = original_research_service
        self.assertIsNotNone(claimed)
        self.assertEqual(claimed["symbol"], "ETHUSDT")
        self.assertTrue(claimed["payload"]["forced_for_validation"])
        self.assertEqual(claimed["payload"]["review_status"], "forced_validation")
        self.assertEqual(claimed["payload"]["ml_context"]["model_admission"]["stage"], "production")


def _admitted_inference(payload: dict[str, object]) -> dict[str, object]:
    """构造按新协议准入且行情仍有效的推理，不把历史分数标为可执行。"""
    from services.worker.qlib_live_policy import EVALUATION_VERSION, UPSIDE_PROBABILITY
    now = datetime.now(timezone.utc)
    version = "qlib-production-fixture-v2"
    payload["model_admission"] = {
        "passed": True, "reasons": [], "stage": "production", "model_version": version,
        "evaluation_version": EVALUATION_VERSION, "prediction_semantics": UPSIDE_PROBABILITY,
    }
    for signal in payload["signals"]:
        signal.update({
            "generated_at": now.isoformat(),
            "feature_asof": (now - timedelta(minutes=5)).isoformat(),
            "expires_at": (now + timedelta(minutes=55)).isoformat(),
            "model_version": version, "executable": True,
            "prediction_semantics": UPSIDE_PROBABILITY,
        })
    return payload


class _PassingResearchService:
    def run_training(self) -> dict[str, object]:
        return {"model_version": "qlib-minimal-test", "status": "completed"}

    def run_inference(self) -> dict[str, object]:
        payload = {
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

        return _admitted_inference(payload)


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
        payload = {
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

        return _admitted_inference(payload)


class _BlockedRecommendationResearchService(_PassingResearchService):
    def run_inference(self) -> dict[str, object]:
        return {
            "backend": "qlib-fallback",
            "signals": [
                {
                    "symbol": "BTCUSDT",
                    "side": "long",
                    "score": "0.7100",
                    "confidence": "0.8100",
                    "target_weight": "0.2000",
                    "generated_at": "2026-04-02T01:00:00+00:00",
                }
            ],
            "candidates": {
                "items": [
                    {
                        "rank": 1,
                        "symbol": "BTCUSDT",
                        "allowed_to_dry_run": False,
                        "dry_run_gate": {"status": "failed", "reasons": ["drawdown_too_large"]},
                        "review_status": "needs_research_iteration",
                        "next_action": "continue_research",
                        "execution_priority": 100,
                    }
                ]
            },
        }


class _ForcedValidationResearchService(_PassingResearchService):
    def run_inference(self) -> dict[str, object]:
        return {
            "backend": "qlib-fallback",
            "signals": [
                {
                    "symbol": "ETHUSDT",
                    "side": "long",
                    "score": "0.8300",
                    "confidence": "0.8400",
                    "target_weight": "0.2000",
                    "generated_at": "2026-04-02T01:00:00+00:00",
                }
            ],
            "candidates": {
                "items": [
                    {
                        "rank": 1,
                        "symbol": "ETHUSDT",
                        "allowed_to_dry_run": True,
                        "forced_for_validation": True,
                        "forced_reason": "force_top_candidate_for_validation",
                        "review_status": "forced_validation",
                        "next_action": "enter_dry_run",
                        "execution_priority": 0,
                        "dry_run_gate": {"status": "failed", "reasons": ["drawdown_too_large"]},
                    }
                ]
            },
        }


class _AdmittedForcedValidationResearchService(_ForcedValidationResearchService):
    def run_inference(self) -> dict[str, object]:
        """为强制研究候选提供独立完整生产准入。"""
        return _admitted_inference(super().run_inference())


class _TemplateMatchedResearchService(_PassingResearchService):
    def run_inference(self) -> dict[str, object]:
        payload = {
            "backend": "qlib-fallback",
            "signals": [
                {
                    "symbol": "ETHUSDT",
                    "side": "long",
                    "score": "0.8300",
                    "confidence": "0.8400",
                    "target_weight": "0.2000",
                    "generated_at": "2026-04-02T01:00:00+00:00",
                }
            ],
            "candidates": {
                "items": [
                    {
                        "rank": 1,
                        "symbol": "ETHUSDT",
                        "strategy_template": "trend_pullback_timing",
                        "allowed_to_dry_run": True,
                        "dry_run_gate": {"status": "passed", "reasons": []},
                        "review_status": "ready_for_dry_run",
                        "next_action": "enter_dry_run",
                        "execution_priority": 0,
                    }
                ]
            },
        }

        return _admitted_inference(payload)


if __name__ == "__main__":
    unittest.main()
