"""验证工作流复盘服务。

这个文件把研究、执行和任务状态整理成一份固定复盘报告。
"""

from __future__ import annotations

from typing import Any

from services.api.app.services.research_service import research_service
from services.api.app.services.sync_service import sync_service
from services.api.app.tasks.scheduler import task_scheduler


class ValidationWorkflowService:
    """构造 dry-run -> 小额 live -> 复盘 的统一摘要。"""

    def __init__(self, *, research_reader=None, sync_reader=None, scheduler=None) -> None:
        self._research_reader = research_reader or research_service
        self._sync_reader = sync_reader or sync_service
        self._scheduler = scheduler or task_scheduler

    def build_report(self, limit: int = 10) -> dict[str, object]:
        """返回固定验证工作流复盘。"""

        research_report = self._research_reader.get_factory_report()
        raw_recent_tasks = self._scheduler.list_tasks(limit=limit)
        task_health = self._scheduler.get_health_summary()
        execution_health = self._sync_reader.get_execution_health_summary(task_health=task_health)
        account_snapshot = self._build_account_snapshot(limit=limit)
        steps = self._build_steps(
            research_report=research_report,
            recent_tasks=raw_recent_tasks,
            execution_health=execution_health,
        )
        recent_tasks = self._serialize_recent_tasks(raw_recent_tasks)
        return {
            "overview": {
                "recommended_symbol": str(research_report.get("overview", {}).get("recommended_symbol", "")),
                "recommended_action": str(research_report.get("overview", {}).get("recommended_action", "")),
                "candidate_count": int(research_report.get("overview", {}).get("candidate_count", 0) or 0),
                "ready_count": int(research_report.get("overview", {}).get("ready_count", 0) or 0),
                "workflow_status": self._resolve_workflow_status(steps),
            },
            "steps": steps,
            "research_report": research_report,
            "task_health": task_health,
            "execution_health": execution_health,
            "recent_tasks": recent_tasks,
            "account_snapshot": account_snapshot,
        }

    def _build_account_snapshot(self, *, limit: int) -> dict[str, object]:
        """用最小同步结果补当前账户状态。"""

        try:
            snapshot = self._sync_reader.sync_task_state(limit=limit)
        except Exception as exc:
            return {
                "status": "unavailable",
                "detail": str(exc),
                "balances": [],
                "orders": [],
                "positions": [],
            }
        return {
            "status": "ready",
            "detail": "",
            "balances": list(snapshot.get("balances") or []),
            "orders": list(snapshot.get("orders") or []),
            "positions": list(snapshot.get("positions") or []),
            "source": str(snapshot.get("source", "")),
            "truth_source": str(snapshot.get("truth_source", "")),
        }

    def _build_steps(
        self,
        *,
        research_report: dict[str, object],
        recent_tasks: list[dict[str, object]],
        execution_health: dict[str, object],
    ) -> list[dict[str, str]]:
        """构造固定验证步骤。"""

        training_status = str(research_report.get("experiments", {}).get("training", {}).get("status", "unavailable"))
        inference_status = str(research_report.get("experiments", {}).get("inference", {}).get("status", "unavailable"))
        recommended_action = str(research_report.get("overview", {}).get("recommended_action", ""))
        latest_sync_status = str(execution_health.get("latest_sync_status", "unknown"))
        runtime_mode = str(execution_health.get("runtime_mode", ""))
        last_review = self._latest_task(recent_tasks, "review")

        return [
            self._step("training", training_status, "最近训练结果"),
            self._step("inference", inference_status, "最近推理结果"),
            self._step("screening", self._screening_status(recommended_action), "研究筛选门"),
            self._step("dry_run", latest_sync_status if runtime_mode != "live" else "waiting", "dry-run 验证"),
            self._step("live", latest_sync_status if runtime_mode == "live" else "waiting", "小额 live 验证"),
            self._step(
            "review",
                str(last_review.get("status", "waiting")) if last_review else "waiting",
                "统一复盘",
            ),
        ]

    @staticmethod
    def _serialize_recent_tasks(items: list[dict[str, object]]) -> list[dict[str, object]]:
        """裁剪任务列表，避免把大结果和自引用直接塞进复盘报告。"""

        serialized: list[dict[str, object]] = []
        for item in items:
            payload = dict(item.get("payload") or {})
            result = item.get("result")
            result_summary = ""
            if isinstance(result, dict):
                result_summary = str(result.get("status") or result.get("detail") or "")
            serialized.append(
                {
                    "id": item.get("id"),
                    "task_type": item.get("task_type"),
                    "source": item.get("source"),
                    "status": item.get("status"),
                    "target_type": item.get("target_type"),
                    "target_id": item.get("target_id"),
                    "requested_at": item.get("requested_at"),
                    "started_at": item.get("started_at"),
                    "finished_at": item.get("finished_at"),
                    "error_message": item.get("error_message"),
                    "payload": payload,
                    "result_summary": result_summary,
                }
            )
        return serialized

    @staticmethod
    def _latest_task(items: list[dict[str, object]], task_type: str) -> dict[str, Any] | None:
        """返回最近一个指定类型任务。"""

        for item in items:
            if str(item.get("task_type", "")) == task_type:
                return item
        return None

    @staticmethod
    def _step(key: str, status: str, detail: str) -> dict[str, str]:
        """统一步骤结构。"""

        normalized = status if status in {"completed", "succeeded", "failed", "waiting", "unavailable"} else "waiting"
        return {"key": key, "status": normalized, "detail": detail}

    @staticmethod
    def _screening_status(action: str) -> str:
        """把推荐动作映射成固定步骤状态。"""

        if action == "enter_dry_run":
            return "succeeded"
        if action == "continue_research":
            return "failed"
        if action == "run_inference":
            return "waiting"
        if action == "run_training":
            return "waiting"
        return "waiting"

    @staticmethod
    def _resolve_workflow_status(steps: list[dict[str, str]]) -> str:
        """根据步骤状态收敛当前工作流状态。"""

        if any(item["status"] == "failed" for item in steps):
            return "attention_required"
        if all(item["status"] in {"completed", "succeeded", "waiting"} for item in steps):
            return "in_progress"
        return "unknown"


validation_workflow_service = ValidationWorkflowService()
