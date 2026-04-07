from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from services.api.app.services.workbench_config_service import WorkbenchConfigService


class WorkbenchConfigServiceTests(unittest.TestCase):
    def test_get_config_returns_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "workbench.json"
            service = WorkbenchConfigService(config_path=path)

            config = service.get_config()

        self.assertIn("priority_tags", config)
        self.assertIn("models", config)
        self.assertIn("backtest", config)
        self.assertIn("automation", config)
        self.assertEqual(config["backtest"]["holding_window"], "1-3d")
        self.assertGreater(len(config["priority_tags"]), 0)
        self.assertIn("long_run_seconds", config["automation"])

    def test_env_overrides_are_applied(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "workbench.json"
            overrides = {"QUANT_WORKBENCH_BACKTEST_MAX_DRAWDOWN_PCT": "-20"}
            service = WorkbenchConfigService(config_path=path, env=overrides)

            config = service.get_config()

        self.assertEqual(config["backtest"]["max_drawdown_pct"], "-20")

    def test_persist_config_merges_updates(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "workbench.json"
            service = WorkbenchConfigService(config_path=path)

            updated = service.persist_config({"backtest": {"holding_window": "2-4d"}})
            written = json.loads(path.read_text(encoding="utf-8"))
            refreshed = service.get_config()

        self.assertEqual(updated["backtest"]["holding_window"], "2-4d")
        self.assertEqual(refreshed["backtest"]["holding_window"], "2-4d")
        self.assertEqual(written["backtest"]["holding_window"], "2-4d")


if __name__ == "__main__":
    unittest.main()
