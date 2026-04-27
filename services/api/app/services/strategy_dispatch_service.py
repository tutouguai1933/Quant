"""策略派发服务。

这个文件负责把"认领信号 -> 风控熔断 -> 风控 -> 执行 -> 同步"收成一条统一链路。
"""

from __future__ import annotations

import logging

from services.api.app.services.alert_push_service import (
    AlertEventType,
    AlertLevel,
    AlertMessage,
    alert_push_service,
    push_open_position_alert,
    push_close_position_alert,
)
from services.api.app.services.execution_service import execution_service
from services.api.app.services.risk_guard_service import risk_guard_service
from services.api.app.services.risk_service import risk_service
from services.api.app.services.signal_service import signal_service
from services.api.app.services.sync_service import sync_service
from services.api.app.tasks.scheduler import task_scheduler

logger = logging.getLogger(__name__)


class StrategyDispatchService:
    """统一封装策略派发，供路由和自动化流程复用。"""

    def dispatch_latest_signal(self, strategy_id: int, *, source: str = "system") -> dict[str, object]:
        """派发一条最新可执行信号。"""

        # 首先执行风控熔断检查
        risk_guard_result = risk_guard_service.check_all(strategy_id=strategy_id)
        if not risk_guard_result.get("passed"):
            error_message = str(risk_guard_result.get("summary") or "risk guard blocked")
            logger.warning("风控熔断检查未通过: %s", error_message)
            # 推送熔断告警
            try:
                alert_push_service.push_sync(
                    AlertMessage(
                        event_type=AlertEventType.RISK_ALERT,
                        level=AlertLevel.CRITICAL,
                        title="风控熔断触发",
                        message=error_message,
                        details={
                            "strategy_id": strategy_id,
                            "checks": risk_guard_result.get("checks", []),
                            "circuit_breaker_state": risk_guard_result.get("circuit_breaker_state", {}),
                        },
                    )
                )
            except Exception as alert_exc:
                logger.warning("熔断告警推送失败: %s", alert_exc)
            return {
                "status": "blocked",
                "error_code": "risk_guard_blocked",
                "message": error_message,
                "risk_guard_result": risk_guard_result,
                "risk_task": None,
                "sync_task": None,
            }

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
            # 推送执行失败告警
            try:
                alert_push_service.push_sync(
                    AlertMessage(
                        event_type=AlertEventType.SYSTEM_ERROR,
                        level=AlertLevel.ERROR,
                        title="交易执行失败",
                        message=f"信号 {latest['signal_id']} 执行失败: {exc}",
                        details={
                            "signal_id": int(latest["signal_id"]),
                            "strategy_id": strategy_id,
                            "error": str(exc)[:200],
                        },
                    )
                )
            except Exception as alert_exc:
                logger.warning("告警推送失败: %s", alert_exc)
            return {
                "status": "failed",
                "error_code": "execution_failed",
                "message": str(exc),
                "risk_task": risk_task,
                "sync_task": None,
            }

        signal_service.update_signal_status(int(latest["signal_id"]), "dispatched")

        # 记录交易计数，用于风控熔断
        risk_guard_service.increment_trade_count()

        # 推送交易执行告警
        try:
            action = result.get("action", {})
            symbol = str(action.get("symbol", "unknown"))
            side = str(action.get("side", "unknown"))
            quantity = action.get("quantity") or action.get("stake_amount") or "0"
            runtime = result.get("runtime", {})
            mode = str(runtime.get("mode", "unknown"))

            if side.lower() == "flat":
                push_close_position_alert(
                    symbol=symbol,
                    side=side,
                    quantity=quantity,
                    reason="signal_dispatch",
                )
            else:
                push_open_position_alert(
                    symbol=symbol,
                    side=side,
                    quantity=quantity,
                    strategy_id=strategy_id,
                    signal_id=int(latest["signal_id"]),
                )
            logger.info("已推送交易告警: %s %s %s", symbol, side, quantity)
        except Exception as alert_exc:
            logger.warning("告警推送失败: %s", alert_exc)
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