"""Quant 研究/执行工作台的共享配置读取。"""

from __future__ import annotations

import copy
import json
import os
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

DEFAULT_WORKBENCH_CONFIG_PATH = Path(".runtime/workbench_config.json")

DEFAULT_WORKBENCH_PAYLOAD = {
    "priority_tags": [
        {"key": "trend", "label": "趋势", "description": "趋势优先候选", "color": "#1E88E5"},
        {"key": "momentum", "label": "动量", "description": "高速突破/加速", "color": "#F4511E"},
        {"key": "volatility", "label": "波动", "description": "震荡内/低波动", "color": "#FB8C00"},
    ],
    "models": {
        "default": "qlib-minimal",
        "choices": [
            {
                "key": "qlib-minimal",
                "label": "稳定模型",
                "description": "主流水平，走 1-3 天择时",
            },
            {
                "key": "qlib-tighter",
                "label": "低回撤模型",
                "description": "更严格回测门控、适合 live 观察",
            },
        ],
    },
    "backtest": {
        "holding_window": "1-3d",
        "fee_bps": 10,
        "slippage_bps": 5,
        "max_drawdown_pct": -15,
        "min_sharpe": 0.5,
        "min_win_rate": 0.5,
        "max_turnover": 0.6,
        "min_sample_count": 20,
        "max_loss_streak": 3,
    },
    "thresholds": {
        "dry_run_min_positive_return_pct": 0,
        "dry_run_min_score": 0.5,
        "dry_run_min_confidence": 0.55,
        "live_min_successful_cycles": 1,
        "live_required_running_seconds": 600,
        "live_max_inflight_cycles": 2,
        "validation_min_sample_count": 12,
        "validation_min_positive_rate": 0.45,
        "validation_min_future_return_pct": -0.1,
        "validation_max_backtest_drift_pct": 1.5,
    },
    "automation": {
        "long_run_seconds": 300,
        "alert_cleanup_minutes": 15,
        "alert_levels": [
            {"level": "info", "title": "消息"},
            {"level": "warning", "title": "警告"},
            {"level": "critical", "title": "严重"},
        ],
    },
}


@dataclass(frozen=True)
class BacktestConfig:
    holding_window: str
    fee_bps: Decimal
    slippage_bps: Decimal
    max_drawdown_pct: Decimal
    min_sharpe: Decimal
    min_win_rate: Decimal
    max_turnover: Decimal
    min_sample_count: int
    max_loss_streak: int

    def to_dict(self) -> dict[str, object]:
        return {
            "holding_window": self.holding_window,
            "fee_bps": _format_decimal(self.fee_bps),
            "slippage_bps": _format_decimal(self.slippage_bps),
            "max_drawdown_pct": _format_decimal(self.max_drawdown_pct),
            "min_sharpe": _format_decimal(self.min_sharpe),
            "min_win_rate": _format_decimal(self.min_win_rate),
            "max_turnover": _format_decimal(self.max_turnover),
            "min_sample_count": self.min_sample_count,
            "max_loss_streak": self.max_loss_streak,
        }


@dataclass(frozen=True)
class ThresholdConfig:
    dry_run_min_positive_return_pct: Decimal
    dry_run_min_score: Decimal
    dry_run_min_confidence: Decimal
    live_min_successful_cycles: int
    live_required_running_seconds: int
    live_max_inflight_cycles: int
    validation_min_sample_count: int
    validation_min_positive_rate: Decimal
    validation_min_future_return_pct: Decimal
    validation_max_backtest_drift_pct: Decimal

    def to_dict(self) -> dict[str, object]:
        return {
            "dry_run_min_positive_return_pct": _format_decimal(self.dry_run_min_positive_return_pct),
            "dry_run_min_score": _format_decimal(self.dry_run_min_score),
            "dry_run_min_confidence": _format_decimal(self.dry_run_min_confidence),
            "live_min_successful_cycles": self.live_min_successful_cycles,
            "live_required_running_seconds": self.live_required_running_seconds,
            "live_max_inflight_cycles": self.live_max_inflight_cycles,
            "validation_min_sample_count": self.validation_min_sample_count,
            "validation_min_positive_rate": _format_decimal(self.validation_min_positive_rate),
            "validation_min_future_return_pct": _format_decimal(self.validation_min_future_return_pct),
            "validation_max_backtest_drift_pct": _format_decimal(self.validation_max_backtest_drift_pct),
        }


