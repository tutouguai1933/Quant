"""训练特征列受注册表启停影响。"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.worker.factor_registry import FactorRegistry  # noqa: E402
from services.worker.qlib_features import (  # noqa: E402
    AUXILIARY_FEATURE_COLUMNS,
    PRIMARY_FEATURE_COLUMNS,
)
from services.worker.qlib_runner import QlibRunner  # noqa: E402


def _make_runner() -> QlibRunner:
    """造一个不带配置文件的 runner 实例，只设置因子列。"""
    runner = object.__new__(QlibRunner)
    runner._config = SimpleNamespace(
        primary_feature_columns=PRIMARY_FEATURE_COLUMNS,
        auxiliary_feature_columns=AUXILIARY_FEATURE_COLUMNS,
    )
    return runner


def test_active_primary_columns_exclude_registry_disabled():
    """注册表禁用某主因子后，active 特征列不再包含它。"""
    runner = _make_runner()
    with tempfile.TemporaryDirectory() as tmp:
        registry = FactorRegistry(state_path=Path(tmp) / "state.json")
        registry.set_enabled("body_pct", False)
        columns = runner._active_primary_feature_columns(registry=registry)
        assert "body_pct" not in columns
        assert "ema20_gap_pct" in columns


def test_active_auxiliary_columns_exclude_registry_disabled():
    """注册表禁用某辅助因子后，active 特征列不再包含它。"""
    runner = _make_runner()
    with tempfile.TemporaryDirectory() as tmp:
        registry = FactorRegistry(state_path=Path(tmp) / "state.json")
        registry.set_enabled("rsi14", False)
        columns = runner._active_auxiliary_feature_columns(registry=registry)
        assert "rsi14" not in columns
        assert "cci20" in columns


def test_active_columns_stay_within_config_scope():
    """config 指定范围优先：注册表启用更多因子时，仍只返回 config 里的列。"""
    runner = object.__new__(QlibRunner)
    runner._config = SimpleNamespace(
        primary_feature_columns=("ema20_gap_pct", "trend_gap_pct"),
        auxiliary_feature_columns=("rsi14",),
    )
    with tempfile.TemporaryDirectory() as tmp:
        registry = FactorRegistry(state_path=Path(tmp) / "state.json")
        columns = runner._active_primary_feature_columns(registry=registry)
        assert columns == ("ema20_gap_pct", "trend_gap_pct")
        aux = runner._active_auxiliary_feature_columns(registry=registry)
        assert aux == ("rsi14",)
