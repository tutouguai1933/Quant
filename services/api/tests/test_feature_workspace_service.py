from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.api.app.services.feature_workspace_service import FeatureWorkspaceService  # noqa: E402


class FeatureWorkspaceServiceTests(unittest.TestCase):
    def test_workspace_returns_factor_protocol_summary(self) -> None:
        service = FeatureWorkspaceService(research_reader=_FakeResearchService(), controls_builder=_fake_controls)

        item = service.get_workspace()

        self.assertEqual(item["status"], "ready")
        self.assertEqual(item["overview"]["feature_version"], "v2")
        self.assertEqual(item["overview"]["factor_count"], 4)
        self.assertIn("trend", item["categories"])
        self.assertIn("ema20_gap_pct", item["roles"]["primary"])
        self.assertIn("rsi14", item["roles"]["auxiliary"])
        self.assertEqual(item["preprocessing"]["missing_policy"], "坏行直接丢弃")
        self.assertEqual(item["controls"]["missing_policy"], "strict_drop")
        self.assertEqual(item["controls"]["outlier_policy"], "clip")
        self.assertEqual(item["controls"]["normalization_policy"], "fixed_4dp")
        self.assertIn("neutral_fill", item["controls"]["available_missing_policies"])
        self.assertIn("raw", item["controls"]["available_outlier_policies"])
        self.assertIn("zscore_by_symbol", item["controls"]["available_normalization_policies"])
        self.assertIn("4h", item["timeframe_profiles"])
        self.assertEqual(item["factors"][0]["name"], "ema20_gap_pct")
        self.assertIn("controls", item)

    def test_workspace_handles_missing_factor_protocol(self) -> None:
        service = FeatureWorkspaceService(research_reader=_UnavailableResearchService(), controls_builder=_fake_controls)

        item = service.get_workspace()

        self.assertEqual(item["status"], "unavailable")
        self.assertEqual(item["overview"]["factor_count"], 0)
        self.assertEqual(item["factors"], [])
        self.assertEqual(item["categories"], {})

    def test_workspace_uses_factor_protocol_as_ready_signal(self) -> None:
        service = FeatureWorkspaceService(research_reader=_ProtocolOnlyResearchService(), controls_builder=_fake_controls)

        item = service.get_workspace()

        self.assertEqual(item["status"], "ready")
        self.assertEqual(item["overview"]["factor_count"], 1)
        self.assertEqual(item["factors"][0]["name"], "ema20_gap_pct")


class _FakeResearchService:
    def get_factory_report(self) -> dict[str, object]:
        return {
            "status": "ready",
            "factor_protocol": {
                "version": "v2",
                "categories": {
                    "trend": ["ema20_gap_pct", "ema55_gap_pct"],
                    "oscillator": ["rsi14"],
                },
                "roles": {
                    "primary": ["ema20_gap_pct", "ema55_gap_pct"],
                    "auxiliary": ["rsi14"],
                },
                "preprocessing": {
                    "missing_policy": "坏行直接丢弃",
                    "outlier_policy": "裁剪极值",
                    "normalization_policy": "统一输出四位小数字符串",
                },
                "timeframe_profiles": {
                    "1h": {"ema_fast": 20, "ema_slow": 55},
                    "4h": {"ema_fast": 12, "ema_slow": 34},
                },
                "factors": [
                    {"name": "ema20_gap_pct", "category": "trend", "role": "primary", "description": "价格相对 EMA20 的偏离"},
                    {"name": "ema55_gap_pct", "category": "trend", "role": "primary", "description": "价格相对 EMA55 的偏离"},
                    {"name": "rsi14", "category": "oscillator", "role": "auxiliary", "description": "14 周期 RSI"},
                    {"name": "atr_pct", "category": "volatility", "role": "auxiliary", "description": "ATR 波动率"},
                ],
            },
        }


class _UnavailableResearchService:
    def get_factory_report(self) -> dict[str, object]:
        return {"status": "unavailable"}


class _ProtocolOnlyResearchService:
    def get_factory_report(self) -> dict[str, object]:
        return {
            "status": "unavailable",
            "factor_protocol": {
                "version": "v2",
                "categories": {"trend": ["ema20_gap_pct"]},
                "roles": {"primary": ["ema20_gap_pct"], "auxiliary": []},
                "preprocessing": {
                    "missing_policy": "坏行直接丢弃",
                    "outlier_policy": "裁剪极值",
                    "normalization_policy": "统一输出四位小数字符串",
                },
                "timeframe_profiles": {"4h": {"ema_fast": 12}},
                "factors": [
                    {"name": "ema20_gap_pct", "category": "trend", "role": "primary", "description": "价格相对 EMA20 的偏离"},
                ],
            },
        }


def _fake_controls() -> dict[str, object]:
    return {
        "config": {
            "features": {
                "primary_factors": ["ema20_gap_pct", "ema55_gap_pct"],
                "auxiliary_factors": ["rsi14"],
                "missing_policy": "strict_drop",
                "outlier_policy": "clip",
                "normalization_policy": "fixed_4dp",
            }
        },
        "options": {
            "primary_factors": ["ema20_gap_pct", "ema55_gap_pct"],
            "auxiliary_factors": ["rsi14", "atr_pct"],
            "missing_policies": ["neutral_fill", "strict_drop"],
            "outlier_policies": ["clip", "raw"],
            "normalization_policies": ["fixed_4dp", "zscore_by_symbol"],
        },
    }


if __name__ == "__main__":
    unittest.main()
