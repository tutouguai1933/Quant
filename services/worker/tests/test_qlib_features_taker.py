"""taker 主动买量占比因子。"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.worker.qlib_features import compute_taker_buy_ratio  # noqa: E402


def test_taker_ratio_basic():
    assert abs(compute_taker_buy_ratio(volume=100.0, taker_buy=60.0) - 0.6) < 1e-9


def test_taker_ratio_zero_volume_neutral():
    assert compute_taker_buy_ratio(volume=0.0, taker_buy=0.0) == 0.5


def test_taker_ratio_missing_taker_data_neutral():
    assert compute_taker_buy_ratio(volume=100.0, taker_buy=None) == 0.5
