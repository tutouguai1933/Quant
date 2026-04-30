"""WebSocket 路由端点。"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from services.api.app.websocket.manager import connection_manager
from services.api.app.websocket.channels import (
    CHANNEL_RESEARCH_RUNTIME,
    CHANNEL_AUTOMATION_STATUS,
    CHANNEL_SYSTEM_HEALTH,
    is_valid_channel,
)
from services.api.app.services.automation_service import automation_service
from services.api.app.services.research_runtime_service import research_runtime_service
from services.api.app.services.auth_service import auth_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])


async def _verify_ws_token(token: str) -> bool:
    """验证WebSocket连接的token。"""
    if not token:
        return False
    session = auth_service.get_session(token)
    return session is not None and session.get("scope") == "control_plane"


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(default="", description="认证令牌"),
) -> None:
    """主 WebSocket 端点，支持多通道订阅。"""

    # 认证验证
    if not await _verify_ws_token(token):
        await websocket.close(code=1008, reason="unauthorized")
        return

    async with connection_manager.managed_connection(websocket):
        try:
            while True:
                # 接收客户端消息（订阅/取消订阅请求）
                raw_message = await websocket.receive_text()

                try:
                    message = json.loads(raw_message)
                    action = message.get("action", "")
                    channel = message.get("channel", "")

                    # 通道白名单验证
                    if channel and not is_valid_channel(channel):
                        await websocket.send_text(json.dumps({
                            "type": "error",
                            "message": f"invalid channel: {channel}",
                        }, ensure_ascii=False))
                        continue

                    if action == "subscribe" and channel:
                        await connection_manager.subscribe(websocket, channel)
                        # 订阅后立即发送当前状态
                        await _send_initial_state(websocket, channel)
                        await websocket.send_text(json.dumps({
                            "type": "subscribed",
                            "channel": channel,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }, ensure_ascii=False))

                    elif action == "unsubscribe" and channel:
                        await connection_manager.unsubscribe(websocket, channel)
                        await websocket.send_text(json.dumps({
                            "type": "unsubscribed",
                            "channel": channel,
                        }, ensure_ascii=False))

                    elif action == "ping":
                        await websocket.send_text(json.dumps({"type": "pong"}, ensure_ascii=False))

                except json.JSONDecodeError:
                    logger.warning(f"无效的 WebSocket 消息: {raw_message}")
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": "invalid JSON format",
                    }, ensure_ascii=False))

        except WebSocketDisconnect:
            logger.info("客户端主动断开连接")
        except Exception as exc:
            logger.error(f"WebSocket 异常: {exc}")


async def _send_initial_state(websocket: WebSocket, channel: str) -> None:
    """订阅后发送当前状态。"""

    if channel == CHANNEL_RESEARCH_RUNTIME:
        status = research_runtime_service.get_status()
        await websocket.send_text(json.dumps({
            "channel": channel,
            "type": "initial",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": status,
        }, ensure_ascii=False))

    elif channel == CHANNEL_AUTOMATION_STATUS:
        status = automation_service.get_status()
        await websocket.send_text(json.dumps({
            "channel": channel,
            "type": "initial",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": status,
        }, ensure_ascii=False))


@router.websocket("/ws/research_runtime")
async def research_runtime_websocket(
    websocket: WebSocket,
    token: str = Query(default="", description="认证令牌"),
) -> None:
    """研究运行时状态专用 WebSocket 端点（简化版）。"""

    # 认证验证
    if not await _verify_ws_token(token):
        await websocket.close(code=1008, reason="unauthorized")
        return

    await connection_manager.connect(websocket)
    await connection_manager.subscribe(websocket, CHANNEL_RESEARCH_RUNTIME)

    # 发送当前状态
    status = research_runtime_service.get_status()
    await websocket.send_text(json.dumps({
        "channel": CHANNEL_RESEARCH_RUNTIME,
        "type": "initial",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": status,
    }, ensure_ascii=False))

    try:
        while True:
            # 保持连接，等待服务端推送
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        pass
    finally:
        await connection_manager.unsubscribe(websocket, CHANNEL_RESEARCH_RUNTIME)
        await connection_manager.disconnect(websocket)


@router.websocket("/ws/automation")
async def automation_websocket(
    websocket: WebSocket,
    token: str = Query(default="", description="认证令牌"),
) -> None:
    """自动化状态专用 WebSocket 端点（简化版）。"""

    # 认证验证
    if not await _verify_ws_token(token):
        await websocket.close(code=1008, reason="unauthorized")
        return

    await connection_manager.connect(websocket)
    await connection_manager.subscribe(websocket, CHANNEL_AUTOMATION_STATUS)

    # 发送当前状态
    status = automation_service.get_status()
    await websocket.send_text(json.dumps({
        "channel": CHANNEL_AUTOMATION_STATUS,
        "type": "initial",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": status,
    }, ensure_ascii=False))

    try:
        while True:
            # 保持连接，等待服务端推送
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        pass
    finally:
        await connection_manager.unsubscribe(websocket, CHANNEL_AUTOMATION_STATUS)
        await connection_manager.disconnect(websocket)