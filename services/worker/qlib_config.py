"""Qlib 研究层配置。

这个文件负责统一读取研究层运行目录，并给出清晰的可执行状态。
"""

from __future__ import annotations

import importlib.util
import json
import os
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

from services.worker.qlib_features import AUXILIARY_FEATURE_COLUMNS, PRIMARY_FEATURE_COLUMNS


DEFAULT_RUNTIME_ROOT = Path("/tmp/quant-qlib-runtime")
DEFAULT_BACKTEST_FEE_BPS = Decimal("10")
DEFAULT_BACKTEST_SLIPPAGE_BPS = Decimal("5")
DEFAULT_BACKTEST_COST_MODEL = "round_trip_basis_points"
DEFAULT_LABEL_TARGET_PCT = Decimal("1")
DEFAULT_LABEL_STOP_PCT = Decimal("-1")
DEFAULT_LOOKBACK_DAYS = 30
DEFAULT_TRAIN_SPLIT_RATIO = Decimal("0.6")
DEFAULT_VALIDATION_SPLIT_RATIO = Decimal("0.2")
DEFAULT_TEST_SPLIT_RATIO = Decimal("0.2")
DEFAULT_DRY_RUN_MIN_SCORE = Decimal("0.55")
DEFAULT_DRY_RUN_MIN_POSITIVE_RATE = Decimal("0.45")
DEFAULT_DRY_RUN_MIN_NET_RETURN_PCT = Decimal("0")
DEFAULT_DRY_RUN_MIN_SHARPE = Decimal("0.5")
DEFAULT_DRY_RUN_MAX_DRAWDOWN_PCT = Decimal("15")
DEFAULT_DRY_RUN_MAX_LOSS_STREAK = 3
DEFAULT_DRY_RUN_MIN_WIN_RATE = Decimal("0.5")
DEFAULT_DRY_RUN_MAX_TURNOVER = Decimal("0.6")
DEFAULT_DRY_RUN_MIN_SAMPLE_COUNT = 20
DEFAULT_VALIDATION_MIN_SAMPLE_COUNT = 12
DEFAULT_VALIDATION_MIN_AVG_FUTURE_RETURN_PCT = Decimal("-0.1")
DEFAULT_CONSISTENCY_MAX_VALIDATION_BACKTEST_RETURN_GAP_PCT = Decimal("1.5")
DEFAULT_CONSISTENCY_MAX_TRAINING_VALIDATION_POSITIVE_RATE_GAP = Decimal("0.2")
DEFAULT_CONSISTENCY_MAX_TRAINING_VALIDATION_RETURN_GAP_PCT = Decimal("1.5")
DEFAULT_RULE_MIN_EMA20_GAP_PCT = Decimal("0")
DEFAULT_RULE_MIN_EMA55_GAP_PCT = Decimal("0")
DEFAULT_RULE_MAX_ATR_PCT = Decimal("5")
DEFAULT_RULE_MIN_VOLUME_RATIO = Decimal("1")
DEFAULT_STRICT_RULE_MIN_EMA20_GAP_PCT = Decimal("1.2")
DEFAULT_STRICT_RULE_MIN_EMA55_GAP_PCT = Decimal("1.8")
DEFAULT_STRICT_RULE_MAX_ATR_PCT = Decimal("4.5")
DEFAULT_STRICT_RULE_MIN_VOLUME_RATIO = Decimal("1.05")
DEFAULT_LIVE_MIN_SCORE = Decimal("0.65")
DEFAULT_LIVE_MIN_POSITIVE_RATE = Decimal("0.50")
DEFAULT_LIVE_MIN_NET_RETURN_PCT = Decimal("0.20")
DEFAULT_LIVE_MIN_WIN_RATE = Decimal("0.55")
DEFAULT_LIVE_MAX_TURNOVER = Decimal("0.45")
DEFAULT_LIVE_MIN_SAMPLE_COUNT = 24
DEFAULT_LIVE_MIN_ML_PROBABILITY = Decimal("0.55")
DEFAULT_ENABLE_ML_LIVE_GATE = True
DEFAULT_RESEARCH_TEMPLATE = "single_asset_timing"
DEFAULT_LABEL_MODE = "earliest_hit"
DEFAULT_LABEL_TRIGGER_BASIS = "close"
DEFAULT_OUTLIER_POLICY = "clip"
DEFAULT_NORMALIZATION_POLICY = "fixed_4dp"
DEFAULT_MISSING_POLICY = "neutral_fill"
DEFAULT_WINDOW_MODE = "rolling"
DEFAULT_SIGNAL_CONFIDENCE_FLOOR = Decimal("0.55")
DEFAULT_TREND_WEIGHT = Decimal("1.3")
DEFAULT_MOMENTUM_WEIGHT = Decimal("1")
DEFAULT_VOLUME_WEIGHT = Decimal("1.1")
DEFAULT_OSCILLATOR_WEIGHT = Decimal("0.7")
DEFAULT_VOLATILITY_WEIGHT = Decimal("0.9")
DEFAULT_STRICT_PENALTY_WEIGHT = Decimal("1")

# ML 模型相关默认值
DEFAULT_MODEL_TYPE = "lightgbm"
DEFAULT_MODEL_LABEL_THRESHOLD = Decimal("0.5")  # 收益 > 0.5% 才算正样本，减少噪声
DEFAULT_HYPEROPT_N_TRIALS = 50
DEFAULT_HYPEROPT_TIMEOUT_SECONDS = 300
SUPPORTED_MODEL_TYPES = ("lightgbm", "xgboost", "heuristic")

# LightGBM 默认参数（增加正则化防止过拟合）
DEFAULT_LIGHTGBM_PARAMS = {
    "objective": "binary",
    "metric": "auc",
    "boosting_type": "gbdt",
    "num_leaves": 15,  # 减少复杂度，防止过拟合
    "learning_rate": 0.03,  # 降低学习率
    "feature_fraction": 0.7,  # 减少特征使用比例
    "bagging_fraction": 0.7,  # 减少样本使用比例
    "bagging_freq": 5,
    "min_child_samples": 20,  # 每个叶子节点最小样本数
    "reg_alpha": 0.1,  # L1 正则化
    "reg_lambda": 0.1,  # L2 正则化
    "verbose": -1,
    "n_estimators": 100,
    "early_stopping_rounds": 15,  # 增加早停耐心
    "random_state": 42,
}

# XGBoost 默认参数（增加正则化防止过拟合）
DEFAULT_XGBOOST_PARAMS = {
    "objective": "binary:logistic",
    "eval_metric": "auc",
    "max_depth": 4,  # 减少深度
    "learning_rate": 0.03,  # 降低学习率
    "subsample": 0.7,  # 减少样本使用比例
    "colsample_bytree": 0.7,  # 减少特征使用比例
    "min_child_weight": 5,  # 最小样本权重
    "reg_alpha": 0.1,  # L1 正则化
    "reg_lambda": 0.1,  # L2 正则化
    "n_estimators": 100,
    "early_stopping_rounds": 15,
    "random_state": 42,
    "verbosity": 0,
}

SUPPORTED_RESEARCH_TEMPLATES = ("single_asset_timing", "single_asset_timing_strict")
SUPPORTED_LABEL_MODES = ("earliest_hit", "close_only", "window_majority")
SUPPORTED_LABEL_TRIGGER_BASES = ("close", "high_low")
SUPPORTED_OUTLIER_POLICIES = ("clip", "raw")
SUPPORTED_NORMALIZATION_POLICIES = ("fixed_4dp", "zscore_by_symbol")
SUPPORTED_MISSING_POLICIES = ("neutral_fill", "strict_drop")
SUPPORTED_WINDOW_MODES = ("rolling", "fixed")
SUPPORTED_BACKTEST_COST_MODELS = (
    "round_trip_basis_points",
    "single_side_basis_points",
    "zero_cost_baseline",
)
_RUNTIME_HINTS: dict[str, str] = {}


