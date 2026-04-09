from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class QuantHardeningPlanDocsTests(unittest.TestCase):
    def test_hardening_plan_mentions_indicator_taxonomy(self) -> None:
        content = (REPO_ROOT / "docs" / "archive" / "plans" / "2026-04-06-quant-system-hardening-implementation.md").read_text(encoding="utf-8")

        self.assertIn("趋势类", content)
        self.assertIn("动量类", content)
        self.assertIn("震荡类", content)
        self.assertIn("成交量类", content)
        self.assertIn("波动率类", content)

    def test_hardening_plan_mentions_indicator_usage_principles(self) -> None:
        content = (REPO_ROOT / "docs" / "archive" / "plans" / "2026-04-06-quant-system-hardening-implementation.md").read_text(encoding="utf-8")

        self.assertIn("指标和因子要组合使用", content)
        self.assertIn("指标参数要按交易周期调整", content)
        self.assertIn("要先判断行情状态", content)
        self.assertIn("不迷信指标本身", content)


if __name__ == "__main__":
    unittest.main()
