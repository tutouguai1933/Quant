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
        inference = dict(latest.get("latest_inference") or {})
        candidates = list((inference.get("candidates") or {}).get("items", []))
        summary = dict((inference.get("candidates") or {}).get("summary", {}))
        return {
            "status": str(latest.get("status", "unavailable")),
            "backend": str(latest.get("backend", "qlib-fallback")),
            "model_version": str(
                inference.get("model_version")
                or (latest.get("latest_training") or {}).get("model_version")
                or ""
            ),
            "generated_at": str(inference.get("generated_at", "")),
            "summary": {
                "candidate_count": int(summary.get("candidate_count", len(candidates)) or 0),
                "ready_count": int(
                    summary.get(
                        "ready_count",
                        sum(1 for item in candidates if bool(item.get("allowed_to_dry_run"))),
                    )
                    or 0
                ),
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
        return {
            "status": str(snapshot.get("status", "unavailable")),
            "backend": str(snapshot.get("backend", "qlib-fallback")),
            "overview": {
                "model_version": str(snapshot.get("model_version", "")),
                "generated_at": str(snapshot.get("generated_at", "")),
                "candidate_count": int(summary.get("candidate_count", 0) or 0),
                "ready_count": int(summary.get("ready_count", 0) or 0),
                "signal_count": int((inference.get("summary") or {}).get("signal_count", 0) or 0),
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
                    "signal_count": int((inference.get("summary") or {}).get("signal_count", 0) or 0),
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
