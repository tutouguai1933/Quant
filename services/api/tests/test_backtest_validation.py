"""回测验证路由测试。"""

from __future__ import annotations

import json
from pathlib import Path


def test_run_backtest_success():
    """测试执行回测成功。"""
    from services.api.app.routes.backtest_validation import run_backtest, _backtest_results_store

    # 清空存储
    _backtest_results_store.clear()

    request = {
        "symbol": "BTCUSDT",
        "strategy_type": "trend_breakout",
        "timeframe": "4h",
        "lookback_bars": 20,
        "days": 30,
        "initial_capital": "10000",
        "fee_bps": 10,
        "slippage_bps": 5,
        "position_size_pct": "100",
        "stop_loss_pct": "5",
        "take_profit_pct": "10",
        "breakout_buffer_pct": "0.5",
    }

    result = run_backtest(request)

    assert result["error"] is None
    assert result["data"]["status"] in ("completed", "error")
    assert result["data"]["symbol"] == "BTCUSDT"
    assert result["data"]["strategy_type"] == "trend_breakout"
    assert "backtest_id" in result["data"]
    assert "metrics" in result["data"]
    assert "trades" in result["data"]


def test_run_backtest_invalid_strategy():
    """测试无效策略类型。"""
    from services.api.app.routes.backtest_validation import run_backtest

    request = {
        "symbol": "BTCUSDT",
        "strategy_type": "invalid_strategy",
        "timeframe": "4h",
        "lookback_bars": 20,
    }

    result = run_backtest(request)

    assert result["error"] is not None
    assert result["error"]["code"] == "invalid_parameter"


def test_run_backtest_invalid_lookback_bars():
    """测试无效的 lookback_bars。"""
    from services.api.app.routes.backtest_validation import run_backtest

    request = {
        "symbol": "BTCUSDT",
        "strategy_type": "trend_breakout",
        "lookback_bars": 2,  # 小于最小值 5
    }

    result = run_backtest(request)

    assert result["error"] is not None
    assert "lookback_bars" in result["error"]["message"]


def test_run_backtest_invalid_days():
    """测试无效的 days 参数。"""
    from services.api.app.routes.backtest_validation import run_backtest

    request = {
        "symbol": "BTCUSDT",
        "strategy_type": "trend_breakout",
        "lookback_bars": 20,
        "days": 400,  # 大于最大值 365
    }

    result = run_backtest(request)

    assert result["error"] is not None
    assert "days" in result["error"]["message"]


def test_get_backtest_result_found():
    """测试获取存在的回测结果。"""
    from services.api.app.routes.backtest_validation import (
        run_backtest,
        get_backtest_result,
        _backtest_results_store,
    )

    # 清空存储
    _backtest_results_store.clear()

    # 先执行一个回测
    request = {
        "symbol": "BTCUSDT",
        "strategy_type": "trend_breakout",
        "timeframe": "4h",
        "lookback_bars": 20,
    }

    run_result = run_backtest(request)
    backtest_id = run_result["data"]["backtest_id"]

    # 获取结果
    result = get_backtest_result(backtest_id)

    assert result["error"] is None
    assert result["data"]["backtest_id"] == backtest_id
    assert result["data"]["symbol"] == "BTCUSDT"


def test_get_backtest_result_not_found():
    """测试获取不存在的回测结果。"""
    from services.api.app.routes.backtest_validation import get_backtest_result

    result = get_backtest_result("non-existent-id")

    assert result["error"] is not None
    assert result["error"]["code"] == "not_found"


def test_validate_strategy_params_all_passed():
    """测试策略参数验证全部通过。"""
    from services.api.app.routes.backtest_validation import validate_strategy_params, VALIDATION_THRESHOLDS

    # 使用一个模拟请求
    request = {
        "symbol": "BTCUSDT",
        "strategy_type": "trend_breakout",
        "timeframe": "4h",
        "lookback_bars": 20,
        "days": 30,
    }

    result = validate_strategy_params(request)

    assert result["error"] is None
    assert "valid" in result["data"]
    assert "validations" in result["data"]
    assert "metrics" in result["data"]
    assert "recommendations" in result["data"]

    # 验证包含所有检查项
    validations = result["data"]["validations"]
    assert "win_rate" in validations
    assert "profit_factor" in validations
    assert "max_drawdown" in validations
    assert "sharpe_ratio" in validations


