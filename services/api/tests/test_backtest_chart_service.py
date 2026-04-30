"""回测图表服务测试。"""

from __future__ import annotations

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
    curve = backtest_chart_service.generate_profit_curve("latest")

    assert len(curve) > 0
    assert curve[0]["date"] == "2026-01-01"
    assert "profit" in curve[0]
    assert "cumulative" in curve[0]
    assert curve[-1]["cumulative"] > curve[0]["cumulative"]


def test_generate_profit_curve_by_symbol(backtest_chart_service):
    """测试按symbol生成收益曲线。"""
    curve = backtest_chart_service.generate_profit_curve("BTCUSDT")

    assert len(curve) > 0
    assert curve[0]["date"] == "2026-01-01"
    assert curve[-1]["cumulative"] > curve[0]["cumulative"]


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
    assert len(charts["profit_curve"]) > 0
    assert charts["statistics"]["total_return"] == 15.5


def test_service_with_empty_result():
    """测试空结果时的处理。"""
    def empty_provider():
        return {"status": "unavailable", "latest_training": {}, "leaderboard": []}

    service = BacktestChartService(result_provider=empty_provider)

    curve = service.generate_profit_curve("latest")
    assert len(curve) > 0

    statistics = service.calculate_statistics("latest")
    assert statistics["total_return"] == 15.0

    distribution = service.generate_trade_distribution("latest")
    assert distribution["wins"] == 10


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