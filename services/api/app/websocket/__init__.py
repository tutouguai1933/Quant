"""WebSocket 模块，提供实时状态推送。"""

from services.api.app.websocket.channels import (
    CHANNEL_RESEARCH_RUNTIME,
    CHANNEL_AUTOMATION_STATUS,
    CHANNEL_SYSTEM_HEALTH,
)
from services.api.app.websocket.manager import connection_manager
from services.api.app.websocket.push_bridge import push_bridge

__all__ = [
    "CHANNEL_RESEARCH_RUNTIME",
    "CHANNEL_AUTOMATION_STATUS",
    "CHANNEL_SYSTEM_HEALTH",
    "connection_manager",
    "push_bridge",
]