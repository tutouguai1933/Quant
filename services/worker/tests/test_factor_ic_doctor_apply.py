"""体检动作落地：禁用因子进入注册表。"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.worker.factor_ic_doctor import FactorIcDoctor  # noqa: E402
from services.worker.factor_registry import FactorRegistry  # noqa: E402


def test_disable_action_updates_registry():
    with tempfile.TemporaryDirectory() as tmp:
        doctor = FactorIcDoctor(state_path=Path(tmp) / "ic.json")
        registry = FactorRegistry(state_path=Path(tmp) / "registry.json")
        # 两次负 IC → disable
        doctor.assess({"factor_evaluation": {"ic_series": [{"factor": "body_pct", "ic": -0.02}]}})
        result = doctor.assess({"factor_evaluation": {"ic_series": [{"factor": "body_pct", "ic": -0.03}]}})
        assert result["actions"]["body_pct"] == "disable"

        applied = doctor.apply_actions(result, registry=registry)
        assert "body_pct" in applied["disabled"]
        assert not registry.is_enabled("body_pct")


def test_downgrade_action_reported_not_disabled():
    with tempfile.TemporaryDirectory() as tmp:
        doctor = FactorIcDoctor(state_path=Path(tmp) / "ic.json")
        registry = FactorRegistry(state_path=Path(tmp) / "registry.json")
        result = doctor.assess({"factor_evaluation": {"ic_series": [{"factor": "body_pct", "ic": 0.01}]}})
        assert result["actions"]["body_pct"] == "downgrade"
        applied = doctor.apply_actions(result, registry=registry)
        assert "body_pct" in applied["downgraded"]
        assert registry.is_enabled("body_pct")  # 降权不禁用
