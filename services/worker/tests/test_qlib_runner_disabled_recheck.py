"""禁用因子复检：对比静态禁用与运行时禁用因子的最近 IC。"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.worker.qlib_runner import QlibRunner  # noqa: E402


def test_disabled_recheck_marks_static_disabled():
    runner = object.__new__(QlibRunner)
    rows = []
    for i in range(30):
        rows.append({"generated_at": 1783486800000 + i * 3600000, "future_return_pct": "0.5", "atr_pct": "1.0", "roc6": "1.0", "close_return_pct": "0.1", "range_pct": "2.0", "momentum_accel": "0.5"})
    result = runner._build_disabled_factors_recheck(rows)
    assert "atr_pct" in result["factors"]
    assert "roc6" in result["factors"]
    assert result["factors"]["atr_pct"]["current_ic"] is not None
