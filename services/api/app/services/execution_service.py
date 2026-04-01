"""Execution mapping service for Quant phase 1."""

from __future__ import annotations

import os
from decimal import Decimal

from services.api.app.adapters.freqtrade.client import freqtrade_client
from services.api.app.core.settings import Settings
from services.api.app.domain.contracts import ExecutionActionContract, ExecutionActionType
from services.api.app.services.signal_service import signal_service


class ExecutionService:
    """Maps control-plane signals to execution actions."""

    def build_execution_action(self, signal_id: int) -> dict[str, object]:
        signal = signal_service.get_signal(signal_id)
        if signal is None:
            raise ValueError(f"signal {signal_id} not found")

        side = signal["side"]
        action_type = self._resolve_action_type(str(side))
        quantity = self._resolve_quantity(str(signal["target_weight"]))

        action = ExecutionActionContract(
            action_type=action_type,
            symbol=str(signal["symbol"]),
            side=side,
            quantity=quantity,
            source_signal_id=signal_id,
            strategy_id=signal.get("strategy_id"),
            account_id=1,
        )
        return action.to_dict()

    def dispatch_signal(self, signal_id: int) -> dict[str, object]:
        settings = Settings.from_env()
        runtime_mode = settings.runtime_mode
        runtime_snapshot = freqtrade_client.get_runtime_snapshot()
        if runtime_mode == "dry-run":
            if settings.has_freqtrade_rest_config():
                if runtime_snapshot.get("backend") != "rest":
                    raise PermissionError("dry-run 模式下检测到 Freqtrade 配置，但执行器没有切到 REST 后端")
                if runtime_snapshot.get("connection_status") != "connected":
                    raise PermissionError("dry-run 模式下无法确认远端 Freqtrade 连接状态")
                if runtime_snapshot.get("mode") != "dry-run":
                    raise PermissionError("dry-run 模式下远端 Freqtrade 没有切到 dry-run 运行模式")
            elif runtime_snapshot.get("mode") != "dry-run":
                raise PermissionError("dry-run 模式下执行器没有切到 dry-run 运行模式")
        if runtime_mode == "live":
            if not self._allow_live_execution():
                raise PermissionError("live 模式下需要设置 QUANT_ALLOW_LIVE_EXECUTION=true 才允许执行")
            raise NotImplementedError("Phase A 当前还没有接通真实 live 执行器，请继续使用 dry-run")

        action = self.build_execution_action(signal_id)
        order = freqtrade_client.submit_execution_action(action)
        return {
            "action": action,
            "order": order,
            "runtime": runtime_snapshot,
        }

    @staticmethod
    def _resolve_action_type(side: str) -> ExecutionActionType:
        if side == "flat":
            return ExecutionActionType.CLOSE_POSITION
        return ExecutionActionType.OPEN_POSITION

    @staticmethod
    def _resolve_quantity(target_weight: str) -> Decimal:
        weight = Decimal(target_weight).copy_abs()
        base_quantity = Decimal("0.0400000000")
        quantity = max(Decimal("0.0010000000"), weight * base_quantity)
        return quantity.quantize(Decimal("0.0000000001"))

    @staticmethod
    def _allow_live_execution() -> bool:
        return os.getenv("QUANT_ALLOW_LIVE_EXECUTION", "").strip().lower() == "true"


execution_service = ExecutionService()