class QlibConfigurationError(RuntimeError):
    """研究层配置不可执行时抛出的错误。"""


@dataclass(frozen=True)
class QlibRuntimePaths:
    """研究层运行目录集合。"""

    runtime_root: Path
    dataset_dir: Path
    dataset_snapshots_dir: Path
    dataset_cache_dir: Path
    artifacts_dir: Path
    runs_dir: Path
    latest_training_path: Path
    latest_inference_path: Path
    latest_dataset_snapshot_path: Path
    experiment_index_path: Path
    best_params_path: Path


@dataclass(frozen=True)
class QlibRuntimeConfig:
    """研究层配置快照。"""

    status: str
    detail: str
    backend: str
    qlib_available: bool
    backtest_fee_bps: Decimal
    backtest_slippage_bps: Decimal
    backtest_cost_model: str
    force_validation_top_candidate: bool
    research_data_layer: str
    selected_symbols: tuple[str, ...]
    selected_timeframes: tuple[str, ...]
    sample_limit: int
    lookback_days: int
    window_mode: str
    start_date: str
    end_date: str
    research_preset_key: str
    label_preset_key: str
    research_template: str
    primary_feature_columns: tuple[str, ...]
    auxiliary_feature_columns: tuple[str, ...]
    missing_policy: str
    outlier_policy: str
    normalization_policy: str
    timeframe_profiles: dict[str, dict[str, int | str]]
    label_mode: str
    label_trigger_basis: str
    label_target_pct: Decimal
    label_stop_pct: Decimal
    holding_window_min_days: int
    holding_window_max_days: int
    holding_window_label: str
    model_key: str
    train_split_ratio: Decimal
    validation_split_ratio: Decimal
    test_split_ratio: Decimal
    dry_run_min_score: Decimal
    dry_run_min_positive_rate: Decimal
    dry_run_min_net_return_pct: Decimal
    dry_run_min_sharpe: Decimal
    dry_run_max_drawdown_pct: Decimal
    dry_run_max_loss_streak: int
    dry_run_min_win_rate: Decimal
    dry_run_max_turnover: Decimal
    dry_run_min_sample_count: int
    validation_min_sample_count: int
    validation_min_avg_future_return_pct: Decimal
    consistency_max_validation_backtest_return_gap_pct: Decimal
    consistency_max_training_validation_positive_rate_gap: Decimal
    consistency_max_training_validation_return_gap_pct: Decimal
    rule_min_ema20_gap_pct: Decimal
    rule_min_ema55_gap_pct: Decimal
    rule_max_atr_pct: Decimal
    rule_min_volume_ratio: Decimal
    strict_rule_min_ema20_gap_pct: Decimal
    strict_rule_min_ema55_gap_pct: Decimal
    strict_rule_max_atr_pct: Decimal
    strict_rule_min_volume_ratio: Decimal
    enable_rule_gate: bool
    enable_validation_gate: bool
    enable_backtest_gate: bool
    enable_consistency_gate: bool
    enable_live_gate: bool
    live_min_score: Decimal
    live_min_positive_rate: Decimal
    live_min_net_return_pct: Decimal
    live_min_win_rate: Decimal
    live_max_turnover: Decimal
    live_min_sample_count: int
    enable_ml_live_gate: bool
    live_min_ml_probability: Decimal
    signal_confidence_floor: Decimal
    trend_weight: Decimal
    momentum_weight: Decimal
    volume_weight: Decimal
    oscillator_weight: Decimal
    volatility_weight: Decimal
    strict_penalty_weight: Decimal
    # ML 模型相关配置
    model_type: str
    model_params: dict[str, object]
    model_label_threshold: Decimal
    enable_ml_training: bool
    hyperopt_n_trials: int
    hyperopt_timeout_seconds: int
    paths: QlibRuntimePaths

    def ensure_ready(self) -> None:
        """确认研究层目录已经可执行。"""

        if self.status != "ready":
            raise QlibConfigurationError(self.detail)
        try:
            self.paths.runtime_root.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise QlibConfigurationError(f"研究层运行目录不可写：{self.paths.runtime_root}") from exc


