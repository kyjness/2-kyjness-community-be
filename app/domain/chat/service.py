# 1:1 DM 비즈니스 로직. 방 upsert·메시지 저장·Redis 팬아웃·커서 목록.
from __future__ import annotations

import json
import logging
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy import case, func, or_, select, tuple_, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.common.enums import UserStatus
from app.common.exceptions import ForbiddenException, InvalidRequestException, UserNotFoundException
from app.core.ids import new_uuid7, uuid_to_base62
from app.db.base_class import utc_now
from app.domain.chat.model import ChatMessage, ChatRoom, normalize_dm_user_ids
from app.domain.chat.schema import (
    ChatMessageBroadcast,
    ChatMessageItem,
    ChatMessageSend,
    ChatMessagesPageData,
    ChatRoomListItem,
    ChatRoomMarkedReadData,
    ChatRoomPeerInfoData,
    ChatRoomsListData,
)
from app.domain.media.model import Image
from app.domain.users.model import DogProfile, User, UsersModel

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
            # 메시지 조회 앞의 authz 가드. 전체 엔티티 대신 멤버 판정에 필요한 두 컬럼만 로드한다.
            rres = await db.execute(
                select(ChatRoom.user1_id, ChatRoom.user2_id).where(ChatRoom.id == room_id).limit(1)
            )
            room = rres.one_or_none()
            if room is None or user_id not in (room.user1_id, room.user2_id):
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

    @classmethod
    async def list_recent_rooms(
        cls,
        db: AsyncSession,
        *,
        user_id: UUID,
        limit: int,
    ) -> ChatRoomsListData:
        """최근 대화 목록(헤더 인박스용).

        - 방은 "최근 메시지가 존재"하는 경우만 노출(빈 방 제외)
        - 미읽음은 내 기준: is_read=false AND sender_id != me
        - N+1 방지: 방/상대/최근메시지/미읽음을 1회 쿼리로 조립
        """
        limit = max(1, min(int(limit), 50))

        peer_id_expr = case(
            (ChatRoom.user1_id == user_id, ChatRoom.user2_id),
            else_=ChatRoom.user1_id,
        ).label("peer_id")

        # 두 서브쿼리(최근메시지 윈도우·미읽음 집계)를 호출자 방으로 한정한다.
        # 스코프가 없으면 전체 chat_messages를 스캔·집계해 메시지 누적에 비례해 비용이 커진다(#16).
        my_room_ids = (
            select(ChatRoom.id)
            .where(or_(ChatRoom.user1_id == user_id, ChatRoom.user2_id == user_id))
            .scalar_subquery()
        )

        last_msg_ranked = (
            select(
                ChatMessage.room_id.label("room_id"),
                ChatMessage.content.label("last_content"),
                ChatMessage.created_at.label("last_created_at"),
                func.row_number()
                .over(
                    partition_by=ChatMessage.room_id,
                    order_by=(ChatMessage.created_at.desc(), ChatMessage.id.desc()),
                )
                .label("rn"),
            )
            .where(ChatMessage.room_id.in_(my_room_ids))
            .subquery()
        )
        last_msg = (
            select(
                last_msg_ranked.c.room_id,
                last_msg_ranked.c.last_content,
                last_msg_ranked.c.last_created_at,
            )
            .where(last_msg_ranked.c.rn == 1)
            .subquery()
        )

        unread = (
            select(
                ChatMessage.room_id.label("room_id"),
                func.count(ChatMessage.id).label("unread_count"),
            )
            .where(
                ChatMessage.room_id.in_(my_room_ids),
                ChatMessage.is_read.is_(False),
                ChatMessage.sender_id != user_id,
            )
            .group_by(ChatMessage.room_id)
            .subquery()
        )

        peer = aliased(User)
        peer_img = aliased(Image)
        peer_dog = aliased(DogProfile)
        peer_dog_img = aliased(Image)

        async with db.begin():
            stmt = (
                select(
                    ChatRoom.id.label("room_id"),
                    peer_id_expr,
                    peer.nickname.label("peer_nickname"),
                    peer_img.file_url.label("peer_profile_image_url"),
                    peer_dog_img.file_url.label("peer_dog_profile_image_url"),
                    peer_dog.name.label("peer_dog_name"),
                    peer_dog.breed.label("peer_dog_breed"),
                    peer_dog.gender.label("peer_dog_gender"),
                    peer_dog.birth_date.label("peer_dog_birth_date"),
                    last_msg.c.last_content,
                    last_msg.c.last_created_at,
                    func.coalesce(unread.c.unread_count, 0).label("unread_count"),
                )
                .where(or_(ChatRoom.user1_id == user_id, ChatRoom.user2_id == user_id))
                .join(peer, peer.id == peer_id_expr)
                .outerjoin(peer_img, peer_img.id == peer.profile_image_id)
                .outerjoin(
                    peer_dog,
                    (peer_dog.owner_id == peer.id) & (peer_dog.is_representative.is_(True)),
                )
                .outerjoin(peer_dog_img, peer_dog_img.id == peer_dog.profile_image_id)
                .join(last_msg, last_msg.c.room_id == ChatRoom.id)
                .outerjoin(unread, unread.c.room_id == ChatRoom.id)
                .order_by(last_msg.c.last_created_at.desc(), ChatRoom.id.desc())
                .limit(limit)
            )
            res = await db.execute(stmt)
            rows = res.all()

        items: list[ChatRoomListItem] = []
        for r in rows:
            preview = (r.last_content or "").replace("\n", " ").strip()
            if len(preview) > 120:
                preview = preview[:117] + "…"
            items.append(
                ChatRoomListItem(
                    room_id=r.room_id,
                    peer_user_id=r.peer_id,
                    peer_nickname=r.peer_nickname or "",
                    peer_profile_image_url=r.peer_profile_image_url,
                    peer_dog_profile_image_url=r.peer_dog_profile_image_url,
                    peer_dog_name=r.peer_dog_name,
                    peer_dog_breed=r.peer_dog_breed,
                    peer_dog_gender=r.peer_dog_gender,
                    peer_dog_birth_date=r.peer_dog_birth_date,
                    last_message_preview=preview,
                    unread_count=int(r.unread_count or 0),
                    updated_at=r.last_created_at,
                )
            )
        return ChatRoomsListData(items=items)

    @classmethod
    async def mark_room_read(
        cls,
        db: AsyncSession,
        *,
        room_id: UUID,
        user_id: UUID,
    ) -> ChatRoomMarkedReadData:
        """내 기준 미읽음(상대가 보낸 메시지)을 읽음으로 일괄 표시."""
        async with db.begin():
            # UPDATE 앞의 authz 가드. 전체 엔티티 대신 멤버 판정에 필요한 두 컬럼만 로드한다.
            rres = await db.execute(
                select(ChatRoom.user1_id, ChatRoom.user2_id).where(ChatRoom.id == room_id).limit(1)
            )
            room = rres.one_or_none()
            if room is None or user_id not in (room.user1_id, room.user2_id):
                raise ForbiddenException(message="이 채팅방에 접근할 수 없습니다.")
            await db.execute(
                update(ChatMessage)
                .where(
                    ChatMessage.room_id == room_id,
                    ChatMessage.sender_id != user_id,
                    ChatMessage.is_read.is_(False),
                )
                .values(is_read=True)
            )
        return ChatRoomMarkedReadData(ok=True)

    @classmethod
    async def get_room_peer_info(
        cls,
        db: AsyncSession,
        *,
        room_id: UUID,
        user_id: UUID,
    ) -> ChatRoomPeerInfoData:
        """채팅방 상단용 상대 정보(닉네임/프로필).

        - 멤버가 아니면 Forbidden
        - N+1 없이 1쿼리
        """
        peer_id_expr = case(
            (ChatRoom.user1_id == user_id, ChatRoom.user2_id),
            else_=ChatRoom.user1_id,
        ).label("peer_id")

        peer = aliased(User)
        peer_img = aliased(Image)
        peer_dog = aliased(DogProfile)
        peer_dog_img = aliased(Image)

        async with db.begin():
            # 멤버십 가드를 projection의 WHERE에 접어넣어 같은 방을 두 번 조회하지 않는다(#19).
            # 비멤버·부재 방이면 행이 없으므로 None → Forbidden.
            stmt = (
                select(
                    ChatRoom.id.label("room_id"),
                    peer_id_expr,
                    peer.nickname.label("peer_nickname"),
                    peer_img.file_url.label("peer_profile_image_url"),
                    peer_dog.name.label("peer_dog_name"),
                    peer_dog_img.file_url.label("peer_dog_profile_image_url"),
                    peer_dog.breed.label("peer_dog_breed"),
                    peer_dog.gender.label("peer_dog_gender"),
                    peer_dog.birth_date.label("peer_dog_birth_date"),
                )
                .where(
                    ChatRoom.id == room_id,
                    or_(ChatRoom.user1_id == user_id, ChatRoom.user2_id == user_id),
                )
                .join(peer, peer.id == peer_id_expr)
                .outerjoin(peer_img, peer_img.id == peer.profile_image_id)
                .outerjoin(
                    peer_dog,
                    (peer_dog.owner_id == peer.id) & (peer_dog.is_representative.is_(True)),
                )
                .outerjoin(peer_dog_img, peer_dog_img.id == peer_dog.profile_image_id)
                .limit(1)
            )
            res = await db.execute(stmt)
            row = res.one_or_none()
            if row is None:
                raise ForbiddenException(message="이 채팅방에 접근할 수 없습니다.")

        return ChatRoomPeerInfoData(
            room_id=row.room_id,
            peer_user_id=row.peer_id,
            peer_nickname=row.peer_nickname or "",
            peer_profile_image_url=row.peer_profile_image_url,
            peer_dog_name=row.peer_dog_name,
            peer_dog_profile_image_url=row.peer_dog_profile_image_url,
            peer_dog_breed=row.peer_dog_breed,
            peer_dog_gender=row.peer_dog_gender,
            peer_dog_birth_date=row.peer_dog_birth_date,
        )
