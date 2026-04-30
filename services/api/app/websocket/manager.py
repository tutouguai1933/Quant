"""WebSocket connection manager for real-time status push."""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class WebSocketConnection:
    """WebSocket connection info."""
    websocket: Any
    channels: set[str] = field(default_factory=set)
    connected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class ConnectionManager:
    """WebSocket connection manager with channel subscription support."""

    def __init__(self) -> None:
        self._connections: dict[str, WebSocketConnection] = {}
        self._lock = threading.RLock()
        self._loop: asyncio.AbstractEventLoop | None = None

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Set the main event loop for async operations from sync context."""
        self._loop = loop

    def connect(self, websocket: Any, connection_id: str) -> None:
        """Register a new WebSocket connection."""
        with self._lock:
            self._connections[connection_id] = WebSocketConnection(
                websocket=websocket,
                channels=set(),
            )
            logger.info("WebSocket connected: %s", connection_id)

    def disconnect(self, connection_id: str) -> None:
        """Remove a WebSocket connection."""
        with self._lock:
            if connection_id in self._connections:
                del self._connections[connection_id]
                logger.info("WebSocket disconnected: %s", connection_id)

    def subscribe(self, connection_id: str, channel: str) -> bool:
        """Subscribe a connection to a channel."""
        from services.api.app.websocket.channels import ALL_CHANNELS

        if channel not in ALL_CHANNELS:
            logger.warning("Unknown channel: %s", channel)
            return False

        with self._lock:
            conn = self._connections.get(connection_id)
            if conn is None:
                logger.warning("Connection not found: %s", connection_id)
                return False
            conn.channels.add(channel)
            logger.info("Subscribed %s to channel: %s", connection_id, channel)
            return True

    def unsubscribe(self, connection_id: str, channel: str) -> bool:
        """Unsubscribe a connection from a channel."""
        with self._lock:
            conn = self._connections.get(connection_id)
            if conn is None:
                return False
            if channel in conn.channels:
                conn.channels.remove(channel)
                logger.info("Unsubscribed %s from channel: %s", connection_id, channel)
            return True

    def schedule_push(self, channel: str, message: dict[str, Any]) -> None:
        """Schedule an async broadcast from sync context."""
        if self._loop is None:
            logger.warning("Event loop not set, cannot push")
            return

        asyncio.run_coroutine_threadsafe(
            self.broadcast_to_channel(channel, message),
            self._loop,
        )

    async def broadcast_to_channel(self, channel: str, message: dict[str, Any]) -> None:
        """Broadcast message to all connections subscribed to a channel."""
        with self._lock:
            connections_to_notify = [
                (conn_id, conn)
                for conn_id, conn in self._connections.items()
                if channel in conn.channels
            ]

        if not connections_to_notify:
            logger.debug("No connections subscribed to channel: %s", channel)
            return

        message_json = json.dumps({
            "channel": channel,
            "data": message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        for conn_id, conn in connections_to_notify:
            try:
                await conn.websocket.send_text(message_json)
                logger.debug("Pushed to %s on channel %s", conn_id, channel)
            except Exception as e:
                logger.warning("Failed to push to %s: %s", conn_id, e)

    async def send_to_connection(self, connection_id: str, message: dict[str, Any]) -> bool:
        """Send message to a specific connection."""
        with self._lock:
            conn = self._connections.get(connection_id)

        if conn is None:
            logger.warning("Connection not found: %s", connection_id)
            return False

        try:
            message_json = json.dumps(message)
            await conn.websocket.send_text(message_json)
            return True
        except Exception as e:
            logger.warning("Failed to send to %s: %s", connection_id, e)
            return False

    def get_connection_count(self) -> int:
        """Get total number of connections."""
        with self._lock:
            return len(self._connections)

    def get_channel_subscribers(self, channel: str) -> list[str]:
        """Get list of connection IDs subscribed to a channel."""
        with self._lock:
            return [
                conn_id
                for conn_id, conn in self._connections.items()
                if channel in conn.channels
            ]


# Global connection manager instance
connection_manager = ConnectionManager()
