"""Qlib 研究层配置。

这个文件负责统一读取研究层运行目录，并给出清晰的可执行状态。
"""

from __future__ import annotations

import importlib.util
import os
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

from services.worker.qlib_features import AUXILIARY_FEATURE_COLUMNS, PRIMARY_FEATURE_COLUMNS


DEFAULT_RUNTIME_ROOT = Path("/tmp/quant-qlib-runtime")
DEFAULT_BACKTEST_FEE_BPS = Decimal("10")
DEFAULT_BACKTEST_SLIPPAGE_BPS = Decimal("5")
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
DEFAULT_LIVE_MIN_SCORE = Decimal("0.65")
DEFAULT_LIVE_MIN_POSITIVE_RATE = Decimal("0.50")
DEFAULT_LIVE_MIN_NET_RETURN_PCT = Decimal("0.20")
DEFAULT_LIVE_MIN_WIN_RATE = Decimal("0.55")
DEFAULT_LIVE_MAX_TURNOVER = Decimal("0.45")
DEFAULT_LIVE_MIN_SAMPLE_COUNT = 24
DEFAULT_RESEARCH_TEMPLATE = "single_asset_timing"
DEFAULT_LABEL_MODE = "earliest_hit"
DEFAULT_OUTLIER_POLICY = "clip"
DEFAULT_NORMALIZATION_POLICY = "fixed_4dp"
SUPPORTED_RESEARCH_TEMPLATES = ("single_asset_timing", "single_asset_timing_strict")
SUPPORTED_LABEL_MODES = ("earliest_hit", "close_only")
SUPPORTED_OUTLIER_POLICIES = ("clip", "raw")
SUPPORTED_NORMALIZATION_POLICIES = ("fixed_4dp", "zscore_by_symbol")
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


