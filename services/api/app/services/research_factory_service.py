"""研究工厂快照服务。

这个文件负责把研究层原始结果整理成控制平面可直接消费的候选摘要。
"""

from __future__ import annotations

from typing import Callable

from services.worker.qlib_experiment_report import build_experiment_report


class ResearchFactoryService:
    """把研究结果转换成统一候选快照。"""

    def __init__(self, *, result_provider: Callable[[], dict[str, object]]) -> None:
        self._result_provider = result_provider

    def build_snapshot(self) -> dict[str, object]:
        """构造候选总览快照。"""

        latest = self._result_provider()
        status = str(latest.get("status", "unavailable"))
        inference = dict(latest.get("latest_inference") or {})
        candidates = list((inference.get("candidates") or {}).get("items", []))
        summary = dict((inference.get("candidates") or {}).get("summary", {}))
        if status != "ready":
            candidates = []
            summary = {}
        candidate_count, ready_count = self._resolve_candidate_counts(candidates=candidates, summary=summary)
        return {
            "status": status,
            "backend": str(latest.get("backend", "qlib-fallback")),
            "model_version": str(
                inference.get("model_version")
                or (latest.get("latest_training") or {}).get("model_version")
                or ""
            ),
            "generated_at": str(inference.get("generated_at", "")),
            "summary": {
                "candidate_count": candidate_count,
                "ready_count": ready_count,
            },
            "candidates": candidates,
        }

    def build_report(self) -> dict[str, object]:
        """构造统一研究报告。"""

        latest = self._result_provider()
        snapshot = self.build_snapshot()
        training = dict(latest.get("latest_training") or {})
        inference = dict(latest.get("latest_inference") or {})
        report = build_experiment_report(
            latest_training=training,
            latest_inference=inference,
            candidates={"items": list(snapshot.get("candidates") or [])},
            recent_runs=list(latest.get("recent_runs") or []),
        )
        overview = dict(report.get("overview") or {})
        return {
            "status": str(snapshot.get("status", "unavailable")),
            "backend": str(snapshot.get("backend", "qlib-fallback")),
            "factor_protocol": dict(report.get("factor_protocol") or {}),
            "overview": {
                "model_version": str(snapshot.get("model_version", "")),
                "generated_at": str(snapshot.get("generated_at", "")),
                "candidate_count": int(overview.get("candidate_count", 0) or 0),
                "ready_count": int(overview.get("ready_count", 0) or 0),
                "blocked_count": int(overview.get("blocked_count", 0) or 0),
                "pass_rate_pct": str(overview.get("pass_rate_pct", "0.00") or "0.00"),
                "signal_count": int(overview.get("signal_count", 0) or 0),
                "top_candidate_symbol": str(overview.get("top_candidate_symbol", "")),
                "top_candidate_score": str(overview.get("top_candidate_score", "")),
                "recommended_symbol": str(overview.get("recommended_symbol", "")),
                "recommended_action": str(overview.get("recommended_action", "")),
                "forced_validation": bool(overview.get("forced_validation")),
                "forced_symbol": str(overview.get("forced_symbol", "")),
            },
            "snapshots": dict(report.get("snapshots") or {}),
            "latest_training": dict(report.get("latest_training") or {}),
            "latest_inference": dict(report.get("latest_inference") or {}),
            "candidates": list(report.get("candidates") or []),
            "leaderboard": list(report.get("leaderboard") or []),
            "screening": dict(report.get("screening") or {}),
            "evaluation": dict(report.get("evaluation") or {}),
            "reviews": dict(report.get("reviews") or {}),
            "experiments": dict(report.get("experiments") or {}),
        }

    def get_symbol_snapshot(self, symbol: str) -> dict[str, object] | None:
        """返回单个标的的候选摘要。"""

        normalized_symbol = symbol.strip().upper()
        for item in self.build_snapshot()["candidates"]:
            if str(item.get("symbol", "")).strip().upper() == normalized_symbol:
                return item
        return None

    @staticmethod
    def _resolve_candidate_counts(*, candidates: list[dict[str, object]], summary: dict[str, object]) -> tuple[int, int]:
        """统一候选数量，避免 summary 和候选列表漂移。"""

        ready_from_items = sum(1 for item in candidates if bool(item.get("allowed_to_dry_run")))
        raw_candidate_count = summary.get("candidate_count")
        raw_ready_count = summary.get("ready_count")
        parsed_candidate_count = int(raw_candidate_count or 0) if raw_candidate_count is not None else 0
        parsed_ready_count = int(raw_ready_count or 0) if raw_ready_count is not None else 0
        return max(parsed_candidate_count, len(candidates)), max(parsed_ready_count, ready_from_items)
