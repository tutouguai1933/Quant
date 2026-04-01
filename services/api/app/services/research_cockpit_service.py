"""统一研究摘要服务。

这个文件把研究结果和策略评估收敛成统一的页面摘要结构。
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from math import isnan, isinf


def build_market_research_brief(
    *,
    symbol: str,
    recommended_strategy: str,
    evaluation: dict[str, object] | None,
    research_summary: dict[str, object] | None,
) -> dict[str, object]:
    """构造市场页使用的简版统一研究摘要。"""

    return _build_research_summary(
        recommended_strategy=recommended_strategy,
        evaluation=evaluation,
        research_summary=research_summary,
    )


def build_symbol_research_cockpit(
    *,
    symbol: str,
    recommended_strategy: str,
    evaluation: dict[str, object] | None,
    research_summary: dict[str, object] | None,
    markers: dict[str, list[dict[str, object]]] | None,
) -> dict[str, object]:
    """构造单币页使用的完整版统一研究摘要。"""

    summary = _build_research_summary(
        recommended_strategy=recommended_strategy,
        evaluation=evaluation,
        research_summary=research_summary,
    )
    signals = _normalize_marker_list((markers or {}).get("signals"))
    entries = _pick_preferred_markers(
        _normalize_marker_list((markers or {}).get("entries")),
        recommended_strategy,
    )
    stops = _pick_preferred_markers(
        _normalize_marker_list((markers or {}).get("stops")),
        recommended_strategy,
    )
    summary["signal_count"] = len(signals)
    summary["entry_hint"] = _latest_marker_price(entries)
    summary["stop_hint"] = _latest_marker_price(stops)
    return summary


def _build_research_summary(
    *,
    recommended_strategy: str,
    evaluation: dict[str, object] | None,
    research_summary: dict[str, object] | None,
) -> dict[str, object]:
    """统一收敛研究摘要字段。"""

    evaluation_payload = dict(evaluation or {})
    research_payload = dict(research_summary or {})
    research_status = _resolve_research_status(research_payload)
    gate = _normalize_research_gate(
        evaluation_payload.get("research_gate"),
        research_status=research_status,
    )
    research_bias = _resolve_research_bias(research_payload.get("signal"), research_status)
    explanation = _resolve_research_explanation(research_payload, research_status)

    return {
        "research_bias": research_bias,
        "recommended_strategy": recommended_strategy,
        "confidence": _normalize_text(evaluation_payload.get("confidence"), "low"),
        "research_gate": gate,
        "primary_reason": _normalize_text(evaluation_payload.get("reason"), "n/a"),
        "research_explanation": explanation,
        "model_version": _normalize_text(research_payload.get("model_version"), ""),
        "generated_at": _normalize_text(research_payload.get("generated_at"), ""),
    }


def _resolve_research_explanation(
    research_payload: dict[str, object],
    research_status: str,
) -> str:
    """把研究解释按可用性统一成页面文案。"""

    if not research_payload:
        explanation = "该币种暂无研究结论"
    elif research_status != "available":
        explanation = "研究结果暂不可用"
    else:
        explanation = _normalize_text(research_payload.get("explanation"), "")
    return explanation


def _resolve_research_bias(signal: object, research_status: str) -> str:
    """把研究信号归一成页面可读倾向。"""

    if research_status != "available":
        return "unavailable"
    normalized_signal = str(signal or "").strip().lower()
    if normalized_signal in {"long", "bullish"}:
        return "bullish"
    if normalized_signal in {"short", "bearish"}:
        return "bearish"
    if normalized_signal in {"neutral", "hold", "flat"}:
        return "neutral"
    return "unavailable"


def _normalize_research_gate(raw_gate: object, *, research_status: str) -> dict[str, object]:
    """复制并规范研究门控信息。"""

    if isinstance(raw_gate, dict):
        gate = dict(raw_gate)
    else:
        gate = {}
    status = _normalize_text(gate.get("status"), "")
    if research_status == "invalid":
        return {"status": "invalid_score"}
    if research_status == "missing":
        return {"status": "unavailable"}
    if not status:
        return {"status": "unavailable"}
    return {"status": status}


def _resolve_research_status(research_payload: dict[str, object]) -> str:
    """判断研究结果是可用、缺失还是异常。"""

    if not research_payload:
        return "missing"
    score = research_payload.get("score")
    if score is None:
        return "invalid"
    try:
        parsed = Decimal(str(score))
    except (TypeError, ValueError, InvalidOperation):
        return "invalid"
    if not parsed.is_finite():
        return "invalid"
    try:
        numeric = float(parsed)
    except (TypeError, ValueError):
        return "invalid"
    if isnan(numeric) or isinf(numeric):
        return "invalid"
    return "available"


def _normalize_text(value: object, fallback: str) -> str:
    """把可选文本统一成干净字符串。"""

    if value is None:
        return fallback
    text = str(value).strip()
    return text if text else fallback


def _latest_marker_price(markers: list[dict[str, object]] | None) -> str:
    """返回最近一个标记的价格。"""

    if not markers:
        return "n/a"
    latest_marker = markers[-1]
    price = str(latest_marker.get("price", "")).strip()
    return price or "n/a"


def _normalize_marker_list(value: object) -> list[dict[str, object]]:
    """把标记输入统一成稳定列表。"""

    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _pick_preferred_markers(
    markers: list[dict[str, object]],
    recommended_strategy: str,
) -> list[dict[str, object]]:
    """优先返回当前推荐策略对应的标记。"""

    if not markers:
        return []
    if recommended_strategy not in {"trend_breakout", "trend_pullback"}:
        return markers
    filtered = [
        item
        for item in markers
        if str(item.get("strategy_id", "")).strip() == recommended_strategy
    ]
    return filtered or markers
