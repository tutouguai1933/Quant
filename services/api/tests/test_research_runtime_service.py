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
        return {"latest_training": {"model_version": "model-demo"} if self.has_training else {}}


class _FakeSignalService:
    def __init__(self) -> None:
        self.refresh_runs = 0

    def refresh_qlib_signals_from_latest_result(self) -> dict[str, object]:
        self.refresh_runs += 1
        return {"signal_count": 1, "source": "qlib"}


class ResearchRuntimeServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.runtime_root = Path(self._temp_dir.name)
        self.research_service = _FakeResearchService()
        self.signal_service = _FakeSignalService()

    def tearDown(self) -> None:
        self._temp_dir.cleanup()

    def _build_service(self) -> ResearchRuntimeService:
        return ResearchRuntimeService(
            config_loader=lambda: load_qlib_config(env={"QUANT_QLIB_RUNTIME_ROOT": str(self.runtime_root)}),
            research_service_instance=self.research_service,
            signal_service_instance=self.signal_service,
            async_runner=lambda fn: fn(),
        )

    def test_start_training_records_running_then_success(self) -> None:
        service = self._build_service()

        accepted = service.start_training()
        latest = service.get_status()

        self.assertEqual(accepted["action"], "training")
        self.assertEqual(latest["status"], "succeeded")
        self.assertEqual(latest["last_completed_action"], "training")
        self.assertEqual(self.research_service.training_runs, 1)
        self.assertEqual(latest["progress_pct"], 100)
        self.assertIn("/research", latest["result_paths"])

    def test_start_pipeline_runs_training_inference_and_signal_refresh(self) -> None:
        service = self._build_service()

        service.start_pipeline()
        latest = service.get_status()

        self.assertEqual(latest["status"], "succeeded")
        self.assertEqual(latest["last_completed_action"], "pipeline")
        self.assertEqual(self.research_service.training_runs, 1)
        self.assertEqual(self.research_service.inference_runs, 1)
        self.assertEqual(self.signal_service.refresh_runs, 1)
        self.assertEqual(latest["current_stage"], "completed")

    def test_next_estimate_uses_previous_duration(self) -> None:
        service = self._build_service()

        service.start_training()
        snapshot_path = self.runtime_root / "research_runtime_status.json"
        payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
        payload["history"]["training"] = [12.5]
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