@dataclass(frozen=True)
class AutomationConfig:
    long_run_seconds: int
    alert_cleanup_minutes: int
    alert_levels: tuple[dict[str, str], ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "long_run_seconds": self.long_run_seconds,
            "alert_cleanup_minutes": self.alert_cleanup_minutes,
            "alert_levels": [dict(item) for item in self.alert_levels],
        }


@dataclass(frozen=True)
class WorkbenchConfig:
    priority_tags: tuple[dict[str, str], ...]
    model_choices: tuple[dict[str, str], ...]
    default_model: str
    backtest: BacktestConfig
    thresholds: ThresholdConfig
    automation: AutomationConfig

    def to_dict(self) -> dict[str, object]:
        return {
            "priority_tags": [dict(item) for item in self.priority_tags],
            "models": {
                "choices": [dict(item) for item in self.model_choices],
                "default": self.default_model,
            },
            "backtest": self.backtest.to_dict(),
            "thresholds": self.thresholds.to_dict(),
            "automation": self.automation.to_dict(),
        }

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "WorkbenchConfig":
        priority_tags = tuple(
            dict(item or {}) for item in payload.get("priority_tags") or DEFAULT_WORKBENCH_PAYLOAD["priority_tags"]
        )
        models_payload = payload.get("models") or DEFAULT_WORKBENCH_PAYLOAD["models"]
        default_choices = DEFAULT_WORKBENCH_PAYLOAD["models"]["choices"]
        model_choices_raw = models_payload.get("choices") or default_choices
        model_choices = tuple(dict(item or {}) for item in model_choices_raw)
        default_model = str(models_payload.get("default") or DEFAULT_WORKBENCH_PAYLOAD["models"]["default"])
        backtest_payload = payload.get("backtest") or DEFAULT_WORKBENCH_PAYLOAD["backtest"]
        thresholds_payload = payload.get("thresholds") or DEFAULT_WORKBENCH_PAYLOAD["thresholds"]
        automation_payload = payload.get("automation") or DEFAULT_WORKBENCH_PAYLOAD["automation"]

        backtest = BacktestConfig(
            holding_window=str(backtest_payload.get("holding_window") or DEFAULT_WORKBENCH_PAYLOAD["backtest"]["holding_window"]),
            fee_bps=_coerce_decimal(backtest_payload.get("fee_bps"), "backtest.fee_bps", Decimal("10")),
            slippage_bps=_coerce_decimal(backtest_payload.get("slippage_bps"), "backtest.slippage_bps", Decimal("5")),
            max_drawdown_pct=_coerce_decimal(backtest_payload.get("max_drawdown_pct"), "backtest.max_drawdown_pct", Decimal("-15")),
            min_sharpe=_coerce_decimal(backtest_payload.get("min_sharpe"), "backtest.min_sharpe", Decimal("0.5")),
            min_win_rate=_coerce_decimal(backtest_payload.get("min_win_rate"), "backtest.min_win_rate", Decimal("0.5")),
            max_turnover=_coerce_decimal(backtest_payload.get("max_turnover"), "backtest.max_turnover", Decimal("0.6")),
            min_sample_count=_coerce_int(backtest_payload.get("min_sample_count"), "backtest.min_sample_count", 20),
            max_loss_streak=_coerce_int(backtest_payload.get("max_loss_streak"), "backtest.max_loss_streak", 3),
        )
        thresholds = ThresholdConfig(
            dry_run_min_positive_return_pct=_coerce_decimal(
                thresholds_payload.get("dry_run_min_positive_return_pct"),
                "thresholds.dry_run_min_positive_return_pct",
                Decimal("0"),
            ),
            dry_run_min_score=_coerce_decimal(
                thresholds_payload.get("dry_run_min_score"),
                "thresholds.dry_run_min_score",
                Decimal("0.5"),
            ),
            dry_run_min_confidence=_coerce_decimal(
                thresholds_payload.get("dry_run_min_confidence"),
                "thresholds.dry_run_min_confidence",
                Decimal("0.55"),
            ),
            live_min_successful_cycles=_coerce_int(
                thresholds_payload.get("live_min_successful_cycles"),
                "thresholds.live_min_successful_cycles",
                1,
            ),
            live_required_running_seconds=_coerce_int(
                thresholds_payload.get("live_required_running_seconds"),
                "thresholds.live_required_running_seconds",
                600,
            ),
            live_max_inflight_cycles=_coerce_int(
                thresholds_payload.get("live_max_inflight_cycles"),
                "thresholds.live_max_inflight_cycles",
                2,
            ),
            validation_min_sample_count=_coerce_int(
                thresholds_payload.get("validation_min_sample_count"),
                "thresholds.validation_min_sample_count",
                12,
            ),
            validation_min_positive_rate=_coerce_decimal(
                thresholds_payload.get("validation_min_positive_rate"),
                "thresholds.validation_min_positive_rate",
                Decimal("0.45"),
            ),
            validation_min_future_return_pct=_coerce_decimal(
                thresholds_payload.get("validation_min_future_return_pct"),
                "thresholds.validation_min_future_return_pct",
                Decimal("-0.1"),
            ),
            validation_max_backtest_drift_pct=_coerce_decimal(
                thresholds_payload.get("validation_max_backtest_drift_pct"),
                "thresholds.validation_max_backtest_drift_pct",
                Decimal("1.5"),
            ),
        )
        automation = AutomationConfig(
            long_run_seconds=_coerce_int(
                automation_payload.get("long_run_seconds"),
                "automation.long_run_seconds",
                300,
            ),
            alert_cleanup_minutes=_coerce_int(
                automation_payload.get("alert_cleanup_minutes"),
                "automation.alert_cleanup_minutes",
                15,
            ),
            alert_levels=tuple(
                dict(item or {}) for item in automation_payload.get("alert_levels") or DEFAULT_WORKBENCH_PAYLOAD["automation"]["alert_levels"]
            ),
        )
        return cls(
            priority_tags=priority_tags,
            model_choices=model_choices,
            default_model=default_model,
            backtest=backtest,
            thresholds=thresholds,
            automation=automation,
        )


