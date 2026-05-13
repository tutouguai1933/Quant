"""Qlib 候选排行与 dry-run 准入门。

这个文件负责把研究候选按分数排序，并判断是否允许进入 dry-run。
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from services.worker.qlib_config import get_runtime_hint


def rank_candidates(
    items: list[dict[str, object]],
    *,
    validation: dict[str, object] | None = None,
    training_metrics: dict[str, object] | None = None,
    force_validation_top_candidate: bool = False,
    research_template: str = "single_asset_timing",
    thresholds: dict[str, object] | None = None,
) -> dict[str, object]:
    """按分数输出统一候选排行。"""

    ranked = sorted(items, key=lambda item: _to_decimal(item.get("score")), reverse=True)
    normalized = [
        _normalize_candidate(
            item,
            index=index,
            validation=validation,
            training_metrics=training_metrics,
            research_template=research_template,
            thresholds=thresholds,
        )
        for index, item in enumerate(ranked, start=1)
    ]
    if force_validation_top_candidate:
        normalized = _apply_force_validation_override(normalized)
    normalized = _apply_recommendation_order(normalized)
    return {
        "items": normalized,
        "summary": {
            "candidate_count": len(normalized),
            "ready_count": sum(1 for item in normalized if item["allowed_to_dry_run"]),
            "live_ready_count": sum(1 for item in normalized if item["allowed_to_live"]),
            "blocked_count": sum(1 for item in normalized if not item["allowed_to_dry_run"]),
        },
    }


def _normalize_candidate(
    item: dict[str, object],
    *,
    index: int,
    validation: dict[str, object] | None,
    training_metrics: dict[str, object] | None,
    research_template: str,
    thresholds: dict[str, object] | None = None,
) -> dict[str, object]:
    """把单个候选统一成稳定结构。"""

    backtest = dict(item.get("backtest") or {})
    metrics = dict(backtest.get("metrics") or {})
    gate_thresholds = _resolve_thresholds(thresholds, research_template=research_template)
    rule_gate = _normalize_rule_gate(item.get("rule_gate"))
    score_gate = _evaluate_score_gate(score=item.get("score"), thresholds=gate_thresholds)
    research_validation_gate = _evaluate_validation_gate(validation, thresholds=gate_thresholds)
    backtest_gate = _evaluate_backtest_gate(metrics, thresholds=gate_thresholds)
    consistency_gate = _evaluate_consistency_gate(
        validation=validation,
        metrics=metrics,
        training_metrics=training_metrics,
        thresholds=gate_thresholds,
    )
    dry_run_gate = _merge_gates(
        score_gate,
        _apply_gate_toggle(rule_gate, enabled=_gate_enabled(gate_thresholds, "enable_rule_gate")),
        _apply_gate_toggle(research_validation_gate, enabled=_gate_enabled(gate_thresholds, "enable_validation_gate")),
        _apply_gate_toggle(backtest_gate, enabled=_gate_enabled(gate_thresholds, "enable_backtest_gate")),
        _apply_gate_toggle(consistency_gate, enabled=_gate_enabled(gate_thresholds, "enable_consistency_gate")),
    )
    allowed_to_dry_run = dry_run_gate["status"] == "passed"
    live_gate = _evaluate_live_gate(
        score=item.get("score"),
        validation=validation,
        metrics=metrics,
        thresholds=gate_thresholds,
        allowed_to_dry_run=allowed_to_dry_run,
    )
    if not _gate_enabled(gate_thresholds, "enable_live_gate") and allowed_to_dry_run:
        live_gate = {"status": "passed", "reasons": [], "disabled": True}
    allowed_to_live = live_gate["status"] == "passed"
    recommendation_context = _normalize_recommendation_context(item.get("recommendation_context"))
    recommendation_score = _build_recommendation_score(
        raw_score=_to_decimal(item.get("score")),
        metrics=metrics,
        validation=validation,
        training_metrics=training_metrics,
        recommendation_context=recommendation_context,
    )
    recommendation_reason = _build_recommendation_reason(
        recommendation_context=recommendation_context,
        allowed_to_dry_run=allowed_to_dry_run,
    )
    ml_prediction = item.get("ml_prediction")
    result = {
        "rank": index,
        "symbol": str(item.get("symbol", "")).strip().upper(),
        "strategy_template": str(item.get("strategy_template", "")).strip() or "trend_breakout_timing",
        "score": _format_decimal(_to_decimal(item.get("score"))),
        "backtest": {"metrics": metrics},
        "rule_gate": rule_gate,
        "score_gate": score_gate,
        "research_validation_gate": research_validation_gate,
        "backtest_gate": backtest_gate,
        "consistency_gate": consistency_gate,
        "dry_run_gate": dry_run_gate,
        "allowed_to_dry_run": allowed_to_dry_run,
        "live_gate": live_gate,
        "allowed_to_live": allowed_to_live,
        "forced_for_validation": False,
        "forced_reason": "",
        "review_status": "ready_for_dry_run" if allowed_to_dry_run else "needs_research_iteration",
        "next_action": "enter_dry_run" if allowed_to_dry_run else "continue_research",
        "execution_priority": 0 if allowed_to_dry_run else 100 + index,
        "recommendation_context": recommendation_context,
        "recommendation_score": _format_decimal(recommendation_score),
        "recommendation_reason": recommendation_reason,
    }
    if ml_prediction:
        result["ml_prediction"] = dict(ml_prediction)
    return result


def _apply_force_validation_override(items: list[dict[str, object]]) -> list[dict[str, object]]:
    """当正常候选全被拦下时，临时放行最优的一个验证全流程。"""

    if not items or any(bool(item.get("allowed_to_dry_run")) for item in items):
        return items
    overridden = [dict(item) for item in items]
    top_item = overridden[0]
    top_item["allowed_to_dry_run"] = True
    top_item["forced_for_validation"] = True
    top_item["forced_reason"] = "force_top_candidate_for_validation"
    top_item["review_status"] = "forced_validation"
    top_item["next_action"] = "enter_dry_run"
    top_item["execution_priority"] = 0
    top_item["allowed_to_live"] = False
    top_item["live_gate"] = {"status": "failed", "reasons": ["force_validation_dry_run_first"]}
    return overridden


def _apply_recommendation_order(items: list[dict[str, object]]) -> list[dict[str, object]]:
    """按推荐可信度重新整理排序和执行优先级。"""

    ordered = sorted(
        [dict(item) for item in items],
        key=lambda item: (
            0 if bool(item.get("allowed_to_dry_run")) else 1,
            -float(str(item.get("recommendation_score") or "0")),
            -float(str(item.get("score") or "0")),
            str(item.get("symbol", "")),
        ),
    )
    ready_rank = 0
    blocked_rank = 0
    for index, item in enumerate(ordered, start=1):
        item["rank"] = index
        if bool(item.get("allowed_to_dry_run")):
            item["execution_priority"] = ready_rank
            ready_rank += 1
        else:
            item["execution_priority"] = 100 + blocked_rank
            blocked_rank += 1
    return ordered


def _evaluate_backtest_gate(metrics: dict[str, object], *, thresholds: dict[str, Decimal | int]) -> dict[str, object]:
    """根据最小回测指标判断是否允许进入 dry-run。"""

    total_return_pct = _to_decimal(metrics.get("net_return_pct") or metrics.get("total_return_pct"))
    max_drawdown_pct = _to_decimal(metrics.get("max_drawdown_pct"))
    sharpe = _to_decimal(metrics.get("sharpe"))
    win_rate = _to_decimal(metrics.get("win_rate"))
    turnover = _to_decimal(metrics.get("turnover"))
    sample_count = _to_int_or_none(metrics.get("sample_count"))
    max_loss_streak = _to_int_or_none(metrics.get("max_loss_streak"))

    failures: list[str] = []
    if total_return_pct <= Decimal(str(thresholds["dry_run_min_net_return_pct"])):
        failures.append("non_positive_return")
    if max_drawdown_pct < -Decimal(str(thresholds["dry_run_max_drawdown_pct"])):
        failures.append("drawdown_too_large")
    if sharpe < Decimal(str(thresholds["dry_run_min_sharpe"])):
        failures.append("sharpe_too_low")
    if win_rate < Decimal(str(thresholds["dry_run_min_win_rate"])):
        failures.append("win_rate_too_low")
    if turnover > Decimal(str(thresholds["dry_run_max_turnover"])):
        failures.append("turnover_too_high")
    if sample_count is None or sample_count < int(thresholds["dry_run_min_sample_count"]):
        failures.append("sample_count_too_low")
    if max_loss_streak is not None and max_loss_streak > int(thresholds["dry_run_max_loss_streak"]):
        failures.append("loss_streak_too_long")

    if failures:
        return {"status": "failed", "reasons": failures}
    return {"status": "passed", "reasons": []}


def _evaluate_validation_gate(validation: dict[str, object] | None, *, thresholds: dict[str, Decimal | int]) -> dict[str, object]:
    """根据训练阶段验证摘要判断研究结果是否足够稳定。"""

    payload = dict(validation or {})
    if not payload:
        return {"status": "passed", "reasons": []}

    sample_count = _to_int_or_none(payload.get("sample_count"))
    positive_rate = _to_decimal(payload.get("positive_rate"))
    avg_future_return_pct = _to_decimal(payload.get("avg_future_return_pct"))

    failures: list[str] = []
    if sample_count is None or sample_count < int(thresholds["validation_min_sample_count"]):
        failures.append("validation_sample_count_too_low")
    if positive_rate < Decimal(str(thresholds["dry_run_min_positive_rate"])):
        failures.append("validation_positive_rate_too_low")
    if avg_future_return_pct < Decimal(str(thresholds["validation_min_avg_future_return_pct"])):
        failures.append("validation_future_return_not_positive")

    if failures:
        return {"status": "failed", "reasons": failures}
    return {"status": "passed", "reasons": []}


def _evaluate_score_gate(*, score: object, thresholds: dict[str, Decimal | int]) -> dict[str, object]:
    """根据最小分数门判断是否允许进入 dry-run。"""

    if _to_decimal(score) < Decimal(str(thresholds["dry_run_min_score"])):
        return {"status": "failed", "reasons": ["score_too_low"]}
    return {"status": "passed", "reasons": []}


def _evaluate_live_gate(
    *,
    score: object,
    validation: dict[str, object] | None,
    metrics: dict[str, object],
    thresholds: dict[str, Decimal | int],
    allowed_to_dry_run: bool,
) -> dict[str, object]:
    """根据更严格的 live 门判断是否允许进入小额 live。"""

    if not allowed_to_dry_run:
        return {"status": "failed", "reasons": ["dry_run_gate_not_passed"]}
    failures: list[str] = []
    if _to_decimal(score) < Decimal(str(thresholds["live_min_score"])):
        failures.append("live_score_too_low")
    positive_rate = _to_decimal(dict(validation or {}).get("positive_rate"))
    if positive_rate < Decimal(str(thresholds["live_min_positive_rate"])):
        failures.append("live_validation_positive_rate_too_low")
    net_return_pct = _to_decimal(metrics.get("net_return_pct") or metrics.get("total_return_pct"))
    if net_return_pct < Decimal(str(thresholds["live_min_net_return_pct"])):
        failures.append("live_net_return_too_low")
    win_rate = _to_decimal(metrics.get("win_rate"))
    if win_rate < Decimal(str(thresholds["live_min_win_rate"])):
        failures.append("live_win_rate_too_low")
    turnover = _to_decimal(metrics.get("turnover"))
    if turnover > Decimal(str(thresholds["live_max_turnover"])):
        failures.append("live_turnover_too_high")
    sample_count = _to_int_or_none(metrics.get("sample_count"))
    if sample_count is None or sample_count < int(thresholds["live_min_sample_count"]):
        failures.append("live_sample_count_too_low")
    if failures:
        return {"status": "failed", "reasons": failures}
    return {"status": "passed", "reasons": []}


def _evaluate_consistency_gate(
    *,
    validation: dict[str, object] | None,
    metrics: dict[str, object],
    training_metrics: dict[str, object] | None,
    thresholds: dict[str, Decimal | int],
) -> dict[str, object]:
    """判断验证摘要和净回测之间是否出现明显漂移。"""

    payload = dict(validation or {})
    if not payload:
        return {"status": "passed", "reasons": []}

    sample_count = _to_int_or_none(metrics.get("sample_count"))
    if sample_count is None or sample_count <= 0:
        return {"status": "passed", "reasons": []}

    validation_avg = _to_decimal(payload.get("avg_future_return_pct"))
    net_return_pct = _to_decimal(metrics.get("net_return_pct") or metrics.get("total_return_pct"))
    avg_net_return_pct = net_return_pct / Decimal(sample_count)

    failures: list[str] = []
    max_validation_backtest_gap = Decimal(str(thresholds["consistency_max_validation_backtest_return_gap_pct"]))
    max_training_validation_positive_rate_gap = Decimal(str(thresholds["consistency_max_training_validation_positive_rate_gap"]))
    max_training_validation_return_gap_pct = Decimal(str(thresholds["consistency_max_training_validation_return_gap_pct"]))

    if validation_avg > Decimal("0") and avg_net_return_pct <= Decimal("0"):
        failures.append("validation_backtest_drift_too_large")
    elif (validation_avg - avg_net_return_pct) > max_validation_backtest_gap:
        failures.append("validation_backtest_drift_too_large")
    training_payload = dict(training_metrics or {})
    training_positive_rate = _to_decimal(training_payload.get("positive_rate"))
    validation_positive_rate = _to_decimal(payload.get("positive_rate"))
    training_avg = _to_decimal(training_payload.get("avg_future_return_pct"))
    if training_payload:
        if (training_positive_rate - validation_positive_rate) > max_training_validation_positive_rate_gap:
            failures.append("validation_training_drift_too_large")
        if (training_avg - validation_avg) > max_training_validation_return_gap_pct:
            failures.append("validation_training_drift_too_large")

    if failures:
        return {"status": "failed", "reasons": failures}
    return {"status": "passed", "reasons": []}


def _normalize_recommendation_context(value: object) -> dict[str, str]:
    """统一推荐上下文结构。"""

    payload = dict(value or {}) if isinstance(value, dict) else {}
    return {
        "regime": str(payload.get("regime", "trend")).strip() or "trend",
        "indicator_mix": str(payload.get("indicator_mix", "")).strip(),
    }


def _build_recommendation_score(
    *,
    raw_score: Decimal,
    metrics: dict[str, object],
    validation: dict[str, object] | None,
    training_metrics: dict[str, object] | None,
    recommendation_context: dict[str, str],
) -> Decimal:
    """根据分数、验证、回测和市场状态生成更稳的推荐分。"""

    net_return_pct = _to_decimal(metrics.get("net_return_pct") or metrics.get("total_return_pct"))
    sharpe = _to_decimal(metrics.get("sharpe"))
    max_drawdown_pct = abs(_to_decimal(metrics.get("max_drawdown_pct")))
    validation_positive_rate = _to_decimal(dict(validation or {}).get("positive_rate"))
    training_positive_rate = _to_decimal(dict(training_metrics or {}).get("positive_rate"))
    recommendation_score = raw_score
    recommendation_score += net_return_pct / Decimal("100")
    recommendation_score += sharpe / Decimal("20")
    recommendation_score -= max_drawdown_pct / Decimal("100")
    recommendation_score += validation_positive_rate / Decimal("10")
    if training_positive_rate > Decimal("0") and validation_positive_rate > Decimal("0"):
        recommendation_score -= abs(training_positive_rate - validation_positive_rate) / Decimal("5")
    if recommendation_context.get("regime") == "trend":
        recommendation_score += Decimal("0.0500")
    return recommendation_score


def _build_recommendation_reason(
    *,
    recommendation_context: dict[str, str],
    allowed_to_dry_run: bool,
) -> str:
    """生成更稳的推荐说明。"""

    regime = recommendation_context.get("regime", "trend")
    indicator_mix = recommendation_context.get("indicator_mix", "") or "trend+momentum"
    if allowed_to_dry_run:
        return f"{regime} 行情下优先参考 {indicator_mix}"
    return f"{regime} 行情下 {indicator_mix} 仍需继续研究"


def _normalize_rule_gate(value: object) -> dict[str, object]:
    """把规则门结果统一成稳定结构。"""

    gate = dict(value or {}) if isinstance(value, dict) else {}
    raw_reasons = gate.get("reasons")
    if isinstance(raw_reasons, str):
        reasons = [raw_reasons.strip()] if raw_reasons.strip() else []
    else:
        reasons = [str(item).strip() for item in list(raw_reasons or []) if str(item).strip()]
    status = str(gate.get("status", "")).strip()
    if not status and reasons:
        status = "failed"
    if not status:
        status = "passed"
    result: dict[str, object] = {"status": status, "reasons": reasons or []}
    # 保留额外的特征值字段（如 volume_ratio, atr_pct 等）
    for key in ("volume_ratio", "threshold", "atr_pct", "ema20_gap_pct", "ema55_gap_pct"):
        if key in gate:
            result[key] = gate[key]
    if status != "passed" and not reasons:
        result["reasons"] = ["rule_gate_blocked"]
    return result


def _merge_gates(*gates: dict[str, object]) -> dict[str, object]:
    """把规则门和模型门合并成最终 dry-run 准入门。"""

    if all(gate.get("status") == "passed" for gate in gates):
        return {"status": "passed", "reasons": []}
    reasons: list[str] = []
    for gate in gates:
        reasons.extend(list(gate.get("reasons") or []))
    return {"status": "failed", "reasons": reasons}


def _apply_gate_toggle(gate: dict[str, object], *, enabled: bool) -> dict[str, object]:
    """按开关决定某个门是否参与阻断。"""

    if enabled:
        return gate
    passthrough = dict(gate)
    passthrough["status"] = "passed"
    passthrough["reasons"] = []
    passthrough["disabled"] = True
    return passthrough


def _resolve_thresholds(value: dict[str, object] | None, *, research_template: str = "single_asset_timing") -> dict[str, Decimal | int]:
    """整理 dry-run 和 live 门槛。"""

    payload = dict(value or {})
    resolved = {
        "dry_run_min_score": _to_decimal(payload.get("dry_run_min_score") or _runtime_decimal("dry_run_min_score", "0.55")),
        "dry_run_min_positive_rate": _to_decimal(payload.get("dry_run_min_positive_rate") or _runtime_decimal("dry_run_min_positive_rate", "0.45")),
        "dry_run_min_net_return_pct": _to_decimal(payload.get("dry_run_min_net_return_pct") or _runtime_decimal("dry_run_min_net_return_pct", "0")),
        "dry_run_min_sharpe": _to_decimal(payload.get("dry_run_min_sharpe") or _runtime_decimal("dry_run_min_sharpe", "0.5")),
        "dry_run_max_drawdown_pct": _to_decimal(payload.get("dry_run_max_drawdown_pct") or _runtime_decimal("dry_run_max_drawdown_pct", "15")),
        "dry_run_max_loss_streak": _to_int_or_none(payload.get("dry_run_max_loss_streak") or _runtime_int("dry_run_max_loss_streak", "3")) or 3,
        "dry_run_min_win_rate": _to_decimal(payload.get("dry_run_min_win_rate") or _runtime_decimal("dry_run_min_win_rate", "0.5")),
        "dry_run_max_turnover": _to_decimal(payload.get("dry_run_max_turnover") or _runtime_decimal("dry_run_max_turnover", "0.6")),
        "dry_run_min_sample_count": _to_int_or_none(payload.get("dry_run_min_sample_count") or _runtime_int("dry_run_min_sample_count", "20")) or 20,
        "validation_min_sample_count": _to_int_or_none(payload.get("validation_min_sample_count") or _runtime_int("validation_min_sample_count", "12")) or 12,
        "validation_min_avg_future_return_pct": _to_decimal(payload.get("validation_min_avg_future_return_pct") or _runtime_decimal("validation_min_avg_future_return_pct", "-0.1")),
        "consistency_max_validation_backtest_return_gap_pct": _to_decimal(payload.get("consistency_max_validation_backtest_return_gap_pct") or _runtime_decimal("consistency_max_validation_backtest_return_gap_pct", "1.5")),
        "consistency_max_training_validation_positive_rate_gap": _to_decimal(payload.get("consistency_max_training_validation_positive_rate_gap") or _runtime_decimal("consistency_max_training_validation_positive_rate_gap", "0.2")),
        "consistency_max_training_validation_return_gap_pct": _to_decimal(payload.get("consistency_max_training_validation_return_gap_pct") or _runtime_decimal("consistency_max_training_validation_return_gap_pct", "1.5")),
        "rule_min_ema20_gap_pct": _to_decimal(payload.get("rule_min_ema20_gap_pct") or _runtime_decimal("rule_min_ema20_gap_pct", "0")),
        "rule_min_ema55_gap_pct": _to_decimal(payload.get("rule_min_ema55_gap_pct") or _runtime_decimal("rule_min_ema55_gap_pct", "0")),
        "rule_max_atr_pct": _to_decimal(payload.get("rule_max_atr_pct") or _runtime_decimal("rule_max_atr_pct", "5")),
        "rule_min_volume_ratio": _to_decimal(payload.get("rule_min_volume_ratio") or _runtime_decimal("rule_min_volume_ratio", "0.8")),
        "enable_rule_gate": _to_bool(payload.get("enable_rule_gate"), _runtime_bool("enable_rule_gate", "true")),
        "enable_validation_gate": _to_bool(payload.get("enable_validation_gate"), _runtime_bool("enable_validation_gate", "true")),
        "enable_backtest_gate": _to_bool(payload.get("enable_backtest_gate"), _runtime_bool("enable_backtest_gate", "true")),
        "enable_consistency_gate": _to_bool(payload.get("enable_consistency_gate"), _runtime_bool("enable_consistency_gate", "true")),
        "enable_live_gate": _to_bool(payload.get("enable_live_gate"), _runtime_bool("enable_live_gate", "true")),
        "live_min_score": _to_decimal(payload.get("live_min_score") or _runtime_decimal("live_min_score", "0.65")),
        "live_min_positive_rate": _to_decimal(payload.get("live_min_positive_rate") or _runtime_decimal("live_min_positive_rate", "0.50")),
        "live_min_net_return_pct": _to_decimal(payload.get("live_min_net_return_pct") or _runtime_decimal("live_min_net_return_pct", "0.20")),
        "live_min_win_rate": _to_decimal(payload.get("live_min_win_rate") or _runtime_decimal("live_min_win_rate", "0.55")),
        "live_max_turnover": _to_decimal(payload.get("live_max_turnover") or _runtime_decimal("live_max_turnover", "0.45")),
        "live_min_sample_count": _to_int_or_none(payload.get("live_min_sample_count") or _runtime_int("live_min_sample_count", "24")) or 24,
    }
    if research_template == "single_asset_timing_strict":
        resolved["dry_run_min_score"] = min(Decimal("1"), resolved["dry_run_min_score"] + Decimal("0.05"))
        resolved["dry_run_min_positive_rate"] = min(Decimal("1"), resolved["dry_run_min_positive_rate"] + Decimal("0.05"))
        resolved["dry_run_min_sharpe"] = resolved["dry_run_min_sharpe"] + Decimal("0.10")
        resolved["dry_run_max_drawdown_pct"] = max(Decimal("5"), resolved["dry_run_max_drawdown_pct"] - Decimal("3"))
        resolved["dry_run_min_win_rate"] = min(Decimal("1"), resolved["dry_run_min_win_rate"] + Decimal("0.03"))
        resolved["dry_run_max_turnover"] = max(Decimal("0"), resolved["dry_run_max_turnover"] - Decimal("0.05"))
        resolved["dry_run_min_sample_count"] = int(resolved["dry_run_min_sample_count"]) + 4
        resolved["validation_min_sample_count"] = int(resolved["validation_min_sample_count"]) + 2
        resolved["live_min_score"] = min(Decimal("1"), resolved["live_min_score"] + Decimal("0.05"))
        resolved["live_min_positive_rate"] = min(Decimal("1"), resolved["live_min_positive_rate"] + Decimal("0.05"))
        resolved["live_min_net_return_pct"] = resolved["live_min_net_return_pct"] + Decimal("0.10")
        resolved["live_min_win_rate"] = min(Decimal("1"), resolved["live_min_win_rate"] + Decimal("0.03"))
        resolved["live_max_turnover"] = max(Decimal("0"), resolved["live_max_turnover"] - Decimal("0.05"))
        resolved["live_min_sample_count"] = int(resolved["live_min_sample_count"]) + 4
    return resolved


def _runtime_decimal(name: str, default: str) -> str:
    """读取运行时十进制提示。"""

    return str(get_runtime_hint(name, default) or default)


def _runtime_int(name: str, default: str) -> str:
    """读取运行时整型提示。"""

    return str(get_runtime_hint(name, default) or default)


def _runtime_bool(name: str, default: str) -> str:
    """读取运行时布尔提示。"""

    return str(get_runtime_hint(name, default) or default)


def _to_decimal(value: object) -> Decimal:
    """把输入统一转成十进制。"""

    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0")


def _to_int_or_none(value: object) -> int | None:
    """把输入转成整数，失败时返回 None。"""

    if value is None:
        return None
    try:
        return int(Decimal(str(value)))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _to_bool(value: object, default: str | bool = True) -> bool:
    """把输入统一转成布尔值。"""

    normalized = str(value if value is not None else default).strip().lower()
    if normalized in {"true", "1", "yes", "on"}:
        return True
    if normalized in {"false", "0", "no", "off"}:
        return False
    return bool(default)


def _gate_enabled(thresholds: dict[str, Decimal | int | bool], name: str) -> bool:
    """读取某个门当前是否开启。"""

    return _to_bool(thresholds.get(name), True)


def _format_decimal(value: Decimal) -> str:
    """把分数统一成字符串。"""

    return format(value.quantize(Decimal("0.0001")), "f")
