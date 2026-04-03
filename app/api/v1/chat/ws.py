# 1:1 DM WebSocket. ?token= Access JWT, 메시지는 ChatService·Redis 팬아웃.
from __future__ import annotations

import json
import logging

from fastapi import APIRouter, WebSocket
from pydantic import ValidationError
from redis.asyncio import Redis
from starlette.websockets import WebSocketDisconnect

from app.chat.manager import chat_connection_manager
from app.chat.payload import parse_incoming_message, validation_error_to_ws_error
from app.chat.schema import ChatWsErrorPayload
from app.chat.service import DM_SAME_USER, ChatService
from app.chat.ws_auth import authenticate_chat_websocket
from app.common.exceptions import (
    BaseProjectException,
    ForbiddenException,
    UnauthorizedException,
    UserNotFoundException,
)
from app.db import AsyncSessionLocal

log = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])


def _redis_from_websocket(websocket: WebSocket) -> Redis | None:
    app = websocket.scope.get("app")
    raw = getattr(app.state, "redis", None) if app is not None else None
    return raw if isinstance(raw, Redis) else None


@router.websocket("/ws/chat")
async def chat_dm_websocket(websocket: WebSocket) -> None:
    async with AsyncSessionLocal() as db:
        try:
            user_id = await authenticate_chat_websocket(websocket, db)
        except UnauthorizedException:
            await websocket.close(code=1008, reason="Unauthorized")
            return
        except ForbiddenException:
            await websocket.close(code=1008, reason="Forbidden")
            return
        except Exception:
            log.exception("chat ws auth 예외")
            await websocket.close(code=1011, reason="Internal error")
            return

    await websocket.accept()
    await chat_connection_manager.connect(user_id, websocket)
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                parsed = parse_incoming_message(raw)
            except ValidationError as e:
                payload = validation_error_to_ws_error(e)
                await websocket.send_text(json.dumps(payload, ensure_ascii=False))
                continue
            try:
                async with AsyncSessionLocal() as db:
                    await ChatService.send_dm_from_ws(
                        db,
                        sender_id=user_id,
                        payload=parsed,
                        redis=_redis_from_websocket(websocket),
                    )
            except ValueError as e:
                if e.args and e.args[0] == DM_SAME_USER:
                    err = ChatWsErrorPayload(
                        code="dm_same_user",
                        message="자기 자신에게는 메시지를 보낼 수 없습니다.",
                    ).model_dump(mode="json", by_alias=True)
                    await websocket.send_text(json.dumps(err, ensure_ascii=False))
                    continue
                log.exception("chat send ValueError")
                err = ChatWsErrorPayload(
                    code="bad_request", message="요청을 처리할 수 없습니다."
                ).model_dump(mode="json", by_alias=True)
                await websocket.send_text(json.dumps(err, ensure_ascii=False))
            except UserNotFoundException as e:
                err = ChatWsErrorPayload(
                    code="peer_not_found",
                    message=e.message or "상대방을 찾을 수 없습니다.",
                ).model_dump(mode="json", by_alias=True)
                await websocket.send_text(json.dumps(err, ensure_ascii=False))
            except BaseProjectException as e:
                err = ChatWsErrorPayload(
                    code=str(e.code) if e.code is not None else "error",
                    message=e.message or "",
                ).model_dump(mode="json", by_alias=True)
                await websocket.send_text(json.dumps(err, ensure_ascii=False))
            except Exception:
                log.exception("chat ws send 실패 user=%s", user_id)
                err = ChatWsErrorPayload(
                    code="internal_error",
                    message="일시적 오류입니다.",
                ).model_dump(mode="json", by_alias=True)
                await websocket.send_text(json.dumps(err, ensure_ascii=False))
    except WebSocketDisconnect:
        pass
    finally:
        await chat_connection_manager.disconnect(user_id, websocket)
