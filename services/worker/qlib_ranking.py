"""Qlib 候选排行与 dry-run 准入门。

这个文件负责把研究候选按分数排序，并判断是否允许进入 dry-run。
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation


def rank_candidates(
    items: list[dict[str, object]],
    *,
    validation: dict[str, object] | None = None,
    force_validation_top_candidate: bool = False,
) -> dict[str, object]:
    """按分数输出统一候选排行。"""

    ranked = sorted(items, key=lambda item: _to_decimal(item.get("score")), reverse=True)
    normalized = [
        _normalize_candidate(item, index=index, validation=validation)
        for index, item in enumerate(ranked, start=1)
    ]
    if force_validation_top_candidate:
        normalized = _apply_force_validation_override(normalized)
    return {
        "items": normalized,
        "summary": {
            "candidate_count": len(normalized),
            "ready_count": sum(1 for item in normalized if item["allowed_to_dry_run"]),
            "blocked_count": sum(1 for item in normalized if not item["allowed_to_dry_run"]),
        },
    }


def _normalize_candidate(
    item: dict[str, object],
    *,
    index: int,
    validation: dict[str, object] | None,
) -> dict[str, object]:
    """把单个候选统一成稳定结构。"""

    backtest = dict(item.get("backtest") or {})
    metrics = dict(backtest.get("metrics") or {})
    rule_gate = _normalize_rule_gate(item.get("rule_gate"))
    research_validation_gate = _evaluate_validation_gate(validation)
    backtest_gate = _evaluate_backtest_gate(metrics)
    consistency_gate = _evaluate_consistency_gate(validation=validation, metrics=metrics)
    dry_run_gate = _merge_gates(rule_gate, research_validation_gate, backtest_gate, consistency_gate)
    allowed_to_dry_run = dry_run_gate["status"] == "passed"
    return {
        "rank": index,
        "symbol": str(item.get("symbol", "")).strip().upper(),
        "strategy_template": str(item.get("strategy_template", "")).strip() or "trend_breakout_timing",
        "score": _format_decimal(_to_decimal(item.get("score"))),
        "backtest": {"metrics": metrics},
        "rule_gate": rule_gate,
        "research_validation_gate": research_validation_gate,
        "backtest_gate": backtest_gate,
        "consistency_gate": consistency_gate,
        "dry_run_gate": dry_run_gate,
        "allowed_to_dry_run": allowed_to_dry_run,
        "forced_for_validation": False,
        "forced_reason": "",
        "review_status": "ready_for_dry_run" if allowed_to_dry_run else "needs_research_iteration",
        "next_action": "enter_dry_run" if allowed_to_dry_run else "continue_research",
        "execution_priority": 0 if allowed_to_dry_run else 100 + index,
    }


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
    return overridden


def _evaluate_backtest_gate(metrics: dict[str, object]) -> dict[str, object]:
    """根据最小回测指标判断是否允许进入 dry-run。"""

    total_return_pct = _to_decimal(metrics.get("net_return_pct") or metrics.get("total_return_pct"))
    max_drawdown_pct = _to_decimal(metrics.get("max_drawdown_pct"))
    sharpe = _to_decimal(metrics.get("sharpe"))
    win_rate = _to_decimal(metrics.get("win_rate"))
    turnover = _to_decimal(metrics.get("turnover"))
    sample_count = _to_int_or_none(metrics.get("sample_count"))
    max_loss_streak = _to_int_or_none(metrics.get("max_loss_streak"))

    failures: list[str] = []
    if total_return_pct <= Decimal("0"):
        failures.append("non_positive_return")
    if max_drawdown_pct < Decimal("-15"):
        failures.append("drawdown_too_large")
    if sharpe < Decimal("0.5"):
        failures.append("sharpe_too_low")
    if win_rate < Decimal("0.5"):
        failures.append("win_rate_too_low")
    if turnover > Decimal("0.6"):
        failures.append("turnover_too_high")
    if sample_count is None or sample_count < 20:
        failures.append("sample_count_too_low")
    if max_loss_streak is not None and max_loss_streak > 3:
        failures.append("loss_streak_too_long")

    if failures:
        return {"status": "failed", "reasons": failures}
    return {"status": "passed", "reasons": []}


def _evaluate_validation_gate(validation: dict[str, object] | None) -> dict[str, object]:
    """根据训练阶段验证摘要判断研究结果是否足够稳定。"""

    payload = dict(validation or {})
    if not payload:
        return {"status": "passed", "reasons": []}

    sample_count = _to_int_or_none(payload.get("sample_count"))
    positive_rate = _to_decimal(payload.get("positive_rate"))
    avg_future_return_pct = _to_decimal(payload.get("avg_future_return_pct"))

    failures: list[str] = []
    if sample_count is None or sample_count < 12:
        failures.append("validation_sample_count_too_low")
    if positive_rate < Decimal("0.45"):
        failures.append("validation_positive_rate_too_low")
    if avg_future_return_pct < Decimal("-0.1"):
        failures.append("validation_future_return_not_positive")

    if failures:
        return {"status": "failed", "reasons": failures}
    return {"status": "passed", "reasons": []}


def _evaluate_consistency_gate(
    *,
    validation: dict[str, object] | None,
    metrics: dict[str, object],
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
    if validation_avg > Decimal("0") and avg_net_return_pct <= Decimal("0"):
        failures.append("validation_backtest_drift_too_large")
    elif (validation_avg - avg_net_return_pct) > Decimal("1.5"):
        failures.append("validation_backtest_drift_too_large")

    if failures:
        return {"status": "failed", "reasons": failures}
    return {"status": "passed", "reasons": []}


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
    if status != "passed":
        return {"status": "failed", "reasons": reasons or ["rule_gate_blocked"]}
    return {"status": "passed", "reasons": []}


def _merge_gates(*gates: dict[str, object]) -> dict[str, object]:
    """把规则门和模型门合并成最终 dry-run 准入门。"""

    if all(gate.get("status") == "passed" for gate in gates):
        return {"status": "passed", "reasons": []}
    reasons: list[str] = []
    for gate in gates:
        reasons.extend(list(gate.get("reasons") or []))
    return {"status": "failed", "reasons": reasons}


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


def _format_decimal(value: Decimal) -> str:
    """把分数统一成字符串。"""

    return format(value.quantize(Decimal("0.0001")), "f")
