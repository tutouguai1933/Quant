from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class QlibValidationWorkflowDocsTests(unittest.TestCase):
    def test_readme_describes_fixed_qlib_validation_order(self) -> None:
        content = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("Qlib 验证工作流", content)
        self.assertIn("1. 先做研究训练", content)
        self.assertIn("5. 先跑 `dry-run`", content)
        self.assertIn("6. `dry-run` 稳定后，才允许进入小额 `live`", content)
        self.assertIn("7. `live` 完成后，统一回看余额、订单、持仓、任务和风险", content)

    def test_ops_qlib_describes_same_validation_order(self) -> None:
        content = (REPO_ROOT / "docs" / "ops-qlib.md").read_text(encoding="utf-8")

        self.assertIn("固定验证顺序", content)
        self.assertIn("1. 研究训练", content)
        self.assertIn("4. 只挑允许进入 `dry-run` 的候选", content)
        self.assertIn("6. `dry-run` 稳定后才允许进入小额 `live`", content)
        self.assertIn("7. `live` 完成后统一回看余额、订单、持仓、任务、风险", content)

    def test_plan_marks_validation_workflow_done(self) -> None:
        content = (REPO_ROOT / "plan.md").read_text(encoding="utf-8")

        self.assertIn("- [x] 固定 `dry-run -> 小额 live -> 复盘` 验证工作流", content)


if __name__ == "__main__":
    unittest.main()