def load_qlib_config(
    env: dict[str, str] | None = None,
    *,
    require_explicit: bool = False,
) -> QlibRuntimeConfig:
    """读取研究层配置。"""

    values = env if env is not None else dict(os.environ)
    runtime_root_raw = values.get("QUANT_QLIB_RUNTIME_ROOT", "").strip()
    session_id = values.get("QUANT_QLIB_SESSION_ID", "").strip()
    backtest_fee_bps = _read_decimal(
        values.get("QUANT_QLIB_BACKTEST_FEE_BPS"),
        default=DEFAULT_BACKTEST_FEE_BPS,
        env_name="QUANT_QLIB_BACKTEST_FEE_BPS",
        minimum=Decimal("0"),
    )
    backtest_slippage_bps = _read_decimal(
        values.get("QUANT_QLIB_BACKTEST_SLIPPAGE_BPS"),
        default=DEFAULT_BACKTEST_SLIPPAGE_BPS,
        env_name="QUANT_QLIB_BACKTEST_SLIPPAGE_BPS",
        minimum=Decimal("0"),
    )
    backtest_cost_model = _read_choice(
        values.get("QUANT_QLIB_BACKTEST_COST_MODEL"),
        default=DEFAULT_BACKTEST_COST_MODEL,
        allowed=SUPPORTED_BACKTEST_COST_MODELS,
    )
    force_validation_top_candidate = str(values.get("QUANT_QLIB_FORCE_TOP_CANDIDATE", "")).strip().lower() == "true"
    selected_symbols = _read_symbol_list(values.get("QUANT_QLIB_SELECTED_SYMBOLS"))
    selected_timeframes = _read_timeframe_list(values.get("QUANT_QLIB_TIMEFRAMES"))
    sample_limit = _read_int(values.get("QUANT_QLIB_SAMPLE_LIMIT"), default=120, env_name="QUANT_QLIB_SAMPLE_LIMIT", minimum=60)
    lookback_days = _read_int(values.get("QUANT_QLIB_LOOKBACK_DAYS"), default=DEFAULT_LOOKBACK_DAYS, env_name="QUANT_QLIB_LOOKBACK_DAYS", minimum=7)
    window_mode = _read_choice(
        values.get("QUANT_QLIB_WINDOW_MODE"),
        default=DEFAULT_WINDOW_MODE,
        allowed=SUPPORTED_WINDOW_MODES,
    )
    start_date = _read_date(values.get("QUANT_QLIB_START_DATE"))
    end_date = _read_date(values.get("QUANT_QLIB_END_DATE"))
    research_preset_key = str(values.get("QUANT_QLIB_RESEARCH_PRESET_KEY") or "").strip() or "baseline_balanced"
    label_preset_key = str(values.get("QUANT_QLIB_LABEL_PRESET_KEY") or "").strip() or "balanced_window"
    research_template = _read_research_template(values.get("QUANT_QLIB_RESEARCH_TEMPLATE"))
    primary_feature_columns = _read_name_list(
        values.get("QUANT_QLIB_PRIMARY_FACTORS"),
        default=PRIMARY_FEATURE_COLUMNS,
    )
    auxiliary_feature_columns = _read_name_list(
        values.get("QUANT_QLIB_AUXILIARY_FACTORS"),
        default=AUXILIARY_FEATURE_COLUMNS,
    )
    missing_policy = _read_choice(
        values.get("QUANT_QLIB_MISSING_POLICY"),
        default=DEFAULT_MISSING_POLICY,
        allowed=SUPPORTED_MISSING_POLICIES,
    )
    outlier_policy = _read_choice(
        values.get("QUANT_QLIB_OUTLIER_POLICY"),
        default=DEFAULT_OUTLIER_POLICY,
        allowed=SUPPORTED_OUTLIER_POLICIES,
    )
    normalization_policy = _read_choice(
        values.get("QUANT_QLIB_NORMALIZATION_POLICY"),
        default=DEFAULT_NORMALIZATION_POLICY,
        allowed=SUPPORTED_NORMALIZATION_POLICIES,
    )
    timeframe_profiles = _read_timeframe_profiles(values.get("QUANT_QLIB_TIMEFRAME_PROFILES"))
    label_mode = _read_choice(
        values.get("QUANT_QLIB_LABEL_MODE"),
        default=DEFAULT_LABEL_MODE,
        allowed=SUPPORTED_LABEL_MODES,
    )
    label_trigger_basis = _read_choice(
        values.get("QUANT_QLIB_LABEL_TRIGGER_BASIS"),
        default=DEFAULT_LABEL_TRIGGER_BASIS,
        allowed=SUPPORTED_LABEL_TRIGGER_BASES,
    )
    label_target_pct = _read_decimal(
        values.get("QUANT_QLIB_LABEL_TARGET_PCT"),
        default=DEFAULT_LABEL_TARGET_PCT,
        env_name="QUANT_QLIB_LABEL_TARGET_PCT",
        minimum=Decimal("0.1"),
    )
    label_stop_pct = _read_decimal(
        values.get("QUANT_QLIB_LABEL_STOP_PCT"),
        default=DEFAULT_LABEL_STOP_PCT,
        env_name="QUANT_QLIB_LABEL_STOP_PCT",
        maximum=Decimal("-0.1"),
    )
    holding_window_min_days = _read_int(
        values.get("QUANT_QLIB_HOLDING_WINDOW_MIN_DAYS"),
        default=1,
        env_name="QUANT_QLIB_HOLDING_WINDOW_MIN_DAYS",
        minimum=1,
    )
    holding_window_max_days = _read_int(
        values.get("QUANT_QLIB_HOLDING_WINDOW_MAX_DAYS"),
        default=3,
        env_name="QUANT_QLIB_HOLDING_WINDOW_MAX_DAYS",
        minimum=1,
    )
    if holding_window_min_days > holding_window_max_days:
        holding_window_min_days, holding_window_max_days = holding_window_max_days, holding_window_min_days
    holding_window_label = (
        str(values.get("QUANT_QLIB_HOLDING_WINDOW_LABEL") or "").strip()
        or f"{holding_window_min_days}-{holding_window_max_days}d"
    )
    model_key = str(values.get("QUANT_QLIB_MODEL_KEY") or "").strip() or "heuristic_v1"
    train_split_ratio = _read_decimal(
        values.get("QUANT_QLIB_TRAIN_SPLIT_RATIO"),
        default=DEFAULT_TRAIN_SPLIT_RATIO,
        env_name="QUANT_QLIB_TRAIN_SPLIT_RATIO",
        minimum=Decimal("0.05"),
        maximum=Decimal("0.9"),
    )
    validation_split_ratio = _read_decimal(
        values.get("QUANT_QLIB_VALIDATION_SPLIT_RATIO"),
        default=DEFAULT_VALIDATION_SPLIT_RATIO,
        env_name="QUANT_QLIB_VALIDATION_SPLIT_RATIO",
        minimum=Decimal("0.05"),
        maximum=Decimal("0.8"),
    )
    test_split_ratio = _read_decimal(
        values.get("QUANT_QLIB_TEST_SPLIT_RATIO"),
        default=DEFAULT_TEST_SPLIT_RATIO,
        env_name="QUANT_QLIB_TEST_SPLIT_RATIO",
        minimum=Decimal("0.05"),
        maximum=Decimal("0.8"),
    )
    dry_run_min_score = _read_decimal(
        values.get("QUANT_QLIB_DRY_RUN_MIN_SCORE"),
        default=DEFAULT_DRY_RUN_MIN_SCORE,
        env_name="QUANT_QLIB_DRY_RUN_MIN_SCORE",
        minimum=Decimal("0"),
        maximum=Decimal("1"),
    )
    dry_run_min_positive_rate = _read_decimal(
        values.get("QUANT_QLIB_DRY_RUN_MIN_POSITIVE_RATE"),
        default=DEFAULT_DRY_RUN_MIN_POSITIVE_RATE,
        env_name="QUANT_QLIB_DRY_RUN_MIN_POSITIVE_RATE",
        minimum=Decimal("0"),
        maximum=Decimal("1"),
    )
    dry_run_min_net_return_pct = _read_decimal(
        values.get("QUANT_QLIB_DRY_RUN_MIN_NET_RETURN_PCT"),
        default=DEFAULT_DRY_RUN_MIN_NET_RETURN_PCT,
        env_name="QUANT_QLIB_DRY_RUN_MIN_NET_RETURN_PCT",
    )
    dry_run_min_sharpe = _read_decimal(
        values.get("QUANT_QLIB_DRY_RUN_MIN_SHARPE"),
        default=DEFAULT_DRY_RUN_MIN_SHARPE,
        env_name="QUANT_QLIB_DRY_RUN_MIN_SHARPE",
    )
    dry_run_max_drawdown_pct = _read_decimal(
        values.get("QUANT_QLIB_DRY_RUN_MAX_DRAWDOWN_PCT"),
        default=DEFAULT_DRY_RUN_MAX_DRAWDOWN_PCT,
        env_name="QUANT_QLIB_DRY_RUN_MAX_DRAWDOWN_PCT",
        minimum=Decimal("0"),
    )
    dry_run_max_loss_streak = _read_int(
        values.get("QUANT_QLIB_DRY_RUN_MAX_LOSS_STREAK"),
        default=DEFAULT_DRY_RUN_MAX_LOSS_STREAK,
        env_name="QUANT_QLIB_DRY_RUN_MAX_LOSS_STREAK",
        minimum=1,
    )
    dry_run_min_win_rate = _read_decimal(
        values.get("QUANT_QLIB_DRY_RUN_MIN_WIN_RATE"),
        default=DEFAULT_DRY_RUN_MIN_WIN_RATE,
        env_name="QUANT_QLIB_DRY_RUN_MIN_WIN_RATE",
        minimum=Decimal("0"),
        maximum=Decimal("1"),
    )
    dry_run_max_turnover = _read_decimal(
        values.get("QUANT_QLIB_DRY_RUN_MAX_TURNOVER"),
        default=DEFAULT_DRY_RUN_MAX_TURNOVER,
        env_name="QUANT_QLIB_DRY_RUN_MAX_TURNOVER",
        minimum=Decimal("0"),
    )
    dry_run_min_sample_count = _read_int(
        values.get("QUANT_QLIB_DRY_RUN_MIN_SAMPLE_COUNT"),
        default=DEFAULT_DRY_RUN_MIN_SAMPLE_COUNT,
        env_name="QUANT_QLIB_DRY_RUN_MIN_SAMPLE_COUNT",
        minimum=3,
    )
    validation_min_sample_count = _read_int(
        values.get("QUANT_QLIB_VALIDATION_MIN_SAMPLE_COUNT"),
        default=DEFAULT_VALIDATION_MIN_SAMPLE_COUNT,
        env_name="QUANT_QLIB_VALIDATION_MIN_SAMPLE_COUNT",
        minimum=3,
    )
    validation_min_avg_future_return_pct = _read_decimal(
        values.get("QUANT_QLIB_VALIDATION_MIN_AVG_FUTURE_RETURN_PCT"),
        default=DEFAULT_VALIDATION_MIN_AVG_FUTURE_RETURN_PCT,
        env_name="QUANT_QLIB_VALIDATION_MIN_AVG_FUTURE_RETURN_PCT",
    )
    consistency_max_validation_backtest_return_gap_pct = _read_decimal(
        values.get("QUANT_QLIB_CONSISTENCY_MAX_VALIDATION_BACKTEST_RETURN_GAP_PCT"),
        default=DEFAULT_CONSISTENCY_MAX_VALIDATION_BACKTEST_RETURN_GAP_PCT,
        env_name="QUANT_QLIB_CONSISTENCY_MAX_VALIDATION_BACKTEST_RETURN_GAP_PCT",
        minimum=Decimal("0"),
    )
    consistency_max_training_validation_positive_rate_gap = _read_decimal(
        values.get("QUANT_QLIB_CONSISTENCY_MAX_TRAINING_VALIDATION_POSITIVE_RATE_GAP"),
        default=DEFAULT_CONSISTENCY_MAX_TRAINING_VALIDATION_POSITIVE_RATE_GAP,
        env_name="QUANT_QLIB_CONSISTENCY_MAX_TRAINING_VALIDATION_POSITIVE_RATE_GAP",
        minimum=Decimal("0"),
        maximum=Decimal("1"),
    )
    consistency_max_training_validation_return_gap_pct = _read_decimal(
        values.get("QUANT_QLIB_CONSISTENCY_MAX_TRAINING_VALIDATION_RETURN_GAP_PCT"),
        default=DEFAULT_CONSISTENCY_MAX_TRAINING_VALIDATION_RETURN_GAP_PCT,
        env_name="QUANT_QLIB_CONSISTENCY_MAX_TRAINING_VALIDATION_RETURN_GAP_PCT",
        minimum=Decimal("0"),
    )
    rule_min_ema20_gap_pct = _read_decimal(
        values.get("QUANT_QLIB_RULE_MIN_EMA20_GAP_PCT"),
        default=DEFAULT_RULE_MIN_EMA20_GAP_PCT,
        env_name="QUANT_QLIB_RULE_MIN_EMA20_GAP_PCT",
    )
    rule_min_ema55_gap_pct = _read_decimal(
        values.get("QUANT_QLIB_RULE_MIN_EMA55_GAP_PCT"),
        default=DEFAULT_RULE_MIN_EMA55_GAP_PCT,
        env_name="QUANT_QLIB_RULE_MIN_EMA55_GAP_PCT",
    )
    rule_max_atr_pct = _read_decimal(
        values.get("QUANT_QLIB_RULE_MAX_ATR_PCT"),
        default=DEFAULT_RULE_MAX_ATR_PCT,
        env_name="QUANT_QLIB_RULE_MAX_ATR_PCT",
        minimum=Decimal("0"),
    )
    rule_min_volume_ratio = _read_decimal(
        values.get("QUANT_QLIB_RULE_MIN_VOLUME_RATIO"),
        default=DEFAULT_RULE_MIN_VOLUME_RATIO,
        env_name="QUANT_QLIB_RULE_MIN_VOLUME_RATIO",
        minimum=Decimal("0"),
    )
    strict_rule_min_ema20_gap_pct = _read_decimal(
        values.get("QUANT_QLIB_STRICT_RULE_MIN_EMA20_GAP_PCT"),
        default=DEFAULT_STRICT_RULE_MIN_EMA20_GAP_PCT,
        env_name="QUANT_QLIB_STRICT_RULE_MIN_EMA20_GAP_PCT",
    )
    strict_rule_min_ema55_gap_pct = _read_decimal(
        values.get("QUANT_QLIB_STRICT_RULE_MIN_EMA55_GAP_PCT"),
        default=DEFAULT_STRICT_RULE_MIN_EMA55_GAP_PCT,
        env_name="QUANT_QLIB_STRICT_RULE_MIN_EMA55_GAP_PCT",
    )
    strict_rule_max_atr_pct = _read_decimal(
        values.get("QUANT_QLIB_STRICT_RULE_MAX_ATR_PCT"),
        default=DEFAULT_STRICT_RULE_MAX_ATR_PCT,
        env_name="QUANT_QLIB_STRICT_RULE_MAX_ATR_PCT",
        minimum=Decimal("0"),
    )
    strict_rule_min_volume_ratio = _read_decimal(
        values.get("QUANT_QLIB_STRICT_RULE_MIN_VOLUME_RATIO"),
        default=DEFAULT_STRICT_RULE_MIN_VOLUME_RATIO,
        env_name="QUANT_QLIB_STRICT_RULE_MIN_VOLUME_RATIO",
        minimum=Decimal("0"),
    )
    enable_rule_gate = _read_bool(values.get("QUANT_QLIB_ENABLE_RULE_GATE"), default=True)
    enable_validation_gate = _read_bool(values.get("QUANT_QLIB_ENABLE_VALIDATION_GATE"), default=True)
    enable_backtest_gate = _read_bool(values.get("QUANT_QLIB_ENABLE_BACKTEST_GATE"), default=True)
    enable_consistency_gate = _read_bool(values.get("QUANT_QLIB_ENABLE_CONSISTENCY_GATE"), default=True)
    enable_live_gate = _read_bool(values.get("QUANT_QLIB_ENABLE_LIVE_GATE"), default=True)
    live_min_score = _read_decimal(
        values.get("QUANT_QLIB_LIVE_MIN_SCORE"),
        default=DEFAULT_LIVE_MIN_SCORE,
        env_name="QUANT_QLIB_LIVE_MIN_SCORE",
        minimum=Decimal("0"),
        maximum=Decimal("1"),
    )
    live_min_positive_rate = _read_decimal(
        values.get("QUANT_QLIB_LIVE_MIN_POSITIVE_RATE"),
        default=DEFAULT_LIVE_MIN_POSITIVE_RATE,
        env_name="QUANT_QLIB_LIVE_MIN_POSITIVE_RATE",
        minimum=Decimal("0"),
        maximum=Decimal("1"),
    )
    live_min_net_return_pct = _read_decimal(
        values.get("QUANT_QLIB_LIVE_MIN_NET_RETURN_PCT"),
        default=DEFAULT_LIVE_MIN_NET_RETURN_PCT,
        env_name="QUANT_QLIB_LIVE_MIN_NET_RETURN_PCT",
    )
    live_min_win_rate = _read_decimal(
        values.get("QUANT_QLIB_LIVE_MIN_WIN_RATE"),
        default=DEFAULT_LIVE_MIN_WIN_RATE,
        env_name="QUANT_QLIB_LIVE_MIN_WIN_RATE",
        minimum=Decimal("0"),
        maximum=Decimal("1"),
    )
    live_max_turnover = _read_decimal(
        values.get("QUANT_QLIB_LIVE_MAX_TURNOVER"),
        default=DEFAULT_LIVE_MAX_TURNOVER,
        env_name="QUANT_QLIB_LIVE_MAX_TURNOVER",
        minimum=Decimal("0"),
    )
    live_min_sample_count = _read_int(
        values.get("QUANT_QLIB_LIVE_MIN_SAMPLE_COUNT"),
        default=DEFAULT_LIVE_MIN_SAMPLE_COUNT,
        env_name="QUANT_QLIB_LIVE_MIN_SAMPLE_COUNT",
        minimum=3,
    )
    enable_ml_live_gate = _read_bool(
        values.get("QUANT_QLIB_ENABLE_ML_LIVE_GATE"),
        default=DEFAULT_ENABLE_ML_LIVE_GATE,
    )
    live_min_ml_probability = _read_decimal(
        values.get("QUANT_QLIB_LIVE_MIN_ML_PROBABILITY"),
        default=DEFAULT_LIVE_MIN_ML_PROBABILITY,
        env_name="QUANT_QLIB_LIVE_MIN_ML_PROBABILITY",
        minimum=Decimal("0"),
        maximum=Decimal("1"),
    )
    signal_confidence_floor = _read_decimal(
        values.get("QUANT_QLIB_SIGNAL_CONFIDENCE_FLOOR"),
        default=DEFAULT_SIGNAL_CONFIDENCE_FLOOR,
        env_name="QUANT_QLIB_SIGNAL_CONFIDENCE_FLOOR",
        minimum=Decimal("0"),
        maximum=Decimal("1"),
    )
    trend_weight = _read_decimal(
        values.get("QUANT_QLIB_TREND_WEIGHT"),
        default=DEFAULT_TREND_WEIGHT,
        env_name="QUANT_QLIB_TREND_WEIGHT",
        minimum=Decimal("0"),
    )
    momentum_weight = _read_decimal(
        values.get("QUANT_QLIB_MOMENTUM_WEIGHT"),
        default=DEFAULT_MOMENTUM_WEIGHT,
        env_name="QUANT_QLIB_MOMENTUM_WEIGHT",
        minimum=Decimal("0"),
    )
    volume_weight = _read_decimal(
        values.get("QUANT_QLIB_VOLUME_WEIGHT"),
        default=DEFAULT_VOLUME_WEIGHT,
        env_name="QUANT_QLIB_VOLUME_WEIGHT",
        minimum=Decimal("0"),
    )
    oscillator_weight = _read_decimal(
        values.get("QUANT_QLIB_OSCILLATOR_WEIGHT"),
        default=DEFAULT_OSCILLATOR_WEIGHT,
        env_name="QUANT_QLIB_OSCILLATOR_WEIGHT",
        minimum=Decimal("0"),
    )
    volatility_weight = _read_decimal(
        values.get("QUANT_QLIB_VOLATILITY_WEIGHT"),
        default=DEFAULT_VOLATILITY_WEIGHT,
        env_name="QUANT_QLIB_VOLATILITY_WEIGHT",
        minimum=Decimal("0"),
    )
    strict_penalty_weight = _read_decimal(
        values.get("QUANT_QLIB_STRICT_PENALTY_WEIGHT"),
        default=DEFAULT_STRICT_PENALTY_WEIGHT,
        env_name="QUANT_QLIB_STRICT_PENALTY_WEIGHT",
        minimum=Decimal("0"),
    )

    # ML 模型配置
    model_type = _read_choice(
        values.get("QUANT_QLIB_MODEL_TYPE"),
        default=DEFAULT_MODEL_TYPE,
        allowed=SUPPORTED_MODEL_TYPES,
    )
    model_params = _read_model_params(values.get("QUANT_QLIB_MODEL_PARAMS"), model_type=model_type)
    model_label_threshold = _read_decimal(
        values.get("QUANT_QLIB_MODEL_LABEL_THRESHOLD"),
        default=DEFAULT_MODEL_LABEL_THRESHOLD,
        env_name="QUANT_QLIB_MODEL_LABEL_THRESHOLD",
    )
    enable_ml_training = _read_bool(values.get("QUANT_QLIB_ENABLE_ML_TRAINING"), default=True)
    hyperopt_n_trials = _read_int(
        values.get("QUANT_QLIB_HYPEROPT_N_TRIALS"),
        default=DEFAULT_HYPEROPT_N_TRIALS,
        env_name="QUANT_QLIB_HYPEROPT_N_TRIALS",
        minimum=10,
    )
    hyperopt_timeout_seconds = _read_int(
        values.get("QUANT_QLIB_HYPEROPT_TIMEOUT_SECONDS"),
        default=DEFAULT_HYPEROPT_TIMEOUT_SECONDS,
        env_name="QUANT_QLIB_HYPEROPT_TIMEOUT_SECONDS",
        minimum=60,
    )

    _publish_runtime_hints(
        {
            "train_split_ratio": format(train_split_ratio.normalize(), "f"),
            "validation_split_ratio": format(validation_split_ratio.normalize(), "f"),
            "test_split_ratio": format(test_split_ratio.normalize(), "f"),
            "label_trigger_basis": label_trigger_basis,
            "dry_run_min_win_rate": format(dry_run_min_win_rate.normalize(), "f"),
            "dry_run_max_turnover": format(dry_run_max_turnover.normalize(), "f"),
            "dry_run_min_sample_count": str(dry_run_min_sample_count),
            "validation_min_sample_count": str(validation_min_sample_count),
            "validation_min_avg_future_return_pct": format(validation_min_avg_future_return_pct.normalize(), "f"),
            "consistency_max_validation_backtest_return_gap_pct": format(consistency_max_validation_backtest_return_gap_pct.normalize(), "f"),
            "consistency_max_training_validation_positive_rate_gap": format(consistency_max_training_validation_positive_rate_gap.normalize(), "f"),
            "consistency_max_training_validation_return_gap_pct": format(consistency_max_training_validation_return_gap_pct.normalize(), "f"),
            "rule_min_ema20_gap_pct": format(rule_min_ema20_gap_pct.normalize(), "f"),
            "rule_min_ema55_gap_pct": format(rule_min_ema55_gap_pct.normalize(), "f"),
            "rule_max_atr_pct": format(rule_max_atr_pct.normalize(), "f"),
            "rule_min_volume_ratio": format(rule_min_volume_ratio.normalize(), "f"),
            "strict_rule_min_ema20_gap_pct": format(strict_rule_min_ema20_gap_pct.normalize(), "f"),
            "strict_rule_min_ema55_gap_pct": format(strict_rule_min_ema55_gap_pct.normalize(), "f"),
            "strict_rule_max_atr_pct": format(strict_rule_max_atr_pct.normalize(), "f"),
            "strict_rule_min_volume_ratio": format(strict_rule_min_volume_ratio.normalize(), "f"),
            "backtest_cost_model": backtest_cost_model,
            "enable_rule_gate": "true" if enable_rule_gate else "false",
            "enable_validation_gate": "true" if enable_validation_gate else "false",
            "enable_backtest_gate": "true" if enable_backtest_gate else "false",
            "enable_consistency_gate": "true" if enable_consistency_gate else "false",
            "enable_live_gate": "true" if enable_live_gate else "false",
            "enable_ml_live_gate": "true" if enable_ml_live_gate else "false",
            "live_min_ml_probability": format(live_min_ml_probability.normalize(), "f"),
            "live_min_win_rate": format(live_min_win_rate.normalize(), "f"),
            "live_max_turnover": format(live_max_turnover.normalize(), "f"),
            "live_min_sample_count": str(live_min_sample_count),
            "lookback_days": str(lookback_days),
            "window_mode": window_mode,
            "start_date": start_date,
            "end_date": end_date,
            "missing_policy": missing_policy,
            "signal_confidence_floor": format(signal_confidence_floor.normalize(), "f"),
            "trend_weight": format(trend_weight.normalize(), "f"),
            "momentum_weight": format(momentum_weight.normalize(), "f"),
            "volume_weight": format(volume_weight.normalize(), "f"),
            "oscillator_weight": format(oscillator_weight.normalize(), "f"),
            "volatility_weight": format(volatility_weight.normalize(), "f"),
            "strict_penalty_weight": format(strict_penalty_weight.normalize(), "f"),
            "model_type": model_type,
            "enable_ml_training": "true" if enable_ml_training else "false",
            "hyperopt_n_trials": str(hyperopt_n_trials),
        }
    )

    if require_explicit and not runtime_root_raw and not session_id:
        return _build_config(
            runtime_root=DEFAULT_RUNTIME_ROOT,
            status="unconfigured",
            detail="未设置 QUANT_QLIB_RUNTIME_ROOT 或 QUANT_QLIB_SESSION_ID，研究层当前只能返回明确状态，不能直接执行训练。",
            backtest_fee_bps=backtest_fee_bps,
            backtest_slippage_bps=backtest_slippage_bps,
            backtest_cost_model=backtest_cost_model,
            force_validation_top_candidate=force_validation_top_candidate,
            selected_symbols=selected_symbols,
            selected_timeframes=selected_timeframes,
            sample_limit=sample_limit,
            lookback_days=lookback_days,
            window_mode=window_mode,
            start_date=start_date,
            end_date=end_date,
            research_preset_key=research_preset_key,
            label_preset_key=label_preset_key,
            research_template=research_template,
            primary_feature_columns=primary_feature_columns,
            auxiliary_feature_columns=auxiliary_feature_columns,
            missing_policy=missing_policy,
            outlier_policy=outlier_policy,
            normalization_policy=normalization_policy,
            timeframe_profiles=timeframe_profiles,
            label_mode=label_mode,
            label_trigger_basis=label_trigger_basis,
            label_target_pct=label_target_pct,
            label_stop_pct=label_stop_pct,
            holding_window_min_days=holding_window_min_days,
            holding_window_max_days=holding_window_max_days,
            holding_window_label=holding_window_label,
            model_key=model_key,
            train_split_ratio=train_split_ratio,
            validation_split_ratio=validation_split_ratio,
            test_split_ratio=test_split_ratio,
            dry_run_min_score=dry_run_min_score,
            dry_run_min_positive_rate=dry_run_min_positive_rate,
            dry_run_min_net_return_pct=dry_run_min_net_return_pct,
            dry_run_min_sharpe=dry_run_min_sharpe,
            dry_run_max_drawdown_pct=dry_run_max_drawdown_pct,
            dry_run_max_loss_streak=dry_run_max_loss_streak,
            dry_run_min_win_rate=dry_run_min_win_rate,
            dry_run_max_turnover=dry_run_max_turnover,
            dry_run_min_sample_count=dry_run_min_sample_count,
            validation_min_sample_count=validation_min_sample_count,
            validation_min_avg_future_return_pct=validation_min_avg_future_return_pct,
            consistency_max_validation_backtest_return_gap_pct=consistency_max_validation_backtest_return_gap_pct,
            consistency_max_training_validation_positive_rate_gap=consistency_max_training_validation_positive_rate_gap,
            consistency_max_training_validation_return_gap_pct=consistency_max_training_validation_return_gap_pct,
            rule_min_ema20_gap_pct=rule_min_ema20_gap_pct,
            rule_min_ema55_gap_pct=rule_min_ema55_gap_pct,
            rule_max_atr_pct=rule_max_atr_pct,
            rule_min_volume_ratio=rule_min_volume_ratio,
            strict_rule_min_ema20_gap_pct=strict_rule_min_ema20_gap_pct,
            strict_rule_min_ema55_gap_pct=strict_rule_min_ema55_gap_pct,
            strict_rule_max_atr_pct=strict_rule_max_atr_pct,
            strict_rule_min_volume_ratio=strict_rule_min_volume_ratio,
            enable_rule_gate=enable_rule_gate,
            enable_validation_gate=enable_validation_gate,
            enable_backtest_gate=enable_backtest_gate,
            enable_consistency_gate=enable_consistency_gate,
            enable_live_gate=enable_live_gate,
            live_min_score=live_min_score,
            live_min_positive_rate=live_min_positive_rate,
            live_min_net_return_pct=live_min_net_return_pct,
            live_min_win_rate=live_min_win_rate,
            live_max_turnover=live_max_turnover,
            live_min_sample_count=live_min_sample_count,
            enable_ml_live_gate=enable_ml_live_gate,
            live_min_ml_probability=live_min_ml_probability,
            signal_confidence_floor=signal_confidence_floor,
            trend_weight=trend_weight,
            momentum_weight=momentum_weight,
            volume_weight=volume_weight,
            oscillator_weight=oscillator_weight,
            volatility_weight=volatility_weight,
            strict_penalty_weight=strict_penalty_weight,
            model_type=model_type,
            model_params=model_params,
            model_label_threshold=model_label_threshold,
            enable_ml_training=enable_ml_training,
            hyperopt_n_trials=hyperopt_n_trials,
            hyperopt_timeout_seconds=hyperopt_timeout_seconds,
        )

    if runtime_root_raw:
        runtime_root = Path(runtime_root_raw).expanduser()
    elif session_id:
        runtime_root = DEFAULT_RUNTIME_ROOT / session_id
    else:
        runtime_root = DEFAULT_RUNTIME_ROOT
    return _build_config(
        runtime_root=runtime_root,
        status="ready",
        detail=f"研究层目录已指向 {runtime_root}",
        backtest_fee_bps=backtest_fee_bps,
        backtest_slippage_bps=backtest_slippage_bps,
        backtest_cost_model=backtest_cost_model,
        force_validation_top_candidate=force_validation_top_candidate,
        selected_symbols=selected_symbols,
        selected_timeframes=selected_timeframes,
        sample_limit=sample_limit,
        lookback_days=lookback_days,
        window_mode=window_mode,
        start_date=start_date,
        end_date=end_date,
        research_preset_key=research_preset_key,
        label_preset_key=label_preset_key,
        research_template=research_template,
        primary_feature_columns=primary_feature_columns,
        auxiliary_feature_columns=auxiliary_feature_columns,
        missing_policy=missing_policy,
        outlier_policy=outlier_policy,
        normalization_policy=normalization_policy,
        timeframe_profiles=timeframe_profiles,
        label_mode=label_mode,
        label_trigger_basis=label_trigger_basis,
        label_target_pct=label_target_pct,
        label_stop_pct=label_stop_pct,
        holding_window_min_days=holding_window_min_days,
        holding_window_max_days=holding_window_max_days,
        holding_window_label=holding_window_label,
        model_key=model_key,
        train_split_ratio=train_split_ratio,
        validation_split_ratio=validation_split_ratio,
        test_split_ratio=test_split_ratio,
        dry_run_min_score=dry_run_min_score,
        dry_run_min_positive_rate=dry_run_min_positive_rate,
        dry_run_min_net_return_pct=dry_run_min_net_return_pct,
        dry_run_min_sharpe=dry_run_min_sharpe,
        dry_run_max_drawdown_pct=dry_run_max_drawdown_pct,
        dry_run_max_loss_streak=dry_run_max_loss_streak,
        dry_run_min_win_rate=dry_run_min_win_rate,
        dry_run_max_turnover=dry_run_max_turnover,
        dry_run_min_sample_count=dry_run_min_sample_count,
        validation_min_sample_count=validation_min_sample_count,
        validation_min_avg_future_return_pct=validation_min_avg_future_return_pct,
        consistency_max_validation_backtest_return_gap_pct=consistency_max_validation_backtest_return_gap_pct,
        consistency_max_training_validation_positive_rate_gap=consistency_max_training_validation_positive_rate_gap,
        consistency_max_training_validation_return_gap_pct=consistency_max_training_validation_return_gap_pct,
        rule_min_ema20_gap_pct=rule_min_ema20_gap_pct,
        rule_min_ema55_gap_pct=rule_min_ema55_gap_pct,
        rule_max_atr_pct=rule_max_atr_pct,
        rule_min_volume_ratio=rule_min_volume_ratio,
        strict_rule_min_ema20_gap_pct=strict_rule_min_ema20_gap_pct,
        strict_rule_min_ema55_gap_pct=strict_rule_min_ema55_gap_pct,
        strict_rule_max_atr_pct=strict_rule_max_atr_pct,
        strict_rule_min_volume_ratio=strict_rule_min_volume_ratio,
        enable_rule_gate=enable_rule_gate,
        enable_validation_gate=enable_validation_gate,
        enable_backtest_gate=enable_backtest_gate,
        enable_consistency_gate=enable_consistency_gate,
        enable_live_gate=enable_live_gate,
        live_min_score=live_min_score,
        live_min_positive_rate=live_min_positive_rate,
        live_min_net_return_pct=live_min_net_return_pct,
        live_min_win_rate=live_min_win_rate,
        live_max_turnover=live_max_turnover,
        live_min_sample_count=live_min_sample_count,
        signal_confidence_floor=signal_confidence_floor,
        trend_weight=trend_weight,
        momentum_weight=momentum_weight,
        volume_weight=volume_weight,
        oscillator_weight=oscillator_weight,
        volatility_weight=volatility_weight,
        strict_penalty_weight=strict_penalty_weight,
        model_type=model_type,
        model_params=model_params,
        model_label_threshold=model_label_threshold,
        enable_ml_training=enable_ml_training,
        hyperopt_n_trials=hyperopt_n_trials,
        hyperopt_timeout_seconds=hyperopt_timeout_seconds,
    )


