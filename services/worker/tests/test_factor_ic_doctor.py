"""因子 IC 体检：低 IC 自动降权，负 IC 连续两轮禁用。"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.worker.factor_ic_doctor import FactorIcDoctor  # noqa: E402


def _eval(factor: str, ic: float):
    return {"factor_evaluation": {"ic_series": [{"factor": factor, "ic": ic, "rank_ic": ic * 0.9}], "quantile_nav": []}}


def test_low_ic_recommends_weight_downgrade():
    doctor = FactorIcDoctor()
    result = doctor.assess(_eval("ema20_gap_pct", 0.01))
    assert result["actions"]["ema20_gap_pct"] == "downgrade"


def test_healthy_ic_no_action():
    doctor = FactorIcDoctor()
    result = doctor.assess(_eval("ema20_gap_pct", 0.06))
    assert result["actions"]["ema20_gap_pct"] == "keep"


def test_negative_ic_first_round_warns():
    doctor = FactorIcDoctor()
    result = doctor.assess(_eval("ema20_gap_pct", -0.02))
    assert result["actions"]["ema20_gap_pct"] == "watch"


def test_negative_ic_two_rounds_disables():
    doctor = FactorIcDoctor()
    doctor.assess(_eval("ema20_gap_pct", -0.02))
    result = doctor.assess(_eval("ema20_gap_pct", -0.03))
    assert result["actions"]["ema20_gap_pct"] == "disable"


def test_assess_returns_rounds_and_timestamp():
    doctor = FactorIcDoctor()
    result = doctor.assess(_eval("ema20_gap_pct", -0.02))
    assert "negative_rounds" in result
    assert "assessed_at" in result
