"""WebSocket route for real-time status push."""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from services.api.app.websocket.manager import connection_manager
from services.api.app.websocket.channels import ALL_CHANNELS

logger = logging.getLogger(__name__)


try:
    from fastapi import APIRouter, WebSocket, WebSocketDisconnect
except ImportError:
    # Lightweight fallback for testing
    class APIRouter:
        def __init__(self, *args, **kwargs) -> None:
            pass

    class WebSocket:
        def __init__(self) -> None:
            pass

        async def accept(self) -> None:
            pass

        async def receive_text(self) -> str:
            return ""

        async def send_text(self, text: str) -> None:
            pass

    class WebSocketDisconnect(Exception):
        pass


router = APIRouter(tags=["websocket"])


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """WebSocket endpoint for real-time status updates."""
    await websocket.accept()
    connection_id = str(uuid.uuid4())
    connection_manager.connect(websocket, connection_id)

    try:
        # Send connection established message
        await connection_manager.send_to_connection(connection_id, {
            "type": "connected",
            "connection_id": connection_id,
            "available_channels": ALL_CHANNELS,
        })

        while True:
            try:
                data = await websocket.receive_text()
                message = json.loads(data)
                await handle_message(connection_id, websocket, message)
            except json.JSONDecodeError:
                await connection_manager.send_to_connection(connection_id, {
                    "type": "error",
                    "message": "Invalid JSON format",
                })
    except WebSocketDisconnect:
        connection_manager.disconnect(connection_id)
        logger.info("WebSocket client disconnected: %s", connection_id)
    except Exception as e:
        logger.error("WebSocket error for %s: %s", connection_id, e)
        connection_manager.disconnect(connection_id)


async def handle_message(connection_id: str, websocket: WebSocket, message: dict[str, Any]) -> None:
    """Handle incoming WebSocket message."""
    msg_type = message.get("type", "")

    if msg_type == "subscribe":
        channel = message.get("channel", "")
        if connection_manager.subscribe(connection_id, channel):
            await connection_manager.send_to_connection(connection_id, {
                "type": "subscribed",
                "channel": channel,
                "success": True,
            })
        else:
            await connection_manager.send_to_connection(connection_id, {
                "type": "subscribed",
                "channel": channel,
                "success": False,
                "error": "Invalid channel or connection",
            })

    elif msg_type == "unsubscribe":
        channel = message.get("channel", "")
        connection_manager.unsubscribe(connection_id, channel)
        await connection_manager.send_to_connection(connection_id, {
            "type": "unsubscribed",
            "channel": channel,
        })

    elif msg_type == "ping":
        await connection_manager.send_to_connection(connection_id, {
            "type": "pong",
        })

    elif msg_type == "get_status":
        await connection_manager.send_to_connection(connection_id, {
            "type": "status",
            "connection_count": connection_manager.get_connection_count(),
            "subscribed_channels": list(
                connection_manager._connections.get(connection_id, {}).channels
            ) if connection_id in connection_manager._connections else [],
        })

    else:
        await connection_manager.send_to_connection(connection_id, {
            "type": "error",
            "message": f"Unknown message type: {msg_type}",
        })
