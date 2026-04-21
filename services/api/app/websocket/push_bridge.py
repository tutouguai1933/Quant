"""状态变更推送桥接，将同步服务的状态变更转发到 WebSocket。"""

from __future__ import annotations

import logging
from typing import Any

from services.api.app.websocket.manager import connection_manager
from services.api.app.websocket.channels import (
    CHANNEL_RESEARCH_RUNTIME,
    CHANNEL_AUTOMATION_STATUS,
)

logger = logging.getLogger(__name__)


class PushBridge:
    """桥接同步服务状态变更到 WebSocket 推送。"""

    @staticmethod
    def push_research_runtime_update(
        *,
        status: str,
        action: str,
        current_stage: str,
        progress_pct: int,
        message: str,
        **extra: Any,
    ) -> None:
        """推送研究运行时状态变更。"""

        payload = {
            "status": status,
            "action": action,
            "current_stage": current_stage,
            "progress_pct": progress_pct,
            "message": message,
            **extra,
        }

        connection_manager.schedule_push(CHANNEL_RESEARCH_RUNTIME, payload)
        logger.debug(f"研究运行时状态推送: {status}/{current_stage} ({progress_pct}%)")

    @staticmethod
    def push_research_runtime_complete(
        *,
        action: str,
        status: str,
        message: str,
        finished_at: str,
        **extra: Any,
    ) -> None:
        """推送研究任务完成状态。"""

        payload = {
            "status": status,
            "action": action,
            "current_stage": "completed" if status == "succeeded" else "failed",
            "progress_pct": 100,
            "message": message,
            "finished_at": finished_at,
            **extra,
        }

        connection_manager.schedule_push(CHANNEL_RESEARCH_RUNTIME, payload)
        logger.info(f"研究任务完成推送: {action} -> {status}")

    @staticmethod
    def push_automation_cycle_update(
        *,
        status: str,
        mode: str,
        recommended_symbol: str,
        next_action: str,
        message: str,
        **extra: Any,
    ) -> None:
        """推送自动化周期状态变更。"""

        payload = {
            "status": status,
            "mode": mode,
            "recommended_symbol": recommended_symbol,
            "next_action": next_action,
            "message": message,
            **extra,
        }

        connection_manager.schedule_push(CHANNEL_AUTOMATION_STATUS, payload)
        logger.debug(f"自动化周期状态推送: {status}/{mode}")

    @staticmethod
    def push_automation_alert(
        *,
        level: str,
        code: str,
        message: str,
        source: str,
        detail: str = "",
    ) -> None:
        """推送自动化告警。"""

        payload = {
            "type": "alert",
            "level": level,
            "code": code,
            "message": message,
            "source": source,
            "detail": detail,
        }

        connection_manager.schedule_push(CHANNEL_AUTOMATION_STATUS, payload)
        logger.info(f"自动化告警推送: {level}/{code}")


# 全局单例
push_bridge = PushBridge()