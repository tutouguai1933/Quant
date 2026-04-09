"""验证工作流复盘服务。

这个文件把研究、执行和任务状态整理成一份固定复盘报告。
"""

from __future__ import annotations

from typing import Any

from services.api.app.services.automation_service import automation_service
from services.api.app.services.research_service import research_service
from services.api.app.services.sync_service import sync_service
from services.api.app.services.workbench_config_service import workbench_config_service
from services.api.app.tasks.scheduler import task_scheduler


class ValidationWorkflowService:
    """构造 dry-run -> 小额 live -> 复盘 的统一摘要。"""

    def __init__(self, *, research_reader=None, sync_reader=None, scheduler=None) -> None:
        self._research_reader = research_reader or research_service
        self._sync_reader = sync_reader or sync_service
        self._scheduler = scheduler or task_scheduler

    def build_report(self, limit: int | None = None) -> dict[str, object]:
        """返回固定验证工作流复盘。"""

        if limit is None or int(limit or 0) <= 0:
            limit = self._resolve_review_limit()
        research_report = self._research_reader.get_factory_report()
        raw_recent_tasks = self._scheduler.list_tasks(limit=limit)
        task_health = self._scheduler.get_health_summary()
        automation_state = automation_service.get_state()
        execution_health = self._sync_reader.get_execution_health_summary(
            task_health=task_health,
            automation_state=automation_state,
        )
        account_snapshot = self._build_account_snapshot(limit=limit)
        automation = {
            "state": automation_state,
            "health": automation_service.build_health_summary(task_health=task_health),
        }
        execution_comparison = self._build_execution_comparison(
            research_report=research_report,
            account_snapshot=account_snapshot,
            execution_health=execution_health,
        )
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
                "next_action": self._resolve_next_action(
                    research_report=research_report,
                    execution_health=execution_health,
                    automation_state=automation["state"],
                ),
            },
            "steps": steps,
            "research_report": research_report,
            "task_health": task_health,
            "execution_health": execution_health,
            "execution_comparison": execution_comparison,
            "reviews": self._build_reviews(
                research_report=research_report,
                execution_health=execution_health,
                execution_comparison=execution_comparison,
                automation_state=automation["state"],
            ),
            "automation": automation,
            "recent_tasks": recent_tasks,
            "account_snapshot": account_snapshot,
        }

    @staticmethod
    def _resolve_review_limit() -> int:
        """读取统一配置里的复盘条数。"""

        operations = dict(workbench_config_service.get_config().get("operations") or {})
        try:
            return max(int(operations.get("review_limit") or 10), 1)
        except (TypeError, ValueError):
            return 10

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

    def _build_execution_comparison(
        self,
        *,
        research_report: dict[str, object],
        account_snapshot: dict[str, object],
        execution_health: dict[str, object],
    ) -> dict[str, object]:
        """把研究回测结果和当前执行结果收成同一份摘要。"""

        candidate = self._pick_recommended_candidate(research_report)
        symbol = str(candidate.get("symbol", ""))
        normalized_symbol = self._normalize_symbol(symbol)
        orders = list(account_snapshot.get("orders") or [])
        positions = list(account_snapshot.get("positions") or [])
        matched_orders = [item for item in orders if self._normalize_symbol(item.get("symbol")) == normalized_symbol]
        matched_positions = [item for item in positions if self._normalize_symbol(item.get("symbol")) == normalized_symbol]
        recommended_action = str(research_report.get("overview", {}).get("recommended_action", ""))
        latest_sync_status = str(execution_health.get("latest_sync_status", ""))

        if not symbol:
            status = "unavailable"
            note = "当前没有可对照的研究候选"
        elif matched_orders or matched_positions:
            status = "matched"
            note = "当前执行结果里已经能看到和研究候选对应的订单或持仓"
        elif recommended_action == "continue_research":
            status = "waiting_research"
            note = "研究结论还没放行到执行，当前应先继续研究"
        elif latest_sync_status == "failed":
            status = "attention_required"
            note = "研究允许执行，但最近同步没有成功，需要先检查执行链"
        else:
            status = "no_execution"
            note = "研究侧已有候选，但当前执行结果里还没有看到对应动作"

        return {
            "status": status,
            "symbol": symbol,
            "recommended_action": recommended_action,
            "note": note,
            "backtest": dict(candidate.get("backtest") or {}),
            "execution": {
                "runtime_mode": str(execution_health.get("runtime_mode", "")),
                "latest_sync_status": latest_sync_status,
                "matched_order_count": len(matched_orders),
                "matched_position_count": len(matched_positions),
                "orders": matched_orders,
                "positions": matched_positions,
            },
        }

    def _build_reviews(
        self,
        *,
        research_report: dict[str, object],
        execution_health: dict[str, object],
        execution_comparison: dict[str, object],
        automation_state: dict[str, object],
    ) -> dict[str, dict[str, object]]:
        """统一给出研究、dry-run、live 三段复盘摘要。"""

        research_review = dict((research_report.get("reviews") or {}).get("research") or {})
        automation_mode = str(automation_state.get("mode", "manual"))
        runtime_mode = str(execution_health.get("runtime_mode", ""))
        latest_sync_status = str(execution_health.get("latest_sync_status", ""))

        dry_run_review = {
            "what_happened": "当前 dry-run 验证还在等待研究候选或执行结果",
            "result": "waiting",
            "next_action": "continue_dry_run",
        }
        if research_review.get("next_action") == "continue_research":
            dry_run_review = {
                "what_happened": "研究层还没有放行候选进入 dry-run",
                "result": "blocked_by_research",
                "next_action": "continue_research",
            }
        elif runtime_mode != "live" and latest_sync_status == "succeeded":
            dry_run_review = {
                "what_happened": "最近一次同步已经完成，dry-run 结果可以进入复盘",
                "result": "succeeded",
                "next_action": "review_dry_run",
            }

        live_review = {
            "what_happened": "当前还没有进入小额 live",
            "result": "waiting",
            "next_action": "wait_live",
        }
        if automation_mode == "manual" and research_review.get("next_action") == "enter_dry_run":
            live_review = {
                "what_happened": "系统当前仍在手动模式，小额 live 需要人工确认",
                "result": "manual_review",
                "next_action": "manual_review",
            }
        elif runtime_mode == "live" and execution_comparison.get("status") == "matched":
            live_review = {
                "what_happened": "当前执行结果已经和研究候选对上，小额 live 已产生可复盘结果",
                "result": "succeeded",
                "next_action": "retain_small_live",
            }
        elif runtime_mode == "live":
            live_review = {
                "what_happened": "系统已经进入 live，但这轮还没有对上可复盘执行结果",
                "result": "attention_required",
                "next_action": "check_execution",
            }

        return {
            "research": {
                "what_happened": str(research_review.get("what_happened", "")),
                "result": str(research_review.get("result", "unavailable")),
                "next_action": str(research_review.get("next_action", "")),
            },
            "dry_run": dry_run_review,
            "live": live_review,
        }

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

    @staticmethod
    def _resolve_next_action(
        *,
        research_report: dict[str, object],
        execution_health: dict[str, object],
        automation_state: dict[str, object],
    ) -> str:
        """给复盘统一输出下一步动作。"""

        if bool(automation_state.get("paused")):
            return "stop"
        recommended_action = str(research_report.get("overview", {}).get("recommended_action", ""))
        if recommended_action != "enter_dry_run":
            return "continue_research"
        automation_mode = str(automation_state.get("mode", "manual"))
        runtime_mode = str(execution_health.get("runtime_mode", ""))
        latest_sync_status = str(execution_health.get("latest_sync_status", ""))
        if automation_mode == "manual":
            return "manual_review"
        if automation_mode == "auto_live" and runtime_mode == "live" and latest_sync_status == "succeeded":
            return "retain_small_live"
        return "continue_dry_run"

    @staticmethod
    def _pick_recommended_candidate(research_report: dict[str, object]) -> dict[str, object]:
        """优先取当前推荐候选，没有则回退到排行第一名。"""

        recommended_symbol = str(research_report.get("overview", {}).get("recommended_symbol", "")).strip().upper()
        candidates = list(research_report.get("candidates") or [])
        if recommended_symbol:
            for item in candidates:
                if str(item.get("symbol", "")).strip().upper() == recommended_symbol:
                    return dict(item)
        if candidates:
            return dict(candidates[0])
        leaderboard = list(research_report.get("leaderboard") or [])
        if leaderboard:
            return dict(leaderboard[0])
        return {}

    @staticmethod
    def _normalize_symbol(value: object) -> str:
        """统一 symbol 口径，方便研究结果和执行结果对照。"""

        raw = str(value or "").strip().upper().replace("/", "")
        if raw.endswith("USDT"):
            return raw
        if raw:
            return f"{raw}USDT"
        return ""


validation_workflow_service = ValidationWorkflowService()
