"""策略研究工作台聚合服务。

这个文件负责把研究报告里的模板、标签、窗口和实验参数整理成前端工作台结构。
"""

from __future__ import annotations

from services.api.app.services.research_service import research_service


LABEL_DEFINITION = "未来 1-3 天内最早达到 +1% 记 buy，最早达到 -1% 记 sell，其余记 watch。"


class ResearchWorkspaceService:
    """聚合当前研究上下文。"""

    def __init__(self, *, report_reader: object | None = None) -> None:
        self._report_reader = report_reader or research_service

    def get_workspace(self) -> dict[str, object]:
        """返回策略研究工作台统一模型。"""

        report = self._read_factory_report()
        latest_training = dict(report.get("latest_training") or {})
        latest_inference = dict(report.get("latest_inference") or {})
        overview = dict(report.get("overview") or {})
        training_context = dict(latest_training.get("training_context") or {})
        sample_window = dict(training_context.get("sample_window") or {})
        parameters = dict(training_context.get("parameters") or {})
        strategy_templates = sorted(
            {
                str(item.get("strategy_template", "")).strip()
                for item in list(report.get("candidates") or [])
                if isinstance(item, dict) and str(item.get("strategy_template", "")).strip()
            }
        )

        status = str(report.get("status", "unavailable") or "unavailable")
        if latest_training or latest_inference or strategy_templates:
            status = "ready"

        return {
            "status": status,
            "backend": str(report.get("backend", "qlib-fallback") or "qlib-fallback"),
            "overview": {
                "holding_window": str(training_context.get("holding_window", "")),
                "candidate_count": int(overview.get("candidate_count", 0) or 0),
                "recommended_symbol": str(overview.get("recommended_symbol", "")),
                "recommended_action": str(overview.get("recommended_action", "")),
            },
            "strategy_templates": strategy_templates,
            "labeling": {
                "label_columns": [str(item) for item in list(latest_training.get("label_columns") or [])],
                "definition": LABEL_DEFINITION,
            },
            "sample_window": {
                name: dict(value or {})
                for name, value in sample_window.items()
            },
            "model": {
                "model_version": str(
                    latest_inference.get("model_version")
                    or latest_training.get("model_version")
                    or ""
                ),
                "backend": str(report.get("backend", "qlib-fallback") or "qlib-fallback"),
            },
            "parameters": {
                str(name): str(value)
                for name, value in parameters.items()
            },
            "selectors": {
                "symbols": [str(item) for item in list(training_context.get("symbols") or [])],
                "timeframes": [str(item) for item in list(training_context.get("timeframes") or [])],
            },
        }

    def _read_factory_report(self) -> dict[str, object]:
        """读取统一研究报告。"""

        reader = getattr(self._report_reader, "get_factory_report", None)
        if callable(reader):
            payload = reader()
            if isinstance(payload, dict):
                return payload
        return {"status": "unavailable", "backend": "qlib-fallback"}


research_workspace_service = ResearchWorkspaceService()
