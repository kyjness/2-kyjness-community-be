# 알림 영속 모델. 수신자·종류·관련 엔티티·읽음 시각. CUD는 단일 트랜잭션 내에서 호출.
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, cast
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, delete, func, select, update
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.common.enums import NotificationKind
from app.core.ids import new_uuid7
from app.db.base_class import Base, utc_now

_PG_UUID = PG_UUID(as_uuid=True)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[UUID] = mapped_column(_PG_UUID, primary_key=True, default=new_uuid7)
    user_id: Mapped[UUID] = mapped_column(
        _PG_UUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_id: Mapped[UUID | None] = mapped_column(
        _PG_UUID, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    post_id: Mapped[UUID | None] = mapped_column(
        _PG_UUID, ForeignKey("posts.id", ondelete="CASCADE"), nullable=True
    )
    comment_id: Mapped[UUID | None] = mapped_column(
        _PG_UUID, ForeignKey("comments.id", ondelete="CASCADE"), nullable=True
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
        user_id: UUID,
        kind: NotificationKind,
        actor_id: UUID | None,
        post_id: UUID | None,
        comment_id: UUID | None,
        db: AsyncSession,
    ) -> UUID:
        nid = new_uuid7()
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
        user_id: UUID,
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
        user_id: UUID,
        *,
        notification_ids: list[UUID] | None,
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

    @classmethod
    async def purge_older_than_days(
        cls,
        *,
        older_than_days: int,
        chunk_size: int = 2_000,
        db: AsyncSession,
    ) -> int:
        """
        created_at 기준 보관기간 초과 알림 삭제.
        대량 삭제 시 락/트랜잭션 부하를 줄이기 위해 id를 청크로 잘라 반복 삭제한다.
        """

        days = max(1, int(older_than_days))
        limit = max(100, int(chunk_size))
        cutoff = utc_now() - timedelta(days=days)
        deleted_total = 0

        while True:
            id_rows = (
                (
                    await db.execute(
                        select(Notification.id)
                        .where(Notification.created_at < cutoff)
                        .order_by(Notification.created_at.asc())
                        .limit(limit)
                    )
                )
                .scalars()
                .all()
            )
            if not id_rows:
                break
            stmt = delete(Notification).where(Notification.id.in_(list(id_rows)))
            cr = cast(CursorResult[Any], await db.execute(stmt))
            deleted_total += int(cr.rowcount or 0)
            await db.flush()

        return deleted_total
