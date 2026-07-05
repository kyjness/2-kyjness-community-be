# 알림 영속 모델. 수신자·종류·관련 엔티티·읽음 시각. CUD는 단일 트랜잭션 내에서 호출.

from datetime import datetime, timedelta
from typing import Any, cast
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, String, delete, select, text, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.common.enums import NotificationKind
from app.core.ids import new_uuid7
from app.db.base_class import PG_UUID, Base, utc_now


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        # 수신자별 최신순 keyset 목록(WHERE user_id + ORDER BY id DESC). uuid7이라 id DESC = 시간
        # 역순이며, comments와 동일한 단일 컬럼 keyset이라 이 인덱스 하나로 정렬·범위를 커버한다.
        Index("ix_notifications_user_recent", "user_id", text("id DESC")),
        # 전체 읽음 처리(WHERE user_id AND read_at IS NULL)용 부분 인덱스 — 미읽음 소수 행만 도는 스캔.
        Index("ix_notifications_user_unread", "user_id", postgresql_where=text("read_at IS NULL")),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID, primary_key=True, default=new_uuid7)
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_id: Mapped[UUID | None] = mapped_column(
        PG_UUID, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    post_id: Mapped[UUID | None] = mapped_column(
        PG_UUID, ForeignKey("posts.id", ondelete="CASCADE"), nullable=True
    )
    comment_id: Mapped[UUID | None] = mapped_column(
        PG_UUID, ForeignKey("comments.id", ondelete="CASCADE"), nullable=True
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
        cursor_id: UUID | None,
        size: int,
        db: AsyncSession,
    ) -> tuple[list[Notification], bool]:
        """수신자 알림 keyset 목록(최신순). cursor_id는 직전 페이지 마지막 알림 id.

        total 없이 has_more로 다음 페이지 표현(ADR 0002). uuid7 id가 시간정렬이라 comments와 동일한
        단일 컬럼 keyset(id < cursor, ORDER BY id DESC)을 쓴다. 커서 행을 조회하지 않으므로 커서
        알림이 보관정책으로 삭제돼도 400 없이 다음 페이지를 반환하고, 타 수신자 id를 커서로 넣어도
        내 알림만 필터되어 노출되지 않는다. size+1 조회로 초과분 존재 여부를 판정한다.
        """
        stmt = select(Notification).where(Notification.user_id == user_id)
        if cursor_id is not None:
            stmt = stmt.where(Notification.id < cursor_id)
        stmt = stmt.order_by(Notification.id.desc()).limit(size + 1)
        rows = list((await db.execute(stmt)).scalars().all())
        has_more = len(rows) > size
        return rows[:size], has_more

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