def _build_config(
    runtime_root: Path,
    *,
    status: str,
    detail: str,
    backtest_fee_bps: Decimal,
    backtest_slippage_bps: Decimal,
    backtest_cost_model: str,
    force_validation_top_candidate: bool,
    selected_symbols: tuple[str, ...],
    selected_timeframes: tuple[str, ...],
    sample_limit: int,
    lookback_days: int,
    window_mode: str,
    start_date: str,
    end_date: str,
    research_preset_key: str,
    label_preset_key: str,
    research_template: str,
    primary_feature_columns: tuple[str, ...],
    auxiliary_feature_columns: tuple[str, ...],
    missing_policy: str,
    outlier_policy: str,
    normalization_policy: str,
    timeframe_profiles: dict[str, dict[str, int | str]],
    label_mode: str,
    label_trigger_basis: str,
    label_target_pct: Decimal,
    label_stop_pct: Decimal,
    holding_window_min_days: int,
    holding_window_max_days: int,
    holding_window_label: str,
    model_key: str,
    train_split_ratio: Decimal,
    validation_split_ratio: Decimal,
    test_split_ratio: Decimal,
    dry_run_min_score: Decimal,
    dry_run_min_positive_rate: Decimal,
    dry_run_min_net_return_pct: Decimal,
    dry_run_min_sharpe: Decimal,
    dry_run_max_drawdown_pct: Decimal,
    dry_run_max_loss_streak: int,
    dry_run_min_win_rate: Decimal,
    dry_run_max_turnover: Decimal,
    dry_run_min_sample_count: int,
    validation_min_sample_count: int,
    validation_min_avg_future_return_pct: Decimal,
    consistency_max_validation_backtest_return_gap_pct: Decimal,
    consistency_max_training_validation_positive_rate_gap: Decimal,
    consistency_max_training_validation_return_gap_pct: Decimal,
    rule_min_ema20_gap_pct: Decimal,
    rule_min_ema55_gap_pct: Decimal,
    rule_max_atr_pct: Decimal,
    rule_min_volume_ratio: Decimal,
    strict_rule_min_ema20_gap_pct: Decimal,
    strict_rule_min_ema55_gap_pct: Decimal,
    strict_rule_max_atr_pct: Decimal,
    strict_rule_min_volume_ratio: Decimal,
    enable_rule_gate: bool,
    enable_validation_gate: bool,
    enable_backtest_gate: bool,
    enable_consistency_gate: bool,
    enable_live_gate: bool,
    live_min_score: Decimal,
    live_min_positive_rate: Decimal,
    live_min_net_return_pct: Decimal,
    live_min_win_rate: Decimal,
    live_max_turnover: Decimal,
    live_min_sample_count: int,
    signal_confidence_floor: Decimal,
    trend_weight: Decimal,
    momentum_weight: Decimal,
    volume_weight: Decimal,
    oscillator_weight: Decimal,
    volatility_weight: Decimal,
    strict_penalty_weight: Decimal,
    model_type: str,
    model_params: dict[str, object],
    model_label_threshold: Decimal,
    enable_ml_training: bool,
    hyperopt_n_trials: int,
    hyperopt_timeout_seconds: int,
) -> QlibRuntimeConfig:
    """构造配置对象。"""

    qlib_available = importlib.util.find_spec("qlib") is not None
    backend = "qlib" if qlib_available else "qlib-fallback"
    paths = QlibRuntimePaths(
        runtime_root=runtime_root,
        dataset_dir=runtime_root / "dataset",
        dataset_snapshots_dir=runtime_root / "dataset" / "snapshots",
        dataset_cache_dir=runtime_root / "dataset" / "cache",
        artifacts_dir=runtime_root / "artifacts",
        runs_dir=runtime_root / "runs",
        latest_training_path=runtime_root / "latest_training.json",
        latest_inference_path=runtime_root / "latest_inference.json",
        latest_dataset_snapshot_path=runtime_root / "dataset" / "latest_dataset_snapshot.json",
        experiment_index_path=runtime_root / "runs" / "experiment_index.json",
        best_params_path=runtime_root / "best_params.json",
    )
    return QlibRuntimeConfig(
        status=status,
        detail=detail,
        backend=backend,
        qlib_available=qlib_available,
        backtest_fee_bps=backtest_fee_bps,
        backtest_slippage_bps=backtest_slippage_bps,
        backtest_cost_model=backtest_cost_model,
        force_validation_top_candidate=force_validation_top_candidate,
        research_data_layer="feature-ready",
        selected_symbols=selected_symbols,
        selected_timeframes=selected_timeframes,
        sample_limit=sample_limit,
        lookback_days=lookback_days,
        window_mode=window_mode,
        start_date=start_date,
        end_date=end_date,
        research_preset_key=research_preset_key,
        label_preset_key=label_preset_key,
        research_template=research_template,
        primary_feature_columns=primary_feature_columns,
        auxiliary_feature_columns=auxiliary_feature_columns,
        missing_policy=missing_policy,
        outlier_policy=outlier_policy,
        normalization_policy=normalization_policy,
        timeframe_profiles=timeframe_profiles,
        label_mode=label_mode,
        label_trigger_basis=label_trigger_basis,
        label_target_pct=label_target_pct,
        label_stop_pct=label_stop_pct,
        holding_window_min_days=holding_window_min_days,
        holding_window_max_days=holding_window_max_days,
        holding_window_label=holding_window_label,
        model_key=model_key,
        train_split_ratio=train_split_ratio,
        validation_split_ratio=validation_split_ratio,
        test_split_ratio=test_split_ratio,
        dry_run_min_score=dry_run_min_score,
        dry_run_min_positive_rate=dry_run_min_positive_rate,
        dry_run_min_net_return_pct=dry_run_min_net_return_pct,
        dry_run_min_sharpe=dry_run_min_sharpe,
        dry_run_max_drawdown_pct=dry_run_max_drawdown_pct,
        dry_run_max_loss_streak=dry_run_max_loss_streak,
        dry_run_min_win_rate=dry_run_min_win_rate,
        dry_run_max_turnover=dry_run_max_turnover,
        dry_run_min_sample_count=dry_run_min_sample_count,
        validation_min_sample_count=validation_min_sample_count,
        validation_min_avg_future_return_pct=validation_min_avg_future_return_pct,
        consistency_max_validation_backtest_return_gap_pct=consistency_max_validation_backtest_return_gap_pct,
        consistency_max_training_validation_positive_rate_gap=consistency_max_training_validation_positive_rate_gap,
        consistency_max_training_validation_return_gap_pct=consistency_max_training_validation_return_gap_pct,
        rule_min_ema20_gap_pct=rule_min_ema20_gap_pct,
        rule_min_ema55_gap_pct=rule_min_ema55_gap_pct,
        rule_max_atr_pct=rule_max_atr_pct,
        rule_min_volume_ratio=rule_min_volume_ratio,
        strict_rule_min_ema20_gap_pct=strict_rule_min_ema20_gap_pct,
        strict_rule_min_ema55_gap_pct=strict_rule_min_ema55_gap_pct,
        strict_rule_max_atr_pct=strict_rule_max_atr_pct,
        strict_rule_min_volume_ratio=strict_rule_min_volume_ratio,
        enable_rule_gate=enable_rule_gate,
        enable_validation_gate=enable_validation_gate,
        enable_backtest_gate=enable_backtest_gate,
        enable_consistency_gate=enable_consistency_gate,
        enable_live_gate=enable_live_gate,
        live_min_score=live_min_score,
        live_min_positive_rate=live_min_positive_rate,
        live_min_net_return_pct=live_min_net_return_pct,
        live_min_win_rate=live_min_win_rate,
        live_max_turnover=live_max_turnover,
        live_min_sample_count=live_min_sample_count,
        signal_confidence_floor=signal_confidence_floor,
        trend_weight=trend_weight,
        momentum_weight=momentum_weight,
        volume_weight=volume_weight,
        oscillator_weight=oscillator_weight,
        volatility_weight=volatility_weight,
        strict_penalty_weight=strict_penalty_weight,
        model_type=model_type,
        model_params=model_params,
        model_label_threshold=model_label_threshold,
        enable_ml_training=enable_ml_training,
        hyperopt_n_trials=hyperopt_n_trials,
        hyperopt_timeout_seconds=hyperopt_timeout_seconds,
        paths=paths,
    )


