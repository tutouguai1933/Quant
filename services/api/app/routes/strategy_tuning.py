"""策略调优API路由。

提供策略参数调优状态查询和应用接口。
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from services.api.app.services.scoring.scoring_service import scoring_service
from services.api.app.services.dynamic_stoploss_service import dynamic_stoploss_service
from services.api.app.services.auth_service import auth_service

try:
    from fastapi import APIRouter, Header
except ImportError:
    class APIRouter:
        def __init__(self, *args, **kwargs) -> None:
            self.args = args
            self.kwargs = kwargs

        def get(self, *args, **kwargs):
            def decorator(func):
                return func
            return decorator

        def post(self, *args, **kwargs):
            def decorator(func):
                return func
            return decorator

    def Header(default: str = "") -> str:
        return default


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/strategy/tuning", tags=["strategy-tuning"])

CONFIG_PATH = Path(__file__).parent.parent.parent.parent / "data" / "config" / "strategy_tuning.json"


def _load_tuning_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {"error": "config_not_found", "message": "strategy_tuning.json not found"}
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning("加载调优配置失败: %s", e)
        return {"error": "load_failed", "message": str(e)}


def _save_tuning_config(data: dict[str, Any]) -> bool:
    try:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        logger.warning("保存调优配置失败: %s", e)
        return False


def _success(data: dict, meta: dict | None = None) -> dict:
    return {"data": data, "error": None, "meta": meta or {}}


def _error(code: str, message: str, meta: dict | None = None) -> dict:
    return {"data": None, "error": {"code": code, "message": message}, "meta": meta or {}}


def _unauthorized() -> dict:
    return _error("unauthorized", "authentication required", {"source": "control-plane-api"})


@router.get("/status")
def get_tuning_status() -> dict:
    """获取当前调优状态和参数配置。"""
    config = _load_tuning_config()
    if "error" in config:
        return _error(config["error"], config["message"])

    current_scoring = scoring_service.get_config()
    current_stoploss = dynamic_stoploss_service.get_config()

    return _success(
        {
            "tuning_config": config,
            "current_scoring": current_scoring,
            "current_stoploss": current_stoploss,
            "pending_changes": _compute_pending_changes(config, current_scoring, current_stoploss),
        },
        {
            "source": "control-plane-api",
            "config_path": str(CONFIG_PATH),
            "tuning_status": config.get("tuning_status", "unknown"),
        },
    )


def _compute_pending_changes(
    tuning: dict,
    scoring: dict,
    stoploss: dict,
) -> list[dict[str, Any]]:
    """计算待应用的变更。"""
    changes = []

    params = tuning.get("parameters", {})

    min_entry = params.get("min_entry_score", {})
    recommended_score = min_entry.get("recommended")
    current_score = scoring.get("min_entry_score")
    if recommended_score and current_score != recommended_score:
        changes.append({
            "field": "min_entry_score",
            "current": current_score,
            "recommended": recommended_score,
            "reason": min_entry.get("reason", ""),
        })

    weights = params.get("factor_weights", {})
    recommended_weights = weights.get("recommended", {})
    current_weights = scoring.get("factor_weights", {})
    for factor, rec_weight in recommended_weights.items():
        cur_weight = current_weights.get(factor)
        if cur_weight and cur_weight != rec_weight:
            changes.append({
                "field": f"factor_weight.{factor}",
                "current": cur_weight,
                "recommended": rec_weight,
            })

    sl_params = params.get("stoploss", {})
    recommended_sl = sl_params.get("recommended", {})
    for key in ["base_stoploss", "min_stoploss", "max_stoploss"]:
        rec_val = recommended_sl.get(key)
        cur_val = stoploss.get(key)
        if rec_val and cur_val and cur_val != str(rec_val):
            changes.append({
                "field": f"stoploss.{key}",
                "current": cur_val,
                "recommended": str(rec_val),
            })

    return changes


@router.post("/apply")
def apply_tuning_params(
    payload: dict[str, Any],
    token: str = "",
    authorization: str = Header(""),
) -> dict:
    """应用调优参数。

    需要认证。可选择性应用部分参数。
    """
    try:
        auth_service.require_control_plane_access(
            auth_service.resolve_access_token(token, authorization)
        )
    except PermissionError:
        return _unauthorized()

    config = _load_tuning_config()
    if "error" in config:
        return _error(config["error"], config["message"])

    apply_all = payload.get("apply_all", True)
    specific_params = payload.get("params", [])
    dry_run = payload.get("dry_run", False)

    applied = []
    errors = []

    params = config.get("parameters", {})

    if apply_all or "min_entry_score" in specific_params:
        min_entry = params.get("min_entry_score", {})
        recommended = min_entry.get("recommended")
        if recommended:
            if dry_run:
                applied.append({"param": "min_entry_score", "value": recommended, "dry_run": True})
            else:
                success = scoring_service.set_min_entry_score(recommended)
                if success:
                    applied.append({"param": "min_entry_score", "value": recommended})
                else:
                    errors.append({"param": "min_entry_score", "error": "update_failed"})

    if apply_all or "factor_weights" in specific_params:
        weights = params.get("factor_weights", {})
        recommended_weights = weights.get("recommended", {})
        if recommended_weights:
            if dry_run:
                applied.append({"param": "factor_weights", "value": recommended_weights, "dry_run": True})
            else:
                success = scoring_service.set_factor_weights(recommended_weights)
                if success:
                    applied.append({"param": "factor_weights", "value": recommended_weights})
                else:
                    errors.append({"param": "factor_weights", "error": "update_failed"})

    if apply_all or "stoploss" in specific_params:
        sl_params = params.get("stoploss", {})
        recommended_sl = sl_params.get("recommended", {})
        if recommended_sl:
            if dry_run:
                applied.append({"param": "stoploss", "value": recommended_sl, "dry_run": True})
            else:
                try:
                    updated = dynamic_stoploss_service.update_config(recommended_sl)
                    applied.append({"param": "stoploss", "value": updated})
                except Exception as e:
                    errors.append({"param": "stoploss", "error": str(e)})

    if not dry_run and applied:
        config["tuning_status"] = "applied"
        config["last_updated"] = datetime.now(timezone.utc).isoformat()
        config["applied_history"] = config.get("applied_history", [])
        config["applied_history"].append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "applied": applied,
        })
        _save_tuning_config(config)

    return _success(
        {
            "applied": applied,
            "errors": errors,
            "dry_run": dry_run,
            "total_applied": len(applied),
            "total_errors": len(errors),
        },
        {
            "source": "control-plane-api",
            "action": "apply_tuning",
            "apply_all": apply_all,
        },
    )


@router.post("/reset")
def reset_tuning_params(
    payload: dict[str, Any],
    token: str = "",
    authorization: str = Header(""),
) -> dict:
    """重置参数为当前配置值（取消推荐值）。"""
    try:
        auth_service.require_control_plane_access(
            auth_service.resolve_access_token(token, authorization)
        )
    except PermissionError:
        return _unauthorized()

    config = _load_tuning_config()
    if "error" in config:
        return _error(config["error"], config["message"])

    params = config.get("parameters", {})

    reset_to = payload.get("reset_to", "current")

    if reset_to == "current":
        min_entry = params.get("min_entry_score", {})
        current_score = min_entry.get("current", 0.60)
        scoring_service.set_min_entry_score(current_score)

        weights = params.get("factor_weights", {})
        current_weights = weights.get("current", {})
        if current_weights:
            scoring_service.set_factor_weights(current_weights)

        sl_params = params.get("stoploss", {})
        current_sl = sl_params.get("current", {})
        if current_sl:
            dynamic_stoploss_service.update_config(current_sl)

    config["tuning_status"] = "ready"
    config["last_updated"] = datetime.now(timezone.utc).isoformat()
    _save_tuning_config(config)

    return _success(
        {"reset": True, "reset_to": reset_to},
        {"source": "control-plane-api", "action": "reset_tuning"},
    )


@router.get("/recommendations")
def get_recommendations(market_condition: str = "") -> dict:
    """获取市场条件相关的调优建议。"""
    config = _load_tuning_config()
    if "error" in config:
        return _error(config["error"], config["message"])

    params = config.get("parameters", {})
    adjustments = config.get("market_condition_adjustments", {})

    recommendations = {
        "base": {
            "min_entry_score": params.get("min_entry_score", {}).get("recommended"),
            "factor_weights": params.get("factor_weights", {}).get("recommended"),
            "stoploss": params.get("stoploss", {}).get("recommended"),
        },
    }

    if market_condition and market_condition in adjustments:
        condition_adj = adjustments[market_condition]
        recommendations["market_adjustment"] = condition_adj

        adjusted_score = recommendations["base"]["min_entry_score"]
        if adjusted_score and "min_entry_score_adjustment" in condition_adj:
            adjusted_score += condition_adj["min_entry_score_adjustment"]
            recommendations["adjusted"] = {
                "min_entry_score": adjusted_score,
            }

    return _success(
        recommendations,
        {
            "source": "control-plane-api",
            "market_condition": market_condition,
            "available_conditions": list(adjustments.keys()),
        },
    )


@router.get("/validation")
def get_validation_criteria() -> dict:
    """获取回测验证标准。"""
    config = _load_tuning_config()
    if "error" in config:
        return _error(config["error"], config["message"])

    validation = config.get("backtest_validation", {})

    return _success(
        {"validation_criteria": validation},
        {
            "source": "control-plane-api",
            "validation_required": True,
        },
    )


@router.post("/update")
def update_tuning_config(
    payload: dict[str, Any],
    token: str = "",
    authorization: str = Header(""),
) -> dict:
    """更新调优配置文件中的推荐值。"""
    try:
        auth_service.require_control_plane_access(
            auth_service.resolve_access_token(token, authorization)
        )
    except PermissionError:
        return _unauthorized()

    config = _load_tuning_config()
    if "error" in config:
        return _error(config["error"], config["message"])

    updates = payload.get("updates", {})
    if not updates:
        return _error("invalid_request", "updates are required")

    params = config.get("parameters", {})

    if "min_entry_score" in updates:
        score_params = params.get("min_entry_score", {})
        score_params["recommended"] = updates["min_entry_score"]
        params["min_entry_score"] = score_params

    if "factor_weights" in updates:
        weights_params = params.get("factor_weights", {})
        weights_params["recommended"] = updates["factor_weights"]
        params["factor_weights"] = weights_params

    if "stoploss" in updates:
        sl_params = params.get("stoploss", {})
        sl_params["recommended"] = updates["stoploss"]
        params["stoploss"] = sl_params

    config["parameters"] = params
    config["last_updated"] = datetime.now(timezone.utc).isoformat()
    config["tuning_status"] = "modified"

    success = _save_tuning_config(config)
    if not success:
        return _error("save_failed", "failed to save tuning config")

    return _success(
        {"updated": True, "updates": updates},
        {"source": "control-plane-api", "action": "update_tuning_config"},
    )