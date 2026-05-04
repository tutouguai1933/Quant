"""终端视图帮助函数。

统一构造指标卡、参数字段和状态，不承载业务逻辑。
"""

from __future__ import annotations

from datetime import datetime


def metric_card(
    key: str,
    label: str,
    value: object,
    *,
    format: str = "text",
    tone: str = "neutral",
    unit: str = "",
    caption: str = "",
) -> dict[str, object]:
    """构造统一指标卡。

    Args:
        key: 稳定英文 key，前端用于 React key
        label: 中文显示名
        value: 后端原始值，字符串或数字均可
        format: integer, decimal, percent, percent_ratio, text, status
        tone: neutral, profit_loss, risk, success, warning, danger
        unit: 可选单位
        caption: 可选短说明

    Returns:
        指标卡字典
    """
    return {
        "key": key,
        "label": label,
        "value": str(value) if value is not None else "",
        "format": format,
        "tone": tone,
        "unit": unit,
        "caption": caption,
    }


def terminal_state(
    status: str,
    *,
    data_quality: str = "real",
    warnings: list[str] | None = None,
    updated_at: str = "",
) -> dict[str, object]:
    """构造统一页面状态。

    Args:
        status: ready, empty, running, degraded, error
        data_quality: real, partial, empty
        warnings: 警告码列表
        updated_at: 更新时间

    Returns:
        状态字典
    """
    return {
        "status": status,
        "data_quality": data_quality,
        "warnings": warnings or [],
        "updated_at": updated_at or datetime.utcnow().isoformat() + "+00:00",
    }


def build_parameter_group(
    title: str,
    fields: list[dict[str, object]],
) -> dict[str, object]:
    """构造参数分组。

    Args:
        title: 分组标题
        fields: 参数字段列表

    Returns:
        参数分组字典
    """
    return {
        "title": title,
        "fields": fields,
    }


def build_parameter_field(
    key: str,
    label: str,
    value: object,
    *,
    control: str = "text",
    unit: str = "",
    options: list[dict[str, object]] | None = None,
    readonly: bool = False,
) -> dict[str, object]:
    """构造参数字段。

    Args:
        key: 字段 key
        label: 中文标签
        value: 当前值
        control: select, number, text, toggle, chips
        unit: 可选单位
        options: select/chips 的候选项
        readonly: 是否只读

    Returns:
        参数字段字典
    """
    return {
        "key": key,
        "label": label,
        "value": str(value) if value is not None else "",
        "control": control,
        "unit": unit,
        "options": options or [],
        "readonly": readonly,
    }


def build_chart_meta(
    *,
    data_quality: str = "empty",
    source: str = "factory-report",
    warnings: list[str] | None = None,
    updated_at: str = "",
) -> dict[str, object]:
    """构造图表元数据。

    Args:
        data_quality: real, partial, empty
        source: 数据来源
        warnings: 警告码列表
        updated_at: 更新时间

    Returns:
        图表元数据字典
    """
    return {
        "data_quality": data_quality,
        "source": source,
        "warnings": warnings or [],
        "updated_at": updated_at or datetime.utcnow().isoformat() + "+00:00",
    }


def build_terminal_page(
    *,
    route: str,
    breadcrumb: str,
    title: str,
    subtitle: str = "",
    updated_at: str = "",
) -> dict[str, object]:
    """构造终端页面信息。

    Args:
        route: 页面路由
        breadcrumb: 面包屑
        title: 页面标题
        subtitle: 页面副标题
        updated_at: 更新时间

    Returns:
        页面信息字典
    """
    return {
        "route": route,
        "breadcrumb": breadcrumb,
        "title": title,
        "subtitle": subtitle,
        "updated_at": updated_at or datetime.utcnow().isoformat() + "+00:00",
    }


# 警告码常量
WARNING_CODES = {
    "training_curve_missing": "缺少训练曲线",
    "feature_importance_missing": "缺少特征重要性",
    "backtest_series_missing": "缺少真实回测序列",
    "candidate_backtest_series_missing": "缺少候选对比序列",
    "factor_ic_missing": "缺少 IC 序列",
    "factor_quantile_missing": "缺少分组收益",
    "config_not_aligned": "当前配置和最新结果不一致",
}