def _read_decimal(
    value: str | None,
    *,
    default: Decimal,
    env_name: str,
    minimum: Decimal | None = None,
    maximum: Decimal | None = None,
) -> Decimal:
    """读取回测配置里的十进制值。"""

    raw = str(value or "").strip()
    if not raw:
        return default
    try:
        parsed = Decimal(raw)
    except InvalidOperation as exc:
        raise ValueError(f"{env_name} 必须是数字") from exc
    if minimum is not None and parsed < minimum:
        raise ValueError(f"{env_name} 不能小于 {minimum}")
    if maximum is not None and parsed > maximum:
        raise ValueError(f"{env_name} 不能大于 {maximum}")
    return parsed


def _read_int(value: str | None, *, default: int, env_name: str, minimum: int = 0) -> int:
    """读取整型配置。"""

    raw = str(value or "").strip()
    if not raw:
        return default
    try:
        parsed = int(raw)
    except ValueError as exc:
        raise ValueError(f"{env_name} 必须是整数") from exc
    if parsed < minimum:
        raise ValueError(f"{env_name} 不能小于 {minimum}")
    return parsed


def _read_symbol_list(value: str | None) -> tuple[str, ...]:
    """读取标的列表。"""

    raw = str(value or "").strip()
    if not raw:
        return ()
    items: list[str] = []
    seen: set[str] = set()
    for item in raw.split(","):
        normalized = item.strip().upper()
        if not normalized:
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        items.append(normalized)
    return tuple(items)


