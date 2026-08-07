# services/worker/tests/test_qlib_features_correlation.py
"""因子相关性矩阵单元测试。"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.worker.qlib_features import build_factor_correlation_matrix  # noqa: E402


def test_correlation_matrix_identical_factors_are_1():
    rows = [
        {"ema20_gap_pct": "1.0", "ema55_gap_pct": "2.0", "trend_gap_pct": "3.0"},
        {"ema20_gap_pct": "2.0", "ema55_gap_pct": "4.0", "trend_gap_pct": "6.0"},
        {"ema20_gap_pct": "3.0", "ema55_gap_pct": "6.0", "trend_gap_pct": "9.0"},
    ]
    matrix = build_factor_correlation_matrix(rows, factor_names=["ema20_gap_pct", "ema55_gap_pct", "trend_gap_pct"])
    # ema20 与 trend 完全线性相关
    assert abs(matrix["pairs"][0]["correlation"]) > 0.99


def test_correlation_matrix_reports_pairs():
    rows = [
        {"ema20_gap_pct": "1.0", "ema55_gap_pct": "2.0"},
        {"ema20_gap_pct": "2.0", "ema55_gap_pct": "2.1"},
        {"ema20_gap_pct": "3.0", "ema55_gap_pct": "2.2"},
    ]
    matrix = build_factor_correlation_matrix(rows, factor_names=["ema20_gap_pct", "ema55_gap_pct"])
    assert len(matrix["pairs"]) == 1
    assert matrix["pairs"][0]["factor_a"] == "ema20_gap_pct"
    assert matrix["pairs"][0]["factor_b"] == "ema55_gap_pct"


def test_correlation_matrix_insufficient_samples():
    rows = [{"ema20_gap_pct": "1.0", "ema55_gap_pct": "2.0"}]
    matrix = build_factor_correlation_matrix(rows, factor_names=["ema20_gap_pct", "ema55_gap_pct"])
    assert matrix["pairs"] == []


def test_correlation_matrix_returns_factor_metadata():
    rows = [
        {"ema20_gap_pct": "1.0", "ema55_gap_pct": "2.0"},
        {"ema20_gap_pct": "2.0", "ema55_gap_pct": "2.1"},
        {"ema20_gap_pct": "3.0", "ema55_gap_pct": "2.2"},
    ]
    matrix = build_factor_correlation_matrix(rows, factor_names=["ema20_gap_pct", "ema55_gap_pct"])
    assert matrix["factors"] == ["ema20_gap_pct", "ema55_gap_pct"]
