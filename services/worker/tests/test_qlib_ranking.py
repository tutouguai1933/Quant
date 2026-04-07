"""Qlib 候选排行测试。

这个文件只验证候选排行和 dry-run 准入门的最小行为。
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.worker.qlib_ranking import rank_candidates  # noqa: E402


class QlibRankingTests(unittest.TestCase):
    def test_rank_candidates_sorts_by_score_descending(self) -> None:
        result = rank_candidates(
            [
                {
                    "symbol": "ETHUSDT",
                    "strategy_template": "trend_pullback_timing",
                    "score": "0.6200",
                    "backtest": {"metrics": _passing_metrics()},
                },
                {
                    "symbol": "BTCUSDT",
                    "strategy_template": "trend_breakout_timing",
                    "score": "0.7800",
                    "backtest": {"metrics": _passing_metrics()},
                },
            ]
        )

        self.assertEqual(result["items"][0]["symbol"], "BTCUSDT")
        self.assertEqual(result["items"][1]["symbol"], "ETHUSDT")

    def test_rank_candidates_marks_dry_run_ready_only_when_metrics_pass(self) -> None:
        result = rank_candidates(
            [
                {
                    "symbol": "BTCUSDT",
                    "strategy_template": "trend_breakout_timing",
                    "score": "0.7800",
                    "backtest": {"metrics": _passing_metrics()},
                }
            ]
        )

        self.assertEqual(result["items"][0]["dry_run_gate"]["status"], "passed")
        self.assertTrue(result["items"][0]["allowed_to_dry_run"])
        self.assertEqual(result["summary"]["candidate_count"], 1)
        self.assertEqual(result["summary"]["ready_count"], 1)

    def test_rank_candidates_marks_failed_when_backtest_metrics_do_not_pass(self) -> None:
        result = rank_candidates(
            [
                {
                    "symbol": "DOGEUSDT",
                    "strategy_template": "trend_pullback_timing",
                    "score": "0.8100",
                    "backtest": {"metrics": _failing_metrics()},
                }
            ]
        )

        self.assertEqual(result["items"][0]["dry_run_gate"]["status"], "failed")
        self.assertFalse(result["items"][0]["allowed_to_dry_run"])

    def test_rank_candidates_respects_configured_min_score_threshold(self) -> None:
        result = rank_candidates(
            [
                {
                    "symbol": "BTCUSDT",
                    "strategy_template": "trend_breakout_timing",
                    "score": "0.7800",
                    "backtest": {"metrics": _passing_metrics()},
                }
            ],
            thresholds={"dry_run_min_score": "0.80"},
        )

        self.assertEqual(result["items"][0]["score_gate"]["status"], "failed")
        self.assertIn("score_too_low", result["items"][0]["dry_run_gate"]["reasons"])
        self.assertFalse(result["items"][0]["allowed_to_dry_run"])

    def test_rank_candidates_uses_stricter_gate_for_strict_template(self) -> None:
        result = rank_candidates(
            [
                {
                    "symbol": "BTCUSDT",
                    "strategy_template": "trend_pullback_timing",
                    "score": "0.5800",
                    "backtest": {"metrics": _passing_metrics()},
                }
            ],
            research_template="single_asset_timing_strict",
        )

        self.assertEqual(result["items"][0]["score_gate"]["status"], "failed")
        self.assertIn("score_too_low", result["items"][0]["dry_run_gate"]["reasons"])

    def test_rank_candidates_exposes_live_gate_when_dry_run_passes_but_live_is_stricter(self) -> None:
        result = rank_candidates(
            [
                {
                    "symbol": "ETHUSDT",
                    "strategy_template": "trend_breakout_timing",
                    "score": "0.7000",
                    "backtest": {"metrics": _passing_metrics()},
                }
            ],
            validation={
                "sample_count": 24,
                "positive_rate": "0.52",
                "avg_future_return_pct": "0.70",
            },
            thresholds={
                "live_min_score": "0.75",
                "live_min_positive_rate": "0.60",
                "live_min_net_return_pct": "0.50",
            },
        )

        self.assertTrue(result["items"][0]["allowed_to_dry_run"])
        self.assertFalse(result["items"][0]["allowed_to_live"])
        self.assertEqual(result["items"][0]["live_gate"]["status"], "failed")
        self.assertIn("live_score_too_low", result["items"][0]["live_gate"]["reasons"])

    def test_rank_candidates_blocks_dry_run_when_rule_gate_fails(self) -> None:
        result = rank_candidates(
            [
                {
                    "symbol": "BTCUSDT",
                    "strategy_template": "trend_breakout_timing",
                    "score": "0.7800",
                    "backtest": {"metrics": _passing_metrics()},
                    "rule_gate": {"status": "failed", "reasons": ["trend_broken"]},
                }
            ]
        )

        self.assertEqual(result["items"][0]["rule_gate"]["status"], "failed")
        self.assertEqual(result["items"][0]["dry_run_gate"]["status"], "failed")
        self.assertIn("trend_broken", result["items"][0]["dry_run_gate"]["reasons"])
        self.assertFalse(result["items"][0]["allowed_to_dry_run"])

    def test_rank_candidates_can_disable_rule_gate_from_thresholds(self) -> None:
        result = rank_candidates(
            [
                {
                    "symbol": "BTCUSDT",
                    "strategy_template": "trend_breakout_timing",
                    "score": "0.7800",
                    "backtest": {"metrics": _passing_metrics()},
                    "rule_gate": {"status": "failed", "reasons": ["trend_broken"]},
                }
            ],
            thresholds={
                "enable_rule_gate": False,
            },
        )

        self.assertEqual(result["items"][0]["rule_gate"]["status"], "failed")
        self.assertEqual(result["items"][0]["dry_run_gate"]["status"], "passed")
        self.assertTrue(result["items"][0]["allowed_to_dry_run"])

    def test_rank_candidates_blocks_dry_run_when_sample_count_is_too_low(self) -> None:
        result = rank_candidates(
            [
                {
                    "symbol": "ETHUSDT",
                    "strategy_template": "trend_pullback_timing",
                    "score": "0.7200",
                    "backtest": {
                        "metrics": {
                            **_passing_metrics(),
                            "sample_count": "12",
                        }
                    },
                }
            ]
        )

        self.assertEqual(result["items"][0]["dry_run_gate"]["status"], "failed")
        self.assertIn("sample_count_too_low", result["items"][0]["dry_run_gate"]["reasons"])
        self.assertFalse(result["items"][0]["allowed_to_dry_run"])

    def test_rank_candidates_blocks_dry_run_when_loss_streak_is_too_long(self) -> None:
        result = rank_candidates(
            [
                {
                    "symbol": "SOLUSDT",
                    "strategy_template": "trend_breakout_timing",
                    "score": "0.8400",
                    "backtest": {
                        "metrics": {
                            **_passing_metrics(),
                            "max_loss_streak": "4",
                        }
                    },
                }
            ]
        )

        self.assertEqual(result["items"][0]["dry_run_gate"]["status"], "failed")
        self.assertIn("loss_streak_too_long", result["items"][0]["dry_run_gate"]["reasons"])
        self.assertFalse(result["items"][0]["allowed_to_dry_run"])

    def test_rank_candidates_blocks_dry_run_when_sample_count_is_missing(self) -> None:
        metrics = _passing_metrics()
        metrics.pop("sample_count", None)
        result = rank_candidates(
            [
                {
                    "symbol": "BTCUSDT",
                    "strategy_template": "trend_breakout_timing",
                    "score": "0.7800",
                    "backtest": {"metrics": metrics},
                }
            ]
        )

        self.assertEqual(result["items"][0]["dry_run_gate"]["status"], "failed")
        self.assertIn("sample_count_too_low", result["items"][0]["dry_run_gate"]["reasons"])
        self.assertFalse(result["items"][0]["allowed_to_dry_run"])

    def test_rank_candidates_blocks_dry_run_when_rule_gate_status_is_missing_but_reason_exists(self) -> None:
        result = rank_candidates(
            [
                {
                    "symbol": "BTCUSDT",
                    "strategy_template": "trend_breakout_timing",
                    "score": "0.7800",
                    "backtest": {"metrics": {**_passing_metrics(), "sample_count": "24"}},
                    "rule_gate": {"reasons": ["trend_broken"]},
                }
            ]
        )

        self.assertEqual(result["items"][0]["rule_gate"]["status"], "failed")
        self.assertIn("trend_broken", result["items"][0]["rule_gate"]["reasons"])
        self.assertFalse(result["items"][0]["allowed_to_dry_run"])

    def test_rank_candidates_keeps_rule_gate_reason_as_single_string_item(self) -> None:
        result = rank_candidates(
            [
                {
                    "symbol": "BTCUSDT",
                    "strategy_template": "trend_breakout_timing",
                    "score": "0.7800",
                    "backtest": {"metrics": {**_passing_metrics(), "sample_count": "24"}},
                    "rule_gate": {"status": "failed", "reasons": "trend_broken"},
                }
            ]
        )

        self.assertEqual(result["items"][0]["rule_gate"]["reasons"], ["trend_broken"])
        self.assertIn("trend_broken", result["items"][0]["dry_run_gate"]["reasons"])

    def test_rank_candidates_blocks_dry_run_when_validation_summary_is_weak(self) -> None:
        result = rank_candidates(
            [
                {
                    "symbol": "BTCUSDT",
                    "strategy_template": "trend_breakout_timing",
                    "score": "0.7800",
                    "backtest": {"metrics": _passing_metrics()},
                }
            ],
            validation={
                "sample_count": 12,
                "positive_rate": "0.41",
                "avg_future_return_pct": "-0.30",
            },
        )

        self.assertEqual(result["items"][0]["research_validation_gate"]["status"], "failed")
        self.assertIn("validation_positive_rate_too_low", result["items"][0]["dry_run_gate"]["reasons"])
        self.assertIn("validation_future_return_not_positive", result["items"][0]["dry_run_gate"]["reasons"])
        self.assertFalse(result["items"][0]["allowed_to_dry_run"])
        self.assertEqual(result["items"][0]["review_status"], "needs_research_iteration")
        self.assertEqual(result["items"][0]["next_action"], "continue_research")

    def test_rank_candidates_respects_configured_validation_sample_threshold(self) -> None:
        result = rank_candidates(
            [
                {
                    "symbol": "BTCUSDT",
                    "strategy_template": "trend_breakout_timing",
                    "score": "0.7800",
                    "backtest": {"metrics": _passing_metrics()},
                }
            ],
            validation={
                "sample_count": 12,
                "positive_rate": "0.62",
                "avg_future_return_pct": "0.40",
            },
            thresholds={
                "validation_min_sample_count": "16",
            },
        )

        self.assertEqual(result["items"][0]["research_validation_gate"]["status"], "failed")
        self.assertIn("validation_sample_count_too_low", result["items"][0]["dry_run_gate"]["reasons"])
        self.assertFalse(result["items"][0]["allowed_to_dry_run"])

    def test_rank_candidates_blocks_dry_run_when_net_return_turns_negative_after_costs(self) -> None:
        metrics = _passing_metrics()
        metrics["gross_return_pct"] = "1.2000"
        metrics["net_return_pct"] = "-0.4000"
        metrics["total_return_pct"] = "-0.4000"
        result = rank_candidates(
            [
                {
                    "symbol": "DOGEUSDT",
                    "strategy_template": "trend_pullback_timing",
                    "score": "0.7100",
                    "backtest": {"metrics": metrics},
                }
            ],
            validation={
                "sample_count": 20,
                "positive_rate": "0.55",
                "avg_future_return_pct": "0.80",
            },
        )

        self.assertIn("non_positive_return", result["items"][0]["dry_run_gate"]["reasons"])
        self.assertIn("validation_backtest_drift_too_large", result["items"][0]["dry_run_gate"]["reasons"])
        self.assertFalse(result["items"][0]["allowed_to_dry_run"])

    def test_rank_candidates_exposes_consistency_gate_for_drifted_candidate(self) -> None:
        result = rank_candidates(
            [
                {
                    "symbol": "BTCUSDT",
                    "strategy_template": "trend_breakout_timing",
                    "score": "0.7800",
                    "backtest": {"metrics": {**_failing_metrics(), "sample_count": "24", "net_return_pct": "-3.20"}},
                    "rule_gate": {"status": "failed", "reasons": ["trend_broken"]},
                }
            ],
            validation={
                "sample_count": 12,
                "positive_rate": "0.60",
                "avg_future_return_pct": "1.80",
            },
        )

        self.assertEqual(result["items"][0]["consistency_gate"]["status"], "failed")
        self.assertIn("validation_backtest_drift_too_large", result["items"][0]["consistency_gate"]["reasons"])

    def test_rank_candidates_blocks_when_validation_drift_from_training_is_too_large(self) -> None:
        result = rank_candidates(
            [
                {
                    "symbol": "ETHUSDT",
                    "strategy_template": "trend_breakout_timing",
                    "score": "0.7900",
                    "backtest": {"metrics": _passing_metrics()},
                }
            ],
            validation={
                "sample_count": 20,
                "positive_rate": "0.48",
                "avg_future_return_pct": "0.20",
            },
            training_metrics={
                "positive_rate": "0.82",
                "avg_future_return_pct": "1.80",
            },
        )

        self.assertIn("validation_training_drift_too_large", result["items"][0]["dry_run_gate"]["reasons"])
        self.assertFalse(result["items"][0]["allowed_to_dry_run"])

    def test_rank_candidates_marks_ready_candidate_with_execution_priority(self) -> None:
        result = rank_candidates(
            [
                {
                    "symbol": "ETHUSDT",
                    "strategy_template": "trend_pullback_timing",
                    "score": "0.8200",
                    "backtest": {"metrics": _passing_metrics()},
                }
            ],
            validation={
                "sample_count": 16,
                "positive_rate": "0.56",
                "avg_future_return_pct": "1.10",
            },
        )

        item = result["items"][0]
        self.assertEqual(item["review_status"], "ready_for_dry_run")
        self.assertEqual(item["next_action"], "enter_dry_run")
        self.assertEqual(item["execution_priority"], 0)

    def test_rank_candidates_force_validation_promotes_only_top_candidate_when_all_blocked(self) -> None:
        result = rank_candidates(
            [
                {
                    "symbol": "ETHUSDT",
                    "strategy_template": "trend_pullback_timing",
                    "score": "0.8600",
                    "backtest": {"metrics": _failing_metrics()},
                },
                {
                    "symbol": "BTCUSDT",
                    "strategy_template": "trend_breakout_timing",
                    "score": "0.7200",
                    "backtest": {"metrics": _failing_metrics()},
                },
            ],
            force_validation_top_candidate=True,
        )

        self.assertEqual(result["summary"]["candidate_count"], 2)
        self.assertEqual(result["summary"]["ready_count"], 1)
        self.assertTrue(result["items"][0]["allowed_to_dry_run"])
        self.assertEqual(result["items"][0]["review_status"], "forced_validation")
        self.assertEqual(result["items"][0]["next_action"], "enter_dry_run")
        self.assertTrue(result["items"][0]["forced_for_validation"])
        self.assertEqual(result["items"][0]["forced_reason"], "force_top_candidate_for_validation")
        self.assertFalse(result["items"][1]["allowed_to_dry_run"])
        self.assertFalse(result["items"][1]["forced_for_validation"])

    def test_rank_candidates_recommendation_score_is_not_only_raw_score(self) -> None:
        result = rank_candidates(
            [
                {
                    "symbol": "BTCUSDT",
                    "strategy_template": "trend_breakout_timing",
                    "score": "0.9000",
                    "backtest": {"metrics": {**_passing_metrics(), "net_return_pct": "3.0000", "max_drawdown_pct": "-10.0000"}},
                    "recommendation_context": {"regime": "range", "indicator_mix": "oscillator+volume"},
                },
                {
                    "symbol": "ETHUSDT",
                    "strategy_template": "trend_breakout_timing",
                    "score": "0.8200",
                    "backtest": {"metrics": {**_passing_metrics(), "net_return_pct": "12.0000", "max_drawdown_pct": "-2.0000", "sharpe": "2.1000"}},
                    "recommendation_context": {"regime": "trend", "indicator_mix": "trend+momentum+volume"},
                },
            ],
            validation={
                "sample_count": 20,
                "positive_rate": "0.62",
                "avg_future_return_pct": "0.80",
            },
            training_metrics={
                "positive_rate": "0.64",
                "avg_future_return_pct": "0.90",
            },
        )

        eth = next(item for item in result["items"] if item["symbol"] == "ETHUSDT")
        btc = next(item for item in result["items"] if item["symbol"] == "BTCUSDT")
        self.assertGreater(float(btc["score"]), float(eth["score"]))
        self.assertGreater(float(eth["recommendation_score"]), float(btc["recommendation_score"]))
        self.assertIn("trend", eth["recommendation_reason"])
        self.assertEqual(eth["next_action"], "enter_dry_run")

    def test_rank_candidates_respects_configured_backtest_win_rate_threshold(self) -> None:
        result = rank_candidates(
            [
                {
                    "symbol": "ETHUSDT",
                    "strategy_template": "trend_pullback_timing",
                    "score": "0.7600",
                    "backtest": {"metrics": _passing_metrics()},
                }
            ],
            thresholds={
                "dry_run_min_win_rate": "0.60",
            },
        )

        self.assertEqual(result["items"][0]["dry_run_gate"]["status"], "failed")
        self.assertIn("win_rate_too_low", result["items"][0]["dry_run_gate"]["reasons"])
        self.assertFalse(result["items"][0]["allowed_to_dry_run"])

    def test_rank_candidates_respects_configured_live_backtest_thresholds(self) -> None:
        result = rank_candidates(
            [
                {
                    "symbol": "ETHUSDT",
                    "strategy_template": "trend_breakout_timing",
                    "score": "0.8200",
                    "backtest": {"metrics": _passing_metrics()},
                }
            ],
            validation={
                "sample_count": 24,
                "positive_rate": "0.70",
                "avg_future_return_pct": "0.80",
            },
            thresholds={
                "live_min_score": "0.80",
                "live_min_positive_rate": "0.60",
                "live_min_net_return_pct": "0.20",
                "live_min_win_rate": "0.65",
            },
        )

        self.assertTrue(result["items"][0]["allowed_to_dry_run"])
        self.assertFalse(result["items"][0]["allowed_to_live"])
        self.assertEqual(result["items"][0]["live_gate"]["status"], "failed")
        self.assertIn("live_win_rate_too_low", result["items"][0]["live_gate"]["reasons"])


def _passing_metrics() -> dict[str, str]:
    return {
        "total_return_pct": "14.20",
        "max_drawdown_pct": "-5.10",
        "sharpe": "1.10",
        "win_rate": "0.58",
        "turnover": "0.24",
        "sample_count": "24",
        "max_loss_streak": "1",
    }


def _failing_metrics() -> dict[str, str]:
    return {
        "total_return_pct": "-3.20",
        "max_drawdown_pct": "-22.40",
        "sharpe": "0.10",
        "win_rate": "0.41",
        "turnover": "0.92",
    }


if __name__ == "__main__":
    unittest.main()
