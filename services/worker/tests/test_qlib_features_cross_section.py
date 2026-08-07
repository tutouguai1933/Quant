"""横截面相对强弱因子。"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.worker.qlib_features import compute_relative_strength  # noqa: E402


def test_relative_strength_ranks_symbols():
    """相对强弱 = 该币 20 根收益 - 全部币收益中位数。"""
    symbol_returns = {"BTCUSDT": 2.0, "ETHUSDT": 5.0, "SOLUSDT": 1.0}
    assert compute_relative_strength("ETHUSDT", symbol_returns, window=20) > 0
    assert compute_relative_strength("SOLUSDT", symbol_returns, window=20) < 0


def test_relative_strength_unknown_symbol_neutral():
    symbol_returns = {"BTCUSDT": 2.0}
    assert compute_relative_strength("DOGEUSDT", symbol_returns, window=20) == 0.0
