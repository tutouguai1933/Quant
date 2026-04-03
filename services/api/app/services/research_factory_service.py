"""研究工厂快照服务。

这个文件负责把研究层原始结果整理成控制平面可直接消费的候选摘要。
"""

from __future__ import annotations

from typing import Callable


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
        summary = dict(snapshot.get("summary") or {})
        signals = list(inference.get("signals") or [])
        signal_count = self._resolve_signal_count(inference=inference, signals=signals)
        return {
            "status": str(snapshot.get("status", "unavailable")),
            "backend": str(snapshot.get("backend", "qlib-fallback")),
            "overview": {
                "model_version": str(snapshot.get("model_version", "")),
                "generated_at": str(snapshot.get("generated_at", "")),
                "candidate_count": int(summary.get("candidate_count", 0) or 0),
                "ready_count": int(summary.get("ready_count", 0) or 0),
                "signal_count": signal_count,
            },
            "latest_training": training,
            "latest_inference": inference,
            "candidates": list(snapshot.get("candidates") or []),
            "experiments": {
                "training": {
                    "run_id": str(training.get("run_id", "")),
                    "status": str(training.get("status", "unavailable")),
                    "generated_at": str(training.get("generated_at", "")),
                    "model_version": str(training.get("model_version", "")),
                    "artifact_path": str(training.get("artifact_path", "")),
                },
                "inference": {
                    "run_id": str(inference.get("run_id", "")),
                    "status": str(inference.get("status", "unavailable")),
                    "generated_at": str(inference.get("generated_at", "")),
                    "model_version": str(inference.get("model_version", "")),
                    "signal_count": signal_count,
                },
            },
        }

    def get_symbol_snapshot(self, symbol: str) -> dict[str, object] | None:
        """返回单个标的的候选摘要。"""

        normalized_symbol = symbol.strip().upper()
        for item in self.build_snapshot()["candidates"]:
            if str(item.get("symbol", "")).strip().upper() == normalized_symbol:
                return item
        return None

    @staticmethod
    def _resolve_signal_count(*, inference: dict[str, object], signals: list[object]) -> int:
        """统一推理信号数量，避免 summary 和 signals 漂移。"""

        summary = dict(inference.get("summary") or {})
        raw_count = summary.get("signal_count")
        parsed_count = int(raw_count or 0) if raw_count is not None else 0
        return max(parsed_count, len(signals))

    @staticmethod
    def _resolve_candidate_counts(*, candidates: list[dict[str, object]], summary: dict[str, object]) -> tuple[int, int]:
        """统一候选数量，避免 summary 和候选列表漂移。"""

        ready_from_items = sum(1 for item in candidates if bool(item.get("allowed_to_dry_run")))
        raw_candidate_count = summary.get("candidate_count")
        raw_ready_count = summary.get("ready_count")
        parsed_candidate_count = int(raw_candidate_count or 0) if raw_candidate_count is not None else 0
        parsed_ready_count = int(raw_ready_count or 0) if raw_ready_count is not None else 0
        return max(parsed_candidate_count, len(candidates)), max(parsed_ready_count, ready_from_items)