def _read_research_template(value: str | None) -> str:
    """读取研究模板。"""

    normalized = str(value or "").strip() or DEFAULT_RESEARCH_TEMPLATE
    if normalized not in SUPPORTED_RESEARCH_TEMPLATES:
        return DEFAULT_RESEARCH_TEMPLATE
    return normalized


def _read_timeframe_list(value: str | None) -> tuple[str, ...]:
    """读取研究周期列表。"""

    if value is None:
        return ("4h", "1h")
    raw = str(value).strip()
    if not raw:
        return ()
    items = [item.strip() for item in raw.split(",") if item.strip() in {"1h", "4h"}]
    deduplicated: list[str] = []
    for item in items:
        if item not in deduplicated:
            deduplicated.append(item)
    return tuple(deduplicated)


def _read_name_list(value: str | None, *, default: tuple[str, ...]) -> tuple[str, ...]:
    """读取名字列表。"""

    if value is None:
        return default
    raw = str(value).strip()
    if not raw:
        return ()
    items: list[str] = []
    for item in raw.split(","):
        normalized = item.strip()
        if not normalized or normalized in items:
            continue
        items.append(normalized)
    return tuple(items)


def _read_choice(value: str | None, *, default: str, allowed: tuple[str, ...]) -> str:
    """读取枚举配置。"""

    normalized = str(value or "").strip()
    return normalized if normalized in allowed else default


