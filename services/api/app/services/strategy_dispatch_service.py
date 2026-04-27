"""策略派发服务。

这个文件负责把"认领信号 -> 风控熔断 -> 风控 -> 执行 -> 同步"收成一条统一链路。
"""

from __future__ import annotations

import logging
from decimal import Decimal

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
from services.api.app.services.strategy_engine_service import (
    strategy_engine_service,
    EntryDecision,
    PositionState,
)
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

        # 策略引擎入场评分验证
        symbol = str(latest.get("symbol", ""))
        signal_side = str(latest.get("side", "long"))
        signal_score = self._parse_signal_score(latest.get("score"))

        entry_decision = strategy_engine_service.calculate_entry_score(
            symbol=symbol,
            signal_side=signal_side,
            signal_score=signal_score,
        )

        if not entry_decision.allowed:
            signal_service.release_dispatch_claim(int(latest["signal_id"]))
            logger.warning(
                "策略引擎入场验证未通过: %s, 原因: %s",
                symbol,
                entry_decision.reason,
            )
            return {
                "status": "blocked",
                "error_code": "strategy_engine_blocked",
                "message": entry_decision.reason,
                "entry_decision": entry_decision.to_dict(),
                "risk_task": None,
                "sync_task": None,
            }

        logger.info(
            "策略引擎入场验证通过: %s, 评分 %.4f, 建议仓位 %.2f%%",
            symbol,
            float(entry_decision.score),
            float(entry_decision.suggested_position_ratio * 100),
        )

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

        # 注册持仓到策略引擎（开仓时）
        action = result.get("action", {})
        result_side = str(action.get("side", "unknown")).strip().lower()
        if result_side != "flat":
            self._register_position_from_execution(
                action=action,
                result=result,
                strategy_id=strategy_id,
                signal_id=int(latest["signal_id"]),
                entry_score=entry_decision.score,
            )

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
            "entry_decision": entry_decision.to_dict(),
        }

    def monitor_positions(self) -> dict[str, object]:
        """监控所有持仓，检查退出条件并触发退出。"""
        monitoring_results = strategy_engine_service.monitor_all_positions()

        exit_triggered: list[dict[str, object]] = []
        for item in monitoring_results:
            exit_decision = item.get("exit_decision", {})
            if not isinstance(exit_decision, dict):
                continue

            should_exit = bool(exit_decision.get("should_exit"))
            if should_exit:
                symbol = str(item.get("symbol", ""))
                exit_result = self._trigger_position_exit(
                    symbol=symbol,
                    reason=str(exit_decision.get("reason", "策略引擎触发退出")),
                )
                exit_triggered.append({
                    "symbol": symbol,
                    "exit_decision": exit_decision,
                    "exit_result": exit_result,
                })

                # 推送退出告警
                try:
                    position = item.get("position", {})
                    if isinstance(position, dict):
                        push_close_position_alert(
                            symbol=symbol,
                            side=str(position.get("side", "flat")),
                            quantity=str(position.get("quantity", "0")),
                            reason=str(exit_decision.get("reason", "策略引擎触发退出")),
                        )
                except Exception as alert_exc:
                    logger.warning("退出告警推送失败: %s", alert_exc)

        return {
            "status": "monitored",
            "total_positions": len(monitoring_results),
            "exit_triggered": exit_triggered,
            "details": monitoring_results,
        }

    def _register_position_from_execution(
        self,
        *,
        action: dict[str, object],
        result: dict[str, object],
        strategy_id: int,
        signal_id: int,
        entry_score: Decimal,
    ) -> PositionState | None:
        """从执行结果注册持仓。"""
        symbol = str(action.get("symbol", "")).strip().upper()
        side = str(action.get("side", "long")).strip().lower()

        if side == "flat":
            strategy_engine_service.remove_position(symbol)
            return None

        # 获取入场价格
        order = result.get("order", {})
        raw_price = order.get("avgPrice") or order.get("price") or action.get("price")
        entry_price = self._parse_decimal(raw_price)
        if entry_price is None:
            logger.warning("无法解析入场价格: %s, 使用默认值", raw_price)
            entry_price = Decimal("0")

        # 获取数量
        raw_quantity = order.get("quantity") or order.get("executedQty") or action.get("quantity")
        quantity = self._parse_decimal(raw_quantity)
        if quantity is None:
            quantity = Decimal("0")

        # 计算动态止损
        dynamic_stop_pct = strategy_engine_service.calculate_dynamic_stop_loss(
            symbol=symbol,
            score=entry_score,
        )

        position = strategy_engine_service.register_position(
            symbol=symbol,
            entry_price=entry_price,
            quantity=quantity,
            side=side,
            strategy_id=strategy_id,
            signal_id=signal_id,
            research_score=entry_score,
            initial_stop_pct=dynamic_stop_pct,
        )

        logger.info(
            "持仓已注册: %s %s @ %s, 止损 %.2f%%",
            side,
            symbol,
            str(entry_price),
            float(dynamic_stop_pct * 100),
        )

        return position

    def _trigger_position_exit(self, symbol: str, reason: str) -> dict[str, object]:
        """触发持仓退出。"""
        position = strategy_engine_service.get_position(symbol)
        if position is None:
            return {"status": "no_position", "message": f"无 {symbol} 持仓"}

        try:
            # 构建平仓信号
            signal_payload = {
                "symbol": symbol,
                "side": "flat",
                "score": str(position.research_score),
                "confidence": "1.0",
                "target_weight": "0",
                "generated_at": strategy_engine_service._position_states.get(symbol).entry_time.isoformat()
                if strategy_engine_service._position_states.get(symbol)
                else "",
                "source": "strategy_engine",
                "strategy_id": position.strategy_id,
            }
            signal = signal_service.ingest_signal(signal_payload)

            # 执行平仓
            result = execution_service.dispatch_signal(
                int(signal["signal_id"]),
                strategy_context_id=position.strategy_id,
            )

            # 移除持仓记录
            strategy_engine_service.remove_position(symbol)

            return {
                "status": "succeeded",
                "signal": signal,
                "execution": result,
                "reason": reason,
            }
        except Exception as exc:
            logger.error("触发退出失败: %s, 错误: %s", symbol, exc)
            return {
                "status": "failed",
                "message": str(exc),
                "reason": reason,
            }

    @staticmethod
    def _parse_signal_score(value: object) -> Decimal | None:
        """解析信号评分。"""
        if value is None:
            return None
        try:
            score = Decimal(str(value))
            if not score.is_finite():
                return None
            return score
        except Exception:
            return None

    @staticmethod
    def _parse_decimal(value: object) -> Decimal | None:
        """解析 Decimal 值。"""
        if value is None:
            return None
        try:
            parsed = Decimal(str(value))
            if not parsed.is_finite():
                return None
            return parsed
        except Exception:
            return None


strategy_dispatch_service = StrategyDispatchService()