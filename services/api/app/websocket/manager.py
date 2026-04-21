"""WebSocket 连接管理器，负责管理所有活跃连接和通道订阅。"""

from __future__ import annotations

import asyncio
import json
import logging
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Callable

from fastapi import WebSocket, WebSocketDisconnect


logger = logging.getLogger(__name__)


class ConnectionManager:
    """管理 WebSocket 连接和通道订阅。"""

    def __init__(self) -> None:
        # 存储所有活跃连接
        self._active_connections: list[WebSocket] = []
        # 通道订阅映射：channel_name -> set[WebSocket]
        self._channel_subscribers: dict[str, set[WebSocket]] = defaultdict(set)
        # 异步事件循环引用（从同步服务调用时使用）
        self._loop: asyncio.AbstractEventLoop | None = None

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """设置事件循环引用，用于从同步代码调度异步推送。"""
        self._loop = loop

    async def connect(self, websocket: WebSocket) -> None:
        """接受新连接并注册到活跃列表。"""
        await websocket.accept()
        self._active_connections.append(websocket)
        logger.info(f"WebSocket 连接已建立，当前活跃连接数: {len(self._active_connections)}")

    async def disconnect(self, websocket: WebSocket) -> None:
        """移除连接并清理所有订阅。"""
        if websocket in self._active_connections:
            self._active_connections.remove(websocket)
        # 清理所有通道订阅
        for channel_subscribers in self._channel_subscribers.values():
            channel_subscribers.discard(websocket)
        logger.info(f"WebSocket 连接已断开，当前活跃连接数: {len(self._active_connections)}")

    async def subscribe(self, websocket: WebSocket, channel: str) -> None:
        """订阅指定通道。"""
        self._channel_subscribers[channel].add(websocket)
        logger.info(f"连接已订阅通道: {channel}")

    async def unsubscribe(self, websocket: WebSocket, channel: str) -> None:
        """取消订阅指定通道。"""
        self._channel_subscribers[channel].discard(websocket)
        logger.info(f"连接已取消订阅通道: {channel}")

    async def broadcast_to_channel(self, channel: str, message: dict[str, Any]) -> None:
        """向指定通道的所有订阅者广播消息。"""
        subscribers = self._channel_subscribers.get(channel, set())
        if not subscribers:
            return

        payload = json.dumps({
            "channel": channel,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": message,
        }, ensure_ascii=False)

        disconnected: list[WebSocket] = []
        for websocket in subscribers:
            try:
                await websocket.send_text(payload)
            except Exception as exc:
                logger.warning(f"推送消息失败: {exc}")
                disconnected.append(websocket)

        # 清理断开的连接
        for ws in disconnected:
            await self.disconnect(ws)

    async def broadcast_to_all(self, message: dict[str, Any]) -> None:
        """向所有活跃连接广播消息。"""
        if not self._active_connections:
            return

        payload = json.dumps({
            "channel": "broadcast",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": message,
        }, ensure_ascii=False)

        disconnected: list[WebSocket] = []
        for websocket in self._active_connections:
            try:
                await websocket.send_text(payload)
            except Exception as exc:
                logger.warning(f"推送消息失败: {exc}")
                disconnected.append(websocket)

        for ws in disconnected:
            await self.disconnect(ws)

    def schedule_push(self, channel: str, message: dict[str, Any]) -> None:
        """从同步代码调度异步推送（线程安全）。"""
        if self._loop is None:
            logger.warning("事件循环未设置，无法调度推送")
            return

        # 使用 call_soon_threadsafe 在主事件循环中调度推送
        asyncio.run_coroutine_threadsafe(
            self.broadcast_to_channel(channel, message),
            self._loop
        )

    @asynccontextmanager
    async def managed_connection(self, websocket: WebSocket):
        """连接生命周期管理上下文。"""
        await self.connect(websocket)
        try:
            yield websocket
        finally:
            await self.disconnect(websocket)


# 全局单例
connection_manager = ConnectionManager()