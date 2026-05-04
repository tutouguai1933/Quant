"""terminal_series_service 单元测试。"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pytest

from services.api.app.services.terminal_series_service import terminal_series_service


def test_build_training_curve_empty():
    """测试训练曲线空状态。"""
    report = {"latest_training": {}}
    result = terminal_series_service.build_training_curve(report)
    assert result["series"] == []
    assert result["meta"]["data_quality"] == "empty"
    assert "training_curve_missing" in result["meta"]["warnings"]


def test_build_training_curve_with_none_training():
    """测试训练曲线当 latest_training 为 None。"""
    report = {}
    result = terminal_series_service.build_training_curve(report)
    assert result["series"] == []
    assert result["meta"]["data_quality"] == "empty"


def test_build_training_curve_with_data():
    """测试训练曲线有数据。"""
    report = {
        "latest_training": {
            "training_metrics": {
                "training_curve": [
                    {"step": 1, "train_score": 0.6, "validation_score": 0.5, "test_score": None}
                ]
            }
        }
    }
    result = terminal_series_service.build_training_curve(report)
    assert len(result["series"]) == 1
    assert result["series"][0]["step"] == 1
    assert result["meta"]["data_quality"] == "real"


def test_build_training_curve_with_multiple_steps():
    """测试训练曲线有多步数据。"""
    report = {
        "latest_training": {
            "training_metrics": {
                "training_curve": [
                    {"step": 1, "train_score": 0.6, "validation_score": 0.5, "test_score": None},
                    {"step": 2, "train_score": 0.65, "validation_score": 0.55, "test_score": 0.52},
                    {"step": 3, "train_score": 0.7, "validation_score": 0.6, "test_score": 0.58},
                ]
            }
        }
    }
    result = terminal_series_service.build_training_curve(report)
    assert len(result["series"]) == 3
    assert result["series"][0]["train_score"] == 0.6
    assert result["series"][1]["validation_score"] == 0.55
    assert result["series"][2]["test_score"] == 0.58


def test_build_training_curve_skips_non_dict_items():
    """测试训练曲线跳过非字典项。"""
    report = {
        "latest_training": {
            "training_metrics": {
                "training_curve": [
                    {"step": 1, "train_score": 0.6},
                    "invalid_item",
                    None,
                    {"step": 2, "train_score": 0.65},
                ]
            }
        }
    }
    result = terminal_series_service.build_training_curve(report)
    assert len(result["series"]) == 2


def test_build_feature_importance_empty():
    """测试特征重要性空状态。"""
    report = {"latest_training": {}}
    result = terminal_series_service.build_feature_importance(report)
    assert result["series"] == []
    assert result["meta"]["data_quality"] == "empty"


def test_build_feature_importance_with_data():
    """测试特征重要性有数据。"""
    report = {
        "latest_training": {
            "training_metrics": {
                "feature_importance": [
                    {"factor": "ema20_gap_pct", "category": "trend", "importance": 0.35, "rank": 1},
                    {"factor": "rsi14", "category": "oscillator", "importance": 0.25, "rank": 2},
                ]
            }
        }
    }
    result = terminal_series_service.build_feature_importance(report)
    assert len(result["series"]) == 2
    assert result["series"][0]["factor"] == "ema20_gap_pct"
    assert result["meta"]["data_quality"] == "real"


def test_build_feature_importance_sorts_by_rank():
    """测试特征重要性按 rank 排序。"""
    report = {
        "latest_training": {
            "training_metrics": {
                "feature_importance": [
                    {"factor": "rsi14", "category": "oscillator", "importance": 0.25, "rank": 2},
                    {"factor": "ema20_gap_pct", "category": "trend", "importance": 0.35, "rank": 1},
                    {"factor": "volume_ratio", "category": "volume", "importance": 0.15, "rank": 3},
                ]
            }
        }
    }
    result = terminal_series_service.build_feature_importance(report)
    assert result["series"][0]["factor"] == "ema20_gap_pct"
    assert result["series"][1]["factor"] == "rsi14"
    assert result["series"][2]["factor"] == "volume_ratio"


def test_build_backtest_performance_series_empty():
    """测试回测净值序列空状态。"""
    report = {"latest_training": {}}
    result = terminal_series_service.build_backtest_performance_series(report)
    assert result["series"] == []
    assert "backtest_series_missing" in result["meta"]["warnings"]


def test_build_backtest_performance_series_with_data():
    """测试回测净值序列有数据。"""
    report = {
        "latest_training": {
            "backtest": {
                "series": {
                    "performance": [
                        {
                            "date": "2026-01-01",
                            "strategy_nav": 1.0,
                            "benchmark_nav": 1.0,
                            "drawdown_pct": 0.0,
                            "daily_return_pct": 0.01,
                            "turnover": 0.05,
                        }
                    ]
                }
            }
        }
    }
    result = terminal_series_service.build_backtest_performance_series(report)
    assert len(result["series"]) == 1
    assert result["series"][0]["date"] == "2026-01-01"
    assert result["meta"]["data_quality"] == "real"


def test_build_backtest_performance_series_with_multiple_days():
    """测试回测净值序列有多天数据。"""
    report = {
        "latest_training": {
            "backtest": {
                "series": {
                    "performance": [
                        {"date": "2026-01-01", "strategy_nav": 1.0, "benchmark_nav": 1.0, "drawdown_pct": 0.0},
                        {"date": "2026-01-02", "strategy_nav": 1.02, "benchmark_nav": 1.01, "drawdown_pct": -0.01},
                        {"date": "2026-01-03", "strategy_nav": 1.01, "benchmark_nav": 1.005, "drawdown_pct": -0.02},
                    ]
                }
            }
        }
    }
    result = terminal_series_service.build_backtest_performance_series(report)
    assert len(result["series"]) == 3


def test_build_backtest_performance_series_with_specific_backtest_id():
    """测试按 ID 获取回测净值序列。"""
    report = {
        "leaderboard": [
            {
                "symbol": "ETHUSDT",
                "backtest": {
                    "series": {
                        "performance": [
                            {"date": "2026-01-01", "strategy_nav": 1.05, "benchmark_nav": 1.02, "drawdown_pct": 0.0}
                        ]
                    }
                },
            }
        ]
    }
    result = terminal_series_service.build_backtest_performance_series(report, backtest_id="ETHUSDT")
    assert len(result["series"]) == 1
    assert result["series"][0]["strategy_nav"] == 1.05


def test_build_top_candidate_nav_series_empty():
    """测试候选净值对比空状态。"""
    report = {}
    result = terminal_series_service.build_top_candidate_nav_series(report)
    assert result["series"] == []
    assert "candidate_backtest_series_missing" in result["meta"]["warnings"]


def test_build_top_candidate_nav_series_with_leaderboard():
    """测试候选净值对比有排行榜数据。"""
    report = {
        "leaderboard": [
            {"symbol": "ETHUSDT", "score": 0.85},
            {"symbol": "BTCUSDT", "score": 0.75},
        ]
    }
    result = terminal_series_service.build_top_candidate_nav_series(report, limit=5)
    # 当前实现返回空状态，因为数据结构可能不包含序列
    assert result["series"] == []


def test_build_factor_ic_series_empty():
    """测试因子 IC 序列空状态。"""
    report = {}
    result = terminal_series_service.build_factor_ic_series(report)
    assert result["series"] == []
    assert "factor_ic_missing" in result["meta"]["warnings"]


def test_build_factor_ic_series_with_data():
    """测试因子 IC 序列有数据。"""
    report = {
        "factor_evaluation": {
            "ic_series": [
                {"date": "2026-01-01", "factor": "ema20_gap_pct", "ic": 0.05, "rank_ic": 0.04, "cumulative_ic": 0.05}
            ]
        }
    }
    result = terminal_series_service.build_factor_ic_series(report)
    assert len(result["series"]) == 1
    assert result["series"][0]["date"] == "2026-01-01"
    assert result["series"][0]["ic"] == 0.05
    assert result["meta"]["data_quality"] == "real"


def test_build_factor_ic_series_with_multiple_records():
    """测试因子 IC 序列有多条记录。"""
    report = {
        "factor_evaluation": {
            "ic_series": [
                {"date": "2026-01-01", "factor": "ema20_gap_pct", "ic": 0.05, "cumulative_ic": 0.05},
                {"date": "2026-01-02", "factor": "ema20_gap_pct", "ic": 0.03, "cumulative_ic": 0.08},
                {"date": "2026-01-03", "factor": "ema20_gap_pct", "ic": -0.02, "cumulative_ic": 0.06},
            ]
        }
    }
    result = terminal_series_service.build_factor_ic_series(report)
    assert len(result["series"]) == 3
    assert result["series"][2]["cumulative_ic"] == 0.06


def test_build_factor_quantile_nav_empty():
    """测试因子分组收益空状态。"""
    report = {}
    result = terminal_series_service.build_factor_quantile_nav(report)
    assert result["series"] == []
    assert "factor_quantile_missing" in result["meta"]["warnings"]


def test_build_factor_quantile_nav_with_data():
    """测试因子分组收益有数据。"""
    report = {
        "factor_evaluation": {
            "quantile_nav": [
                {"date": "2026-01-01", "q1": 1.0, "q2": 1.01, "q3": 1.02, "q4": 1.03, "q5": 1.05, "long_short": 0.05}
            ]
        }
    }
    result = terminal_series_service.build_factor_quantile_nav(report)
    assert len(result["series"]) == 1
    assert result["series"][0]["date"] == "2026-01-01"
    assert result["series"][0]["q1"] == 1.0
    assert result["series"][0]["long_short"] == 0.05
    assert result["meta"]["data_quality"] == "real"


def test_build_factor_quantile_nav_with_multiple_dates():
    """测试因子分组收益有多日数据。"""
    report = {
        "factor_evaluation": {
            "quantile_nav": [
                {"date": "2026-01-01", "q1": 1.0, "q2": 1.01, "q3": 1.02, "q4": 1.03, "q5": 1.05, "long_short": 0.05},
                {"date": "2026-01-02", "q1": 1.01, "q2": 1.02, "q3": 1.03, "q4": 1.04, "q5": 1.06, "long_short": 0.05},
            ]
        }
    }
    result = terminal_series_service.build_factor_quantile_nav(report)
    assert len(result["series"]) == 2


def test_resolve_backtest_data_with_latest():
    """测试解析 latest 回测数据。"""
    report = {
        "latest_training": {
            "backtest": {"metrics": {"net_return_pct": "5.0"}}
        }
    }
    result = terminal_series_service._resolve_backtest_data(report, "latest")
    assert result is not None
    assert result["metrics"]["net_return_pct"] == "5.0"


def test_resolve_backtest_data_with_empty_string():
    """测试空字符串回测 ID 解析为 latest。"""
    report = {
        "latest_training": {
            "backtest": {"metrics": {"net_return_pct": "5.0"}}
        }
    }
    result = terminal_series_service._resolve_backtest_data(report, "")
    assert result is not None


def test_resolve_backtest_data_with_symbol():
    """测试按 symbol 解析回测数据。"""
    report = {
        "leaderboard": [
            {"symbol": "ETHUSDT", "backtest": {"metrics": {"net_return_pct": "3.0"}}}
        ]
    }
    result = terminal_series_service._resolve_backtest_data(report, "ETHUSDT")
    assert result is not None
    assert result["metrics"]["net_return_pct"] == "3.0"


def test_resolve_backtest_data_with_symbol_case_insensitive():
    """测试按 symbol 解析回测数据（大小写不敏感）。"""
    report = {
        "leaderboard": [
            {"symbol": "ETHUSDT", "backtest": {"metrics": {"net_return_pct": "3.0"}}}
        ]
    }
    result = terminal_series_service._resolve_backtest_data(report, "ethusdt")
    assert result is not None


def test_resolve_backtest_data_not_found():
    """测试未找到回测数据返回 None。"""
    report = {}
    result = terminal_series_service._resolve_backtest_data(report, "NOTEXIST")
    assert result is None


def test_safe_float_with_none():
    """测试 None 值安全转换。"""
    result = terminal_series_service._safe_float(None)
    assert result == 0.0


def test_safe_float_with_string():
    """测试字符串值安全转换。"""
    result = terminal_series_service._safe_float("3.14")
    assert result == 3.14


def test_safe_float_with_percent_string():
    """测试百分号字符串值安全转换。"""
    result = terminal_series_service._safe_float("5.5%")
    assert result == 5.5


def test_safe_float_with_invalid_string():
    """测试无效字符串值安全转换。"""
    result = terminal_series_service._safe_float("invalid")
    assert result == 0.0


def test_safe_float_with_number():
    """测试数字值安全转换。"""
    result = terminal_series_service._safe_float(42)
    assert result == 42.0
