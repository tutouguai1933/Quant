from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.api.app.services.research_cockpit_service import build_market_research_brief  # noqa: E402
from services.api.app.services.research_cockpit_service import build_symbol_research_cockpit  # noqa: E402


class ResearchCockpitServiceTests(unittest.TestCase):
    def test_build_market_research_brief_returns_unified_fields(self) -> None:
        summary = build_market_research_brief(
            symbol="BTCUSDT",
            recommended_strategy="trend_breakout",
            evaluation={
                "decision": "signal",
                "confidence": "high",
                "reason": "close_breaks_recent_high_research_confirmed",
                "research_gate": {"status": "confirmed_by_research"},
            },
            research_summary={
                "score": "0.7100",
                "signal": "long",
                "model_version": "qlib-minimal-20260402120000",
                "explanation": "trend_gap=2.1%",
                "generated_at": "2026-04-02T12:00:00+00:00",
            },
        )

        self.assertEqual(
            set(summary.keys()),
            {
                "research_bias",
                "recommended_strategy",
                "confidence",
                "research_gate",
                "primary_reason",
                "research_explanation",
                "model_version",
                "generated_at",
            },
        )
        self.assertEqual(summary["research_bias"], "bullish")
        self.assertEqual(summary["recommended_strategy"], "trend_breakout")
        self.assertEqual(summary["confidence"], "high")
        self.assertEqual(summary["research_gate"]["status"], "confirmed_by_research")
        self.assertEqual(summary["primary_reason"], "close_breaks_recent_high_research_confirmed")
        self.assertEqual(summary["research_explanation"], "trend_gap=2.1%")
        self.assertEqual(summary["model_version"], "qlib-minimal-20260402120000")
        self.assertEqual(summary["generated_at"], "2026-04-02T12:00:00+00:00")

    def test_build_symbol_research_cockpit_includes_full_fields(self) -> None:
        summary = build_symbol_research_cockpit(
            symbol="BTCUSDT",
            recommended_strategy="trend_breakout",
            evaluation={
                "decision": "signal",
                "confidence": "high",
                "reason": "close_breaks_recent_high_research_confirmed",
                "research_gate": {"status": "confirmed_by_research"},
            },
            research_summary={
                "score": "0.7100",
                "signal": "long",
                "model_version": "qlib-minimal-20260402120000",
                "explanation": "trend_gap=2.1%",
                "generated_at": "2026-04-02T12:00:00+00:00",
            },
            markers={
                "signals": [{"price": "106"}],
                "entries": [{"price": "105"}],
                "stops": [{"price": "99"}],
            },
        )

        self.assertEqual(
            set(summary.keys()),
            {
                "research_bias",
                "recommended_strategy",
                "confidence",
                "research_gate",
                "primary_reason",
                "research_explanation",
                "model_version",
                "generated_at",
                "signal_count",
                "entry_hint",
                "stop_hint",
                "overlay_summary",
            },
        )
        self.assertEqual(summary["research_bias"], "bullish")
        self.assertEqual(summary["signal_count"], 1)
        self.assertEqual(summary["entry_hint"], "105")
        self.assertEqual(summary["stop_hint"], "99")
        self.assertEqual(summary["overlay_summary"], "1 个信号点 / 入场 105 / 止损 99")
        self.assertEqual(summary["research_gate"]["status"], "confirmed_by_research")

    def test_build_symbol_research_cockpit_degrades_invalid_score_and_missing_research(self) -> None:
        invalid_score_summary = build_symbol_research_cockpit(
            symbol="BTCUSDT",
            recommended_strategy="trend_breakout",
            evaluation={
                "decision": "signal",
                "confidence": "high",
                "reason": "close_breaks_recent_high",
                "research_gate": {"status": "invalid_score"},
            },
            research_summary={"score": "NaN"},
            markers={"signals": [], "entries": [], "stops": []},
        )

        missing_research_summary = build_market_research_brief(
            symbol="BTCUSDT",
            recommended_strategy="trend_breakout",
            evaluation={
                "decision": "watch",
                "confidence": "medium",
                "reason": "close_stays_inside_recent_range",
                "research_gate": {"status": "unavailable"},
            },
            research_summary=None,
        )

        self.assertEqual(invalid_score_summary["research_bias"], "unavailable")
        self.assertEqual(invalid_score_summary["research_gate"]["status"], "invalid_score")
        self.assertEqual(invalid_score_summary["research_explanation"], "研究结果暂不可用")
        self.assertEqual(invalid_score_summary["entry_hint"], "n/a")
        self.assertEqual(invalid_score_summary["stop_hint"], "n/a")
        self.assertEqual(invalid_score_summary["overlay_summary"], "0 个信号点 / 入场 n/a / 止损 n/a")
        self.assertEqual(missing_research_summary["research_explanation"], "该币种暂无研究结论")
        self.assertEqual(missing_research_summary["research_gate"]["status"], "unavailable")

    def test_build_market_research_brief_rejects_unknown_signal_and_dirty_gate_values(self) -> None:
        summary = build_market_research_brief(
            symbol="BTCUSDT",
            recommended_strategy="trend_breakout",
            evaluation={
                "decision": "watch",
                "confidence": None,
                "reason": None,
                "research_gate": {"status": None, "score": "0.6200"},
            },
            research_summary={
                "score": "0.6200",
                "signal": "weird",
                "model_version": None,
                "generated_at": None,
            },
        )

        self.assertEqual(summary["research_bias"], "unavailable")
        self.assertEqual(summary["research_gate"]["status"], "unavailable")
        self.assertEqual(summary["confidence"], "low")
        self.assertEqual(summary["primary_reason"], "n/a")
        self.assertEqual(summary["model_version"], "")
        self.assertEqual(summary["generated_at"], "")

    def test_build_market_research_brief_maps_flat_signal_to_neutral(self) -> None:
        summary = build_market_research_brief(
            symbol="BTCUSDT",
            recommended_strategy="trend_pullback",
            evaluation={
                "decision": "watch",
                "confidence": "low",
                "reason": "pullback_pending",
                "research_gate": {"status": "neutral_research"},
            },
            research_summary={
                "score": "0.4547",
                "signal": "flat",
                "model_version": "qlib-minimal-20260401185935033840",
                "generated_at": "2026-04-01T18:59:37.111024+00:00",
            },
        )

        self.assertEqual(summary["research_bias"], "neutral")

    def test_build_symbol_research_cockpit_tolerates_none_marker_lists(self) -> None:
        summary = build_symbol_research_cockpit(
            symbol="BTCUSDT",
            recommended_strategy="trend_breakout",
            evaluation={
                "decision": "watch",
                "confidence": "medium",
                "reason": "close_stays_inside_recent_range",
                "research_gate": {"status": "neutral_research"},
            },
            research_summary={
                "score": "0.5100",
                "signal": "neutral",
                "model_version": "qlib-minimal-20260402120000",
                "generated_at": "2026-04-02T12:00:00+00:00",
            },
            markers={"signals": None, "entries": None, "stops": None},
        )

        self.assertEqual(summary["signal_count"], 0)
        self.assertEqual(summary["entry_hint"], "n/a")
        self.assertEqual(summary["stop_hint"], "n/a")
        self.assertEqual(summary["overlay_summary"], "0 个信号点 / 入场 n/a / 止损 n/a")


if __name__ == "__main__":
    unittest.main()
