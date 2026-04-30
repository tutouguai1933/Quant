"""WebSocket module for real-time status push."""

from services.api.app.websocket.manager import connection_manager
from services.api.app.websocket.channels import (
    CHANNEL_RESEARCH_RUNTIME,
    CHANNEL_AUTOMATION_STATUS,
)

__all__ = [
    "connection_manager",
    "CHANNEL_RESEARCH_RUNTIME",
    "CHANNEL_AUTOMATION_STATUS",
]
