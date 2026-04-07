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

from services.api.app.core.settings import DEFAULT_MARKET_SYMBOLS
from services.worker.qlib_features import AUXILIARY_FEATURE_COLUMNS, FEATURE_PROTOCOL, PRIMARY_FEATURE_COLUMNS


REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_WORKBENCH_CONFIG_PATH = REPO_ROOT / ".runtime" / "workbench_config.json"
SUPPORTED_TIMEFRAMES = ("4h", "1h")
SUPPORTED_MODELS = ("heuristic_v1", "trend_bias_v2")
SUPPORTED_RESEARCH_TEMPLATES = ("single_asset_timing", "single_asset_timing_strict")
SUPPORTED_LABEL_MODES = ("earliest_hit", "close_only")
SUPPORTED_OUTLIER_POLICIES = ("clip", "raw")
SUPPORTED_NORMALIZATION_POLICIES = ("fixed_4dp", "zscore_by_symbol")
SUPPORTED_MISSING_POLICIES = ("neutral_fill", "strict_drop")
SUPPORTED_WINDOW_MODES = ("rolling", "fixed")


def _default_config() -> dict[str, object]:
    """返回默认配置。"""

    return {
        "version": "v1",
        "data": {
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
            "primary_factors": list(PRIMARY_FEATURE_COLUMNS),
            "auxiliary_factors": list(AUXILIARY_FEATURE_COLUMNS),
            "missing_policy": "neutral_fill",
            "outlier_policy": "clip",
            "normalization_policy": "fixed_4dp",
        },
        "research": {
            "research_template": "single_asset_timing",
            "model_key": "heuristic_v1",
            "label_mode": "earliest_hit",
            "holding_window_label": "1-3d",
            "min_holding_days": 1,
            "max_holding_days": 3,
            "label_target_pct": "1",
            "label_stop_pct": "-1",
            "train_split_ratio": "0.6",
            "validation_split_ratio": "0.2",
            "test_split_ratio": "0.2",
            "signal_confidence_floor": "0.55",
            "trend_weight": "1.3",
            "volume_weight": "1.1",
            "oscillator_weight": "0.7",
            "volatility_weight": "0.9",
            "strict_penalty_weight": "1",
        },
        "backtest": {
            "fee_bps": "10",
            "slippage_bps": "5",
        },
        "execution": {
            "live_allowed_symbols": list(DEFAULT_MARKET_SYMBOLS),
            "live_max_stake_usdt": "6",
            "live_max_open_trades": "1",
        },
        "thresholds": {
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
            "live_min_score": "0.65",
            "live_min_positive_rate": "0.50",
            "live_min_net_return_pct": "0.20",
            "live_min_win_rate": "0.55",
            "live_max_turnover": "0.45",
            "live_min_sample_count": "24",
        },
        "operations": {
            "pause_after_consecutive_failures": "2",
            "stale_sync_failure_threshold": "1",
            "auto_pause_on_error": True,
            "review_limit": "10",
            "cycle_cooldown_minutes": "15",
            "max_daily_cycle_count": "8",
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
        next_section = {**current_section, **dict(values or {})}

        if normalized_section == "data":
            merged["data"] = self._normalize_data_section(next_section)
        elif normalized_section == "features":
            merged["features"] = self._normalize_features_section(next_section)
        elif normalized_section == "research":
            merged["research"] = self._normalize_research_section(next_section)
        elif normalized_section == "backtest":
            merged["backtest"] = self._normalize_backtest_section(next_section)
        elif normalized_section == "execution":
            merged["execution"] = self._normalize_execution_section(next_section)
        elif normalized_section == "thresholds":
            merged["thresholds"] = self._normalize_thresholds_section(next_section)
        elif normalized_section == "operations":
            merged["operations"] = self._normalize_operations_section(next_section)
        else:
            raise ValueError("unsupported workbench config section")

        normalized = self._normalize_config(merged)
        self._write_config_file(normalized)
        return normalized

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
                "research_templates": list(SUPPORTED_RESEARCH_TEMPLATES),
                "label_modes": list(SUPPORTED_LABEL_MODES),
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
            "QUANT_QLIB_RESEARCH_TEMPLATE": str(research.get("research_template", "single_asset_timing")),
            "QUANT_QLIB_LABEL_MODE": str(research.get("label_mode", "earliest_hit")),
            "QUANT_QLIB_LABEL_TARGET_PCT": str(research.get("label_target_pct", "1")),
            "QUANT_QLIB_LABEL_STOP_PCT": str(research.get("label_stop_pct", "-1")),
            "QUANT_QLIB_HOLDING_WINDOW_MIN_DAYS": str(research.get("min_holding_days", 1)),
            "QUANT_QLIB_HOLDING_WINDOW_MAX_DAYS": str(research.get("max_holding_days", 3)),
            "QUANT_QLIB_HOLDING_WINDOW_LABEL": str(research.get("holding_window_label", "1-3d")),
            "QUANT_QLIB_MODEL_KEY": str(research.get("model_key", "heuristic_v1")),
            "QUANT_QLIB_TRAIN_SPLIT_RATIO": str(research.get("train_split_ratio", "0.6")),
            "QUANT_QLIB_VALIDATION_SPLIT_RATIO": str(research.get("validation_split_ratio", "0.2")),
            "QUANT_QLIB_TEST_SPLIT_RATIO": str(research.get("test_split_ratio", "0.2")),
            "QUANT_QLIB_SIGNAL_CONFIDENCE_FLOOR": str(research.get("signal_confidence_floor", "0.55")),
            "QUANT_QLIB_TREND_WEIGHT": str(research.get("trend_weight", "1.3")),
            "QUANT_QLIB_VOLUME_WEIGHT": str(research.get("volume_weight", "1.1")),
            "QUANT_QLIB_OSCILLATOR_WEIGHT": str(research.get("oscillator_weight", "0.7")),
            "QUANT_QLIB_VOLATILITY_WEIGHT": str(research.get("volatility_weight", "0.9")),
            "QUANT_QLIB_STRICT_PENALTY_WEIGHT": str(research.get("strict_penalty_weight", "1")),
            "QUANT_QLIB_BACKTEST_FEE_BPS": str(backtest.get("fee_bps", "10")),
            "QUANT_QLIB_BACKTEST_SLIPPAGE_BPS": str(backtest.get("slippage_bps", "5")),
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
        return {
            "version": "v1",
            "data": self._normalize_data_section(row.get("data")),
            "features": self._normalize_features_section(row.get("features")),
            "research": self._normalize_research_section(row.get("research")),
            "backtest": self._normalize_backtest_section(row.get("backtest")),
            "execution": self._normalize_execution_section(row.get("execution")),
            "thresholds": self._normalize_thresholds_section(row.get("thresholds")),
            "operations": self._normalize_operations_section(row.get("operations")),
        }

    def _normalize_data_section(self, value: object) -> dict[str, object]:
        """整理数据工作台配置。"""

        payload = dict(value or {}) if isinstance(value, dict) else {}
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
        }

    def _normalize_research_section(self, value: object) -> dict[str, object]:
        """整理研究工作台配置。"""

        payload = dict(value or {}) if isinstance(value, dict) else {}
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
        min_days = self._normalize_int(payload.get("min_holding_days"), default=1, minimum=1, maximum=7)
        max_days = self._normalize_int(payload.get("max_holding_days"), default=3, minimum=1, maximum=7)
        if min_days > max_days:
            min_days, max_days = max_days, min_days
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
            "research_template": research_template,
            "model_key": model_key,
            "label_mode": label_mode,
            "holding_window_label": f"{min_days}-{max_days}d",
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
        return {
            "fee_bps": self._normalize_decimal(payload.get("fee_bps"), default=Decimal("10"), minimum=Decimal("0")),
            "slippage_bps": self._normalize_decimal(payload.get("slippage_bps"), default=Decimal("5"), minimum=Decimal("0")),
        }

    def _normalize_execution_section(self, value: object) -> dict[str, object]:
        """整理执行安全门配置。"""

        payload = dict(value or {}) if isinstance(value, dict) else {}
        live_allowed_symbols = self._normalize_symbol_list(
            payload.get("live_allowed_symbols"),
            fallback=DEFAULT_MARKET_SYMBOLS,
            allow_empty=True,
        )
        return {
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
        return {
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
        return {
            "pause_after_consecutive_failures": str(
                self._normalize_int(payload.get("pause_after_consecutive_failures"), default=2, minimum=1, maximum=20)
            ),
            "stale_sync_failure_threshold": str(
                self._normalize_int(payload.get("stale_sync_failure_threshold"), default=1, minimum=1, maximum=20)
            ),
            "auto_pause_on_error": self._normalize_bool(payload.get("auto_pause_on_error"), default=True),
            "review_limit": str(self._normalize_int(payload.get("review_limit"), default=10, minimum=1, maximum=100)),
            "cycle_cooldown_minutes": str(
                self._normalize_int(payload.get("cycle_cooldown_minutes"), default=15, minimum=0, maximum=1440)
            ),
            "max_daily_cycle_count": str(
                self._normalize_int(payload.get("max_daily_cycle_count"), default=8, minimum=1, maximum=200)
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
