"""BTC 相关性因子。"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.worker.qlib_features import compute_btc_correlation  # noqa: E402


def test_btc_correlation_perfect_positive():
    btc = [1.0, 2.0, 3.0]
    coin = [10.0, 20.0, 30.0]
    assert compute_btc_correlation(coin, btc) > 0.99


def test_btc_correlation_missing_btc_neutral():
    assert compute_btc_correlation([1.0, 2.0, 3.0], []) == 0.0
