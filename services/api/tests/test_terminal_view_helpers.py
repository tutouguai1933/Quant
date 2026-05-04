"""terminal_view_helpers 单元测试。"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pytest

from services.api.app.services.terminal_view_helpers import (
    metric_card,
    terminal_state,
    build_parameter_group,
    build_parameter_field,
    build_chart_meta,
    build_terminal_page,
    WARNING_CODES,
)


def test_metric_card_basic():
    """测试基本指标卡构造。"""
    result = metric_card("test_key", "测试标签", "123")
    assert result["key"] == "test_key"
    assert result["label"] == "测试标签"
    assert result["value"] == "123"
    assert result["format"] == "text"
    assert result["tone"] == "neutral"


def test_metric_card_with_options():
    """测试带选项的指标卡构造。"""
    result = metric_card(
        "return_pct",
        "收益率",
        "5.5",
        format="percent",
        tone="profit_loss",
        unit="%",
        caption="扣除手续费后",
    )
    assert result["format"] == "percent"
    assert result["tone"] == "profit_loss"
    assert result["unit"] == "%"
    assert result["caption"] == "扣除手续费后"


def test_metric_card_with_none_value():
    """测试值为 None 时的指标卡构造。"""
    result = metric_card("test_key", "测试标签", None)
    assert result["value"] == ""


def test_metric_card_with_numeric_value():
    """测试数字值的指标卡构造。"""
    result = metric_card("count", "数量", 42)
    assert result["value"] == "42"


def test_terminal_state_ready():
    """测试就绪状态。"""
    result = terminal_state("ready", data_quality="real")
    assert result["status"] == "ready"
    assert result["data_quality"] == "real"
    assert result["warnings"] == []


def test_terminal_state_empty():
    """测试空状态。"""
    result = terminal_state("empty", data_quality="empty", warnings=["backtest_series_missing"])
    assert result["status"] == "empty"
    assert result["data_quality"] == "empty"
    assert "backtest_series_missing" in result["warnings"]


def test_terminal_state_with_warnings():
    """测试带警告的状态。"""
    result = terminal_state(
        "degraded",
        data_quality="partial",
        warnings=["training_curve_missing", "feature_importance_missing"],
    )
    assert result["status"] == "degraded"
    assert result["data_quality"] == "partial"
    assert len(result["warnings"]) == 2


def test_terminal_state_with_updated_at():
    """测试带更新时间的状态。"""
    result = terminal_state("ready", updated_at="2026-05-05T12:00:00+00:00")
    assert result["updated_at"] == "2026-05-05T12:00:00+00:00"


def test_terminal_state_generates_updated_at():
    """测试自动生成更新时间。"""
    result = terminal_state("ready")
    assert result["updated_at"]
    assert "+00:00" in result["updated_at"]


def test_build_parameter_group():
    """测试参数分组构造。"""
    fields = [
        build_parameter_field("model", "模型", "lightgbm", control="select"),
        build_parameter_field("days", "天数", "30", control="number", unit="天"),
    ]
    result = build_parameter_group("模型配置", fields)
    assert result["title"] == "模型配置"
    assert len(result["fields"]) == 2


def test_build_parameter_field_basic():
    """测试基本参数字段构造。"""
    result = build_parameter_field("model", "模型", "lightgbm")
    assert result["key"] == "model"
    assert result["label"] == "模型"
    assert result["value"] == "lightgbm"
    assert result["control"] == "text"
    assert result["readonly"] is False


def test_build_parameter_field_with_options():
    """测试带选项的参数字段构造。"""
    options = [
        {"value": "lightgbm", "label": "LightGBM"},
        {"value": "xgboost", "label": "XGBoost"},
    ]
    result = build_parameter_field(
        "model",
        "模型",
        "lightgbm",
        control="select",
        options=options,
        readonly=True,
    )
    assert result["control"] == "select"
    assert result["options"] == options
    assert result["readonly"] is True


def test_build_parameter_field_with_unit():
    """测试带单位的参数字段构造。"""
    result = build_parameter_field("days", "天数", "30", control="number", unit="天")
    assert result["unit"] == "天"


def test_build_parameter_field_with_none_value():
    """测试值为 None 时的参数字段构造。"""
    result = build_parameter_field("test", "测试", None)
    assert result["value"] == ""


def test_build_chart_meta_basic():
    """测试基本图表元数据构造。"""
    result = build_chart_meta()
    assert result["data_quality"] == "empty"
    assert result["source"] == "factory-report"
    assert result["warnings"] == []


def test_build_chart_meta_with_warnings():
    """测试带警告的图表元数据构造。"""
    result = build_chart_meta(data_quality="empty", warnings=["training_curve_missing"])
    assert result["data_quality"] == "empty"
    assert "training_curve_missing" in result["warnings"]


def test_build_chart_meta_with_real_data():
    """测试真实数据的图表元数据构造。"""
    result = build_chart_meta(data_quality="real", source="backtest")
    assert result["data_quality"] == "real"
    assert result["source"] == "backtest"


def test_build_chart_meta_generates_updated_at():
    """测试自动生成更新时间。"""
    result = build_chart_meta()
    assert result["updated_at"]
    assert "+00:00" in result["updated_at"]


def test_build_terminal_page():
    """测试终端页面信息构造。"""
    result = build_terminal_page(
        route="/research",
        breadcrumb="研究 / 模型训练",
        title="模型训练",
        subtitle="LightGBM 因子模型训练",
    )
    assert result["route"] == "/research"
    assert result["title"] == "模型训练"
    assert result["subtitle"] == "LightGBM 因子模型训练"
    assert result["breadcrumb"] == "研究 / 模型训练"


def test_build_terminal_page_generates_updated_at():
    """测试自动生成更新时间。"""
    result = build_terminal_page(
        route="/research",
        breadcrumb="研究",
        title="模型训练",
    )
    assert result["updated_at"]
    assert "+00:00" in result["updated_at"]


def test_warning_codes_exist():
    """测试警告码常量存在。"""
    assert "backtest_series_missing" in WARNING_CODES
    assert "training_curve_missing" in WARNING_CODES
    assert "feature_importance_missing" in WARNING_CODES
    assert "candidate_backtest_series_missing" in WARNING_CODES
    assert "factor_ic_missing" in WARNING_CODES
    assert "factor_quantile_missing" in WARNING_CODES
    assert "config_not_aligned" in WARNING_CODES


def test_warning_codes_have_descriptions():
    """测试警告码有中文描述。"""
    assert "缺少训练曲线" in WARNING_CODES["training_curve_missing"]
    assert "缺少真实回测序列" in WARNING_CODES["backtest_series_missing"]
    assert "缺少特征重要性" in WARNING_CODES["feature_importance_missing"]
    assert "缺少 IC 序列" in WARNING_CODES["factor_ic_missing"]
    assert "缺少分组收益" in WARNING_CODES["factor_quantile_missing"]
    assert "当前配置和最新结果不一致" in WARNING_CODES["config_not_aligned"]
