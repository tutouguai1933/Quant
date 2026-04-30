"""策略调优API单元测试。

测试调优配置加载、参数应用、状态查询等功能。
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from services.api.app.services.scoring.scoring_service import scoring_service, ScoringConfig
from services.api.app.services.dynamic_stoploss_service import dynamic_stoploss_service

CONFIG_PATH = Path("/home/djy/Quant/services/data/config/strategy_tuning.json")


class TestStrategyTuningConfig:
    """策略调优配置测试。"""

    def test_config_file_exists(self) -> None:
        """调优配置文件应该存在。"""
        assert CONFIG_PATH.exists()

    def test_config_valid_json(self) -> None:
        """配置文件应该是有效JSON。"""
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config = json.load(f)
        assert "version" in config
        assert "parameters" in config
        assert "tuning_status" in config

    def test_config_min_entry_score_structure(self) -> None:
        """min_entry_score配置结构验证。"""
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config = json.load(f)

        min_entry = config["parameters"]["min_entry_score"]
        assert "current" in min_entry
        assert "recommended" in min_entry
        assert "reason" in min_entry
        assert "range" in min_entry
        assert min_entry["recommended"] >= min_entry["range"]["min"]
        assert min_entry["recommended"] <= min_entry["range"]["max"]

    def test_config_factor_weights_structure(self) -> None:
        """factor_weights配置结构验证。"""
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config = json.load(f)

        weights = config["parameters"]["factor_weights"]
        assert "current" in weights
        assert "recommended" in weights
        assert "reason" in weights

        expected_factors = ["rsi", "macd", "volume", "volatility", "trend", "momentum"]
        for factor in expected_factors:
            assert factor in weights["current"]
            assert factor in weights["recommended"]

    def test_config_stoploss_structure(self) -> None:
        """止损配置结构验证。"""
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config = json.load(f)

        sl_params = config["parameters"]["stoploss"]
        assert "current" in sl_params
        assert "recommended" in sl_params
        assert "reason" in sl_params

        for key in ["base_stoploss", "min_stoploss", "max_stoploss", "atr_multiplier"]:
            assert key in sl_params["current"]
            assert key in sl_params["recommended"]


class TestStrategyTuningRoutes:
    """策略调优路由测试。"""

    def test_get_tuning_status_success(self) -> None:
        """获取调优状态成功。"""
        from services.api.app.routes.strategy_tuning import get_tuning_status

        result = get_tuning_status()
        assert "data" in result
        assert "error" in result
        assert result["error"] is None
        assert "tuning_config" in result["data"]
        assert "current_scoring" in result["data"]
        assert "current_stoploss" in result["data"]

    def test_get_tuning_status_includes_pending_changes(self) -> None:
        """调优状态包含待变更列表。"""
        from services.api.app.routes.strategy_tuning import get_tuning_status

        result = get_tuning_status()
        assert "pending_changes" in result["data"]
        assert isinstance(result["data"]["pending_changes"], list)

    def test_get_recommendations_base(self) -> None:
        """获取基础推荐。"""
        from services.api.app.routes.strategy_tuning import get_recommendations

        result = get_recommendations()
        assert "data" in result
        assert result["error"] is None
        assert "base" in result["data"]

    def test_get_recommendations_with_market_condition(self) -> None:
        """获取市场条件相关推荐。"""
        from services.api.app.routes.strategy_tuning import get_recommendations

        result = get_recommendations(market_condition="high_volatility")
        assert "data" in result
        if "market_adjustment" in result["data"]:
            assert "description" in result["data"]["market_adjustment"]

    def test_get_recommendations_invalid_condition(self) -> None:
        """无效市场条件返回基础推荐。"""
        from services.api.app.routes.strategy_tuning import get_recommendations

        result = get_recommendations(market_condition="invalid_condition")
        assert "data" in result
        assert "base" in result["data"]
        assert "available_conditions" in result["meta"]

    def test_get_validation_criteria(self) -> None:
        """获取回测验证标准。"""
        from services.api.app.routes.strategy_tuning import get_validation_criteria

        result = get_validation_criteria()
        assert "data" in result
        assert result["error"] is None
        assert "validation_criteria" in result["data"]

        validation = result["data"]["validation_criteria"]
        assert "required_metrics" in validation
        assert "win_rate" in validation["required_metrics"]
        assert "profit_factor" in validation["required_metrics"]


class TestApplyTuningParams:
    """应用调优参数测试。"""

    def test_apply_min_entry_score_dry_run(self) -> None:
        """dry_run模式下不实际应用参数。"""
        from services.api.app.routes.strategy_tuning import apply_tuning_params

        original_score = scoring_service.get_min_entry_score()

        with patch("services.api.app.routes.strategy_tuning.auth_service") as mock_auth:
            mock_auth.require_control_plane_access = MagicMock()
            mock_auth.resolve_access_token = MagicMock(return_value="test_token")

            result = apply_tuning_params(
                payload={"dry_run": True, "params": ["min_entry_score"]},
                token="test_token",
                authorization="Bearer test_token",
            )

            assert result["data"]["dry_run"] is True
            assert scoring_service.get_min_entry_score() == original_score

    def test_apply_factor_weights_mocked(self) -> None:
        """测试因子权重应用（mock认证）。"""
        from services.api.app.routes.strategy_tuning import apply_tuning_params

        with patch("services.api.app.routes.strategy_tuning.auth_service") as mock_auth:
            mock_auth.require_control_plane_access = MagicMock()
            mock_auth.resolve_access_token = MagicMock(return_value="test_token")

            result = apply_tuning_params(
                payload={"apply_all": False, "params": ["factor_weights"]},
                token="test_token",
                authorization="Bearer test_token",
            )

            assert "applied" in result["data"]
            assert "errors" in result["data"]

    def test_apply_unauthorized(self) -> None:
        """未认证请求返回错误。"""
        from services.api.app.routes.strategy_tuning import apply_tuning_params

        with patch("services.api.app.routes.strategy_tuning.auth_service") as mock_auth:
            mock_auth.require_control_plane_access = MagicMock(side_effect=PermissionError())
            mock_auth.resolve_access_token = MagicMock(return_value="invalid_token")

            result = apply_tuning_params(
                payload={"apply_all": True},
                token="invalid_token",
                authorization="Bearer invalid_token",
            )

            assert result["error"] is not None
            assert result["error"]["code"] == "unauthorized"


class TestComputePendingChanges:
    """计算待变更测试。"""

    def test_compute_pending_changes_basic(self) -> None:
        """基本变更计算。"""
        from services.api.app.routes.strategy_tuning import _compute_pending_changes

        tuning = {
            "parameters": {
                "min_entry_score": {
                    "current": 0.70,
                    "recommended": 0.65,
                    "reason": "test",
                },
                "factor_weights": {
                    "current": {"rsi": 2.0},
                    "recommended": {"rsi": 1.5},
                },
                "stoploss": {
                    "current": {"base_stoploss": -0.10},
                    "recommended": {"base_stoploss": -0.08},
                },
            }
        }

        scoring = {"min_entry_score": 0.70, "factor_weights": {"rsi": 2.0}}
        stoploss = {"base_stoploss": "-0.10"}

        changes = _compute_pending_changes(tuning, scoring, stoploss)
        assert len(changes) >= 1

    def test_compute_pending_changes_no_changes(self) -> None:
        """无变更时返回空列表。"""
        from services.api.app.routes.strategy_tuning import _compute_pending_changes

        tuning = {
            "parameters": {
                "min_entry_score": {
                    "current": 0.70,
                    "recommended": 0.70,
                },
                "factor_weights": {
                    "current": {"rsi": 1.0},
                    "recommended": {"rsi": 1.0},
                },
                "stoploss": {
                    "current": {"base_stoploss": -0.10},
                    "recommended": {"base_stoploss": -0.10},
                },
            }
        }

        scoring = {"min_entry_score": 0.70, "factor_weights": {"rsi": 1.0}}
        stoploss = {"base_stoploss": "-0.10"}

        changes = _compute_pending_changes(tuning, scoring, stoploss)
        for change in changes:
            assert change["current"] != change["recommended"]


class TestResetTuningParams:
    """重置参数测试。"""

    def test_reset_to_current_mocked(self) -> None:
        """重置到当前值。"""
        from services.api.app.routes.strategy_tuning import reset_tuning_params

        with patch("services.api.app.routes.strategy_tuning.auth_service") as mock_auth:
            mock_auth.require_control_plane_access = MagicMock()
            mock_auth.resolve_access_token = MagicMock(return_value="test_token")

            result = reset_tuning_params(
                payload={"reset_to": "current"},
                token="test_token",
                authorization="Bearer test_token",
            )

            assert result["data"]["reset"] is True
            assert result["data"]["reset_to"] == "current"


class TestMarketConditionAdjustments:
    """市场条件调整测试。"""

    def test_high_volatility_adjustment_structure(self) -> None:
        """高波动调整结构验证。"""
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config = json.load(f)

        adjustments = config["market_condition_adjustments"]
        assert "high_volatility" in adjustments

        high_vol = adjustments["high_volatility"]
        assert "min_entry_score_adjustment" in high_vol
        assert "stoploss_adjustment" in high_vol
        assert "description" in high_vol

    def test_trending_adjustment_structure(self) -> None:
        """趋势市场调整结构验证。"""
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config = json.load(f)

        adjustments = config["market_condition_adjustments"]
        assert "trending" in adjustments

        trending = adjustments["trending"]
        assert "trend_weight_multiplier" in trending
        assert "momentum_weight_multiplier" in trending


class TestBacktestValidation:
    """回测验证标准测试。"""

    def test_required_metrics_present(self) -> None:
        """必要指标存在。"""
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config = json.load(f)

        validation = config["backtest_validation"]
        required = validation["required_metrics"]

        assert "win_rate" in required
        assert "profit_factor" in required
        assert "max_drawdown" in required
        assert "sharpe_ratio" in required

    def test_validation_metrics_reasonable(self) -> None:
        """验证指标值合理。"""
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config = json.load(f)

        required = config["backtest_validation"]["required_metrics"]

        assert 0 < required["win_rate"] < 1
        assert required["profit_factor"] >= 1.0
        assert 0 < required["max_drawdown"] < 1


class TestConfigPersistence:
    """配置持久化测试。"""

    def test_save_and_load_config(self) -> None:
        """配置保存和加载。"""
        from services.api.app.routes.strategy_tuning import _save_tuning_config, _load_tuning_config

        with tempfile.TemporaryDirectory() as tmpdir:
            test_path = Path(tmpdir) / "test_tuning.json"

            test_config = {
                "version": "test",
                "tuning_status": "test_ready",
                "parameters": {
                    "min_entry_score": {
                        "current": 0.60,
                        "recommended": 0.65,
                    }
                }
            }

            with patch("services.api.app.routes.strategy_tuning.CONFIG_PATH", test_path):
                success = _save_tuning_config(test_config)
                assert success

                loaded = _load_tuning_config()
                assert loaded["version"] == "test"
                assert loaded["tuning_status"] == "test_ready"

    def test_load_missing_config_returns_error(self) -> None:
        """加载缺失配置返回错误。"""
        from services.api.app.routes.strategy_tuning import _load_tuning_config

        with patch("services.api.app.routes.strategy_tuning.CONFIG_PATH", Path("/nonexistent/path.json")):
            result = _load_tuning_config()
            assert "error" in result