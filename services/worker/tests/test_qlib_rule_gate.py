"""Qlib 规则门测试。

这个文件只验证趋势、波动和量能的最小门控逻辑。
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.worker.qlib_rule_gate import evaluate_rule_gate  # noqa: E402


class QlibRuleGateTests(unittest.TestCase):
    def test_rule_gate_blocks_when_trend_is_broken(self) -> None:
        decision = evaluate_rule_gate(
            {
                "ema20_gap_pct": "-1.2000",
                "ema55_gap_pct": "-2.4000",
                "atr_pct": "3.1000",
                "volume_ratio": "1.1200",
            }
        )

        self.assertFalse(decision["allowed"])
        self.assertEqual(decision["reason"], "trend_broken")

    def test_rule_gate_blocks_when_volatility_is_too_high(self) -> None:
        decision = evaluate_rule_gate(
            {
                "ema20_gap_pct": "1.4000",
                "ema55_gap_pct": "2.1000",
                "atr_pct": "5.6000",
                "volume_ratio": "1.1500",
            }
        )

        self.assertFalse(decision["allowed"])
        self.assertEqual(decision["reason"], "volatility_too_high")

    def test_rule_gate_blocks_when_volume_is_not_confirmed(self) -> None:
        decision = evaluate_rule_gate(
            {
                "ema20_gap_pct": "1.3000",
                "ema55_gap_pct": "2.2000",
                "atr_pct": "2.8000",
                "volume_ratio": "0.9200",
            }
        )

        self.assertFalse(decision["allowed"])
        self.assertEqual(decision["reason"], "volume_not_confirmed")

    def test_rule_gate_allows_when_trend_and_volume_confirm(self) -> None:
        decision = evaluate_rule_gate(
            {
                "ema20_gap_pct": "1.4000",
                "ema55_gap_pct": "2.3000",
                "atr_pct": "2.2000",
                "volume_ratio": "1.1500",
            }
        )

        self.assertTrue(decision["allowed"])
        self.assertEqual(decision["reason"], "ready")

    def test_rule_gate_uses_stricter_thresholds_for_strict_template(self) -> None:
        decision = evaluate_rule_gate(
            {
                "ema20_gap_pct": "1.1000",
                "ema55_gap_pct": "1.7000",
                "atr_pct": "4.7000",
                "volume_ratio": "1.0200",
            },
            research_template="single_asset_timing_strict",
        )

        self.assertFalse(decision["allowed"])
        self.assertEqual(decision["reason"], "strict_template_not_confirmed")

    def test_rule_gate_accepts_runtime_threshold_overrides(self) -> None:
        decision = evaluate_rule_gate(
            {
                "ema20_gap_pct": "0.2000",
                "ema55_gap_pct": "0.4000",
                "atr_pct": "4.1000",
                "volume_ratio": "1.0100",
            },
            thresholds={
                "rule_min_ema20_gap_pct": "0.1",
                "rule_min_ema55_gap_pct": "0.3",
                "rule_max_atr_pct": "4.2",
                "rule_min_volume_ratio": "1.0",
            },
        )

        self.assertTrue(decision["allowed"])
        self.assertEqual(decision["reason"], "ready")

    def test_rule_gate_accepts_runtime_threshold_override(self) -> None:
        decision = evaluate_rule_gate(
            {
                "ema20_gap_pct": "0.2500",
                "ema55_gap_pct": "0.3500",
                "atr_pct": "4.1000",
                "volume_ratio": "1.0100",
            },
            thresholds={
                "rule_min_ema20_gap_pct": "0.20",
                "rule_min_ema55_gap_pct": "0.30",
                "rule_max_atr_pct": "4.20",
                "rule_min_volume_ratio": "1.00",
            },
        )

        self.assertTrue(decision["allowed"])
        self.assertEqual(decision["reason"], "ready")


if __name__ == "__main__":
    unittest.main()