def _read_timeframe_profiles(value: str | None) -> dict[str, dict[str, int | str]]:
    """读取周期参数覆盖。"""

    from services.worker.qlib_features import TIMEFRAME_PROFILES

    defaults = {
        str(interval): dict(profile)
        for interval, profile in TIMEFRAME_PROFILES.items()
    }
    raw = str(value or "").strip()
    if not raw:
        return defaults
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return defaults
    if not isinstance(payload, dict):
        return defaults

    normalized = {
        str(interval): dict(profile)
        for interval, profile in defaults.items()
    }
    for interval, profile in payload.items():
        if interval not in normalized or not isinstance(profile, dict):
            continue
        merged = dict(normalized[interval])
        for key, default in merged.items():
            candidate = profile.get(key, default)
            if isinstance(default, int):
                try:
                    merged[key] = max(1, int(candidate))
                except (TypeError, ValueError):
                    merged[key] = default
            else:
                text = str(candidate or default).strip()
                merged[key] = text or default
        normalized[interval] = merged
    return normalized


def _read_bool(value: str | None, *, default: bool) -> bool:
    """读取布尔配置。"""

    if value is None:
        return default
    normalized = str(value).strip().lower()
    if normalized in {"true", "1", "yes", "on"}:
        return True
    if normalized in {"false", "0", "no", "off"}:
        return False
    return default


