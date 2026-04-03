# 워커 로컬 WebSocket 세션. 유저당 다중 소켓(탭·기기). 분산 전달은 Redis → 본 모듈 send.
from __future__ import annotations

import asyncio
import logging
from typing import Any
from uuid import UUID

from starlette.websockets import WebSocket, WebSocketDisconnect

log = logging.getLogger(__name__)


class ConnectionManager:
    """인스턴스(워커) 단위. `user_id` → 해당 유저에 붙은 모든 WebSocket."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._by_user: dict[UUID, set[WebSocket]] = {}

    async def connect(self, user_id: UUID, ws: WebSocket) -> None:
        async with self._lock:
            if user_id not in self._by_user:
                self._by_user[user_id] = set()
            self._by_user[user_id].add(ws)

    async def disconnect(self, user_id: UUID, ws: WebSocket) -> None:
        async with self._lock:
            bucket = self._by_user.get(user_id)
            if not bucket:
                return
            bucket.discard(ws)
            if not bucket:
                del self._by_user[user_id]

    async def send_personal_message(self, user_id: UUID, message: str | dict[str, Any]) -> None:
        async with self._lock:
            sockets = list(self._by_user.get(user_id, ()))
        for ws in sockets:
            try:
                if isinstance(message, dict):
                    await ws.send_json(message)
                else:
                    await ws.send_text(message)
            except (WebSocketDisconnect, RuntimeError, OSError) as e:
                log.debug("chat ws send skip disconnect user=%s: %s", user_id, e)
                await self.disconnect(user_id, ws)
            except Exception:
                log.exception("chat ws send error user=%s", user_id)
                await self.disconnect(user_id, ws)


chat_connection_manager = ConnectionManager()
