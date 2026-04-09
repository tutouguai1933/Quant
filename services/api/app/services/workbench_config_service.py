"""工作台配置服务。

这个文件负责保存研究到执行工作台的可配置项，并把它们整理成研究、回测和自动化链路可直接消费的结构。
"""

from __future__ import annotations

import json
import os
import re
from copy import deepcopy
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable

from services.api.app.core.settings import DEFAULT_LIVE_ALLOWED_SYMBOLS, DEFAULT_MARKET_SYMBOLS
from services.worker.qlib_features import (
    AUXILIARY_FEATURE_COLUMNS,
    FEATURE_PROTOCOL,
    PRIMARY_FEATURE_COLUMNS,
    TIMEFRAME_PROFILES,
)


REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_WORKBENCH_CONFIG_PATH = REPO_ROOT / ".runtime" / "workbench_config.json"
SUPPORTED_TIMEFRAMES = ("4h", "1h")
SUPPORTED_MODELS = ("heuristic_v1", "trend_bias_v2", "balanced_v3", "momentum_drive_v4", "stability_guard_v5")
SUPPORTED_RESEARCH_TEMPLATES = ("single_asset_timing", "single_asset_timing_strict")
SUPPORTED_LABEL_MODES = ("earliest_hit", "close_only", "window_majority")
SUPPORTED_LABEL_TRIGGER_BASES = ("close", "high_low")
SUPPORTED_LABEL_PRESETS = ("balanced_window", "breakout_path", "closing_confirmation", "majority_filter", "pullback_reclaim", "volatility_breakout")
SUPPORTED_OUTLIER_POLICIES = ("clip", "raw")
SUPPORTED_NORMALIZATION_POLICIES = ("fixed_4dp", "zscore_by_symbol")
SUPPORTED_MISSING_POLICIES = ("neutral_fill", "strict_drop")
SUPPORTED_WINDOW_MODES = ("rolling", "fixed")
SUPPORTED_HOLDING_WINDOWS = ("1-2d", "1-3d", "2-4d", "2-5d", "3-5d")
SUPPORTED_BACKTEST_COST_MODELS = (
    "round_trip_basis_points",
    "single_side_basis_points",
    "zero_cost_baseline",
)
SUPPORTED_CANDIDATE_POOL_PRESETS = ("top10_liquid", "majors_focus", "execution_focus")
SUPPORTED_LIVE_SUBSET_PRESETS = ("core_live", "majors_only", "strict_pairs")
SUPPORTED_OPERATIONS_PRESETS = ("balanced_guard", "strict_guard", "extended_observation")
SUPPORTED_AUTOMATION_PRESETS = ("balanced_runtime", "fast_feedback", "cautious_watch")
SUPPORTED_FEATURE_PRESETS = ("balanced_default", "trend_focus", "confirmation_focus")
SUPPORTED_RESEARCH_PRESETS = ("baseline_balanced", "trend_following", "conservative_validation", "momentum_breakout", "stability_first")
SUPPORTED_BACKTEST_PRESETS = ("realistic_standard", "cost_stress", "signal_baseline")
SUPPORTED_THRESHOLD_PRESETS = ("standard_gate", "strict_live_gate", "exploratory_dry_run")

CANDIDATE_POOL_PRESET_VALUES = {
    "top10_liquid": list(DEFAULT_MARKET_SYMBOLS),
    "majors_focus": ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT"],
    "execution_focus": ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT", "BNBUSDT"],
}

LIVE_SUBSET_PRESET_VALUES = {
    "core_live": list(DEFAULT_LIVE_ALLOWED_SYMBOLS),
    "majors_only": ["BTCUSDT", "ETHUSDT", "SOLUSDT"],
    "strict_pairs": ["BTCUSDT", "ETHUSDT"],
}

OPERATIONS_PRESET_VALUES = {
    "balanced_guard": {
        "pause_after_consecutive_failures": "2",
        "stale_sync_failure_threshold": "1",
        "auto_pause_on_error": True,
        "review_limit": "10",
        "comparison_run_limit": "5",
        "cycle_cooldown_minutes": "15",
        "max_daily_cycle_count": "8",
    },
    "strict_guard": {
        "pause_after_consecutive_failures": "1",
        "stale_sync_failure_threshold": "1",
        "auto_pause_on_error": True,
        "review_limit": "12",
        "comparison_run_limit": "6",
        "cycle_cooldown_minutes": "20",
        "max_daily_cycle_count": "6",
    },
    "extended_observation": {
        "pause_after_consecutive_failures": "3",
        "stale_sync_failure_threshold": "2",
        "auto_pause_on_error": True,
        "review_limit": "15",
        "comparison_run_limit": "8",
        "cycle_cooldown_minutes": "10",
        "max_daily_cycle_count": "10",
    },
}

AUTOMATION_PRESET_VALUES = {
    "balanced_runtime": {
        "long_run_seconds": "300",
        "alert_cleanup_minutes": "15",
    },
    "fast_feedback": {
        "long_run_seconds": "180",
        "alert_cleanup_minutes": "10",
    },
    "cautious_watch": {
        "long_run_seconds": "600",
        "alert_cleanup_minutes": "30",
    },
}


FEATURE_PRESET_VALUES = {
    "balanced_default": {
        "primary_factors": list(PRIMARY_FEATURE_COLUMNS),
        "auxiliary_factors": list(AUXILIARY_FEATURE_COLUMNS),
        "missing_policy": "neutral_fill",
        "outlier_policy": "clip",
        "normalization_policy": "fixed_4dp",
    },
    "trend_focus": {
        "primary_factors": ["trend_gap_pct", "ema20_gap_pct", "ema55_gap_pct", "breakout_strength", "volume_ratio"],
        "auxiliary_factors": ["rsi14", "cci20"],
        "missing_policy": "neutral_fill",
        "outlier_policy": "clip",
        "normalization_policy": "fixed_4dp",
    },
    "confirmation_focus": {
        "primary_factors": ["volume_ratio", "ema20_gap_pct", "atr_pct", "range_pct", "close_return_pct"],
        "auxiliary_factors": ["rsi14", "stoch_k14"],
        "missing_policy": "strict_drop",
        "outlier_policy": "raw",
        "normalization_policy": "zscore_by_symbol",
    },
}

RESEARCH_PRESET_VALUES = {
    "baseline_balanced": {
        "label_preset_key": "balanced_window",
        "research_template": "single_asset_timing",
        "model_key": "heuristic_v1",
        "label_mode": "earliest_hit",
        "label_trigger_basis": "close",
        "holding_window_label": "1-3d",
        "force_validation_top_candidate": False,
        "label_target_pct": "1",
        "label_stop_pct": "-1",
        "signal_confidence_floor": "0.55",
        "trend_weight": "1.3",
        "momentum_weight": "1",
        "volume_weight": "1.1",
        "oscillator_weight": "0.7",
        "volatility_weight": "0.9",
        "strict_penalty_weight": "1",
    },
    "trend_following": {
        "label_preset_key": "breakout_path",
        "research_template": "single_asset_timing_strict",
        "model_key": "trend_bias_v2",
        "label_mode": "earliest_hit",
        "label_trigger_basis": "high_low",
        "holding_window_label": "2-4d",
        "force_validation_top_candidate": False,
        "label_target_pct": "1.4",
        "label_stop_pct": "-0.9",
        "signal_confidence_floor": "0.6",
        "trend_weight": "1.8",
        "momentum_weight": "1.2",
        "volume_weight": "1.4",
        "oscillator_weight": "0.4",
        "volatility_weight": "0.7",
        "strict_penalty_weight": "1.2",
    },
    "conservative_validation": {
        "label_preset_key": "closing_confirmation",
        "research_template": "single_asset_timing_strict",
        "model_key": "balanced_v3",
        "label_mode": "close_only",
        "label_trigger_basis": "close",
        "holding_window_label": "2-4d",
        "force_validation_top_candidate": True,
        "label_target_pct": "0.8",
        "label_stop_pct": "-0.6",
        "signal_confidence_floor": "0.62",
        "trend_weight": "1.4",
        "momentum_weight": "0.9",
        "volume_weight": "1.2",
        "oscillator_weight": "0.8",
        "volatility_weight": "1",
        "strict_penalty_weight": "1.4",
    },
    "momentum_breakout": {
        "label_preset_key": "volatility_breakout",
        "research_template": "single_asset_timing",
        "model_key": "momentum_drive_v4",
        "label_mode": "earliest_hit",
        "label_trigger_basis": "high_low",
        "holding_window_label": "1-2d",
        "force_validation_top_candidate": False,
        "label_target_pct": "1.6",
        "label_stop_pct": "-0.8",
        "signal_confidence_floor": "0.6",
        "trend_weight": "1.2",
        "momentum_weight": "1.8",
        "volume_weight": "1.5",
        "oscillator_weight": "0.4",
        "volatility_weight": "0.8",
        "strict_penalty_weight": "0.8",
    },
    "stability_first": {
        "label_preset_key": "pullback_reclaim",
        "research_template": "single_asset_timing_strict",
        "model_key": "stability_guard_v5",
        "label_mode": "window_majority",
        "label_trigger_basis": "close",
        "holding_window_label": "2-5d",
        "force_validation_top_candidate": True,
        "label_target_pct": "0.9",
        "label_stop_pct": "-0.7",
        "signal_confidence_floor": "0.64",
        "trend_weight": "1.5",
        "momentum_weight": "0.8",
        "volume_weight": "1.1",
        "oscillator_weight": "0.9",
        "volatility_weight": "1.3",
        "strict_penalty_weight": "1.6",
    },
}

LABEL_PRESET_VALUES = {
    "balanced_window": {
        "label_mode": "earliest_hit",
        "label_trigger_basis": "close",
        "holding_window_label": "1-3d",
        "min_holding_days": 1,
        "max_holding_days": 3,
        "label_target_pct": "1",
        "label_stop_pct": "-1",
    },
    "breakout_path": {
        "label_mode": "earliest_hit",
        "label_trigger_basis": "high_low",
        "holding_window_label": "2-4d",
        "min_holding_days": 2,
        "max_holding_days": 4,
        "label_target_pct": "1.4",
        "label_stop_pct": "-0.9",
    },
    "closing_confirmation": {
        "label_mode": "close_only",
        "label_trigger_basis": "close",
        "holding_window_label": "2-4d",
        "min_holding_days": 2,
        "max_holding_days": 4,
        "label_target_pct": "0.8",
        "label_stop_pct": "-0.6",
    },
    "majority_filter": {
        "label_mode": "window_majority",
        "label_trigger_basis": "close",
        "holding_window_label": "3-5d",
        "min_holding_days": 3,
        "max_holding_days": 5,
        "label_target_pct": "1.1",
        "label_stop_pct": "-0.7",
    },
    "pullback_reclaim": {
        "label_mode": "window_majority",
        "label_trigger_basis": "close",
        "holding_window_label": "2-5d",
        "min_holding_days": 2,
        "max_holding_days": 5,
        "label_target_pct": "0.9",
        "label_stop_pct": "-0.7",
    },
    "volatility_breakout": {
        "label_mode": "earliest_hit",
        "label_trigger_basis": "high_low",
        "holding_window_label": "1-2d",
        "min_holding_days": 1,
        "max_holding_days": 2,
        "label_target_pct": "1.6",
        "label_stop_pct": "-0.8",
    },
}

