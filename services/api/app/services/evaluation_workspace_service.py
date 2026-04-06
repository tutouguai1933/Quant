"""评估与实验中心聚合服务。

这个文件负责把研究报告里的评估摘要、淘汰原因和实验账本整理成前端可见结构。
"""

from __future__ import annotations

from services.api.app.services.research_service import research_service


class EvaluationWorkspaceService:
    """聚合评估与实验中心上下文。"""

    def __init__(self, *, report_reader: object | None = None) -> None:
        self._report_reader = report_reader or research_service

    def get_workspace(self) -> dict[str, object]:
        """返回评估与实验中心统一模型。"""

        report = self._read_factory_report()
        leaderboard = [
            dict(item)
            for item in list(report.get("leaderboard") or [])
            if isinstance(item, dict)
        ]
        evaluation = dict(report.get("evaluation") or {})
        reviews = dict(report.get("reviews") or {})
        overview = dict(report.get("overview") or {})
        recent_runs = list((report.get("experiments") or {}).get("recent_runs") or [])

        status = str(report.get("status", "unavailable") or "unavailable")
        if evaluation or leaderboard or reviews:
            status = "ready"

        return {
            "status": status,
            "backend": str(report.get("backend", "qlib-fallback") or "qlib-fallback"),
            "overview": {
                "recommended_symbol": str(overview.get("recommended_symbol", "")),
                "recommended_action": str(overview.get("recommended_action", "")),
                "candidate_count": int(overview.get("candidate_count", 0) or 0),
            },
            "evaluation": evaluation,
            "reviews": reviews,
            "leaderboard": leaderboard,
            "recent_runs": [dict(item) for item in recent_runs if isinstance(item, dict)],
        }

    def _read_factory_report(self) -> dict[str, object]:
        """读取统一研究报告。"""

        reader = getattr(self._report_reader, "get_factory_report", None)
        if callable(reader):
            payload = reader()
            if isinstance(payload, dict):
                return payload
        return {"status": "unavailable", "backend": "qlib-fallback"}


evaluation_workspace_service = EvaluationWorkspaceService()
