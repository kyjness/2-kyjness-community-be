# 1:1 채팅방·메시지 ORM. user1_id < user2_id 정규화 + 복합 유니크로 동시 생성 레이스 방지.
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.ids import new_uuid7
from app.db.base_class import Base, utc_now

_PG_UUID = PG_UUID(as_uuid=True)


def normalize_dm_user_ids(user_a: UUID, user_b: UUID) -> tuple[UUID, UUID]:
    """채팅방 upsert 시 항상 동일한 (user1_id, user2_id) 행으로 수렴. DB CHECK·UNIQUE와 일치."""
    if user_a == user_b:
        raise ValueError("dm_same_user")
    return (user_a, user_b) if user_a < user_b else (user_b, user_a)


class ChatRoom(Base):
    __tablename__ = "chat_rooms"
    __table_args__ = (
        UniqueConstraint("user1_id", "user2_id", name="uq_chat_rooms_user_pair"),
        CheckConstraint("user1_id < user2_id", name="ck_chat_rooms_user_order"),
    )

    id: Mapped[UUID] = mapped_column(_PG_UUID, primary_key=True, default=new_uuid7)
    user1_id: Mapped[UUID] = mapped_column(
        _PG_UUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user2_id: Mapped[UUID] = mapped_column(
        _PG_UUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    __table_args__ = (
        Index(
            "ix_chat_messages_room_created",
            "room_id",
            text("created_at DESC"),
        ),
    )

    id: Mapped[UUID] = mapped_column(_PG_UUID, primary_key=True, default=new_uuid7)
    room_id: Mapped[UUID] = mapped_column(
        _PG_UUID, ForeignKey("chat_rooms.id", ondelete="CASCADE"), nullable=False
    )
    sender_id: Mapped[UUID] = mapped_column(
        _PG_UUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
