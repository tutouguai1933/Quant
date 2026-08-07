# services/worker/tests/test_qlib_features_correlation.py
"""因子相关性矩阵单元测试。"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.worker.qlib_features import build_factor_correlation_matrix  # noqa: E402


def test_correlation_matrix_fully_linear_factors_are_1():
    rows = [
        {"ema20_gap_pct": "1.0", "ema55_gap_pct": "2.0", "trend_gap_pct": "3.0"},
        {"ema20_gap_pct": "2.0", "ema55_gap_pct": "4.0", "trend_gap_pct": "6.0"},
        {"ema20_gap_pct": "3.0", "ema55_gap_pct": "6.0", "trend_gap_pct": "9.0"},
    ]
    matrix = build_factor_correlation_matrix(rows, factor_names=["ema20_gap_pct", "ema55_gap_pct", "trend_gap_pct"])
    pairs = {frozenset((p["factor_a"], p["factor_b"])): p for p in matrix["pairs"]}
    assert pairs[frozenset(("ema20_gap_pct", "trend_gap_pct"))]["correlation"] > 0.99
    assert pairs[frozenset(("ema20_gap_pct", "ema55_gap_pct"))]["correlation"] > 0.99


def test_correlation_matrix_threshold_0_8():
    # 构造 20 行：ema20 与 ema55 完全线性（corr≈1 → redundant），
    # ema20 与 body 低相关（corr < 0.8 → 不冗余）
    import math

    rows = []
    for i in range(20):
        x = float(i)
        noise = math.sin(i)  # 让 body 与 ema20 的相关系数明显小于 0.8
        rows.append(
            {
                "ema20_gap_pct": str(x),
                "ema55_gap_pct": str(x * 2 + 1),  # 与 ema20 完全线性
                "body_pct": str(50 + (x % 3) * 20 + noise),  # 与 ema20 低相关
            }
        )
    matrix = build_factor_correlation_matrix(
        rows,
        factor_names=["ema20_gap_pct", "ema55_gap_pct", "body_pct"],
    )
    all_pairs = {frozenset((p["factor_a"], p["factor_b"])): p for p in matrix["pairs"]}
    redundant_set = {frozenset((p["factor_a"], p["factor_b"])) for p in matrix["redundancy_pairs"]}
    # ema20-ema55 对：相关≈1，必须在 redundancy_pairs 中且 redundant=True
    ema_pair = all_pairs[frozenset(("ema20_gap_pct", "ema55_gap_pct"))]
    assert ema_pair["redundant"] is True
    assert frozenset(("ema20_gap_pct", "ema55_gap_pct")) in redundant_set
    # ema20-body 对：相关 < 0.8，redundant=False 且不在 redundancy_pairs
    body_pair = all_pairs[frozenset(("ema20_gap_pct", "body_pct"))]
    assert body_pair["redundant"] is False
    assert frozenset(("ema20_gap_pct", "body_pct")) not in redundant_set


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
