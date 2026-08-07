"""训练结果携带相关性矩阵。"""
from __future__ import annotations

import sys
from types import SimpleNamespace
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.worker.qlib_features import PRIMARY_FEATURE_COLUMNS  # noqa: E402
from services.worker.qlib_runner import QlibRunner  # noqa: E402


def test_factor_evaluation_includes_correlation_matrix():
    # 用一个最小 runner，直接调用 _build_factor_evaluation
    runner = object.__new__(QlibRunner)
    # object.__new__ 跳过 __init__，需手动注入最小配置
    runner._config = SimpleNamespace(primary_feature_columns=PRIMARY_FEATURE_COLUMNS)
    rows = []
    for i in range(30):
        rows.append({
            "generated_at": 1783486800000 + i * 3600000,
            "future_return_pct": str(i % 5 - 2),
            "ema20_gap_pct": str(i),
            "ema55_gap_pct": str(i + 1),   # 与 ema20 高度相关
            "body_pct": str(i % 7 - 3),
            "volume_ratio": str(1.0),
            "trend_gap_pct": str(i * 2),
            "breakout_strength": str(i % 3),
            "trend_strength": str(i),
            "volatility_contraction": str(50),
            "volume_price_divergence": str(0),
            "bull_bear_ratio": str(1),
            "rsi14": str(50),
            "cci20": str(0),
            "stoch_k14": str(50),
        })
    evaluation = runner._build_factor_evaluation(rows)
    assert "correlation_matrix" in evaluation
    assert evaluation["correlation_matrix"]["redundancy_pairs"], "应检出 ema20/ema55 冗余"
