from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import services.api.app.routes.signals as signals_route  # noqa: E402
import services.api.app.services.research_service as research_service_module  # noqa: E402
from services.api.app.services.auth_service import auth_service  # noqa: E402
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

    def test_research_service_returns_ranked_candidates(self) -> None:
        self.service.run_training()
        self.service.run_inference()

        snapshot = self.service.get_factory_snapshot()

        self.assertEqual(snapshot["status"], "ready")
        self.assertIn("candidates", snapshot)
        self.assertIn("summary", snapshot)
        self.assertTrue(snapshot["candidates"])
        self.assertEqual(snapshot["summary"]["candidate_count"], len(snapshot["candidates"]))

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
        self.assertEqual(report["experiments"]["training"]["status"], "completed")
        self.assertEqual(report["experiments"]["inference"]["status"], "completed")

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
        self.assertEqual(training_response["data"]["item"]["status"], "completed")
        self.assertEqual(inference_response["data"]["item"]["status"], "completed")
        self.assertTrue(inference_response["data"]["item"]["signals"])

    def test_research_routes_require_login_for_write_actions(self) -> None:
        training_response = signals_route.run_research_training()
        inference_response = signals_route.run_research_inference()

        self.assertEqual(training_response["error"]["code"], "unauthorized")
        self.assertEqual(inference_response["error"]["code"], "unauthorized")


class _FakeMarketReader:
    def get_symbol_chart(
        self,
        symbol: str,
        interval: str = "1h",
        limit: int = 120,
        allowed_symbols: tuple[str, ...] | None = None,
    ) -> dict[str, object]:
        base_price = 100 if symbol == "BTCUSDT" else 50
        items = []
        for index in range(120):
            close = base_price + index * 0.8
            items.append(
                {
                    "open_time": 1712016000000 + (index * 3600000),
                    "open": str(close - 1),
                    "high": str(close + 2),
                    "low": str(close - 2),
                    "close": str(close),
                    "volume": str(1000 + (index * 100)),
                    "close_time": 1712019599999 + (index * 3600000),
                }
            )
        return {"items": items, "overlays": {}, "markers": {"signals": [], "entries": [], "stops": []}}


if __name__ == "__main__":
    unittest.main()