@dataclass(frozen=True)
class QlibRuntimeConfig:
    """研究层配置快照。"""

    status: str
    detail: str
    backend: str
    qlib_available: bool
    backtest_fee_bps: Decimal
    backtest_slippage_bps: Decimal
    force_validation_top_candidate: bool
    research_data_layer: str
    selected_symbols: tuple[str, ...]
    selected_timeframes: tuple[str, ...]
    sample_limit: int
    lookback_days: int
    research_template: str
    primary_feature_columns: tuple[str, ...]
    auxiliary_feature_columns: tuple[str, ...]
    outlier_policy: str
    normalization_policy: str
    label_mode: str
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
    live_min_score: Decimal
    live_min_positive_rate: Decimal
    live_min_net_return_pct: Decimal
    live_min_win_rate: Decimal
    live_max_turnover: Decimal
    live_min_sample_count: int
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
    force_validation_top_candidate = str(values.get("QUANT_QLIB_FORCE_TOP_CANDIDATE", "")).strip().lower() == "true"
    selected_symbols = _read_symbol_list(values.get("QUANT_QLIB_SELECTED_SYMBOLS"))
    selected_timeframes = _read_timeframe_list(values.get("QUANT_QLIB_TIMEFRAMES"))
    sample_limit = _read_int(values.get("QUANT_QLIB_SAMPLE_LIMIT"), default=120, env_name="QUANT_QLIB_SAMPLE_LIMIT", minimum=60)
    lookback_days = _read_int(values.get("QUANT_QLIB_LOOKBACK_DAYS"), default=DEFAULT_LOOKBACK_DAYS, env_name="QUANT_QLIB_LOOKBACK_DAYS", minimum=7)
    research_template = _read_research_template(values.get("QUANT_QLIB_RESEARCH_TEMPLATE"))
    primary_feature_columns = _read_name_list(
        values.get("QUANT_QLIB_PRIMARY_FACTORS"),
        default=PRIMARY_FEATURE_COLUMNS,
    )
    auxiliary_feature_columns = _read_name_list(
        values.get("QUANT_QLIB_AUXILIARY_FACTORS"),
        default=AUXILIARY_FEATURE_COLUMNS,
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
    label_mode = _read_choice(
        values.get("QUANT_QLIB_LABEL_MODE"),
        default=DEFAULT_LABEL_MODE,
        allowed=SUPPORTED_LABEL_MODES,
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

    _publish_runtime_hints(
        {
            "train_split_ratio": format(train_split_ratio.normalize(), "f"),
            "validation_split_ratio": format(validation_split_ratio.normalize(), "f"),
            "test_split_ratio": format(test_split_ratio.normalize(), "f"),
            "dry_run_min_win_rate": format(dry_run_min_win_rate.normalize(), "f"),
            "dry_run_max_turnover": format(dry_run_max_turnover.normalize(), "f"),
            "dry_run_min_sample_count": str(dry_run_min_sample_count),
            "validation_min_sample_count": str(validation_min_sample_count),
            "live_min_win_rate": format(live_min_win_rate.normalize(), "f"),
            "live_max_turnover": format(live_max_turnover.normalize(), "f"),
            "live_min_sample_count": str(live_min_sample_count),
            "lookback_days": str(lookback_days),
        }
    )

    if require_explicit and not runtime_root_raw and not session_id:
        return _build_config(
            runtime_root=DEFAULT_RUNTIME_ROOT,
            status="unconfigured",
            detail="未设置 QUANT_QLIB_RUNTIME_ROOT 或 QUANT_QLIB_SESSION_ID，研究层当前只能返回明确状态，不能直接执行训练。",
            backtest_fee_bps=backtest_fee_bps,
            backtest_slippage_bps=backtest_slippage_bps,
            force_validation_top_candidate=force_validation_top_candidate,
            selected_symbols=selected_symbols,
            selected_timeframes=selected_timeframes,
            sample_limit=sample_limit,
            lookback_days=lookback_days,
            research_template=research_template,
            primary_feature_columns=primary_feature_columns,
            auxiliary_feature_columns=auxiliary_feature_columns,
            outlier_policy=outlier_policy,
            normalization_policy=normalization_policy,
            label_mode=label_mode,
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
            live_min_score=live_min_score,
            live_min_positive_rate=live_min_positive_rate,
            live_min_net_return_pct=live_min_net_return_pct,
            live_min_win_rate=live_min_win_rate,
            live_max_turnover=live_max_turnover,
            live_min_sample_count=live_min_sample_count,
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
        force_validation_top_candidate=force_validation_top_candidate,
        selected_symbols=selected_symbols,
        selected_timeframes=selected_timeframes,
        sample_limit=sample_limit,
        lookback_days=lookback_days,
        research_template=research_template,
        primary_feature_columns=primary_feature_columns,
        auxiliary_feature_columns=auxiliary_feature_columns,
        outlier_policy=outlier_policy,
        normalization_policy=normalization_policy,
        label_mode=label_mode,
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
        live_min_score=live_min_score,
        live_min_positive_rate=live_min_positive_rate,
        live_min_net_return_pct=live_min_net_return_pct,
        live_min_win_rate=live_min_win_rate,
        live_max_turnover=live_max_turnover,
        live_min_sample_count=live_min_sample_count,
    )


def _build_config(
    runtime_root: Path,
    *,
    status: str,
    detail: str,
    backtest_fee_bps: Decimal,
    backtest_slippage_bps: Decimal,
    force_validation_top_candidate: bool,
    selected_symbols: tuple[str, ...],
    selected_timeframes: tuple[str, ...],
    sample_limit: int,
    lookback_days: int,
    research_template: str,
    primary_feature_columns: tuple[str, ...],
    auxiliary_feature_columns: tuple[str, ...],
    outlier_policy: str,
    normalization_policy: str,
    label_mode: str,
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
    live_min_score: Decimal,
    live_min_positive_rate: Decimal,
    live_min_net_return_pct: Decimal,
    live_min_win_rate: Decimal,
    live_max_turnover: Decimal,
    live_min_sample_count: int,
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
    )
    return QlibRuntimeConfig(
        status=status,
        detail=detail,
        backend=backend,
        qlib_available=qlib_available,
        backtest_fee_bps=backtest_fee_bps,
        backtest_slippage_bps=backtest_slippage_bps,
        force_validation_top_candidate=force_validation_top_candidate,
        research_data_layer="feature-ready",
        selected_symbols=selected_symbols,
        selected_timeframes=selected_timeframes,
        sample_limit=sample_limit,
        lookback_days=lookback_days,
        research_template=research_template,
        primary_feature_columns=primary_feature_columns,
        auxiliary_feature_columns=auxiliary_feature_columns,
        outlier_policy=outlier_policy,
        normalization_policy=normalization_policy,
        label_mode=label_mode,
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
        live_min_score=live_min_score,
        live_min_positive_rate=live_min_positive_rate,
        live_min_net_return_pct=live_min_net_return_pct,
        live_min_win_rate=live_min_win_rate,
        live_max_turnover=live_max_turnover,
        live_min_sample_count=live_min_sample_count,
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


def _publish_runtime_hints(values: dict[str, str]) -> None:
    """更新本进程可复用的运行时提示。"""

    _RUNTIME_HINTS.update({key: str(value) for key, value in values.items()})


def get_runtime_hint(name: str, default: str | None = None, *, consume: bool = False) -> str | None:
    """读取运行时提示。"""

    if consume:
        return _RUNTIME_HINTS.pop(name, default)
    return _RUNTIME_HINTS.get(name, default)