BACKTEST_PRESET_VALUES = {
    "realistic_standard": {
        "fee_bps": "10",
        "slippage_bps": "5",
        "cost_model": "round_trip_basis_points",
    },
    "cost_stress": {
        "fee_bps": "16",
        "slippage_bps": "9",
        "cost_model": "round_trip_basis_points",
    },
    "signal_baseline": {
        "fee_bps": "0",
        "slippage_bps": "0",
        "cost_model": "zero_cost_baseline",
    },
}

THRESHOLD_PRESET_VALUES = {
    "standard_gate": {
        "dry_run_min_score": "0.55",
        "dry_run_min_positive_rate": "0.45",
        "dry_run_min_net_return_pct": "0",
        "dry_run_min_sharpe": "0.5",
        "dry_run_max_drawdown_pct": "15",
        "dry_run_max_loss_streak": "3",
        "dry_run_min_win_rate": "0.5",
        "dry_run_max_turnover": "0.6",
        "dry_run_min_sample_count": "20",
        "validation_min_sample_count": "12",
        "validation_min_avg_future_return_pct": "-0.1",
        "live_min_score": "0.65",
        "live_min_positive_rate": "0.50",
        "live_min_net_return_pct": "0.20",
        "live_min_win_rate": "0.55",
        "live_max_turnover": "0.45",
        "live_min_sample_count": "24",
        "enable_rule_gate": True,
        "enable_validation_gate": True,
        "enable_backtest_gate": True,
        "enable_consistency_gate": True,
        "enable_live_gate": True,
    },
    "strict_live_gate": {
        "dry_run_min_score": "0.6",
        "dry_run_min_positive_rate": "0.5",
        "dry_run_min_net_return_pct": "0.15",
        "dry_run_min_sharpe": "0.7",
        "dry_run_max_drawdown_pct": "12",
        "dry_run_max_loss_streak": "2",
        "dry_run_min_win_rate": "0.54",
        "dry_run_max_turnover": "0.5",
        "dry_run_min_sample_count": "28",
        "validation_min_sample_count": "18",
        "validation_min_avg_future_return_pct": "0.1",
        "live_min_score": "0.72",
        "live_min_positive_rate": "0.56",
        "live_min_net_return_pct": "0.35",
        "live_min_win_rate": "0.6",
        "live_max_turnover": "0.38",
        "live_min_sample_count": "32",
        "enable_rule_gate": True,
        "enable_validation_gate": True,
        "enable_backtest_gate": True,
        "enable_consistency_gate": True,
        "enable_live_gate": True,
    },
    "exploratory_dry_run": {
        "dry_run_min_score": "0.48",
        "dry_run_min_positive_rate": "0.4",
        "dry_run_min_net_return_pct": "-0.1",
        "dry_run_min_sharpe": "0.2",
        "dry_run_max_drawdown_pct": "18",
        "dry_run_max_loss_streak": "4",
        "dry_run_min_win_rate": "0.46",
        "dry_run_max_turnover": "0.75",
        "dry_run_min_sample_count": "12",
        "validation_min_sample_count": "8",
        "validation_min_avg_future_return_pct": "-0.3",
        "live_min_score": "0.68",
        "live_min_positive_rate": "0.52",
        "live_min_net_return_pct": "0.25",
        "live_min_win_rate": "0.57",
        "live_max_turnover": "0.45",
        "live_min_sample_count": "24",
        "enable_rule_gate": True,
        "enable_validation_gate": True,
        "enable_backtest_gate": True,
        "enable_consistency_gate": False,
        "enable_live_gate": True,
    },
}

FEATURE_PRESET_FIELDS = {
    "primary_factors",
    "auxiliary_factors",
    "missing_policy",
    "outlier_policy",
    "normalization_policy",
}

RESEARCH_PRESET_FIELDS = {
    "research_template",
    "model_key",
    "label_mode",
    "label_trigger_basis",
    "holding_window_label",
    "force_validation_top_candidate",
    "min_holding_days",
    "max_holding_days",
    "label_target_pct",
    "label_stop_pct",
    "signal_confidence_floor",
    "trend_weight",
    "momentum_weight",
    "volume_weight",
    "oscillator_weight",
    "volatility_weight",
    "strict_penalty_weight",
}

LABEL_PRESET_FIELDS = {
    "label_mode",
    "label_trigger_basis",
    "holding_window_label",
    "min_holding_days",
    "max_holding_days",
    "label_target_pct",
    "label_stop_pct",
}

BACKTEST_PRESET_FIELDS = {
    "fee_bps",
    "slippage_bps",
    "cost_model",
}

DATA_PRESET_FIELDS = {
    "selected_symbols",
    "primary_symbol",
}

EXECUTION_PRESET_FIELDS = {
    "live_allowed_symbols",
}

OPERATIONS_PRESET_FIELDS = {
    "pause_after_consecutive_failures",
    "stale_sync_failure_threshold",
    "auto_pause_on_error",
    "review_limit",
    "comparison_run_limit",
    "cycle_cooldown_minutes",
    "max_daily_cycle_count",
}

AUTOMATION_PRESET_FIELDS = {
    "long_run_seconds",
    "alert_cleanup_minutes",
}

THRESHOLD_PRESET_FIELDS = {
    "dry_run_min_score",
    "dry_run_min_positive_rate",
    "dry_run_min_net_return_pct",
    "dry_run_min_sharpe",
    "dry_run_max_drawdown_pct",
    "dry_run_max_loss_streak",
    "dry_run_min_win_rate",
    "dry_run_max_turnover",
    "dry_run_min_sample_count",
    "validation_min_sample_count",
    "validation_min_avg_future_return_pct",
    "consistency_max_validation_backtest_return_gap_pct",
    "consistency_max_training_validation_positive_rate_gap",
    "consistency_max_training_validation_return_gap_pct",
    "rule_min_ema20_gap_pct",
    "rule_min_ema55_gap_pct",
    "rule_max_atr_pct",
    "rule_min_volume_ratio",
    "strict_rule_min_ema20_gap_pct",
    "strict_rule_min_ema55_gap_pct",
    "strict_rule_max_atr_pct",
    "strict_rule_min_volume_ratio",
    "enable_rule_gate",
    "enable_validation_gate",
    "enable_backtest_gate",
    "enable_consistency_gate",
    "enable_live_gate",
    "live_min_score",
    "live_min_positive_rate",
    "live_min_net_return_pct",
    "live_min_win_rate",
    "live_max_turnover",
    "live_min_sample_count",
}


def _build_candidate_pool_preset_catalog() -> list[dict[str, str]]:
    """返回候选池预设目录。"""

    return [
        {
            "key": "top10_liquid",
            "label": "top10_liquid / 默认 10 币候选池",
            "fit": "适合先做统一研究",
            "detail": "覆盖默认 10 个流动性较好的标的，适合先跑完整研究链和实验对比。",
        },
        {
            "key": "majors_focus",
            "label": "majors_focus / 主流币聚焦",
            "fit": "适合先缩小研究范围",
            "detail": "只保留 BTC、ETH、BNB、SOL、XRP，适合先盯主流币候选池。",
        },
        {
            "key": "execution_focus",
            "label": "execution_focus / 执行优先",
            "fit": "适合对齐研究和执行",
            "detail": "保留更贴近执行观察的核心币种，方便先比较研究候选和实际执行差异。",
        },
    ]


def _build_live_subset_preset_catalog() -> list[dict[str, str]]:
    """返回 live 子集预设目录。"""

    return [
        {
            "key": "core_live",
            "label": "core_live / 默认 live 子集",
            "fit": "适合默认小额 live",
            "detail": "保留默认 5 个 live 标的，用于小额验证和统一执行观察。",
        },
        {
            "key": "majors_only",
            "label": "majors_only / 主流币 live",
            "fit": "适合先压缩 live 风险面",
            "detail": "只允许 BTC、ETH、SOL 进入 live，更适合保守验证。",
        },
        {
            "key": "strict_pairs",
            "label": "strict_pairs / 严格双币 live",
            "fit": "适合最小真实验证",
            "detail": "只保留 BTC、ETH 两个 live 标的，方便先做最小规模真实验证。",
        },
    ]


def _build_operations_preset_catalog() -> list[dict[str, str]]:
    """返回长期运行预设目录。"""

    return [
        {
            "key": "balanced_guard",
            "label": "balanced_guard / 默认守护",
            "fit": "适合日常自动化运行",
            "detail": "失败、冷却和每日轮次数都保持均衡，适合先稳定跑完整个自动化流程。",
        },
        {
            "key": "strict_guard",
            "label": "strict_guard / 严格守护",
            "fit": "适合先收紧自动化风险",
            "detail": "更快暂停、更少轮次、更长冷却，更适合先把长期运行风险压下来。",
        },
        {
            "key": "extended_observation",
            "label": "extended_observation / 扩展观察",
            "fit": "适合多看几轮变化",
            "detail": "允许更多轮次和更宽的复盘窗口，适合先积累实验与运行对照。",
        },
    ]


def _build_automation_preset_catalog() -> list[dict[str, str]]:
    """返回自动化运行预设目录。"""

    return [
        {
            "key": "balanced_runtime",
            "label": "balanced_runtime / 默认运行",
            "fit": "适合一般日常运行",
            "detail": "接管阈值和告警窗口都保持默认，适合作为标准自动化观察口径。",
        },
        {
            "key": "fast_feedback",
            "label": "fast_feedback / 快速反馈",
            "fit": "适合频繁人工盯盘",
            "detail": "更快进入接管复核，也更快把旧告警移出活跃窗口，方便快速迭代。",
        },
        {
            "key": "cautious_watch",
            "label": "cautious_watch / 保守观察",
            "fit": "适合先稳住长期运行",
            "detail": "把接管阈值拉长、告警窗口放宽，更适合减少频繁切换状态。",
        },
    ]


