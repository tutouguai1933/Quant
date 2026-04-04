"""Qlib 统一实验对比摘要。

这个文件负责把训练、推理、候选和实验摘要收成一份稳定结果。
"""

from __future__ import annotations


def build_experiment_report(
    *,
    latest_training: dict[str, object] | None,
    latest_inference: dict[str, object] | None,
    candidates: dict[str, object] | None,
) -> dict[str, object]:
    """统一整理研究实验对比摘要。"""

    latest_training_payload = dict(latest_training or {})
    latest_inference_payload = dict(latest_inference or {})
    candidate_payload = dict(candidates or {})
    candidate_items = list(candidate_payload.get("items") or [])
    inference_summary = dict(latest_inference_payload.get("summary") or {})
    ready_count = sum(1 for item in candidate_items if bool(item.get("allowed_to_dry_run")))
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
        "blocked_count": blocked_count,
        "pass_rate_pct": _format_ratio(ready_count, len(candidate_items)),
        "signal_count": max(len(list(latest_inference_payload.get("signals") or [])), _parse_int(inference_summary.get("signal_count"))),
        "top_candidate_symbol": str(top_candidate.get("symbol", "")),
        "top_candidate_score": str(top_candidate.get("score", "")),
        "recommended_symbol": str(recommended.get("symbol", "")),
        "recommended_action": str(recommended.get("next_action", "")),
    }
    return {
        "overview": overview,
        "latest_training": latest_training_payload,
        "latest_inference": latest_inference_payload,
        "candidates": candidate_items,
        "leaderboard": _build_leaderboard(candidate_items),
        "screening": _build_screening_summary(candidate_items),
        "experiments": {
            "training": _build_experiment_entry(latest_training_payload),
            "inference": _build_experiment_entry(latest_inference_payload),
        },
    }


def _build_experiment_entry(payload: dict[str, object]) -> dict[str, object]:
    """把单次实验结果整理成统一摘要。"""

    return {
        "run_id": str(payload.get("run_id", "")),
        "status": str(payload.get("status", "unavailable")),
        "generated_at": str(payload.get("generated_at", "")),
        "model_version": str(payload.get("model_version", "")),
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
                "review_status": str(item.get("review_status", "")),
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
    return {
        "ready_symbols": ready_symbols,
        "blocked_symbols": blocked_symbols,
        "blocked_reason_counts": blocked_reason_counts,
    }


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