def test_validate_strategy_params_thresholds():
    """测试验证阈值正确性。"""
    from services.api.app.routes.backtest_validation import VALIDATION_THRESHOLDS

    assert VALIDATION_THRESHOLDS["win_rate"] == 0.55
    assert VALIDATION_THRESHOLDS["profit_factor"] == 1.5
    assert VALIDATION_THRESHOLDS["max_drawdown"] == 0.15
    assert VALIDATION_THRESHOLDS["sharpe_ratio"] == 1.0


def test_get_optimization_suggestions():
    """测试获取优化建议。"""
    from services.api.app.routes.backtest_validation import get_optimization_suggestions

    result = get_optimization_suggestions()

    assert result["error"] is None
    assert "optimization_suggestions" in result["data"]
    assert "market_condition_adjustments" in result["data"]
    assert "validation_thresholds" in result["data"]
    assert "tuning_status" in result["data"]


def test_get_optimization_suggestions_structure():
    """测试优化建议结构。"""
    from services.api.app.routes.backtest_validation import get_optimization_suggestions

    result = get_optimization_suggestions()

    suggestions = result["data"]["optimization_suggestions"]

    # 验证建议项包含必要字段
    for suggestion in suggestions:
        assert "parameter" in suggestion
        assert "current_value" in suggestion
        assert "recommended_value" in suggestion
        assert "reason" in suggestion


def test_get_metrics_info():
    """测试获取指标信息。"""
    from services.api.app.routes.backtest_validation import get_metrics_info

    result = get_metrics_info()

    assert result["error"] is None
    assert "metrics" in result["data"]
    assert "strategies" in result["data"]

    # 验证指标列表
    metrics = result["data"]["metrics"]
    assert len(metrics) > 0
    for metric in metrics:
        assert "key" in metric
        assert "label" in metric
        assert "description" in metric


def test_compare_backtests():
    """测试对比多个策略。"""
    from services.api.app.routes.backtest_validation import compare_backtests

    request = {
        "symbol": "BTCUSDT",
        "days": 30,
        "configs": [
            {
                "strategy_type": "trend_breakout",
                "timeframe": "4h",
                "lookback_bars": 20,
                "stop_loss_pct": "5",
                "take_profit_pct": "10",
            },
            {
                "strategy_type": "trend_pullback",
                "timeframe": "4h",
                "lookback_bars": 20,
                "stop_loss_pct": "3",
                "take_profit_pct": "8",
            },
        ],
    }

    result = compare_backtests(request)

    assert result["error"] is None
    assert "comparison" in result["data"]
    assert "best_strategy" in result["data"]


def test_compare_backtests_empty_configs():
    """测试空的配置列表。"""
    from services.api.app.routes.backtest_validation import compare_backtests

    request = {
        "symbol": "BTCUSDT",
        "days": 30,
        "configs": [],
    }

    result = compare_backtests(request)

    assert result["error"] is not None
    assert result["error"]["code"] == "invalid_parameter"


def test_success_error_envelope_format():
    """测试统一响应格式。"""
    from services.api.app.routes.backtest_validation import _success, _error

    success = _success({"test": "data"}, {"meta": "info"})
    assert success["data"] is not None
    assert success["error"] is None
    assert "meta" in success

    error = _error("test error", "test_code")
    assert error["data"] is None
    assert error["error"]["code"] == "test_code"
    assert error["error"]["message"] == "test error"


def test_strategy_tuning_config_exists():
    """测试 strategy_tuning.json 配置文件存在。"""
    tuning_path = Path("/home/djy/Quant/services/data/config/strategy_tuning.json")
    assert tuning_path.exists()

    with open(tuning_path) as f:
        config = json.load(f)

    assert "backtest_validation" in config
    assert "required_metrics" in config["backtest_validation"]

    required_metrics = config["backtest_validation"]["required_metrics"]
    assert required_metrics["win_rate"] == 0.55
    assert required_metrics["profit_factor"] == 1.5
    assert required_metrics["max_drawdown"] == 0.15
    assert required_metrics["sharpe_ratio"] == 1.0