def _describe_catalog_item(
    catalog: Iterable[dict[str, str]],
    *,
    key: str,
    title: str,
) -> str:
    """按目录键生成当前预设说明。"""

    normalized_key = str(key or "").strip()
    for item in catalog:
        if str(item.get("key", "")) != normalized_key:
            continue
        label = str(item.get("label", normalized_key)).strip()
        detail = str(item.get("detail", "")).strip()
        return f"{title}：{label} / {detail}".strip(" /")
    return f"{title}：{normalized_key or '未设置'}"


def _build_feature_preset_catalog() -> list[dict[str, str]]:
    """返回因子预设目录。"""

    return [
        {
            "key": "balanced_default",
            "label": "balanced_default / 均衡默认",
            "fit": "适合先确认整体链路",
            "detail": "保留默认主因子和辅助因子，适合先把训练、推理、回测和评估串起来。",
        },
        {
            "key": "trend_focus",
            "label": "trend_focus / 趋势优先",
            "fit": "更重视顺趋势候选",
            "detail": "会把趋势位置、突破强度和量能放在更靠前的位置，适合先找明显顺趋势机会。",
        },
        {
            "key": "confirmation_focus",
            "label": "confirmation_focus / 确认优先",
            "fit": "更适合保守验证",
            "detail": "会更强调成交量、波动和确认因子，适合先过滤噪音再比较候选。",
        },
    ]


def _build_research_preset_catalog() -> list[dict[str, str]]:
    """返回研究预设目录。"""

    return [
        {
            "key": "baseline_balanced",
            "label": "baseline_balanced / 均衡基线",
            "fit": "先做默认研究",
            "detail": "适合跑第一轮训练和推理，方便和其他预设做对照。",
        },
        {
            "key": "trend_following",
            "label": "trend_following / 趋势跟随",
            "fit": "更偏顺趋势推进",
            "detail": "会提高趋势和量能权重，研究模板也更严格，适合先看明显强势标的。",
        },
        {
            "key": "conservative_validation",
            "label": "conservative_validation / 保守验证",
            "fit": "更重视稳定性",
            "detail": "会提高放行门槛并偏向收盘确认，适合先验证候选是否真的稳。",
        },
        {
            "key": "momentum_breakout",
            "label": "momentum_breakout / 动量突破",
            "fit": "更适合追踪快速放量突破",
            "detail": "会提高动量和量能权重，并把持有窗口收短，适合先找更快的推进段。",
        },
        {
            "key": "stability_first",
            "label": "stability_first / 稳定优先",
            "fit": "更适合先筛稳定候选",
            "detail": "会提高波动惩罚和一致性要求，更适合先筛出更稳、再继续进 dry-run 和 live。",
        },
    ]


def _build_research_template_catalog() -> list[dict[str, str]]:
    """返回研究模板目录。"""

    return [
        {
            "key": "single_asset_timing",
            "label": "single_asset_timing / 单币择时",
            "fit": "先跑主研究链",
            "detail": "默认研究模板，重点回答某个币在 1 到 3 天内是否值得买入、继续观察或回避。",
        },
        {
            "key": "single_asset_timing_strict",
            "label": "single_asset_timing_strict / 单币择时严格版",
            "fit": "更偏收紧放行",
            "detail": "会更强调趋势确认、一致性和稳定性，适合准备进入 dry-run 或 live 前再复核一次。",
        },
    ]


def _build_threshold_preset_catalog() -> list[dict[str, str]]:
    """返回门槛预设目录。"""

    return [
        {
            "key": "standard_gate",
            "label": "standard_gate / 标准门槛",
            "fit": "默认放行口径",
            "detail": "适合先跑统一研究链，再看哪些候选可以进 dry-run。",
        },
        {
            "key": "strict_live_gate",
            "label": "strict_live_gate / 严格 live",
            "fit": "更适合小额 live 前复核",
            "detail": "会抬高收益、胜率和样本数门槛，适合做更严格的放行判断。",
        },
        {
            "key": "exploratory_dry_run",
            "label": "exploratory_dry_run / 探索型 dry-run",
            "fit": "先扩大 dry-run 候选池",
            "detail": "会放宽 dry-run 的一部分限制，但 live 门仍然保持较严口径。",
        },
    ]


def _build_model_catalog() -> list[dict[str, str]]:
    """返回模型说明目录。"""

    return [
        {
            "key": "heuristic_v1",
            "label": "heuristic_v1 / 基础启发式",
            "fit": "先跑通最小研究闭环",
            "detail": "更适合先确认数据、标签和回测链路是否稳定，方便快速比较配置变化带来的影响。",
        },
        {
            "key": "trend_bias_v2",
            "label": "trend_bias_v2 / 趋势偏置",
            "fit": "更偏顺趋势确认",
            "detail": "会更重视趋势、量能和突破一致性，适合把明显顺趋势的标的优先排前。",
        },
        {
            "key": "balanced_v3",
            "label": "balanced_v3 / 平衡评分",
            "fit": "适合多状态横向比较",
            "detail": "会同时看趋势、动量、波动和震荡，适合比较不同市场状态下哪一轮更稳。",
        },
        {
            "key": "momentum_drive_v4",
            "label": "momentum_drive_v4 / 动量推进",
            "fit": "更适合快节奏突破段",
            "detail": "会更重视突破强度、短期动量和量能配合，适合先找最近正在加速的候选。",
        },
        {
            "key": "stability_guard_v5",
            "label": "stability_guard_v5 / 稳定守门",
            "fit": "更适合进 live 前复核",
            "detail": "会更重视稳定收益、较低回撤和较短亏损段，适合先筛掉波动太大的候选。",
        },
    ]


def _build_label_mode_catalog() -> list[dict[str, str]]:
    """返回标签方式目录。"""

    return [
        {
            "key": "earliest_hit",
            "label": "earliest_hit / 最早命中",
            "fit": "更接近真实退出逻辑",
            "detail": "谁先命中目标或止损就按谁记账，适合 1 到 3 天择时验证。",
        },
        {
            "key": "close_only",
            "label": "close_only / 只看窗口结束",
            "fit": "更看重收盘稳定性",
            "detail": "只在窗口结束时按收盘结果记账，能弱化盘中波动，但会忽略中途先命中的路径差异。",
        },
        {
            "key": "window_majority",
            "label": "window_majority / 多数窗口表决",
            "fit": "更保守的标签判断",
            "detail": "按整个窗口里的多数结果来定标签，适合过滤单根极端波动。",
        },
    ]


def _build_label_trigger_catalog() -> list[dict[str, str]]:
    """返回标签触发基础目录。"""

    return [
        {
            "key": "close",
            "label": "close / 按收盘价判断",
            "fit": "口径更稳",
            "detail": "只看收盘价是否达到目标或止损，更适合日内波动较大但最终收盘更可信的场景。",
        },
        {
            "key": "high_low",
            "label": "high_low / 按高低点命中",
            "fit": "更接近盘中触发",
            "detail": "只要窗口里的最高价或最低价先命中目标或止损，就会记成已触发。",
        },
    ]


def _build_label_preset_catalog() -> list[dict[str, str]]:
    """返回标签预设目录。"""

    return [
        {
            "key": "balanced_window",
            "label": "balanced_window / 均衡窗口",
            "fit": "适合第一轮默认研究",
            "detail": "按收盘价和最早命中结合判断，兼顾节奏和稳定性，适合作为默认标签口径。",
        },
        {
            "key": "breakout_path",
            "label": "breakout_path / 突破路径",
            "fit": "更看重盘中先命中",
            "detail": "按高低点命中判断，更适合验证突破和止损在盘中是否先被触发。",
        },
        {
            "key": "closing_confirmation",
            "label": "closing_confirmation / 收盘确认",
            "fit": "更保守的窗口结束判断",
            "detail": "只看窗口结束时的收盘结果，更适合过滤盘中噪音，强调最终收盘是否站住。",
        },
        {
            "key": "majority_filter",
            "label": "majority_filter / 多数过滤",
            "fit": "更适合保守筛选候选",
            "detail": "按窗口内多数阶段结果决定标签，适合先过滤单根极端波动带来的误判。",
        },
        {
            "key": "pullback_reclaim",
            "label": "pullback_reclaim / 回踩收复",
            "fit": "更适合慢一点的趋势回踩",
            "detail": "会拉长持有窗口，并更看重收盘站回关键位置，适合先过滤只是一闪而过的反弹。",
        },
        {
            "key": "volatility_breakout",
            "label": "volatility_breakout / 波动突破",
            "fit": "更适合快节奏放量突破",
            "detail": "会缩短持有窗口，并按盘中高低点先命中记账，适合先验证快速突破能不能真的走出来。",
        },
    ]


def _build_holding_window_catalog() -> list[dict[str, str]]:
    """返回持有窗口目录。"""

    return [
        {
            "key": "1-2d",
            "label": "1-2d / 短节奏窗口",
            "fit": "更适合快进快出",
            "detail": "会更重视最近两天内有没有快速推进，更适合配合突破类研究模板。",
        },
        {
            "key": "1-3d",
            "label": "1-3d / 默认窗口",
            "fit": "兼顾节奏和稳定性",
            "detail": "适合当前单币择时主线，也是默认研究口径。",
        },
        {
            "key": "2-4d",
            "label": "2-4d / 更耐心持有",
            "fit": "更偏中短波段",
            "detail": "会让研究更看重持有稳定性，但短线信号的反应会更慢。",
        },
        {
            "key": "2-5d",
            "label": "2-5d / 稳定复核窗口",
            "fit": "更适合先看走势能否站稳",
            "detail": "会给回踩、修复和收盘确认更多时间，适合进 live 前再复核一次稳定性。",
        },
        {
            "key": "3-5d",
            "label": "3-5d / 更完整走势",
            "fit": "更看重完整一段行情",
            "detail": "适合验证较完整的趋势段，但更容易错过很短的快节奏机会。",
        },
    ]


def _build_cost_model_catalog() -> list[dict[str, str]]:
    """返回成本模型目录。"""

    return [
        {
            "key": "round_trip_basis_points",
            "label": "round_trip_basis_points / 双边成本",
            "fit": "最贴近真实交易",
            "detail": "买入和卖出都会扣手续费和滑点，适合用来判断真实可执行性。",
        },
        {
            "key": "single_side_basis_points",
            "label": "single_side_basis_points / 单边成本",
            "fit": "适合看单边成本影响",
            "detail": "只按单边成本估算，更适合先拆出手续费和滑点分别影响多大。",
        },
        {
            "key": "zero_cost_baseline",
            "label": "zero_cost_baseline / 零成本基线",
            "fit": "只看策略裸表现",
            "detail": "不计手续费和滑点，只适合做基线对照，不能直接拿来放行到实盘。",
        },
    ]


