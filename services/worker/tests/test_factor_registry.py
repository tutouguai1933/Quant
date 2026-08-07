"""运行时因子启停注册表。"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.worker.factor_registry import FactorRegistry  # noqa: E402


def test_registry_defaults_use_static_enabled():
    with tempfile.TemporaryDirectory() as tmp:
        registry = FactorRegistry(state_path=Path(tmp) / "state.json")
        # ema20 默认启用
        assert registry.is_enabled("ema20_gap_pct")
        # 静态定义里 enabled=False 的默认禁用
        assert not registry.is_enabled("atr_pct")


def test_registry_set_enabled_persists():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "state.json"
        registry = FactorRegistry(state_path=path)
        registry.set_enabled("atr_pct", True)
        registry2 = FactorRegistry(state_path=path)
        assert registry2.is_enabled("atr_pct")


def test_registry_disable_factor():
    with tempfile.TemporaryDirectory() as tmp:
        registry = FactorRegistry(state_path=Path(tmp) / "state.json")
        registry.set_enabled("ema20_gap_pct", False)
        assert not registry.is_enabled("ema20_gap_pct")


def test_registry_enabled_columns_filters_by_role():
    with tempfile.TemporaryDirectory() as tmp:
        registry = FactorRegistry(state_path=Path(tmp) / "state.json")
        primary = registry.enabled_columns("primary")
        # 主因子应包含 ema20，不应包含辅助 rsi14
        assert "ema20_gap_pct" in primary
        assert "rsi14" not in primary
        assert "body_pct" in primary