def load_workbench_config(
    env: dict[str, str] | None = None,
    *,
    config_path: Path | None = None,
) -> WorkbenchConfig:
    values = env if env is not None else dict(os.environ)
    config_file = Path(values.get("QUANT_WORKBENCH_CONFIG_PATH", "")) if values.get("QUANT_WORKBENCH_CONFIG_PATH") else config_path
    if config_file is None:
        config_file = DEFAULT_WORKBENCH_CONFIG_PATH
    payload = copy.deepcopy(DEFAULT_WORKBENCH_PAYLOAD)
    if config_file.exists():
        try:
            file_payload = json.loads(config_file.read_text(encoding="utf-8"))
            payload = _deep_merge(payload, file_payload)
        except json.JSONDecodeError:
            pass
    payload = _apply_env_overrides(payload, values)
    return WorkbenchConfig.from_payload(payload)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in base.items():
        if isinstance(value, dict):
            result[key] = copy.deepcopy(value)
        else:
            result[key] = value
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _apply_env_overrides(payload: dict[str, Any], env: dict[str, str]) -> dict[str, Any]:
    backtest = payload.setdefault("backtest", {})
    thresholds = payload.setdefault("thresholds", {})
    automation = payload.setdefault("automation", {})

    _set_if_env(backtest, "fee_bps", env.get("QUANT_QLIB_BACKTEST_FEE_BPS"))
    _set_if_env(backtest, "slippage_bps", env.get("QUANT_QLIB_BACKTEST_SLIPPAGE_BPS"))
    _set_if_env(backtest, "max_drawdown_pct", env.get("QUANT_WORKBENCH_BACKTEST_MAX_DRAWDOWN_PCT"))
    _set_if_env(backtest, "min_sharpe", env.get("QUANT_WORKBENCH_BACKTEST_MIN_SHARPE"))
    _set_if_env(backtest, "min_win_rate", env.get("QUANT_WORKBENCH_BACKTEST_MIN_WIN_RATE"))
    _set_if_env(backtest, "max_turnover", env.get("QUANT_WORKBENCH_BACKTEST_MAX_TURNOVER"))
    _set_if_env(backtest, "min_sample_count", env.get("QUANT_WORKBENCH_BACKTEST_MIN_SAMPLE_COUNT"))
    _set_if_env(backtest, "max_loss_streak", env.get("QUANT_WORKBENCH_BACKTEST_MAX_LOSS_STREAK"))
    _set_if_env(backtest, "holding_window", env.get("QUANT_WORKBENCH_BACKTEST_HOLDING_WINDOW"))

    _set_if_env(thresholds, "dry_run_min_positive_return_pct", env.get("QUANT_WORKBENCH_THRESHOLD_DRY_RUN_MIN_POSITIVE_RETURN_PCT"))
    _set_if_env(thresholds, "dry_run_min_score", env.get("QUANT_WORKBENCH_THRESHOLD_DRY_RUN_MIN_SCORE"))
    _set_if_env(thresholds, "dry_run_min_confidence", env.get("QUANT_WORKBENCH_THRESHOLD_DRY_RUN_MIN_CONFIDENCE"))
    _set_if_env(thresholds, "live_min_successful_cycles", env.get("QUANT_WORKBENCH_THRESHOLD_LIVE_MIN_CYCLES"))
    _set_if_env(thresholds, "live_required_running_seconds", env.get("QUANT_WORKBENCH_THRESHOLD_LIVE_REQUIRED_SECONDS"))
    _set_if_env(thresholds, "live_max_inflight_cycles", env.get("QUANT_WORKBENCH_THRESHOLD_LIVE_MAX_INFLIGHT"))
    _set_if_env(thresholds, "validation_min_sample_count", env.get("QUANT_WORKBENCH_VALIDATION_MIN_SAMPLE_COUNT"))
    _set_if_env(thresholds, "validation_min_positive_rate", env.get("QUANT_WORKBENCH_VALIDATION_MIN_POSITIVE_RATE"))
    _set_if_env(thresholds, "validation_min_future_return_pct", env.get("QUANT_WORKBENCH_VALIDATION_MIN_FUTURE_RETURN_PCT"))
    _set_if_env(thresholds, "validation_max_backtest_drift_pct", env.get("QUANT_WORKBENCH_VALIDATION_MAX_BACKTEST_DRIFT_PCT"))

    _set_if_env(automation, "long_run_seconds", env.get("QUANT_WORKBENCH_AUTOMATION_LONG_RUN_SECONDS"))
    _set_if_env(automation, "alert_cleanup_minutes", env.get("QUANT_WORKBENCH_AUTOMATION_ALERT_CLEANUP_MINUTES"))

    return payload


def _set_if_env(target: dict[str, Any], key: str, value: str | None) -> None:
    if value is None:
        return
    normalized = value.strip()
    if not normalized:
        return
    target[key] = normalized


def _coerce_decimal(value: Any, field_name: str, default: Decimal) -> Decimal:
    raw = value if value is not None else default
    try:
        return Decimal(str(raw))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"{field_name} 必须是可解析为数字的值")


def _coerce_int(value: Any, field_name: str, default: int) -> int:
    raw = value if value is not None else default
    try:
        parsed = int(str(raw))
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} 必须是整数")
    if parsed < 0:
        raise ValueError(f"{field_name} 必须不小于 0")
    return parsed


def _format_decimal(value: Decimal) -> str:
    return format(value.normalize(), "f")