def _build_backtest_preset_catalog() -> list[dict[str, str]]:
    """返回回测预设目录。"""

    return [
        {
            "key": "realistic_standard",
            "label": "realistic_standard / 真实标准",
            "fit": "默认回测口径",
            "detail": "按常用双边成本估算，更适合直接和 dry-run 结果对照。",
        },
        {
            "key": "cost_stress",
            "label": "cost_stress / 成本压力",
            "fit": "先看高成本下还能不能站住",
            "detail": "会抬高手续费和滑点，更适合先验证策略是不是只靠低成本假设。",
        },
        {
            "key": "signal_baseline",
            "label": "signal_baseline / 信号基线",
            "fit": "先看策略裸表现",
            "detail": "不计手续费和滑点，只适合做基线对照，不能直接拿来放行到 live。",
        },
    ]


def _default_config() -> dict[str, object]:
    """返回默认配置。"""

    return {
        "version": "v1",
        "data": {
            "candidate_pool_preset_key": "top10_liquid",
            "selected_symbols": list(DEFAULT_MARKET_SYMBOLS),
            "primary_symbol": DEFAULT_MARKET_SYMBOLS[0],
            "timeframes": list(SUPPORTED_TIMEFRAMES),
            "sample_limit": 120,
            "lookback_days": 30,
            "window_mode": "rolling",
            "start_date": "",
            "end_date": "",
        },
        "features": {
            "feature_preset_key": "balanced_default",
            "primary_factors": list(PRIMARY_FEATURE_COLUMNS),
            "auxiliary_factors": list(AUXILIARY_FEATURE_COLUMNS),
            "missing_policy": "neutral_fill",
            "outlier_policy": "clip",
            "normalization_policy": "fixed_4dp",
            "timeframe_profiles": {
                str(interval): dict(profile)
                for interval, profile in TIMEFRAME_PROFILES.items()
            },
        },
        "research": {
            "research_preset_key": "baseline_balanced",
            "label_preset_key": "balanced_window",
            "research_template": "single_asset_timing",
            "model_key": "heuristic_v1",
            "label_mode": "earliest_hit",
            "label_trigger_basis": "close",
            "holding_window_label": "1-3d",
            "force_validation_top_candidate": False,
            "min_holding_days": 1,
            "max_holding_days": 3,
            "label_target_pct": "1",
            "label_stop_pct": "-1",
            "train_split_ratio": "0.6",
            "validation_split_ratio": "0.2",
            "test_split_ratio": "0.2",
            "signal_confidence_floor": "0.55",
            "trend_weight": "1.3",
            "momentum_weight": "1",
            "volume_weight": "1.1",
            "oscillator_weight": "0.7",
            "volatility_weight": "0.9",
            "strict_penalty_weight": "1",
        },
        "backtest": {
            "backtest_preset_key": "realistic_standard",
            "fee_bps": "10",
            "slippage_bps": "5",
            "cost_model": "round_trip_basis_points",
        },
        "execution": {
            "live_subset_preset_key": "core_live",
            "live_allowed_symbols": list(DEFAULT_LIVE_ALLOWED_SYMBOLS),
            "live_max_stake_usdt": "6",
            "live_max_open_trades": "1",
        },
        "thresholds": {
            "threshold_preset_key": "standard_gate",
            "dry_run_min_score": "0.55",
            "dry_run_min_positive_rate": "0.45",
            "dry_run_min_net_return_pct": "0",
            "dry_run_min_sharpe": "0.5",
            "dry_run_max_drawdown_pct": "15",
            "dry_run_max_loss_streak": "3",
            "dry_run_min_win_rate": "0.5",
            "dry_run_max_turnover": "0.6",
            "dry_run_min_sample_count": "20",
            "validation_min_sample_count": "12",
            "validation_min_avg_future_return_pct": "-0.1",
            "consistency_max_validation_backtest_return_gap_pct": "1.5",
            "consistency_max_training_validation_positive_rate_gap": "0.2",
            "consistency_max_training_validation_return_gap_pct": "1.5",
            "rule_min_ema20_gap_pct": "0",
            "rule_min_ema55_gap_pct": "0",
            "rule_max_atr_pct": "5",
            "rule_min_volume_ratio": "1",
            "strict_rule_min_ema20_gap_pct": "1.2",
            "strict_rule_min_ema55_gap_pct": "1.8",
            "strict_rule_max_atr_pct": "4.5",
            "strict_rule_min_volume_ratio": "1.05",
            "enable_rule_gate": True,
            "enable_validation_gate": True,
            "enable_backtest_gate": True,
            "enable_consistency_gate": True,
            "enable_live_gate": True,
            "live_min_score": "0.65",
            "live_min_positive_rate": "0.50",
            "live_min_net_return_pct": "0.20",
            "live_min_win_rate": "0.55",
            "live_max_turnover": "0.45",
            "live_min_sample_count": "24",
        },
        "operations": {
            "operations_preset_key": "balanced_guard",
            "pause_after_consecutive_failures": "2",
            "stale_sync_failure_threshold": "1",
            "auto_pause_on_error": True,
            "review_limit": "10",
            "comparison_run_limit": "5",
            "cycle_cooldown_minutes": "15",
            "max_daily_cycle_count": "8",
        },
        "automation": {
            "automation_preset_key": "balanced_runtime",
            "long_run_seconds": "300",
            "alert_cleanup_minutes": "15",
        },
    }


