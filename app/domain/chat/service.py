# 1:1 DM 비즈니스 로직. 방 upsert·메시지 저장·Redis 팬아웃·커서 목록.
from __future__ import annotations

import json
import logging
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy import select, tuple_
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.chat.model import ChatMessage, ChatRoom, normalize_dm_user_ids
from app.chat.schema import (
    ChatMessageBroadcast,
    ChatMessageItem,
    ChatMessageSend,
    ChatMessagesPageData,
)
from app.common.enums import UserStatus
from app.common.exceptions import ForbiddenException, InvalidRequestException, UserNotFoundException
from app.core.ids import new_uuid7, uuid_to_base62
from app.db.base_class import utc_now
from app.users.model import UsersModel

from .manager import chat_connection_manager
from .pubsub import publish_chat_dm

log = logging.getLogger(__name__)

DM_SAME_USER = "dm_same_user"


class ChatService:
    @classmethod
    async def resolve_direct_room(
        cls,
        db: AsyncSession,
        *,
        user_id: UUID,
        peer_id: UUID,
    ) -> UUID:
        """커밋 전에 room PK를 확정해 반환(만료 ORM으로 인한 room.id None 방지)."""
        if peer_id == user_id:
            raise InvalidRequestException(message="자기 자신과는 채팅할 수 없습니다.")
        async with db.begin():
            peer = await UsersModel.get_user_by_id(peer_id, db=db)
            if not peer or not UserStatus.is_active_value(peer.status):
                raise UserNotFoundException(message="상대방을 찾을 수 없습니다.")
            room = await cls.get_or_create_room(db, user_id=user_id, peer_id=peer_id)
            rid = room.id
            if rid is None:
                await db.refresh(room)
                rid = room.id
            if rid is None:
                log.error(
                    "chat room id missing after get_or_create user_id=%s peer_id=%s",
                    user_id,
                    peer_id,
                )
                raise InvalidRequestException(message="채팅방을 열 수 없습니다.")
            return rid

    @classmethod
    async def get_or_create_room(
        cls,
        db: AsyncSession,
        *,
        user_id: UUID,
        peer_id: UUID,
    ) -> ChatRoom:
        u1, u2 = normalize_dm_user_ids(user_id, peer_id)
        now = utc_now()
        rid = new_uuid7()
        await db.execute(
            pg_insert(ChatRoom)
            .values(id=rid, user1_id=u1, user2_id=u2, created_at=now, updated_at=now)
            .on_conflict_do_nothing(constraint="uq_chat_rooms_user_pair")
        )
        await db.flush()
        res = await db.execute(
            select(ChatRoom).where(ChatRoom.user1_id == u1, ChatRoom.user2_id == u2).limit(1)
        )
        row = res.scalar_one_or_none()
        if row is None:
            log.error("chat room missing after upsert u1=%s u2=%s", u1, u2)
            raise InvalidRequestException(message="채팅방을 열 수 없습니다.")
        if row.id is None:
            await db.refresh(row)
        if row.id is None:
            log.error("chat room row id still null after refresh u1=%s u2=%s", u1, u2)
            raise InvalidRequestException(message="채팅방을 열 수 없습니다.")
        return row

    @classmethod
    def _is_room_member(cls, room: ChatRoom, user_id: UUID) -> bool:
        return user_id == room.user1_id or user_id == room.user2_id

    @classmethod
    async def send_dm_from_ws(
        cls,
        db: AsyncSession,
        *,
        sender_id: UUID,
        payload: ChatMessageSend,
        redis: Redis | None,
    ) -> None:
        peer_id = payload.peer_user_id
        if peer_id == sender_id:
            raise ValueError(DM_SAME_USER)
        async with db.begin():
            peer = await UsersModel.get_user_by_id(peer_id, db=db)
            if not peer or not UserStatus.is_active_value(peer.status):
                raise UserNotFoundException(message="상대방을 찾을 수 없습니다.")
            room = await cls.get_or_create_room(db, user_id=sender_id, peer_id=peer_id)
            msg = ChatMessage(
                id=new_uuid7(),
                room_id=room.id,
                sender_id=sender_id,
                content=payload.content,
                is_read=False,
                created_at=utc_now(),
            )
            db.add(msg)
            await db.flush()
            broadcast = ChatMessageBroadcast(
                id=msg.id,
                room_id=room.id,
                sender_id=sender_id,
                content=msg.content,
                is_read=msg.is_read,
                created_at=msg.created_at,
            )
            wire = json.dumps(
                broadcast.model_dump(mode="json", by_alias=True),
                ensure_ascii=False,
            )
        await cls._fanout_dm(redis, peer_id=peer_id, sender_id=sender_id, wire=wire)

    @classmethod
    async def _fanout_dm(
        cls,
        redis: Redis | None,
        *,
        peer_id: UUID,
        sender_id: UUID,
        wire: str,
    ) -> None:
        if redis is None:
            await chat_connection_manager.send_personal_message(peer_id, wire)
            await chat_connection_manager.send_personal_message(sender_id, wire)
            return
        try:
            await publish_chat_dm(redis, target_user_id=peer_id, payload=wire)
            await publish_chat_dm(redis, target_user_id=sender_id, payload=wire)
        except Exception:
            log.exception("chat redis fanout 실패, 로컬만 시도")
            await chat_connection_manager.send_personal_message(peer_id, wire)
            await chat_connection_manager.send_personal_message(sender_id, wire)

    @classmethod
    async def list_room_messages(
        cls,
        db: AsyncSession,
        *,
        room_id: UUID,
        user_id: UUID,
        cursor_message_id: UUID | None,
        limit: int,
    ) -> ChatMessagesPageData:
        async with db.begin():
            rres = await db.execute(select(ChatRoom).where(ChatRoom.id == room_id).limit(1))
            room = rres.scalar_one_or_none()
            if room is None or not cls._is_room_member(room, user_id):
                raise ForbiddenException(message="이 채팅방에 접근할 수 없습니다.")
            stmt = select(ChatMessage).where(ChatMessage.room_id == room_id)
            if cursor_message_id is not None:
                cur = await db.execute(
                    select(ChatMessage.created_at, ChatMessage.id).where(
                        ChatMessage.id == cursor_message_id,
                        ChatMessage.room_id == room_id,
                    )
                )
                cur_row = cur.one_or_none()
                if cur_row is None:
                    raise InvalidRequestException(message="유효하지 않은 cursor 입니다.")
                c_at, c_id = cur_row[0], cur_row[1]
                stmt = stmt.where(
                    tuple_(ChatMessage.created_at, ChatMessage.id) < tuple_(c_at, c_id),
                )
            stmt = stmt.order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc()).limit(
                limit + 1
            )
            mres = await db.execute(stmt)
            rows = list(mres.scalars().all())
        has_more = len(rows) > limit
        page_rows = rows[:limit]
        items = [
            ChatMessageItem(
                id=m.id,
                room_id=m.room_id,
                sender_id=m.sender_id,
                content=m.content,
                is_read=m.is_read,
                created_at=m.created_at,
            )
            for m in page_rows
        ]
        next_cursor: str | None = None
        if has_more and page_rows:
            next_cursor = uuid_to_base62(page_rows[-1].id)
        return ChatMessagesPageData(items=items, next_cursor=next_cursor)
