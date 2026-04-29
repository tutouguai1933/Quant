from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from services.api.app.services.research_runtime_service import ResearchRuntimeService
from services.worker.qlib_config import load_qlib_config


class _FakeResearchService:
    def __init__(self) -> None:
        self.training_runs = 0
        self.inference_runs = 0
        self.has_training = False

    def run_training(self) -> dict[str, object]:
        self.training_runs += 1
        self.has_training = True
        return {"run_id": "train-demo", "model_version": "model-demo", "status": "completed"}

    def run_inference(self) -> dict[str, object]:
        self.inference_runs += 1
        return {"run_id": "infer-demo", "status": "completed"}

    def get_latest_result(self) -> dict[str, object]:
        if not self.has_training:
            return {"latest_training": {}}
        return {
            "latest_training": {
                "model_version": "model-demo",
                "training_context": {
                    "parameters": {
                        "research_template": "single_asset_timing_strict",
                    }
                },
            },
            "latest_inference": {
                "inference_context": {
                    "input_summary": {
                        "research_template": "single_asset_timing_strict",
                    }
                }
            },
        }

    def get_research_recommendation(self) -> dict[str, object]:
        return {
            "symbol": "ETHUSDT",
            "next_action": "enter_dry_run",
            "research_template": "single_asset_timing_strict",
            "strategy_id": 1,
            "strategy_template": "trend_pullback_timing",
        }


class _FakeSignalService:
    def __init__(self) -> None:
        self.refresh_runs = 0

    def refresh_qlib_signals_from_latest_result(self) -> dict[str, object]:
        self.refresh_runs += 1
        return {"signal_count": 1, "source": "qlib"}


class _FakeScheduler:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def run_named_task(
        self,
        task_type: str,
        source: str = "user",
        target_type: str = "system",
        target_id: int | None = None,
        payload: dict[str, object] | None = None,
    ) -> dict[str, object]:
        self.calls.append(task_type)
        return {
            "id": len(self.calls),
            "task_type": task_type,
            "status": "succeeded",
            "source": source,
            "target_type": target_type,
            "target_id": target_id,
            "payload": payload or {},
            "result": {"task_type": task_type},
        }


class _FakeReviewer:
    def __init__(self) -> None:
        self.calls = 0

    def build_report(self, limit: int = 10) -> dict[str, object]:
        self.calls += 1
        return {
            "overview": {
                "recommended_symbol": "ETHUSDT",
                "recommended_action": "enter_dry_run",
                "candidate_count": 1,
                "ready_count": 1,
            }
        }


class _FakeAutomation:
    def __init__(self) -> None:
        self.cycles: list[tuple[dict[str, object], bool]] = []
        self.alerts: list[dict[str, object]] = []

    def record_cycle(self, payload: dict[str, object], *, count_towards_daily: bool = True) -> None:
        self.cycles.append((dict(payload), count_towards_daily))

    def record_alert(self, *, level: str, code: str, message: str, source: str, detail: str = "") -> dict[str, object]:
        item = {
            "level": level,
            "code": code,
            "message": message,
            "source": source,
            "detail": detail,
        }
        self.alerts.append(item)
        return item


class ResearchRuntimeServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.runtime_root = Path(self._temp_dir.name)
        self.research_service = _FakeResearchService()
        self.signal_service = _FakeSignalService()
        self.scheduler = _FakeScheduler()
        self.reviewer = _FakeReviewer()
        self.automation = _FakeAutomation()

    def tearDown(self) -> None:
        self._temp_dir.cleanup()

    def _build_service(self) -> ResearchRuntimeService:
        return ResearchRuntimeService(
            config_loader=lambda: load_qlib_config(env={"QUANT_QLIB_RUNTIME_ROOT": str(self.runtime_root)}),
            research_service_instance=self.research_service,
            signal_service_instance=self.signal_service,
            scheduler_instance=self.scheduler,
            reviewer_instance=self.reviewer,
            automation_instance=self.automation,
            async_runner=lambda fn: fn(),
        )

    def _build_deferred_service(self, sink: list[object]) -> ResearchRuntimeService:
        return ResearchRuntimeService(
            config_loader=lambda: load_qlib_config(env={"QUANT_QLIB_RUNTIME_ROOT": str(self.runtime_root)}),
            research_service_instance=self.research_service,
            signal_service_instance=self.signal_service,
            scheduler_instance=self.scheduler,
            reviewer_instance=self.reviewer,
            automation_instance=self.automation,
            async_runner=lambda fn: sink.append(fn),
        )

    def test_start_training_records_running_then_success(self) -> None:
        service = self._build_service()

        accepted = service.start_training()
        latest = service.get_status()

        self.assertEqual(accepted["action"], "training")
        self.assertEqual(latest["status"], "succeeded")
        self.assertEqual(latest["last_completed_action"], "training")
        self.assertEqual(self.scheduler.calls, ["research_train"])
        self.assertEqual(self.research_service.training_runs, 0)
        self.assertEqual(latest["progress_pct"], 100)
        self.assertIn("/research", latest["result_paths"])

    def test_start_pipeline_runs_training_inference_and_signal_refresh(self) -> None:
        service = self._build_service()

        service.start_pipeline()
        latest = service.get_status()

        self.assertEqual(latest["status"], "succeeded")
        self.assertEqual(latest["last_completed_action"], "pipeline")
        self.assertEqual(self.scheduler.calls, ["research_train", "research_infer", "signal_output", "review"])
        self.assertEqual(self.research_service.training_runs, 0)
        self.assertEqual(self.research_service.inference_runs, 0)
        self.assertEqual(self.signal_service.refresh_runs, 0)
        self.assertEqual(latest["current_stage"], "completed")
        self.assertEqual(len(self.automation.cycles), 2)
        recorded_cycle, count_towards_daily = self.automation.cycles[-1]
        self.assertFalse(count_towards_daily)
        self.assertEqual(recorded_cycle["source"], "manual_pipeline")
        self.assertEqual(recorded_cycle["recommended_symbol"], "ETHUSDT")
        self.assertEqual(recorded_cycle["next_action"], "enter_dry_run")
        self.assertEqual(recorded_cycle["research_template"], "single_asset_timing_strict")
        self.assertEqual(recorded_cycle["strategy_template"], "trend_pullback_timing")

    def test_start_pipeline_records_manual_cycle_as_running_before_background_job_finishes(self) -> None:
        deferred_jobs: list[object] = []
        service = self._build_deferred_service(deferred_jobs)

        accepted = service.start_pipeline()

        self.assertEqual(len(self.automation.cycles), 1)
        recorded_cycle, count_towards_daily = self.automation.cycles[0]
        self.assertFalse(count_towards_daily)
        self.assertEqual(recorded_cycle["source"], "manual_pipeline")
        self.assertEqual(recorded_cycle["status"], "running")
        self.assertEqual(recorded_cycle["next_action"], "wait_pipeline_completion")
        self.assertEqual(recorded_cycle["recommended_symbol"], "ETHUSDT")
        self.assertEqual(recorded_cycle["research_template"], "single_asset_timing_strict")
        self.assertEqual(recorded_cycle["strategy_template"], "trend_pullback_timing")
        self.assertEqual(len(deferred_jobs), 1)
        self.assertEqual(accepted["action"], "pipeline")

        deferred_jobs[0]()
        final_cycle, _ = self.automation.cycles[-1]
        self.assertEqual(final_cycle["status"], "succeeded")
        self.assertEqual(final_cycle["next_action"], "enter_dry_run")

    def test_start_training_records_scheduler_task_without_counting_automatic_cycles(self) -> None:
        service = self._build_service()

        service.start_training()
        latest = service.get_status()

        self.assertEqual(latest["status"], "succeeded")
        self.assertEqual(self.scheduler.calls, ["research_train"])
        self.assertEqual(len(self.automation.cycles), 0)

    def test_next_estimate_uses_previous_duration(self) -> None:
        service = self._build_service()

        service.start_training()
        snapshot_path = self.runtime_root / "research_runtime_status.json"
        payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
        # 使用新格式历史记录（包含时间戳和 duration_seconds）
        payload["history"]["training"] = [
            {
                "started_at": "2026-04-06T10:00:00+00:00",
                "finished_at": "2026-04-06T10:00:12+00:00",
                "duration_seconds": 12.5
            }
        ]
        snapshot_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

        status = service.get_status()
        self.assertEqual(status["estimated_seconds"]["training"], 13)

    def test_stale_running_state_becomes_interrupted_and_allows_restart(self) -> None:
        running_state = {
            "status": "running",
            "action": "training",
            "current_stage": "training_model",
            "progress_pct": 55,
            "started_at": "2026-04-06T00:00:00+00:00",
            "finished_at": "",
            "message": "正在训练",
            "history": {},
            "last_completed_action": "",
            "result_paths": ["/research", "/evaluation", "/signals"],
        }
        snapshot_path = self.runtime_root / "research_runtime_status.json"
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        snapshot_path.write_text(json.dumps(running_state, ensure_ascii=False, indent=2), encoding="utf-8")

        service = self._build_service()
        self.research_service.has_training = True
        status = service.get_status()
        self.assertEqual(status["status"], "interrupted")

        accepted = service.start_inference()
        self.assertIn(accepted["status"], {"running", "succeeded"})


if __name__ == "__main__":
    unittest.main()
