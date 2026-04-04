from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class QlibReplayDocsTests(unittest.TestCase):
    def test_readme_mentions_dataset_snapshot_and_validation_review(self) -> None:
        content = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("dataset/latest_dataset_snapshot.json", content)
        self.assertIn("runs/experiment_index.json", content)
        self.assertIn("GET /api/v1/tasks/validation-review", content)

    def test_ops_qlib_mentions_backtest_assumptions_and_review_task(self) -> None:
        content = (REPO_ROOT / "docs" / "ops-qlib.md").read_text(encoding="utf-8")

        self.assertIn("QUANT_QLIB_BACKTEST_FEE_BPS", content)
        self.assertIn("QUANT_QLIB_BACKTEST_SLIPPAGE_BPS", content)
        self.assertIn("POST /api/v1/tasks/review", content)


if __name__ == "__main__":
    unittest.main()