def _read_date(value: str | None) -> str:
    """读取固定日期窗口。"""

    raw = str(value or "").strip()
    if not raw:
        return ""
    parts = raw.split("-")
    if len(parts) != 3:
        return ""
    year, month, day = parts
    if not (year.isdigit() and month.isdigit() and day.isdigit()):
        return ""
    return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"


def _publish_runtime_hints(values: dict[str, str]) -> None:
    """更新本进程可复用的运行时提示。"""

    _RUNTIME_HINTS.update({key: str(value) for key, value in values.items()})


def get_runtime_hint(name: str, default: str | None = None, *, consume: bool = False) -> str | None:
    """读取运行时提示。"""

    if consume:
        return _RUNTIME_HINTS.pop(name, default)
    return _RUNTIME_HINTS.get(name, default)


def _read_model_params(value: str | None, *, model_type: str) -> dict[str, object]:
    """读取模型参数。

    优先使用用户提供的 JSON 参数，否则返回对应模型类型的默认参数。
    """
    raw = str(value or "").strip()
    if raw:
        try:
            payload = json.loads(raw)
            if isinstance(payload, dict):
                return {str(k): v for k, v in payload.items()}
        except json.JSONDecodeError:
            pass

    # 返回默认参数
    if model_type == "lightgbm":
        return dict(DEFAULT_LIGHTGBM_PARAMS)
    elif model_type == "xgboost":
        return dict(DEFAULT_XGBOOST_PARAMS)
    return {}
