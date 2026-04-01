# 알림 영속 모델. 수신자·종류·관련 엔티티·읽음 시각. CUD는 단일 트랜잭션 내에서 호출.
from __future__ import annotations

from datetime import datetime
from typing import Any, cast

from sqlalchemy import DateTime, ForeignKey, String, func, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.common.enums import NotificationKind
from app.core.ids import new_ulid_str
from app.db.base_class import Base, utc_now


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=new_ulid_str)
    user_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    post_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("posts.id", ondelete="CASCADE"), nullable=True
    )
    comment_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("comments.id", ondelete="CASCADE"), nullable=True
    )
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class NotificationsModel:
    @classmethod
    async def insert(
        cls,
        *,
        user_id: str,
        kind: NotificationKind,
        actor_id: str | None,
        post_id: str | None,
        comment_id: str | None,
        db: AsyncSession,
    ) -> str:
        nid = new_ulid_str()
        row = Notification(
            id=nid,
            user_id=user_id,
            kind=kind.value,
            actor_id=actor_id,
            post_id=post_id,
            comment_id=comment_id,
        )
        db.add(row)
        await db.flush()
        return nid

    @classmethod
    async def list_for_user(
        cls,
        user_id: str,
        *,
        page: int,
        size: int,
        db: AsyncSession,
    ) -> tuple[list[Notification], int]:
        count_stmt = (
            select(func.count()).select_from(Notification).where(Notification.user_id == user_id)
        )
        total = int((await db.execute(count_stmt)).scalar_one())
        offset = (page - 1) * size
        stmt = (
            select(Notification)
            .where(Notification.user_id == user_id)
            .order_by(Notification.created_at.desc())
            .offset(offset)
            .limit(size)
        )
        rows = list((await db.execute(stmt)).scalars().all())
        return rows, total

    @classmethod
    async def mark_read(
        cls,
        user_id: str,
        *,
        notification_ids: list[str] | None,
        db: AsyncSession,
    ) -> int:
        now = utc_now()
        stmt = (
            update(Notification)
            .where(
                Notification.user_id == user_id,
                Notification.read_at.is_(None),
            )
            .values(read_at=now)
        )
        if notification_ids:
            stmt = stmt.where(Notification.id.in_(notification_ids))
        cr = cast(CursorResult[Any], await db.execute(stmt))
        return int(cr.rowcount or 0)
