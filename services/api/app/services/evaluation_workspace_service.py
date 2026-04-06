"""评估与实验中心聚合服务。

这个文件负责把研究报告里的评估摘要、淘汰原因和实验账本整理成前端可见结构。
"""

from __future__ import annotations

from services.api.app.services.research_service import research_service
from services.api.app.services.validation_workflow_service import validation_workflow_service
from services.api.app.services.workbench_config_service import workbench_config_service


class EvaluationWorkspaceService:
    """聚合评估与实验中心上下文。"""

    def __init__(self, *, report_reader: object | None = None, controls_builder=None, review_reader: object | None = None) -> None:
        self._report_reader = report_reader or research_service
        self._controls_builder = controls_builder or workbench_config_service.build_workspace_controls
        self._review_reader = review_reader or validation_workflow_service

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
        review_report = self._read_validation_review()
        execution_alignment = dict(review_report.get("execution_comparison") or {})
        validation_reviews = dict(review_report.get("reviews") or {})
        controls = self._controls_builder()
        configured_thresholds = dict((controls.get("config") or {}).get("thresholds") or {})

        status = str(report.get("status", "unavailable") or "unavailable")
        if evaluation or leaderboard or reviews:
            status = "ready"

        return {
            "status": status,
            "backend": str(report.get("backend", "qlib-fallback") or "qlib-fallback"),
            "config_alignment": dict(report.get("config_alignment") or {}),
            "overview": {
                "recommended_symbol": str(overview.get("recommended_symbol", "")),
                "recommended_action": str(overview.get("recommended_action", "")),
                "candidate_count": int(overview.get("candidate_count", 0) or 0),
            },
            "controls": {
                "dry_run_min_score": str(configured_thresholds.get("dry_run_min_score", "")),
                "dry_run_min_positive_rate": str(configured_thresholds.get("dry_run_min_positive_rate", "")),
                "dry_run_min_net_return_pct": str(configured_thresholds.get("dry_run_min_net_return_pct", "")),
                "dry_run_min_sharpe": str(configured_thresholds.get("dry_run_min_sharpe", "")),
                "dry_run_max_drawdown_pct": str(configured_thresholds.get("dry_run_max_drawdown_pct", "")),
                "dry_run_max_loss_streak": str(configured_thresholds.get("dry_run_max_loss_streak", "")),
                "live_min_score": str(configured_thresholds.get("live_min_score", "")),
                "live_min_positive_rate": str(configured_thresholds.get("live_min_positive_rate", "")),
                "live_min_net_return_pct": str(configured_thresholds.get("live_min_net_return_pct", "")),
            },
            "evaluation": evaluation,
            "reviews": {
                **reviews,
                **{key: dict(value or {}) for key, value in validation_reviews.items()},
            },
            "leaderboard": leaderboard,
            "recent_runs": [dict(item) for item in recent_runs if isinstance(item, dict)],
            "experiment_comparison": self._build_experiment_comparison(report),
            "execution_alignment": execution_alignment,
        }

    def _read_factory_report(self) -> dict[str, object]:
        """读取统一研究报告。"""

        reader = getattr(self._report_reader, "get_factory_report", None)
        if callable(reader):
            payload = reader()
            if isinstance(payload, dict):
                return payload
        return {"status": "unavailable", "backend": "qlib-fallback"}

    def _read_validation_review(self) -> dict[str, object]:
        """读取统一复盘摘要。"""

        reader = getattr(self._review_reader, "build_report", None)
        if callable(reader):
            payload = reader(limit=10)
            if isinstance(payload, dict):
                return payload
        return {}

    @staticmethod
    def _build_experiment_comparison(report: dict[str, object]) -> list[dict[str, object]]:
        """把训练、推理和最近运行压成统一对照表。"""

        experiments = dict(report.get("experiments") or {})
        training = dict(experiments.get("training") or {})
        inference = dict(experiments.get("inference") or {})
        recent_runs = [dict(item) for item in list(experiments.get("recent_runs") or []) if isinstance(item, dict)]
        rows: list[dict[str, object]] = []
        if training:
            rows.append(
                {
                    "run_type": "training",
                    "run_id": str(training.get("run_id", "")),
                    "status": str(training.get("status", "")),
                    "model_version": str(training.get("model_version", "")),
                    "dataset_snapshot_id": str(training.get("dataset_snapshot_id", "")),
                    "signal_count": str(training.get("signal_count", "")),
                }
            )
        if inference:
            rows.append(
                {
                    "run_type": "inference",
                    "run_id": str(inference.get("run_id", "")),
                    "status": str(inference.get("status", "")),
                    "model_version": str(inference.get("model_version", "")),
                    "dataset_snapshot_id": str(inference.get("dataset_snapshot_id", "")),
                    "signal_count": str(inference.get("signal_count", "")),
                }
            )
        for item in recent_runs:
            if not training and str(item.get("run_type", "")) == "training":
                rows.append(
                    {
                        "run_type": "training",
                        "run_id": str(item.get("run_id", "")),
                        "status": str(item.get("status", "")),
                        "model_version": str(item.get("model_version", "")),
                        "dataset_snapshot_id": str(dict(item.get("dataset_snapshot") or {}).get("snapshot_id", "")),
                        "signal_count": str(item.get("signal_count", "")),
                    }
                )
                continue
            if not inference and str(item.get("run_type", "")) == "inference":
                rows.append(
                    {
                        "run_type": "inference",
                        "run_id": str(item.get("run_id", "")),
                        "status": str(item.get("status", "")),
                        "model_version": str(item.get("model_version", "")),
                        "dataset_snapshot_id": str(dict(item.get("dataset_snapshot") or {}).get("snapshot_id", "")),
                        "signal_count": str(item.get("signal_count", "")),
                    }
                )
                continue
            if str(item.get("run_type", "")) in {"training", "inference"}:
                continue
            rows.append(
                {
                    "run_type": str(item.get("run_type", "")),
                    "run_id": str(item.get("run_id", "")),
                    "status": str(item.get("status", "")),
                    "model_version": str(item.get("model_version", "")),
                    "dataset_snapshot_id": str(dict(item.get("dataset_snapshot") or {}).get("snapshot_id", "")),
                    "signal_count": "",
                }
            )
        return rows


evaluation_workspace_service = EvaluationWorkspaceService()
