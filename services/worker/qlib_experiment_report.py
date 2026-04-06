"""Qlib 统一实验对比摘要。

这个文件负责把训练、推理、候选和实验摘要收成一份稳定结果。
"""

from __future__ import annotations


def build_experiment_report(
    *,
    latest_training: dict[str, object] | None,
    latest_inference: dict[str, object] | None,
    candidates: dict[str, object] | None,
    recent_runs: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    """统一整理研究实验对比摘要。"""

    latest_training_payload = dict(latest_training or {})
    latest_inference_payload = dict(latest_inference or {})
    candidate_payload = dict(candidates or {})
    candidate_items = list(candidate_payload.get("items") or [])
    inference_summary = dict(latest_inference_payload.get("summary") or {})
    ready_count = sum(1 for item in candidate_items if bool(item.get("allowed_to_dry_run")))
    live_ready_count = sum(1 for item in candidate_items if bool(item.get("allowed_to_live")))
    blocked_count = max(len(candidate_items) - ready_count, 0)
    top_candidate = candidate_items[0] if candidate_items else {}
    recommended = _resolve_recommendation(
        candidate_items=candidate_items,
        latest_training=latest_training_payload,
        latest_inference=latest_inference_payload,
    )
    overview = {
        "candidate_count": len(candidate_items),
        "ready_count": ready_count,
        "live_ready_count": live_ready_count,
        "blocked_count": blocked_count,
        "pass_rate_pct": _format_ratio(ready_count, len(candidate_items)),
        "signal_count": max(len(list(latest_inference_payload.get("signals") or [])), _parse_int(inference_summary.get("signal_count"))),
        "top_candidate_symbol": str(top_candidate.get("symbol", "")),
        "top_candidate_score": str(top_candidate.get("score", "")),
        "recommended_symbol": str(recommended.get("symbol", "")),
        "recommended_action": str(recommended.get("next_action", "")),
        "forced_validation": bool(recommended.get("forced_for_validation")),
        "forced_symbol": str(recommended.get("symbol", "")) if bool(recommended.get("forced_for_validation")) else "",
    }
    return {
        "overview": overview,
        "factor_protocol": dict(
            latest_training_payload.get("factor_protocol")
            or latest_inference_payload.get("factor_protocol")
            or {}
        ),
        "snapshots": {
            "training": _build_dataset_snapshot_summary(latest_training_payload),
            "inference": _build_dataset_snapshot_summary(latest_inference_payload),
        },
        "latest_training": latest_training_payload,
        "latest_inference": latest_inference_payload,
        "candidates": candidate_items,
        "leaderboard": _build_leaderboard(candidate_items),
        "screening": _build_screening_summary(candidate_items),
        "evaluation": _build_evaluation_summary(
            overview=overview,
            latest_training=latest_training_payload,
            leaderboard=_build_leaderboard(candidate_items),
            screening=_build_screening_summary(candidate_items),
        ),
        "reviews": {
            "research": _build_research_review(
                overview=overview,
                screening=_build_screening_summary(candidate_items),
                leaderboard=_build_leaderboard(candidate_items),
            )
        },
        "experiments": {
            "training": _build_experiment_entry(latest_training_payload),
            "inference": _build_experiment_entry(latest_inference_payload),
            "recent_runs": _build_recent_runs(recent_runs),
        },
    }


def _build_experiment_entry(payload: dict[str, object]) -> dict[str, object]:
    """把单次实验结果整理成统一摘要。"""

    return {
        "run_id": str(payload.get("run_id", "")),
        "status": str(payload.get("status", "unavailable")),
        "generated_at": str(payload.get("generated_at", "")),
        "model_version": str(payload.get("model_version", "")),
        "dataset_snapshot_id": str(dict(payload.get("dataset_snapshot") or {}).get("snapshot_id", "")),
        "active_data_state": str(dict(payload.get("dataset_snapshot") or {}).get("active_data_state", "")),
        "dataset_snapshot": _build_dataset_snapshot_summary(payload),
        "signal_count": max(
            len(list(payload.get("signals") or [])),
            _parse_int(dict(payload.get("summary") or {}).get("signal_count")),
        ),
        "backtest": _build_backtest_snapshot(payload.get("backtest")),
    }


def _build_backtest_snapshot(value: object) -> dict[str, str]:
    """抽取统一回测摘要，方便 API 和页面直接展示。"""

    payload = dict(value or {}) if isinstance(value, dict) else {}
    metrics = dict(payload.get("metrics") or {})
    return {
        "total_return_pct": str(metrics.get("total_return_pct", "")),
        "gross_return_pct": str(metrics.get("gross_return_pct", metrics.get("total_return_pct", ""))),
        "net_return_pct": str(metrics.get("net_return_pct", metrics.get("total_return_pct", ""))),
        "max_drawdown_pct": str(metrics.get("max_drawdown_pct", "")),
        "sharpe": str(metrics.get("sharpe", "")),
        "win_rate": str(metrics.get("win_rate", "")),
        "turnover": str(metrics.get("turnover", "")),
        "max_loss_streak": str(metrics.get("max_loss_streak", "")),
    }


def _parse_int(value: object) -> int:
    """把输入转成整数。"""

    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _build_leaderboard(items: list[dict[str, object]]) -> list[dict[str, object]]:
    """把候选压成更适合页面和报告展示的排行榜。"""

    leaderboard: list[dict[str, object]] = []
    for item in items:
        leaderboard.append(
            {
                "rank": _parse_int(item.get("rank")),
                "symbol": str(item.get("symbol", "")),
                "score": str(item.get("score", "")),
                "strategy_template": str(item.get("strategy_template", "")),
                "allowed_to_dry_run": bool(item.get("allowed_to_dry_run")),
                "allowed_to_live": bool(item.get("allowed_to_live")),
                "review_status": str(item.get("review_status", "")),
                "forced_for_validation": bool(item.get("forced_for_validation")),
                "forced_reason": str(item.get("forced_reason", "")),
                "next_action": str(item.get("next_action", ""))
                or ("enter_dry_run" if bool(item.get("allowed_to_dry_run")) else "continue_research"),
                "execution_priority": _parse_int(item.get("execution_priority")),
                "failure_reasons": list(dict(item.get("dry_run_gate") or {}).get("reasons") or []),
                "backtest": _build_backtest_snapshot(item.get("backtest")),
            }
        )
    return leaderboard


def _build_screening_summary(items: list[dict[str, object]]) -> dict[str, object]:
    """汇总候选的失败原因和通过名单。"""

    blocked_reason_counts: dict[str, int] = {}
    gate_reason_counts = {
        "rule_gate": {},
        "validation_gate": {},
        "backtest_gate": {},
        "consistency_gate": {},
    }
    ready_symbols: list[str] = []
    blocked_symbols: list[str] = []
    for item in items:
        symbol = str(item.get("symbol", ""))
        reasons = [str(reason) for reason in list(dict(item.get("dry_run_gate") or {}).get("reasons") or [])]
        if bool(item.get("allowed_to_dry_run")):
            ready_symbols.append(symbol)
            continue
        blocked_symbols.append(symbol)
        for reason in reasons:
            blocked_reason_counts[reason] = blocked_reason_counts.get(reason, 0) + 1
        _accumulate_gate_reasons(gate_reason_counts["rule_gate"], dict(item.get("rule_gate") or {}))
        _accumulate_gate_reasons(gate_reason_counts["validation_gate"], dict(item.get("research_validation_gate") or {}))
        _accumulate_gate_reasons(gate_reason_counts["backtest_gate"], dict(item.get("backtest_gate") or {}))
        _accumulate_gate_reasons(gate_reason_counts["consistency_gate"], dict(item.get("consistency_gate") or {}))
    return {
        "ready_symbols": ready_symbols,
        "blocked_symbols": blocked_symbols,
        "blocked_reason_counts": blocked_reason_counts,
        "gate_reason_counts": gate_reason_counts,
    }


def _build_evaluation_summary(
    *,
    overview: dict[str, object],
    latest_training: dict[str, object],
    leaderboard: list[dict[str, object]],
    screening: dict[str, object],
) -> dict[str, object]:
    """统一整理评估层摘要。"""

    forced_validation_count = sum(1 for item in leaderboard if bool(item.get("forced_for_validation")))
    return {
        "metrics_catalog": [
            "gross_return_pct",
            "net_return_pct",
            "cost_impact_pct",
            "max_drawdown_pct",
            "sharpe",
            "win_rate",
            "turnover",
            "max_loss_streak",
        ],
        "candidate_status": {
            "candidate_count": int(overview.get("candidate_count", 0) or 0),
            "ready_count": int(overview.get("ready_count", 0) or 0),
            "live_ready_count": int(overview.get("live_ready_count", 0) or 0),
            "blocked_count": int(overview.get("blocked_count", 0) or 0),
            "forced_validation_count": forced_validation_count,
            "pass_rate_pct": str(overview.get("pass_rate_pct", "0.00") or "0.00"),
        },
        "training_backtest": _build_backtest_snapshot(latest_training.get("backtest")),
        "recommended_candidate": dict(leaderboard[0]) if leaderboard else {},
        "elimination_rules": {
            "blocked_reason_counts": dict(screening.get("blocked_reason_counts") or {}),
            "gate_reason_counts": dict(screening.get("gate_reason_counts") or {}),
        },
    }


def _build_research_review(
    *,
    overview: dict[str, object],
    screening: dict[str, object],
    leaderboard: list[dict[str, object]],
) -> dict[str, object]:
    """构造研究阶段复盘摘要。"""

    recommended_action = str(overview.get("recommended_action", ""))
    recommended_symbol = str(overview.get("recommended_symbol", ""))
    top_candidate = dict(leaderboard[0]) if leaderboard else {}
    blocked_reason_counts = dict(screening.get("blocked_reason_counts") or {})

    if recommended_action == "enter_dry_run":
        result = "candidate_ready"
        what_happened = f"研究结果已放行 {recommended_symbol or top_candidate.get('symbol', '')} 进入 dry-run"
        next_action = "enter_dry_run"
    elif recommended_action == "run_inference":
        result = "training_ready"
        what_happened = "训练结果已准备好，但还没有完成推理"
        next_action = "run_inference"
    elif recommended_action == "run_training":
        result = "training_missing"
        what_happened = "当前还没有可用训练结果"
        next_action = "run_training"
    else:
        result = "candidate_blocked"
        reason_text = ", ".join(sorted(blocked_reason_counts.keys())[:3]) or "筛选门未通过"
        what_happened = f"当前最佳候选仍被研究筛选门拦下：{reason_text}"
        next_action = "continue_research"

    return {
        "what_happened": what_happened,
        "result": result,
        "next_action": next_action,
        "recommended_symbol": recommended_symbol,
        "blocked_reason_counts": blocked_reason_counts,
    }


def _build_recent_runs(items: list[dict[str, object]] | None) -> list[dict[str, object]]:
    """整理最近实验账本，方便页面和接口直接消费。"""

    recent_runs: list[dict[str, object]] = []
    for item in list(items or []):
        payload = dict(item or {})
        recent_runs.append(
            {
                "run_id": str(payload.get("run_id", "")),
                "run_type": str(payload.get("run_type", "")),
                "status": str(payload.get("status", "")),
                "generated_at": str(payload.get("generated_at", "")),
                "model_version": str(payload.get("model_version", "")),
                "signal_count": str(payload.get("signal_count", "")),
                "dataset_snapshot_path": str(payload.get("dataset_snapshot_path", "")),
                "dataset_snapshot": dict(payload.get("dataset_snapshot") or {}),
                "backtest": _build_backtest_snapshot(payload.get("backtest")),
                "artifact_path": str(payload.get("artifact_path", "")),
            }
        )
    return recent_runs


def _build_dataset_snapshot_summary(payload: dict[str, object]) -> dict[str, object]:
    """抽取统一数据快照摘要。"""

    snapshot = dict(payload.get("dataset_snapshot") or {})
    snapshot_summary = dict(snapshot.get("summary") or {})
    data_states = dict(snapshot.get("data_states") or {})
    if not data_states and isinstance(snapshot_summary.get("data_states"), dict):
        data_states = dict(snapshot_summary.get("data_states") or {})
    if "current" not in data_states:
        data_states["current"] = str(snapshot.get("active_data_state", ""))
    return {
        "snapshot_id": str(snapshot.get("snapshot_id", "")),
        "cache_signature": str(snapshot.get("cache_signature", "")),
        "cache_status": str(snapshot.get("cache_status", "")),
        "active_data_state": str(snapshot.get("active_data_state", "")) or str(data_states.get("current", "")),
        "data_states": data_states,
        "cache": dict(snapshot_summary.get("cache") or snapshot.get("cache") or {}),
        "dataset_snapshot_path": str(payload.get("dataset_snapshot_path", "")),
    }


def _accumulate_gate_reasons(target: dict[str, int], gate: dict[str, object]) -> None:
    """把单个门控里的失败原因累计到汇总里。"""

    for reason in list(gate.get("reasons") or []):
        normalized = str(reason).strip()
        if not normalized:
            continue
        target[normalized] = target.get(normalized, 0) + 1


def _resolve_recommendation(
    *,
    candidate_items: list[dict[str, object]],
    latest_training: dict[str, object],
    latest_inference: dict[str, object],
) -> dict[str, object]:
    """统一给出当前研究流程的下一步。"""

    ready_items = [item for item in candidate_items if bool(item.get("allowed_to_dry_run"))]
    if ready_items:
        chosen = dict(sorted(ready_items, key=_recommendation_sort_key)[0])
        chosen.setdefault("next_action", "enter_dry_run")
        return chosen
    if candidate_items:
        fallback = dict(sorted(candidate_items, key=_recommendation_sort_key)[0])
        fallback.setdefault("next_action", "continue_research")
        return fallback
    if latest_training and not latest_inference:
        return {"symbol": "", "next_action": "run_inference"}
    if latest_training:
        return {"symbol": "", "next_action": "continue_research"}
    return {"symbol": "", "next_action": "run_training"}


def _recommendation_sort_key(item: dict[str, object]) -> tuple[int, int, str]:
    """按执行优先级、候选 rank 和 symbol 选推荐项。"""

    return (
        _parse_int(item.get("execution_priority")) or 0,
        _parse_int(item.get("rank")) or 0,
        str(item.get("symbol", "")),
    )


def _format_ratio(part: int, whole: int) -> str:
    """把通过率统一格式化成百分比字符串。"""

    if whole <= 0:
        return "0.00"
    return f"{(part / whole) * 100:.2f}"
