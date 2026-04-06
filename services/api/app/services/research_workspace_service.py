"""策略研究工作台聚合服务。

这个文件负责把研究报告里的模板、标签、窗口和实验参数整理成前端工作台结构。
"""

from __future__ import annotations

from services.api.app.services.research_service import research_service
from services.api.app.services.workbench_config_service import workbench_config_service


class ResearchWorkspaceService:
    """聚合当前研究上下文。"""

    def __init__(self, *, report_reader: object | None = None, controls_builder=None) -> None:
        self._report_reader = report_reader or research_service
        self._controls_builder = controls_builder or workbench_config_service.build_workspace_controls

    def get_workspace(self) -> dict[str, object]:
        """返回策略研究工作台统一模型。"""

        report = self._read_factory_report()
        latest_training = dict(report.get("latest_training") or {})
        latest_inference = dict(report.get("latest_inference") or {})
        overview = dict(report.get("overview") or {})
        training_context = dict(latest_training.get("training_context") or {})
        sample_window = dict(training_context.get("sample_window") or {})
        parameters = dict(training_context.get("parameters") or {})
        controls = self._controls_builder()
        configured_research = dict((controls.get("config") or {}).get("research") or {})
        min_days = int(configured_research.get("min_holding_days", 1) or 1)
        max_days = int(configured_research.get("max_holding_days", 3) or 3)
        label_target_pct = str(configured_research.get("label_target_pct", "1"))
        label_stop_pct = str(configured_research.get("label_stop_pct", "-1"))
        label_mode = str(configured_research.get("label_mode", "earliest_hit") or "earliest_hit")
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
            "config_alignment": dict(report.get("config_alignment") or {}),
            "overview": {
                "holding_window": str(training_context.get("holding_window", "")),
                "candidate_count": int(overview.get("candidate_count", 0) or 0),
                "recommended_symbol": str(overview.get("recommended_symbol", "")),
                "recommended_action": str(overview.get("recommended_action", "")),
            },
            "strategy_templates": strategy_templates,
            "labeling": {
                "label_columns": [str(item) for item in list(latest_training.get("label_columns") or [])],
                "label_mode": label_mode,
                "definition": self._build_label_definition(
                    label_mode=label_mode,
                    min_days=min_days,
                    max_days=max_days,
                    label_target_pct=label_target_pct,
                    label_stop_pct=label_stop_pct,
                ),
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
            "controls": {
                "research_template": str(configured_research.get("research_template", "")),
                "model_key": str(configured_research.get("model_key", "")),
                "label_mode": label_mode,
                "holding_window_label": str(configured_research.get("holding_window_label", "")),
                "min_holding_days": int(configured_research.get("min_holding_days", 1) or 1),
                "max_holding_days": int(configured_research.get("max_holding_days", 3) or 3),
                "label_target_pct": str(configured_research.get("label_target_pct", "")),
                "label_stop_pct": str(configured_research.get("label_stop_pct", "")),
                "available_models": [str(item) for item in list((controls.get("options") or {}).get("models") or [])],
                "available_research_templates": [str(item) for item in list((controls.get("options") or {}).get("research_templates") or [])],
                "available_label_modes": [str(item) for item in list((controls.get("options") or {}).get("label_modes") or [])],
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

    @staticmethod
    def _build_label_definition(
        *,
        label_mode: str,
        min_days: int,
        max_days: int,
        label_target_pct: str,
        label_stop_pct: str,
    ) -> str:
        """生成更直白的标签说明。"""

        if label_mode == "close_only":
            return f"未来 {min_days}-{max_days} 天窗口结束时，收盘达到 +{label_target_pct}% 记 buy，收盘低于 {label_stop_pct}% 记 sell，其余记 watch。"
        return f"未来 {min_days}-{max_days} 天内最早达到 +{label_target_pct}% 记 buy，最早达到 {label_stop_pct}% 记 sell，其余记 watch。"


research_workspace_service = ResearchWorkspaceService()
