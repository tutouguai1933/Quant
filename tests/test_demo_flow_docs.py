from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEMO_SCRIPT = REPO_ROOT / "infra" / "scripts" / "demo_flow.ps1"
OPS_DOC = REPO_ROOT / "docs" / "ops.md"
README_DOC = REPO_ROOT / "README.md"


class DemoFlowDocsTests(unittest.TestCase):
    def test_demo_script_exists_and_covers_main_flow(self) -> None:
        self.assertTrue(DEMO_SCRIPT.exists(), f"missing file: {DEMO_SCRIPT}")
        content = DEMO_SCRIPT.read_text(encoding="utf-8")
        self.assertIn("/api/v1/auth/login", content)
        self.assertIn("/api/v1/signals/pipeline/run", content)
        self.assertIn("/api/v1/strategies/1/start", content)
        self.assertIn("/api/v1/strategies/1/dispatch-latest-signal", content)
        self.assertIn("/api/v1/risk-events", content)
        self.assertIn("/api/v1/tasks/reconcile", content)

    def test_ops_doc_describes_demo_and_failure_path(self) -> None:
        content = OPS_DOC.read_text(encoding="utf-8")
        self.assertIn("最小演示流程", content)
        self.assertIn("demo_flow.ps1", content)
        self.assertIn("风控拒绝", content)
        self.assertIn("失败任务", content)
        self.assertIn("1. 创建或导入一个策略定义", content)
        self.assertIn("7. 人为制造一个失败任务或风险事件并确认可见", content)

    def test_readme_points_to_acceptance_path(self) -> None:
        content = README_DOC.read_text(encoding="utf-8")
        self.assertIn("最小演示与验收", content)
        self.assertIn("docs/ops.md", content)
        self.assertIn("infra/scripts/demo_flow.ps1", content)
        self.assertIn("signal -> risk -> execution -> monitoring", content)


if __name__ == "__main__":
    unittest.main()
