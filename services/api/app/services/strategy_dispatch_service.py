"""策略派发服务。

这个文件负责把“认领信号 -> 风控 -> 执行 -> 同步”收成一条统一链路。
"""

from __future__ import annotations

from services.api.app.services.execution_service import execution_service
from services.api.app.services.risk_service import risk_service
from services.api.app.services.signal_service import signal_service
from services.api.app.services.sync_service import sync_service
from services.api.app.tasks.scheduler import task_scheduler


class StrategyDispatchService:
    """统一封装策略派发，供路由和自动化流程复用。"""

    def dispatch_latest_signal(self, strategy_id: int, *, source: str = "system") -> dict[str, object]:
        """派发一条最新可执行信号。"""

        latest = signal_service.claim_latest_dispatchable_signal(strategy_id)
        if latest is None:
            return {
                "status": "blocked",
                "error_code": "signal_not_ready",
                "message": f"no pending signal available for strategy {strategy_id}",
                "risk_task": None,
                "sync_task": None,
            }

        risk_task = task_scheduler.run_custom_task(
            task_type="risk_check",
            source=source,
            target_type="signal",
            target_id=int(latest["signal_id"]),
            payload={"strategy_id": strategy_id},
            runner=lambda: risk_service.evaluate_signal(int(latest["signal_id"]), strategy_context_id=strategy_id),
        )
        if not isinstance(risk_task, dict):
            risk_task = {}
        decision = risk_task.get("result")
        risk_task_status = str(risk_task.get("status") or "").strip().lower()
        if risk_task_status != "succeeded":
            signal_service.release_dispatch_claim(int(latest["signal_id"]))
            error_message = str(risk_task.get("error_message") or "").strip()
            return {
                "status": "failed",
                "error_code": "risk_evaluation_failed",
                "message": f"risk evaluation failed: {error_message}" if error_message else "risk evaluation failed",
                "risk_task": risk_task,
                "sync_task": None,
            }
        if not isinstance(decision, dict):
            signal_service.release_dispatch_claim(int(latest["signal_id"]))
            return {
                "status": "failed",
                "error_code": "risk_evaluation_failed",
                "message": "risk evaluation failed",
                "risk_task": risk_task,
                "sync_task": None,
            }
        decision_status = str(decision.get("status") or "").strip().lower()
        if not decision_status:
            signal_service.release_dispatch_claim(int(latest["signal_id"]))
            decision_message = str(decision.get("reason") or decision.get("message") or "").strip()
            fallback_message = "risk evaluation failed: missing decision status"
            return {
                "status": "failed",
                "error_code": "risk_evaluation_failed",
                "message": f"risk evaluation failed: {decision_message}" if decision_message else fallback_message,
                "risk_task": risk_task,
                "sync_task": None,
            }
        if decision_status == "block":
            signal_service.release_dispatch_claim(int(latest["signal_id"]))
            return {
                "status": "blocked",
                "error_code": "risk_blocked",
                "message": str(decision.get("reason") or "risk blocked"),
                "risk_task": risk_task,
                "sync_task": None,
            }

        try:
            result = execution_service.dispatch_signal(int(latest["signal_id"]), strategy_context_id=strategy_id)
        except Exception as exc:
            signal_service.release_dispatch_claim(int(latest["signal_id"]))
            return {
                "status": "failed",
                "error_code": "execution_failed",
                "message": str(exc),
                "risk_task": risk_task,
                "sync_task": None,
            }

        signal_service.update_signal_status(int(latest["signal_id"]), "dispatched")
        sync_payload: dict[str, object] = {}
        if str(result.get("runtime", {}).get("mode", "")).strip().lower() == "live":
            sync_payload.update(sync_service.build_live_sync_payload(result))
        sync_payload["source_signal_id"] = int(latest["signal_id"])
        sync_task = task_scheduler.run_named_task(
            task_type="sync",
            source=source,
            target_type="strategy",
            target_id=strategy_id,
            payload=sync_payload,
        )
        if not isinstance(sync_task, dict):
            sync_task = {}
        sync_status = str(sync_task.get("status") or "").strip().lower()
        signal_service.release_dispatch_claim(int(latest["signal_id"]))
        if sync_status != "succeeded":
            error_message = str(sync_task.get("error_message") or "").strip()
            return {
                "status": "failed",
                "error_code": "sync_failed",
                "message": f"sync failed: {error_message}" if error_message else "sync failed",
                "signal": latest,
                "item": result,
                "risk_decision": decision,
                "risk_task": risk_task,
                "sync_task": sync_task,
            }
        return {
            "status": "succeeded",
            "signal": latest,
            "item": result,
            "risk_decision": decision,
            "risk_task": risk_task,
            "sync_task": sync_task,
        }


strategy_dispatch_service = StrategyDispatchService()
