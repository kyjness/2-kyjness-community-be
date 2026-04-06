# 1:1 DM REST: 방별 메시지 커서 페이지네이션.
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import CurrentUser, get_current_user, get_master_db, get_slave_db
from app.chat.schema import ChatDirectRoomData, ChatMessagesPageData
from app.chat.service import ChatService
from app.common import ApiCode, ApiResponse, PublicId, api_response
from app.common.exceptions import InvalidRequestException
from app.core.ids import parse_public_id_value

router = APIRouter(prefix="/chat", tags=["chat"])


@router.get(
    "/rooms/direct/{peer_user_id}",
    status_code=200,
    response_model=ApiResponse[ChatDirectRoomData],
)
async def get_or_create_direct_room(
    request: Request,
    peer_user_id: Annotated[PublicId, Path(..., description="상대방 공개 사용자 ID (Base62)")],
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_master_db),
):
    room_id = await ChatService.resolve_direct_room(db, user_id=user.id, peer_id=peer_user_id)
    return api_response(request, code=ApiCode.OK, data=ChatDirectRoomData(room_id=room_id))


@router.get(
    "/rooms/{room_id}/messages", status_code=200, response_model=ApiResponse[ChatMessagesPageData]
)
async def list_room_messages(
    request: Request,
    room_id: Annotated[PublicId, Path(..., description="채팅방 공개 ID (Base62)")],
    user: CurrentUser = Depends(get_current_user),
    cursor: str | None = Query(None, description="이전 응답의 next_cursor (더 과거 메시지)"),
    limit: int = Query(30, ge=1, le=100, description="한 번에 가져올 최대 개수"),
    db: AsyncSession = Depends(get_slave_db),
):
    cursor_id = None
    if cursor is not None and cursor.strip():
        try:
            cursor_id = parse_public_id_value(cursor.strip())
        except ValueError as e:
            raise InvalidRequestException(message="유효하지 않은 cursor 입니다.") from e
    data = await ChatService.list_room_messages(
        db,
        room_id=room_id,
        user_id=user.id,
        cursor_message_id=cursor_id,
        limit=limit,
    )
    return api_response(request, code=ApiCode.OK, data=data)