class WorkbenchConfigService:
    """管理工作台统一配置。"""

    def __init__(self, *, config_path: Path | None = None) -> None:
        self._config_path = config_path or Path(
            (os.getenv("QUANT_WORKBENCH_CONFIG_PATH") or str(DEFAULT_WORKBENCH_CONFIG_PATH)).strip()
        ).expanduser()

    def get_config(self) -> dict[str, object]:
        """读取当前配置。"""

        payload = self._read_config_file()
        return self._normalize_config(payload)

    def update_section(self, section: str, values: dict[str, object]) -> dict[str, object]:
        """更新某一段配置。"""

        normalized_section = str(section or "").strip().lower()
        current = self.get_config()
        merged = deepcopy(current)
        current_section = dict(current.get(normalized_section) or {})
        explicit_values = self._expand_nested_values(dict(values or {}))
        next_section = {**current_section, **explicit_values}

        if normalized_section == "data":
            next_section = self._apply_preset_reset(
                current_section=next_section,
                explicit_values=explicit_values,
                preset_key="candidate_pool_preset_key",
                managed_fields=DATA_PRESET_FIELDS,
            )
            merged["data"] = self._normalize_data_section(next_section)
        elif normalized_section == "features":
            next_section = self._apply_preset_reset(
                current_section=next_section,
                explicit_values=explicit_values,
                preset_key="feature_preset_key",
                managed_fields=FEATURE_PRESET_FIELDS,
            )
            merged["features"] = self._normalize_features_section(next_section)
        elif normalized_section == "research":
            next_section = self._apply_preset_reset(
                current_section=next_section,
                explicit_values=explicit_values,
                preset_key="research_preset_key",
                managed_fields=RESEARCH_PRESET_FIELDS,
            )
            if "research_preset_key" in explicit_values and "label_preset_key" not in explicit_values:
                next_section.pop("label_preset_key", None)
            next_section = self._apply_preset_reset(
                current_section=next_section,
                explicit_values=explicit_values,
                preset_key="label_preset_key",
                managed_fields=LABEL_PRESET_FIELDS,
            )
            if "holding_window_label" not in explicit_values and (
                "min_holding_days" in explicit_values or "max_holding_days" in explicit_values
            ):
                next_section["holding_window_label"] = self._format_explicit_holding_window(
                    min_days=explicit_values.get("min_holding_days"),
                    max_days=explicit_values.get("max_holding_days"),
                    fallback_min=next_section.get("min_holding_days"),
                    fallback_max=next_section.get("max_holding_days"),
                )
            merged["research"] = self._normalize_research_section(next_section)
        elif normalized_section == "backtest":
            next_section = self._apply_preset_reset(
                current_section=next_section,
                explicit_values=explicit_values,
                preset_key="backtest_preset_key",
                managed_fields=BACKTEST_PRESET_FIELDS,
            )
            merged["backtest"] = self._normalize_backtest_section(next_section)
        elif normalized_section == "execution":
            next_section = self._apply_preset_reset(
                current_section=next_section,
                explicit_values=explicit_values,
                preset_key="live_subset_preset_key",
                managed_fields=EXECUTION_PRESET_FIELDS,
            )
            data_section = dict(merged.get("data") or {})
            merged["execution"] = self._normalize_execution_section(
                next_section,
                candidate_symbols=tuple(str(item) for item in list(data_section.get("selected_symbols") or [])),
            )
        elif normalized_section == "thresholds":
            next_section = self._apply_preset_reset(
                current_section=next_section,
                explicit_values=explicit_values,
                preset_key="threshold_preset_key",
                managed_fields=THRESHOLD_PRESET_FIELDS,
            )
            merged["thresholds"] = self._normalize_thresholds_section(next_section)
        elif normalized_section == "operations":
            next_section = self._apply_preset_reset(
                current_section=next_section,
                explicit_values=explicit_values,
                preset_key="operations_preset_key",
                managed_fields=OPERATIONS_PRESET_FIELDS,
            )
            merged["operations"] = self._normalize_operations_section(next_section)
        elif normalized_section == "automation":
            next_section = self._apply_preset_reset(
                current_section=next_section,
                explicit_values=explicit_values,
                preset_key="automation_preset_key",
                managed_fields=AUTOMATION_PRESET_FIELDS,
            )
            merged["automation"] = self._normalize_automation_section(next_section)
        else:
            raise ValueError("unsupported workbench config section")

        normalized = self._normalize_config(merged)
        self._write_config_file(normalized)
        return normalized

    @staticmethod
    def _apply_preset_reset(
        *,
        current_section: dict[str, object],
        explicit_values: dict[str, object],
        preset_key: str,
        managed_fields: set[str],
    ) -> dict[str, object]:
        """切换预设时，先清掉预设负责的旧字段，避免旧值压住新预设。"""

        if preset_key not in explicit_values:
            return current_section
        next_section = dict(current_section)
        explicit_keys = {str(key) for key in explicit_values.keys()}
        for field in managed_fields:
            if field in explicit_keys:
                continue
            next_section.pop(field, None)
        return next_section

    def _format_explicit_holding_window(
        self,
        *,
        min_days: object,
        max_days: object,
        fallback_min: object,
        fallback_max: object,
    ) -> str:
        """把手动输入的最小/最大持有天数整理成窗口标签。"""

        resolved_min = self._normalize_int(min_days if min_days is not None else fallback_min, default=1, minimum=1, maximum=7)
        resolved_max = self._normalize_int(max_days if max_days is not None else fallback_max, default=3, minimum=1, maximum=7)
        if resolved_min > resolved_max:
            resolved_min, resolved_max = resolved_max, resolved_min
        return f"{resolved_min}-{resolved_max}d"

    def _expand_nested_values(self, values: dict[str, object]) -> dict[str, object]:
        """把点分隔的表单字段还原成嵌套结构。"""

        expanded: dict[str, object] = {}
        for key, value in dict(values or {}).items():
            field = str(key or "").strip()
            if not field:
                continue
            if "." not in field:
                expanded[field] = value
                continue
            self._assign_nested_value(expanded, field.split("."), value)
        return expanded

    def _assign_nested_value(self, target: dict[str, object], path: list[str], value: object) -> None:
        """按路径写入嵌套字段。"""

        if not path:
            return
        cursor = target
        for name in path[:-1]:
            current = cursor.get(name)
            if not isinstance(current, dict):
                current = {}
                cursor[name] = current
            cursor = current
        cursor[path[-1]] = value

    def build_workspace_controls(self) -> dict[str, object]:
        """返回给前端工作台使用的配置和选项。"""

        config = self.get_config()
        feature_categories = {
            str(name): [str(item) for item in list(items or [])]
            for name, items in dict(FEATURE_PROTOCOL.get("categories") or {}).items()
        }
        all_factors = [
            {
                "name": str(item.get("name", "")),
                "category": str(item.get("category", "")),
                "role": str(item.get("role", "")),
                "description": str(item.get("description", "")),
            }
            for item in list(FEATURE_PROTOCOL.get("factors") or [])
            if isinstance(item, dict)
        ]
        return {
            "config": config,
            "options": {
                "timeframes": list(SUPPORTED_TIMEFRAMES),
                "models": list(SUPPORTED_MODELS),
                "model_catalog": _build_model_catalog(),
                "research_templates": list(SUPPORTED_RESEARCH_TEMPLATES),
                "research_template_catalog": _build_research_template_catalog(),
                "label_modes": list(SUPPORTED_LABEL_MODES),
                "label_mode_catalog": _build_label_mode_catalog(),
                "label_trigger_bases": list(SUPPORTED_LABEL_TRIGGER_BASES),
                "label_trigger_catalog": _build_label_trigger_catalog(),
                "label_presets": list(SUPPORTED_LABEL_PRESETS),
                "label_preset_catalog": _build_label_preset_catalog(),
                "holding_windows": list(SUPPORTED_HOLDING_WINDOWS),
                "holding_window_catalog": _build_holding_window_catalog(),
                "backtest_cost_models": list(SUPPORTED_BACKTEST_COST_MODELS),
                "cost_model_catalog": _build_cost_model_catalog(),
                "feature_presets": list(SUPPORTED_FEATURE_PRESETS),
                "feature_preset_catalog": _build_feature_preset_catalog(),
                "research_presets": list(SUPPORTED_RESEARCH_PRESETS),
                "research_preset_catalog": _build_research_preset_catalog(),
                "backtest_presets": list(SUPPORTED_BACKTEST_PRESETS),
                "backtest_preset_catalog": _build_backtest_preset_catalog(),
                "threshold_presets": list(SUPPORTED_THRESHOLD_PRESETS),
                "threshold_preset_catalog": _build_threshold_preset_catalog(),
                "candidate_pool_presets": list(SUPPORTED_CANDIDATE_POOL_PRESETS),
                "candidate_pool_preset_catalog": _build_candidate_pool_preset_catalog(),
                "live_subset_presets": list(SUPPORTED_LIVE_SUBSET_PRESETS),
                "live_subset_preset_catalog": _build_live_subset_preset_catalog(),
                "operations_presets": list(SUPPORTED_OPERATIONS_PRESETS),
                "operations_preset_catalog": _build_operations_preset_catalog(),
                "automation_presets": list(SUPPORTED_AUTOMATION_PRESETS),
                "automation_preset_catalog": _build_automation_preset_catalog(),
                "all_symbols": list(DEFAULT_MARKET_SYMBOLS),
                "primary_factors": list(PRIMARY_FEATURE_COLUMNS),
                "auxiliary_factors": list(AUXILIARY_FEATURE_COLUMNS),
                "outlier_policies": list(SUPPORTED_OUTLIER_POLICIES),
                "normalization_policies": list(SUPPORTED_NORMALIZATION_POLICIES),
                "missing_policies": list(SUPPORTED_MISSING_POLICIES),
                "window_modes": list(SUPPORTED_WINDOW_MODES),
                "factor_categories": feature_categories,
                "all_factors": all_factors,
            },
        }

    def get_research_runtime_overrides(self) -> dict[str, str]:
        """把配置转换成研究层可直接消费的运行覆盖项。"""

        config = self.get_config()
        data = dict(config.get("data") or {})
        features = dict(config.get("features") or {})
        research = dict(config.get("research") or {})
        backtest = dict(config.get("backtest") or {})
        thresholds = dict(config.get("thresholds") or {})

        return {
            "QUANT_QLIB_SELECTED_SYMBOLS": ",".join(str(item) for item in list(data.get("selected_symbols") or [])),
            "QUANT_QLIB_TIMEFRAMES": ",".join(str(item) for item in list(data.get("timeframes") or [])),
            "QUANT_QLIB_SAMPLE_LIMIT": str(data.get("sample_limit", 120)),
            "QUANT_QLIB_LOOKBACK_DAYS": str(data.get("lookback_days", 30)),
            "QUANT_QLIB_WINDOW_MODE": str(data.get("window_mode", "rolling")),
            "QUANT_QLIB_START_DATE": str(data.get("start_date", "")),
            "QUANT_QLIB_END_DATE": str(data.get("end_date", "")),
            "QUANT_QLIB_PRIMARY_FACTORS": ",".join(str(item) for item in list(features.get("primary_factors") or [])),
            "QUANT_QLIB_AUXILIARY_FACTORS": ",".join(str(item) for item in list(features.get("auxiliary_factors") or [])),
            "QUANT_QLIB_MISSING_POLICY": str(features.get("missing_policy", "neutral_fill")),
            "QUANT_QLIB_OUTLIER_POLICY": str(features.get("outlier_policy", "clip")),
            "QUANT_QLIB_NORMALIZATION_POLICY": str(features.get("normalization_policy", "fixed_4dp")),
            "QUANT_QLIB_TIMEFRAME_PROFILES": json.dumps(
                self._stringify_timeframe_profiles(dict(features.get("timeframe_profiles") or {})),
                ensure_ascii=False,
            ),
            "QUANT_QLIB_RESEARCH_PRESET_KEY": str(research.get("research_preset_key", "baseline_balanced")),
            "QUANT_QLIB_LABEL_PRESET_KEY": str(research.get("label_preset_key", "balanced_window")),
            "QUANT_QLIB_RESEARCH_TEMPLATE": str(research.get("research_template", "single_asset_timing")),
            "QUANT_QLIB_LABEL_MODE": str(research.get("label_mode", "earliest_hit")),
            "QUANT_QLIB_LABEL_TRIGGER_BASIS": str(research.get("label_trigger_basis", "close")),
            "QUANT_QLIB_LABEL_TARGET_PCT": str(research.get("label_target_pct", "1")),
            "QUANT_QLIB_LABEL_STOP_PCT": str(research.get("label_stop_pct", "-1")),
            "QUANT_QLIB_HOLDING_WINDOW_MIN_DAYS": str(research.get("min_holding_days", 1)),
            "QUANT_QLIB_HOLDING_WINDOW_MAX_DAYS": str(research.get("max_holding_days", 3)),
            "QUANT_QLIB_HOLDING_WINDOW_LABEL": str(research.get("holding_window_label", "1-3d")),
            "QUANT_QLIB_MODEL_KEY": str(research.get("model_key", "heuristic_v1")),
            "QUANT_QLIB_FORCE_TOP_CANDIDATE": "true"
            if bool(research.get("force_validation_top_candidate", False))
            else "false",
            "QUANT_QLIB_TRAIN_SPLIT_RATIO": str(research.get("train_split_ratio", "0.6")),
            "QUANT_QLIB_VALIDATION_SPLIT_RATIO": str(research.get("validation_split_ratio", "0.2")),
            "QUANT_QLIB_TEST_SPLIT_RATIO": str(research.get("test_split_ratio", "0.2")),
            "QUANT_QLIB_SIGNAL_CONFIDENCE_FLOOR": str(research.get("signal_confidence_floor", "0.55")),
            "QUANT_QLIB_TREND_WEIGHT": str(research.get("trend_weight", "1.3")),
            "QUANT_QLIB_MOMENTUM_WEIGHT": str(research.get("momentum_weight", "1")),
            "QUANT_QLIB_VOLUME_WEIGHT": str(research.get("volume_weight", "1.1")),
            "QUANT_QLIB_OSCILLATOR_WEIGHT": str(research.get("oscillator_weight", "0.7")),
            "QUANT_QLIB_VOLATILITY_WEIGHT": str(research.get("volatility_weight", "0.9")),
            "QUANT_QLIB_STRICT_PENALTY_WEIGHT": str(research.get("strict_penalty_weight", "1")),
            "QUANT_QLIB_BACKTEST_FEE_BPS": str(backtest.get("fee_bps", "10")),
            "QUANT_QLIB_BACKTEST_SLIPPAGE_BPS": str(backtest.get("slippage_bps", "5")),
            "QUANT_QLIB_BACKTEST_COST_MODEL": str(backtest.get("cost_model", "round_trip_basis_points")),
            "QUANT_QLIB_DRY_RUN_MIN_SCORE": str(thresholds.get("dry_run_min_score", "0.55")),
            "QUANT_QLIB_DRY_RUN_MIN_POSITIVE_RATE": str(thresholds.get("dry_run_min_positive_rate", "0.45")),
            "QUANT_QLIB_DRY_RUN_MIN_NET_RETURN_PCT": str(thresholds.get("dry_run_min_net_return_pct", "0")),
            "QUANT_QLIB_DRY_RUN_MIN_SHARPE": str(thresholds.get("dry_run_min_sharpe", "0.5")),
            "QUANT_QLIB_DRY_RUN_MAX_DRAWDOWN_PCT": str(thresholds.get("dry_run_max_drawdown_pct", "15")),
            "QUANT_QLIB_DRY_RUN_MAX_LOSS_STREAK": str(thresholds.get("dry_run_max_loss_streak", "3")),
            "QUANT_QLIB_DRY_RUN_MIN_WIN_RATE": str(thresholds.get("dry_run_min_win_rate", "0.5")),
            "QUANT_QLIB_DRY_RUN_MAX_TURNOVER": str(thresholds.get("dry_run_max_turnover", "0.6")),
            "QUANT_QLIB_DRY_RUN_MIN_SAMPLE_COUNT": str(thresholds.get("dry_run_min_sample_count", "20")),
            "QUANT_QLIB_VALIDATION_MIN_SAMPLE_COUNT": str(thresholds.get("validation_min_sample_count", "12")),
            "QUANT_QLIB_VALIDATION_MIN_AVG_FUTURE_RETURN_PCT": str(thresholds.get("validation_min_avg_future_return_pct", "-0.1")),
            "QUANT_QLIB_CONSISTENCY_MAX_VALIDATION_BACKTEST_RETURN_GAP_PCT": str(thresholds.get("consistency_max_validation_backtest_return_gap_pct", "1.5")),
            "QUANT_QLIB_CONSISTENCY_MAX_TRAINING_VALIDATION_POSITIVE_RATE_GAP": str(thresholds.get("consistency_max_training_validation_positive_rate_gap", "0.2")),
            "QUANT_QLIB_CONSISTENCY_MAX_TRAINING_VALIDATION_RETURN_GAP_PCT": str(thresholds.get("consistency_max_training_validation_return_gap_pct", "1.5")),
            "QUANT_QLIB_RULE_MIN_EMA20_GAP_PCT": str(thresholds.get("rule_min_ema20_gap_pct", "0")),
            "QUANT_QLIB_RULE_MIN_EMA55_GAP_PCT": str(thresholds.get("rule_min_ema55_gap_pct", "0")),
            "QUANT_QLIB_RULE_MAX_ATR_PCT": str(thresholds.get("rule_max_atr_pct", "5")),
            "QUANT_QLIB_RULE_MIN_VOLUME_RATIO": str(thresholds.get("rule_min_volume_ratio", "1")),
            "QUANT_QLIB_STRICT_RULE_MIN_EMA20_GAP_PCT": str(thresholds.get("strict_rule_min_ema20_gap_pct", "1.2")),
            "QUANT_QLIB_STRICT_RULE_MIN_EMA55_GAP_PCT": str(thresholds.get("strict_rule_min_ema55_gap_pct", "1.8")),
            "QUANT_QLIB_STRICT_RULE_MAX_ATR_PCT": str(thresholds.get("strict_rule_max_atr_pct", "4.5")),
            "QUANT_QLIB_STRICT_RULE_MIN_VOLUME_RATIO": str(thresholds.get("strict_rule_min_volume_ratio", "1.05")),
            "QUANT_QLIB_ENABLE_RULE_GATE": "true"
            if self._normalize_bool(thresholds.get("enable_rule_gate"), default=True)
            else "false",
            "QUANT_QLIB_ENABLE_VALIDATION_GATE": "true"
            if self._normalize_bool(thresholds.get("enable_validation_gate"), default=True)
            else "false",
            "QUANT_QLIB_ENABLE_BACKTEST_GATE": "true"
            if self._normalize_bool(thresholds.get("enable_backtest_gate"), default=True)
            else "false",
            "QUANT_QLIB_ENABLE_CONSISTENCY_GATE": "true"
            if self._normalize_bool(thresholds.get("enable_consistency_gate"), default=True)
            else "false",
            "QUANT_QLIB_ENABLE_LIVE_GATE": "true"
            if self._normalize_bool(thresholds.get("enable_live_gate"), default=True)
            else "false",
            "QUANT_QLIB_LIVE_MIN_SCORE": str(thresholds.get("live_min_score", "0.65")),
            "QUANT_QLIB_LIVE_MIN_POSITIVE_RATE": str(thresholds.get("live_min_positive_rate", "0.50")),
            "QUANT_QLIB_LIVE_MIN_NET_RETURN_PCT": str(thresholds.get("live_min_net_return_pct", "0.20")),
            "QUANT_QLIB_LIVE_MIN_WIN_RATE": str(thresholds.get("live_min_win_rate", "0.55")),
            "QUANT_QLIB_LIVE_MAX_TURNOVER": str(thresholds.get("live_max_turnover", "0.45")),
            "QUANT_QLIB_LIVE_MIN_SAMPLE_COUNT": str(thresholds.get("live_min_sample_count", "24")),
        }

    def _normalize_config(self, payload: dict[str, object] | None) -> dict[str, object]:
        """把任意输入整理成完整配置。"""

        row = dict(payload or {})
        data_section = self._normalize_data_section(row.get("data"))
        return {
            "version": "v1",
            "data": data_section,
            "features": self._normalize_features_section(row.get("features")),
            "research": self._normalize_research_section(row.get("research")),
            "backtest": self._normalize_backtest_section(row.get("backtest")),
            "execution": self._normalize_execution_section(
                row.get("execution"),
                candidate_symbols=tuple(str(item) for item in list(data_section.get("selected_symbols") or [])),
            ),
            "thresholds": self._normalize_thresholds_section(row.get("thresholds")),
            "operations": self._normalize_operations_section(row.get("operations")),
            "automation": self._normalize_automation_section(row.get("automation")),
        }

    def _normalize_data_section(self, value: object) -> dict[str, object]:
        """整理数据工作台配置。"""

        payload = dict(value or {}) if isinstance(value, dict) else {}
        candidate_pool_preset_key = self._normalize_choice(
            payload.get("candidate_pool_preset_key"),
            default="top10_liquid",
            allowed=SUPPORTED_CANDIDATE_POOL_PRESETS,
        )
        payload = {**{"selected_symbols": CANDIDATE_POOL_PRESET_VALUES.get(candidate_pool_preset_key, list(DEFAULT_MARKET_SYMBOLS))}, **payload}
        selected_symbols = self._normalize_symbol_list(
            payload.get("selected_symbols"),
            fallback=DEFAULT_MARKET_SYMBOLS,
            allow_empty=True,
        )
        primary_symbol = str(payload.get("primary_symbol", "")).strip().upper()
        if primary_symbol not in selected_symbols:
            primary_symbol = selected_symbols[0] if selected_symbols else ""
        timeframes = self._normalize_timeframes(payload.get("timeframes"), allow_empty=True)
        sample_limit = self._normalize_int(payload.get("sample_limit"), default=120, minimum=60, maximum=1000)
        lookback_days = self._normalize_int(payload.get("lookback_days"), default=30, minimum=7, maximum=365)
        window_mode = self._normalize_choice(
            payload.get("window_mode"),
            default="rolling",
            allowed=SUPPORTED_WINDOW_MODES,
        )
        start_date = self._normalize_date(payload.get("start_date"))
        end_date = self._normalize_date(payload.get("end_date"))
        return {
            "candidate_pool_preset_key": candidate_pool_preset_key,
            "selected_symbols": list(selected_symbols),
            "primary_symbol": primary_symbol,
            "timeframes": list(timeframes),
            "sample_limit": sample_limit,
            "lookback_days": lookback_days,
            "window_mode": window_mode,
            "start_date": start_date,
            "end_date": end_date,
        }

    def _normalize_features_section(self, value: object) -> dict[str, object]:
        """整理特征工作台配置。"""

        payload = dict(value or {}) if isinstance(value, dict) else {}
        feature_preset_key = self._normalize_choice(
            payload.get("feature_preset_key"),
            default="balanced_default",
            allowed=SUPPORTED_FEATURE_PRESETS,
        )
        payload = {**FEATURE_PRESET_VALUES.get(feature_preset_key, {}), **payload}
        primary_factors = self._normalize_factor_list(
            payload.get("primary_factors"),
            allowed=PRIMARY_FEATURE_COLUMNS,
            fallback=PRIMARY_FEATURE_COLUMNS,
            allow_empty=True,
        )
        auxiliary_factors = self._normalize_factor_list(
            payload.get("auxiliary_factors"),
            allowed=AUXILIARY_FEATURE_COLUMNS,
            fallback=AUXILIARY_FEATURE_COLUMNS,
            allow_empty=True,
        )
        return {
            "feature_preset_key": feature_preset_key,
            "primary_factors": list(primary_factors),
            "auxiliary_factors": list(auxiliary_factors),
            "missing_policy": self._normalize_choice(
                payload.get("missing_policy"),
                default="neutral_fill",
                allowed=SUPPORTED_MISSING_POLICIES,
            ),
            "outlier_policy": self._normalize_choice(
                payload.get("outlier_policy"),
                default="clip",
                allowed=SUPPORTED_OUTLIER_POLICIES,
            ),
            "normalization_policy": self._normalize_choice(
                payload.get("normalization_policy"),
                default="fixed_4dp",
                allowed=SUPPORTED_NORMALIZATION_POLICIES,
            ),
            "timeframe_profiles": self._normalize_timeframe_profiles(payload.get("timeframe_profiles")),
        }

    def _normalize_research_section(self, value: object) -> dict[str, object]:
        """整理研究工作台配置。"""

        payload = dict(value or {}) if isinstance(value, dict) else {}
        research_preset_key = self._normalize_choice(
            payload.get("research_preset_key"),
            default="baseline_balanced",
            allowed=SUPPORTED_RESEARCH_PRESETS,
        )
        research_preset_values = dict(RESEARCH_PRESET_VALUES.get(research_preset_key, {}))
        label_preset_key = self._normalize_choice(
            payload.get("label_preset_key", research_preset_values.get("label_preset_key", "balanced_window")),
            default="balanced_window",
            allowed=SUPPORTED_LABEL_PRESETS,
        )
        payload = {
            **research_preset_values,
            **LABEL_PRESET_VALUES.get(label_preset_key, {}),
            **payload,
        }
        model_key = str(payload.get("model_key", "heuristic_v1")).strip() or "heuristic_v1"
        if model_key not in SUPPORTED_MODELS:
            model_key = "heuristic_v1"
        research_template = str(payload.get("research_template", "single_asset_timing")).strip() or "single_asset_timing"
        if research_template not in SUPPORTED_RESEARCH_TEMPLATES:
            research_template = "single_asset_timing"
        label_mode = self._normalize_choice(
            payload.get("label_mode"),
            default="earliest_hit",
            allowed=SUPPORTED_LABEL_MODES,
        )
        label_trigger_basis = self._normalize_choice(
            payload.get("label_trigger_basis"),
            default="close",
            allowed=SUPPORTED_LABEL_TRIGGER_BASES,
        )
        normalized_label = self._normalize_holding_window_label(
            payload.get("holding_window_label"),
            min_days=self._normalize_int(payload.get("min_holding_days"), default=1, minimum=1, maximum=7),
            max_days=self._normalize_int(payload.get("max_holding_days"), default=3, minimum=1, maximum=7),
        )
        min_days, max_days = self._holding_window_bounds(normalized_label)
        train_ratio = Decimal(
            self._normalize_decimal(payload.get("train_split_ratio"), default=Decimal("0.6"), minimum=Decimal("0.1"), maximum=Decimal("0.9"))
        )
        validation_ratio = Decimal(
            self._normalize_decimal(payload.get("validation_split_ratio"), default=Decimal("0.2"), minimum=Decimal("0.05"), maximum=Decimal("0.8"))
        )
        test_ratio = Decimal(
            self._normalize_decimal(payload.get("test_split_ratio"), default=Decimal("0.2"), minimum=Decimal("0.05"), maximum=Decimal("0.8"))
        )
        normalized_ratios = self._normalize_split_ratios(
            train_ratio=train_ratio,
            validation_ratio=validation_ratio,
            test_ratio=test_ratio,
        )
        return {
            "research_preset_key": research_preset_key,
            "label_preset_key": label_preset_key,
            "research_template": research_template,
            "model_key": model_key,
            "label_mode": label_mode,
            "label_trigger_basis": label_trigger_basis,
            "holding_window_label": normalized_label,
            "force_validation_top_candidate": self._normalize_bool(
                payload.get("force_validation_top_candidate"),
                default=False,
            ),
            "min_holding_days": min_days,
            "max_holding_days": max_days,
            "label_target_pct": self._normalize_decimal(payload.get("label_target_pct"), default=Decimal("1"), minimum=Decimal("0.1")),
            "label_stop_pct": self._normalize_decimal(payload.get("label_stop_pct"), default=Decimal("-1"), maximum=Decimal("-0.1")),
            "train_split_ratio": normalized_ratios["train_split_ratio"],
            "validation_split_ratio": normalized_ratios["validation_split_ratio"],
            "test_split_ratio": normalized_ratios["test_split_ratio"],
            "signal_confidence_floor": self._normalize_decimal(
                payload.get("signal_confidence_floor"),
                default=Decimal("0.55"),
                minimum=Decimal("0"),
                maximum=Decimal("1"),
            ),
            "trend_weight": self._normalize_decimal(
                payload.get("trend_weight"),
                default=Decimal("1.3"),
                minimum=Decimal("0"),
                maximum=Decimal("5"),
            ),
            "momentum_weight": self._normalize_decimal(
                payload.get("momentum_weight"),
                default=Decimal("1"),
                minimum=Decimal("0"),
                maximum=Decimal("5"),
            ),
            "volume_weight": self._normalize_decimal(
                payload.get("volume_weight"),
                default=Decimal("1.1"),
                minimum=Decimal("0"),
                maximum=Decimal("5"),
            ),
            "oscillator_weight": self._normalize_decimal(
                payload.get("oscillator_weight"),
                default=Decimal("0.7"),
                minimum=Decimal("0"),
                maximum=Decimal("5"),
            ),
            "volatility_weight": self._normalize_decimal(
                payload.get("volatility_weight"),
                default=Decimal("0.9"),
                minimum=Decimal("0"),
                maximum=Decimal("5"),
            ),
            "strict_penalty_weight": self._normalize_decimal(
                payload.get("strict_penalty_weight"),
                default=Decimal("1"),
                minimum=Decimal("0"),
                maximum=Decimal("5"),
            ),
        }

    def _normalize_backtest_section(self, value: object) -> dict[str, object]:
        """整理回测配置。"""

        payload = dict(value or {}) if isinstance(value, dict) else {}
        backtest_preset_key = self._normalize_choice(
            payload.get("backtest_preset_key"),
            default="realistic_standard",
            allowed=SUPPORTED_BACKTEST_PRESETS,
        )
        payload = {**BACKTEST_PRESET_VALUES.get(backtest_preset_key, {}), **payload}
        return {
            "backtest_preset_key": backtest_preset_key,
            "fee_bps": self._normalize_decimal(payload.get("fee_bps"), default=Decimal("10"), minimum=Decimal("0")),
            "slippage_bps": self._normalize_decimal(payload.get("slippage_bps"), default=Decimal("5"), minimum=Decimal("0")),
            "cost_model": self._normalize_choice(
                payload.get("cost_model"),
                default="round_trip_basis_points",
                allowed=SUPPORTED_BACKTEST_COST_MODELS,
            ),
        }

    def _normalize_timeframe_profiles(self, value: object) -> dict[str, dict[str, object]]:
        """整理周期参数配置。"""

        payload = dict(value or {}) if isinstance(value, dict) else {}
        normalized: dict[str, dict[str, object]] = {
            str(interval): dict(profile)
            for interval, profile in TIMEFRAME_PROFILES.items()
        }
        for interval, defaults in TIMEFRAME_PROFILES.items():
            incoming = payload.get(interval)
            if not isinstance(incoming, dict):
                continue
            merged = dict(normalized.get(interval) or {})
            for key, default in defaults.items():
                raw = incoming.get(key, merged.get(key, default))
                if isinstance(default, int):
                    merged[key] = self._normalize_int(raw, default=default, minimum=1, maximum=120)
                else:
                    text = str(raw or default).strip()
                    merged[key] = text or default
            normalized[interval] = merged
        return normalized

    def _stringify_timeframe_profiles(self, value: dict[str, dict[str, object]]) -> dict[str, dict[str, str]]:
        """把周期参数转成适合环境变量传递的字符串结构。"""

        result: dict[str, dict[str, str]] = {}
        for interval, profile in dict(value or {}).items():
            result[str(interval)] = {
                str(name): str(raw)
                for name, raw in dict(profile or {}).items()
            }
        return result

    def _normalize_execution_section(
        self,
        value: object,
        *,
        candidate_symbols: tuple[str, ...],
    ) -> dict[str, object]:
        """整理执行安全门配置。"""

        payload = dict(value or {}) if isinstance(value, dict) else {}
        has_explicit_live_allowed_symbols = "live_allowed_symbols" in payload
        live_subset_preset_key = self._normalize_choice(
            payload.get("live_subset_preset_key"),
            default="core_live",
            allowed=SUPPORTED_LIVE_SUBSET_PRESETS,
        )
        payload = {
            **{"live_allowed_symbols": LIVE_SUBSET_PRESET_VALUES.get(live_subset_preset_key, list(DEFAULT_LIVE_ALLOWED_SYMBOLS))},
            **payload,
        }
        normalized_live_allowed_symbols = self._normalize_symbol_list(
            payload.get("live_allowed_symbols"),
            fallback=DEFAULT_LIVE_ALLOWED_SYMBOLS,
            allow_empty=True,
        )
        if candidate_symbols:
            candidate_set = {item for item in candidate_symbols}
            live_allowed_symbols = tuple(
                item for item in normalized_live_allowed_symbols if item in candidate_set
            )
            if not live_allowed_symbols and not has_explicit_live_allowed_symbols:
                live_allowed_symbols = tuple(
                    item for item in DEFAULT_LIVE_ALLOWED_SYMBOLS if item in candidate_set
                )
        else:
            live_allowed_symbols = ()
        return {
            "live_subset_preset_key": live_subset_preset_key,
            "live_allowed_symbols": list(live_allowed_symbols),
            "live_max_stake_usdt": self._normalize_decimal(
                payload.get("live_max_stake_usdt"),
                default=Decimal("6"),
                minimum=Decimal("0.1"),
            ),
            "live_max_open_trades": str(
                self._normalize_int(payload.get("live_max_open_trades"), default=1, minimum=1, maximum=20)
            ),
        }

    def _normalize_thresholds_section(self, value: object) -> dict[str, object]:
        """整理 dry-run / live 门槛。"""

        payload = dict(value or {}) if isinstance(value, dict) else {}
        threshold_preset_key = self._normalize_choice(
            payload.get("threshold_preset_key"),
            default="standard_gate",
            allowed=SUPPORTED_THRESHOLD_PRESETS,
        )
        payload = {**THRESHOLD_PRESET_VALUES.get(threshold_preset_key, {}), **payload}
        return {
            "threshold_preset_key": threshold_preset_key,
            "dry_run_min_score": self._normalize_decimal(payload.get("dry_run_min_score"), default=Decimal("0.55"), minimum=Decimal("0"), maximum=Decimal("1")),
            "dry_run_min_positive_rate": self._normalize_decimal(payload.get("dry_run_min_positive_rate"), default=Decimal("0.45"), minimum=Decimal("0"), maximum=Decimal("1")),
            "dry_run_min_net_return_pct": self._normalize_decimal(payload.get("dry_run_min_net_return_pct"), default=Decimal("0")),
            "dry_run_min_sharpe": self._normalize_decimal(payload.get("dry_run_min_sharpe"), default=Decimal("0.5")),
            "dry_run_max_drawdown_pct": self._normalize_decimal(payload.get("dry_run_max_drawdown_pct"), default=Decimal("15"), minimum=Decimal("0")),
            "dry_run_max_loss_streak": str(self._normalize_int(payload.get("dry_run_max_loss_streak"), default=3, minimum=1, maximum=20)),
            "dry_run_min_win_rate": self._normalize_decimal(payload.get("dry_run_min_win_rate"), default=Decimal("0.5"), minimum=Decimal("0"), maximum=Decimal("1")),
            "dry_run_max_turnover": self._normalize_decimal(payload.get("dry_run_max_turnover"), default=Decimal("0.6"), minimum=Decimal("0")),
            "dry_run_min_sample_count": str(self._normalize_int(payload.get("dry_run_min_sample_count"), default=20, minimum=3, maximum=500)),
            "validation_min_sample_count": str(self._normalize_int(payload.get("validation_min_sample_count"), default=12, minimum=3, maximum=500)),
            "validation_min_avg_future_return_pct": self._normalize_decimal(payload.get("validation_min_avg_future_return_pct"), default=Decimal("-0.1")),
            "consistency_max_validation_backtest_return_gap_pct": self._normalize_decimal(payload.get("consistency_max_validation_backtest_return_gap_pct"), default=Decimal("1.5"), minimum=Decimal("0")),
            "consistency_max_training_validation_positive_rate_gap": self._normalize_decimal(payload.get("consistency_max_training_validation_positive_rate_gap"), default=Decimal("0.2"), minimum=Decimal("0"), maximum=Decimal("1")),
            "consistency_max_training_validation_return_gap_pct": self._normalize_decimal(payload.get("consistency_max_training_validation_return_gap_pct"), default=Decimal("1.5"), minimum=Decimal("0")),
            "rule_min_ema20_gap_pct": self._normalize_decimal(payload.get("rule_min_ema20_gap_pct"), default=Decimal("0")),
            "rule_min_ema55_gap_pct": self._normalize_decimal(payload.get("rule_min_ema55_gap_pct"), default=Decimal("0")),
            "rule_max_atr_pct": self._normalize_decimal(payload.get("rule_max_atr_pct"), default=Decimal("5"), minimum=Decimal("0")),
            "rule_min_volume_ratio": self._normalize_decimal(payload.get("rule_min_volume_ratio"), default=Decimal("1"), minimum=Decimal("0")),
            "strict_rule_min_ema20_gap_pct": self._normalize_decimal(payload.get("strict_rule_min_ema20_gap_pct"), default=Decimal("1.2")),
            "strict_rule_min_ema55_gap_pct": self._normalize_decimal(payload.get("strict_rule_min_ema55_gap_pct"), default=Decimal("1.8")),
            "strict_rule_max_atr_pct": self._normalize_decimal(payload.get("strict_rule_max_atr_pct"), default=Decimal("4.5"), minimum=Decimal("0")),
            "strict_rule_min_volume_ratio": self._normalize_decimal(payload.get("strict_rule_min_volume_ratio"), default=Decimal("1.05"), minimum=Decimal("0")),
            "enable_rule_gate": self._normalize_bool(payload.get("enable_rule_gate"), default=True),
            "enable_validation_gate": self._normalize_bool(payload.get("enable_validation_gate"), default=True),
            "enable_backtest_gate": self._normalize_bool(payload.get("enable_backtest_gate"), default=True),
            "enable_consistency_gate": self._normalize_bool(payload.get("enable_consistency_gate"), default=True),
            "enable_live_gate": self._normalize_bool(payload.get("enable_live_gate"), default=True),
            "live_min_score": self._normalize_decimal(payload.get("live_min_score"), default=Decimal("0.65"), minimum=Decimal("0"), maximum=Decimal("1")),
            "live_min_positive_rate": self._normalize_decimal(payload.get("live_min_positive_rate"), default=Decimal("0.50"), minimum=Decimal("0"), maximum=Decimal("1")),
            "live_min_net_return_pct": self._normalize_decimal(payload.get("live_min_net_return_pct"), default=Decimal("0.20")),
            "live_min_win_rate": self._normalize_decimal(payload.get("live_min_win_rate"), default=Decimal("0.55"), minimum=Decimal("0"), maximum=Decimal("1")),
            "live_max_turnover": self._normalize_decimal(payload.get("live_max_turnover"), default=Decimal("0.45"), minimum=Decimal("0")),
            "live_min_sample_count": str(self._normalize_int(payload.get("live_min_sample_count"), default=24, minimum=3, maximum=500)),
        }

    def _normalize_operations_section(self, value: object) -> dict[str, object]:
        """整理长期运行参数。"""

        payload = dict(value or {}) if isinstance(value, dict) else {}
        operations_preset_key = self._normalize_choice(
            payload.get("operations_preset_key"),
            default="balanced_guard",
            allowed=SUPPORTED_OPERATIONS_PRESETS,
        )
        payload = {**OPERATIONS_PRESET_VALUES.get(operations_preset_key, {}), **payload}
        return {
            "operations_preset_key": operations_preset_key,
            "pause_after_consecutive_failures": str(
                self._normalize_int(payload.get("pause_after_consecutive_failures"), default=2, minimum=1, maximum=20)
            ),
            "stale_sync_failure_threshold": str(
                self._normalize_int(payload.get("stale_sync_failure_threshold"), default=1, minimum=1, maximum=20)
            ),
            "auto_pause_on_error": self._normalize_bool(payload.get("auto_pause_on_error"), default=True),
            "review_limit": str(self._normalize_int(payload.get("review_limit"), default=10, minimum=1, maximum=100)),
            "comparison_run_limit": str(
                self._normalize_int(payload.get("comparison_run_limit"), default=5, minimum=1, maximum=20)
            ),
            "cycle_cooldown_minutes": str(
                self._normalize_int(payload.get("cycle_cooldown_minutes"), default=15, minimum=0, maximum=1440)
            ),
            "max_daily_cycle_count": str(
                self._normalize_int(payload.get("max_daily_cycle_count"), default=8, minimum=1, maximum=200)
            ),
        }

    def _normalize_automation_section(self, value: object) -> dict[str, object]:
        """整理自动化长期运行和告警窗口。"""

        payload = dict(value or {}) if isinstance(value, dict) else {}
        automation_preset_key = self._normalize_choice(
            payload.get("automation_preset_key"),
            default="balanced_runtime",
            allowed=SUPPORTED_AUTOMATION_PRESETS,
        )
        payload = {**AUTOMATION_PRESET_VALUES.get(automation_preset_key, {}), **payload}
        return {
            "automation_preset_key": automation_preset_key,
            "long_run_seconds": str(
                self._normalize_int(payload.get("long_run_seconds"), default=300, minimum=60, maximum=86400)
            ),
            "alert_cleanup_minutes": str(
                self._normalize_int(payload.get("alert_cleanup_minutes"), default=15, minimum=1, maximum=1440)
            ),
        }

    def _normalize_symbol_list(
        self,
        value: object,
        *,
        fallback: Iterable[str],
        allow_empty: bool = False,
    ) -> tuple[str, ...]:
        """整理交易对列表。"""

        items: list[str]
        explicit_value = value is not None
        if isinstance(value, str):
            items = value.split(",")
        elif isinstance(value, (list, tuple)):
            items = [str(item) for item in value]
        else:
            items = list(fallback)

        normalized: list[str] = []
        seen: set[str] = set()
        for item in items:
            symbol = str(item).strip().upper()
            if not symbol or not re.fullmatch(r"[A-Z0-9]+", symbol):
                continue
            if symbol in seen:
                continue
            seen.add(symbol)
            normalized.append(symbol)
        if normalized:
            return tuple(normalized)
        if allow_empty and explicit_value:
            return ()
        return tuple(list(fallback))

    def _normalize_timeframes(self, value: object, *, allow_empty: bool = False) -> tuple[str, ...]:
        """整理周期列表。"""

        explicit_value = value is not None
        if isinstance(value, str):
            items = value.split(",")
        elif isinstance(value, (list, tuple)):
            items = [str(item) for item in value]
        else:
            items = list(SUPPORTED_TIMEFRAMES)

        normalized: list[str] = []
        seen: set[str] = set()
        for item in items:
            timeframe = str(item).strip()
            if timeframe not in SUPPORTED_TIMEFRAMES or timeframe in seen:
                continue
            seen.add(timeframe)
            normalized.append(timeframe)
        if normalized:
            return tuple(normalized)
        if allow_empty and explicit_value:
            return ()
        return tuple(list(SUPPORTED_TIMEFRAMES))

    def _normalize_factor_list(
        self,
        value: object,
        *,
        allowed: Iterable[str],
        fallback: Iterable[str],
        allow_empty: bool = False,
    ) -> tuple[str, ...]:
        """整理因子列表。"""

        allowed_list = tuple(str(item) for item in allowed)
        allowed_set = set(allowed_list)
        explicit_value = value is not None
        if isinstance(value, str):
            items = value.split(",")
        elif isinstance(value, (list, tuple)):
            items = [str(item) for item in value]
        else:
            items = list(fallback)

        normalized: list[str] = []
        seen: set[str] = set()
        for item in items:
            factor_name = str(item).strip()
            if factor_name not in allowed_set or factor_name in seen:
                continue
            seen.add(factor_name)
            normalized.append(factor_name)
        if normalized:
            return tuple(normalized)
        if allow_empty and explicit_value:
            return ()
        return tuple(list(fallback))

    @staticmethod
    def _normalize_choice(value: object, *, default: str, allowed: Iterable[str]) -> str:
        """整理枚举型配置。"""

        normalized = str(value or "").strip()
        return normalized if normalized in set(str(item) for item in allowed) else default

    def _normalize_holding_window_label(self, value: object, *, min_days: int, max_days: int) -> str:
        """整理持有窗口标签。"""

        normalized = str(value or "").strip()
        if normalized in SUPPORTED_HOLDING_WINDOWS:
            return normalized
        return f"{min_days}-{max_days}d"

    @staticmethod
    def _holding_window_bounds(label: str) -> tuple[int, int]:
        """把持有窗口标签拆成最小和最大天数。"""

        matched = re.fullmatch(r"(\d+)-(\d+)d", str(label or "").strip())
        if not matched:
            return 1, 3
        min_days = max(1, min(7, int(matched.group(1))))
        max_days = max(1, min(7, int(matched.group(2))))
        if min_days > max_days:
            min_days, max_days = max_days, min_days
        return min_days, max_days

    @staticmethod
    def _normalize_bool(value: object, *, default: bool) -> bool:
        """整理布尔配置。"""

        if isinstance(value, bool):
            return value
        normalized = str(value or "").strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off"}:
            return False
        return default

    @staticmethod
    def _normalize_date(value: object) -> str:
        """整理日期字符串。"""

        normalized = str(value or "").strip()
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", normalized):
            return normalized
        return ""

    @staticmethod
    def _normalize_decimal(
        value: object,
        *,
        default: Decimal,
        minimum: Decimal | None = None,
        maximum: Decimal | None = None,
    ) -> str:
        """整理十进制配置。"""

        try:
            parsed = Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            parsed = default
        if minimum is not None and parsed < minimum:
            parsed = minimum
        if maximum is not None and parsed > maximum:
            parsed = maximum
        return format(parsed.normalize(), "f")

    @staticmethod
    def _normalize_int(value: object, *, default: int, minimum: int, maximum: int) -> int:
        """整理整数配置。"""

        try:
            parsed = int(str(value))
        except (TypeError, ValueError):
            parsed = default
        return max(minimum, min(maximum, parsed))

    @staticmethod
    def _normalize_split_ratios(
        *,
        train_ratio: Decimal,
        validation_ratio: Decimal,
        test_ratio: Decimal,
    ) -> dict[str, str]:
        """把切分比例归一化成总和为 1 的稳定值。"""

        total = train_ratio + validation_ratio + test_ratio
        if total <= 0:
            train_ratio = Decimal("0.6")
            validation_ratio = Decimal("0.2")
            test_ratio = Decimal("0.2")
            total = Decimal("1")
        normalized = {
            "train_split_ratio": format((train_ratio / total).quantize(Decimal("0.0001")).normalize(), "f"),
            "validation_split_ratio": format((validation_ratio / total).quantize(Decimal("0.0001")).normalize(), "f"),
            "test_split_ratio": format((test_ratio / total).quantize(Decimal("0.0001")).normalize(), "f"),
        }
        return normalized

    def _read_config_file(self) -> dict[str, object]:
        """读取配置文件。"""

        if not self._config_path.exists():
            return _default_config()
        try:
            payload = json.loads(self._config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return _default_config()
        return payload if isinstance(payload, dict) else _default_config()

    def _write_config_file(self, payload: dict[str, object]) -> None:
        """原子写入配置文件。"""

        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self._config_path.with_suffix(f"{self._config_path.suffix}.tmp")
        temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temp_path.replace(self._config_path)


workbench_config_service = WorkbenchConfigService()
