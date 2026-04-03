"""Qlib 候选排行与 dry-run 准入门。

这个文件负责把研究候选按分数排序，并判断是否允许进入 dry-run。
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation


def rank_candidates(items: list[dict[str, object]]) -> dict[str, object]:
    """按分数输出统一候选排行。"""

    ranked = sorted(items, key=lambda item: _to_decimal(item.get("score")), reverse=True)
    normalized = [_normalize_candidate(item, index=index) for index, item in enumerate(ranked, start=1)]
    return {
        "items": normalized,
        "summary": {
            "candidate_count": len(normalized),
            "ready_count": sum(1 for item in normalized if item["allowed_to_dry_run"]),
        },
    }


def _normalize_candidate(item: dict[str, object], *, index: int) -> dict[str, object]:
    """把单个候选统一成稳定结构。"""

    backtest = dict(item.get("backtest") or {})
    metrics = dict(backtest.get("metrics") or {})
    dry_run_gate = _evaluate_dry_run_gate(metrics)
    return {
        "rank": index,
        "symbol": str(item.get("symbol", "")).strip().upper(),
        "strategy_template": str(item.get("strategy_template", "")).strip() or "trend_breakout_timing",
        "score": _format_decimal(_to_decimal(item.get("score"))),
        "backtest": {"metrics": metrics},
        "dry_run_gate": dry_run_gate,
        "allowed_to_dry_run": dry_run_gate["status"] == "passed",
    }


def _evaluate_dry_run_gate(metrics: dict[str, object]) -> dict[str, object]:
    """根据最小回测指标判断是否允许进入 dry-run。"""

    total_return_pct = _to_decimal(metrics.get("total_return_pct"))
    max_drawdown_pct = _to_decimal(metrics.get("max_drawdown_pct"))
    sharpe = _to_decimal(metrics.get("sharpe"))
    win_rate = _to_decimal(metrics.get("win_rate"))
    turnover = _to_decimal(metrics.get("turnover"))

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

    if failures:
        return {"status": "failed", "reasons": failures}
    return {"status": "passed", "reasons": []}


def _to_decimal(value: object) -> Decimal:
    """把输入统一转成十进制。"""

    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0")


def _format_decimal(value: Decimal) -> str:
    """把分数统一成字符串。"""

    return format(value.quantize(Decimal("0.0001")), "f")
