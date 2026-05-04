"""回测图表服务测试。"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pytest

from services.api.app.services.backtest_chart_service import BacktestChartService


@pytest.fixture
def mock_result_provider():
    """提供模拟研究结果。"""
    def provider():
        return {
            "status": "ready",
            "latest_training": {
                "backtest": {
                    "metrics": {
                        "total_return_pct": "15.5",
                        "gross_return_pct": "16.5",
                        "net_return_pct": "15.0",
                        "max_drawdown_pct": "-8.2",
                        "sharpe": "1.25",
                        "win_rate": "0.65",
                        "turnover": "0.6",
                        "max_loss_streak": "3",
                    },
                },
                "training_context": {
                    "sample_window": {
                        "train": {
                            "start_date": "2026-01-01",
                            "end_date": "2026-01-31",
                        },
                    },
                },
            },
            "leaderboard": [
                {
                    "symbol": "BTCUSDT",
                    "backtest": {
                        "metrics": {
                            "total_return_pct": "12.0",
                            "gross_return_pct": "13.0",
                            "net_return_pct": "12.0",
                            "max_drawdown_pct": "-6.0",
                            "sharpe": "1.1",
                            "win_rate": "0.60",
                            "turnover": "0.5",
                            "max_loss_streak": "2",
                        },
                    },
                },
            ],
        }
    return provider


@pytest.fixture
def backtest_chart_service(mock_result_provider):
    """创建图表服务实例。"""
    return BacktestChartService(result_provider=mock_result_provider)


def test_generate_profit_curve_latest(backtest_chart_service):
    """测试生成最新回测的收益曲线。"""
    result = backtest_chart_service.generate_profit_curve("latest")

    assert "series" in result
    assert "meta" in result
    series = result["series"]
    meta = result["meta"]

    assert len(series) > 0
    assert series[0]["date"] == "2026-01-01"
    assert "profit" in series[0]
    assert "cumulative" in series[0]
    assert series[-1]["cumulative"] > series[0]["cumulative"]
    assert meta["data_quality"] == "real"
    assert meta["warnings"] == []


def test_generate_profit_curve_by_symbol(backtest_chart_service):
    """测试按symbol生成收益曲线。"""
    result = backtest_chart_service.generate_profit_curve("BTCUSDT")

    assert "series" in result
    assert "meta" in result
    series = result["series"]
    meta = result["meta"]

    assert len(series) > 0
    assert series[0]["date"] == "2026-01-01"
    assert series[-1]["cumulative"] > series[0]["cumulative"]
    assert meta["data_quality"] == "real"


def test_calculate_statistics(backtest_chart_service):
    """测试计算统计指标。"""
    statistics = backtest_chart_service.calculate_statistics("latest")

    assert statistics["total_return"] == 15.5
    assert statistics["gross_return"] == 16.5
    assert statistics["net_return"] == 15.0
    assert statistics["max_drawdown"] == -8.2
    assert statistics["sharpe_ratio"] == 1.25
    assert statistics["win_rate"] == 0.65
    assert statistics["turnover"] == 0.6
    assert statistics["max_loss_streak"] == 3


def test_calculate_statistics_by_symbol(backtest_chart_service):
    """测试按symbol计算统计指标。"""
    statistics = backtest_chart_service.calculate_statistics("BTCUSDT")

    assert statistics["total_return"] == 12.0
    assert statistics["sharpe_ratio"] == 1.1


def test_generate_trade_distribution(backtest_chart_service):
    """测试生成交易分布数据。"""
    distribution = backtest_chart_service.generate_trade_distribution("latest")

    assert distribution["total_trades"] == 60
    assert distribution["wins"] == 39
    assert distribution["losses"] == 21
    assert distribution["win_rate"] == 0.65


def test_get_all_charts(backtest_chart_service):
    """测试获取所有图表数据。"""
    charts = backtest_chart_service.get_all_charts("latest")

    assert "profit_curve" in charts
    assert "statistics" in charts
    assert "distribution" in charts
    profit_curve = charts["profit_curve"]
    assert "series" in profit_curve
    assert "meta" in profit_curve
    assert len(profit_curve["series"]) > 0
    assert charts["statistics"]["total_return"] == 15.5


# ========== 不生成 demo 曲线测试 ==========

def test_empty_result_returns_empty_series_not_demo():
    """测试空结果时返回空序列，而非 demo 曲线。"""
    def empty_provider():
        return {"status": "unavailable", "latest_training": {}, "leaderboard": []}

    service = BacktestChartService(result_provider=empty_provider)

    result = service.generate_profit_curve("latest")

    # 应返回空序列，而非 demo 数据
    assert result["series"] == []
    assert result["meta"]["data_quality"] == "empty"
    assert "backtest_series_missing" in result["meta"]["warnings"]


def test_empty_result_returns_empty_statistics_not_demo():
    """测试空结果时返回空统计，而非 demo 数据。"""
    def empty_provider():
        return {"status": "unavailable", "latest_training": {}, "leaderboard": []}

    service = BacktestChartService(result_provider=empty_provider)

    statistics = service.calculate_statistics("latest")

    # 应返回空字典，而非 demo 统计数据
    assert statistics == {}


def test_empty_result_returns_empty_distribution_not_demo():
    """测试空结果时返回空分布，而非 demo 数据。"""
    def empty_provider():
        return {"status": "unavailable", "latest_training": {}, "leaderboard": []}

    service = BacktestChartService(result_provider=empty_provider)

    distribution = service.generate_trade_distribution("latest")

    # 应返回空字典，而非 demo 分布数据
    assert distribution == {}


def test_zero_return_returns_empty_series():
    """测试收益率为 0 时返回空序列。"""
    def zero_return_provider():
        return {
            "status": "ready",
            "latest_training": {
                "backtest": {
                    "metrics": {
                        "total_return_pct": "0",
                        "gross_return_pct": "0",
                        "net_return_pct": "0",
                        "max_drawdown_pct": "0",
                        "sharpe": "0",
                        "win_rate": "0",
                        "turnover": "0",
                        "max_loss_streak": "0",
                    },
                },
            },
        }

    service = BacktestChartService(result_provider=zero_return_provider)

    result = service.generate_profit_curve("latest")

    # 收益率为 0 时应返回空序列
    assert result["series"] == []
    assert result["meta"]["data_quality"] == "empty"
    assert "backtest_series_missing" in result["meta"]["warnings"]


def test_zero_win_rate_returns_empty_distribution():
    """测试胜率为 0 时返回空分布。"""
    def zero_win_rate_provider():
        return {
            "status": "ready",
            "latest_training": {
                "backtest": {
                    "metrics": {
                        "total_return_pct": "15.5",
                        "win_rate": "0",
                        "turnover": "0.6",
                    },
                },
            },
        }

    service = BacktestChartService(result_provider=zero_win_rate_provider)

    distribution = service.generate_trade_distribution("latest")

    # 关键指标为 0 时应返回空字典
    assert distribution == {}


def test_zero_turnover_returns_empty_distribution():
    """测试换手率为 0 时返回空分布。"""
    def zero_turnover_provider():
        return {
            "status": "ready",
            "latest_training": {
                "backtest": {
                    "metrics": {
                        "total_return_pct": "15.5",
                        "win_rate": "0.65",
                        "turnover": "0",
                    },
                },
            },
        }

    service = BacktestChartService(result_provider=zero_turnover_provider)

    distribution = service.generate_trade_distribution("latest")

    # 关键指标为 0 时应返回空字典
    assert distribution == {}


def test_missing_backtest_returns_empty_series():
    """测试缺少回测数据时返回空序列。"""
    def missing_backtest_provider():
        return {
            "status": "ready",
            "latest_training": {
                # 没有 backtest 字段
            },
        }

    service = BacktestChartService(result_provider=missing_backtest_provider)

    result = service.generate_profit_curve("latest")

    assert result["series"] == []
    assert result["meta"]["data_quality"] == "empty"


def test_missing_metrics_returns_empty_statistics():
    """测试缺少指标数据时返回空统计。"""
    def missing_metrics_provider():
        return {
            "status": "ready",
            "latest_training": {
                "backtest": {
                    # 没有 metrics 字段
                },
            },
        }

    service = BacktestChartService(result_provider=missing_metrics_provider)

    statistics = service.calculate_statistics("latest")

    assert statistics == {}


def test_nonexistent_symbol_returns_empty_series():
    """测试不存在的 symbol 返回空序列。"""
    def provider():
        return {
            "status": "ready",
            "latest_training": {
                "backtest": {
                    "metrics": {"total_return_pct": "15.5"},
                },
            },
            "leaderboard": [
                {"symbol": "BTCUSDT", "backtest": {"metrics": {"total_return_pct": "12.0"}}}
            ],
        }

    service = BacktestChartService(result_provider=provider)

    result = service.generate_profit_curve("NOTEXIST")

    assert result["series"] == []
    assert result["meta"]["data_quality"] == "empty"


def test_profit_curve_meta_structure():
    """测试收益曲线 meta 结构。"""
    def provider():
        return {
            "latest_training": {
                "backtest": {
                    "metrics": {"total_return_pct": "10.0"},
                    "training_context": {"sample_window": {"train": {"start_date": "2026-01-01", "end_date": "2026-01-10"}}},
                }
            }
        }

    service = BacktestChartService(result_provider=provider)
    result = service.generate_profit_curve("latest")

    meta = result["meta"]
    assert "data_quality" in meta
    assert "warnings" in meta
    assert isinstance(meta["warnings"], list)


def test_empty_result_meta_has_warning():
    """测试空结果的 meta 包含警告。"""
    def empty_provider():
        return {"status": "unavailable"}

    service = BacktestChartService(result_provider=empty_provider)
    result = service.generate_profit_curve("latest")

    meta = result["meta"]
    assert meta["data_quality"] == "empty"
    assert len(meta["warnings"]) > 0
    assert "backtest_series_missing" in meta["warnings"]


# ========== 工具函数测试 ==========

def test_parse_float():
    """测试浮点数解析。"""
    assert BacktestChartService._parse_float("15.5") == 15.5
    assert BacktestChartService._parse_float("15.5%") == 15.5
    assert BacktestChartService._parse_float(None) == 0.0
    assert BacktestChartService._parse_float("") == 0.0


def test_parse_int():
    """测试整数解析。"""
    assert BacktestChartService._parse_int("3") == 3
    assert BacktestChartService._parse_int("3.5") == 3
    assert BacktestChartService._parse_int(None) == 0
    assert BacktestChartService._parse_int("") == 0
