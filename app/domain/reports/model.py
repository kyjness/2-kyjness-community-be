# 신고 도메인 ORM(Report)과 쿼리 클래스.
# User 참조는 문자열 관계("User")만 사용 — users.model을 런타임 임포트하지 않는다(순환 차단).

from collections import defaultdict
from datetime import datetime
from datetime import datetime as DateTimeType
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.enums import TargetType
from app.core.ids import new_uuid7
from app.db.base_class import PG_UUID, Base, utc_now

if TYPE_CHECKING:
    from app.domain.users.model import User


class Report(Base):
    __tablename__ = "reports"
    __table_args__ = (
        # 관리자 신고 집계·delete_by_target는 모두 WHERE target_type AND target_id (AND deleted_at
        # IS NULL)로 조회한다. 모든 read 경로가 미삭제만 보므로 부분 인덱스로 살아있는 신고만 커버.
        Index(
            "ix_reports_target",
            "target_type",
            "target_id",
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID, primary_key=True, default=new_uuid7)
    reporter_id: Mapped[UUID] = mapped_column(
        PG_UUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_type: Mapped[str] = mapped_column(String(50), nullable=False)
    target_id: Mapped[UUID] = mapped_column(PG_UUID, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[DateTimeType] = mapped_column(DateTime(timezone=True), nullable=False)
    deleted_at: Mapped[DateTimeType | None] = mapped_column(DateTime(timezone=True), nullable=True)

    reporter: Mapped["User"] = relationship("User", foreign_keys=[reporter_id], lazy="raise_on_sql")


# PostgreSQL IN (...)·파라미터·응답 메모리 폭주 완화 (관리자 신고 목록 등 대량 ID)
REPORT_BULK_IN_CHUNK = 200


def _not_deleted():
    return Report.deleted_at.is_(None)


def _target_type_value(v: TargetType | str) -> str:
    return v.value if isinstance(v, TargetType) else v


def _chunk_ids(ids: list[UUID], size: int) -> list[list[UUID]]:
    if not ids:
        return []
    return [ids[i : i + size] for i in range(0, len(ids), size)]


class ReportsModel:
    @classmethod
    async def create_report(
        cls,
        reporter_id: UUID,
        target_type: TargetType | str,
        target_id: UUID,
        reason: str | None,
        db: AsyncSession,
    ) -> None:
        db.add(
            Report(
                reporter_id=reporter_id,
                target_type=_target_type_value(target_type),
                target_id=target_id,
                reason=reason,
                created_at=utc_now(),
            )
        )
        await db.flush()

    @classmethod
    async def get_last_reported_at(cls, post_id: UUID, db: AsyncSession) -> datetime | None:
        return await cls.get_last_reported_at_for_target(TargetType.POST, post_id, db=db)

    @classmethod
    async def get_last_reported_at_for_target(
        cls, target_type: TargetType | str, target_id: UUID, db: AsyncSession
    ) -> datetime | None:
        tv = _target_type_value(target_type)
        result = await db.execute(
            select(func.max(Report.created_at)).where(
                Report.target_type == tv,
                Report.target_id == target_id,
                _not_deleted(),
            )
        )
        return result.scalar_one_or_none()

    @classmethod
    async def get_reasons_for_post(cls, post_id: UUID, db: AsyncSession) -> list[str]:
        return await cls.get_reasons_for_target(TargetType.POST, post_id, db=db)

    @classmethod
    async def get_reasons_for_target(
        cls, target_type: TargetType | str, target_id: UUID, db: AsyncSession
    ) -> list[str]:
        tv = _target_type_value(target_type)
        result = await db.execute(
            select(Report.reason)
            .where(
                Report.target_type == tv,
                Report.target_id == target_id,
                _not_deleted(),
            )
            .order_by(Report.created_at.asc())
        )
        rows = result.scalars().all()
        return [r for r in rows if r]

    @classmethod
    async def bulk_max_created_at_by_target_ids(
        cls,
        target_type: TargetType | str,
        target_ids: list[UUID],
        db: AsyncSession,
    ) -> dict[UUID, datetime]:
        """삭제되지 않은 신고 기준 target_id별 max(created_at). IN은 청크 분할."""
        if not target_ids:
            return {}
        tv = _target_type_value(target_type)
        out: dict[UUID, datetime] = {}
        for chunk in _chunk_ids(target_ids, REPORT_BULK_IN_CHUNK):
            stmt = (
                select(Report.target_id, func.max(Report.created_at))
                .where(
                    Report.target_type == tv,
                    Report.target_id.in_(chunk),
                    _not_deleted(),
                )
                .group_by(Report.target_id)
            )
            result = await db.execute(stmt)
            for tid, ts in result.all():
                if tid is not None and ts is not None:
                    out[tid] = ts
        return out

    @classmethod
    async def bulk_reasons_ordered_by_target_ids(
        cls,
        target_type: TargetType | str,
        target_ids: list[UUID],
        db: AsyncSession,
    ) -> dict[UUID, list[str]]:
        """target_id별 reason 목록(created_at 오름차순). 빈 reason은 제외 — 단건 get_reasons_for_target과 동일."""
        if not target_ids:
            return {}
        tv = _target_type_value(target_type)
        agg: defaultdict[UUID, list[str]] = defaultdict(list)
        for chunk in _chunk_ids(target_ids, REPORT_BULK_IN_CHUNK):
            stmt = (
                select(Report.target_id, Report.reason, Report.created_at)
                .where(
                    Report.target_type == tv,
                    Report.target_id.in_(chunk),
                    _not_deleted(),
                )
                .order_by(Report.target_id, Report.created_at.asc())
            )
            result = await db.execute(stmt)
            for tid, reason, _ in result.all():
                if tid and reason:
                    agg[tid].append(reason)
        return dict(agg)

    @classmethod
    async def delete_by_post_id(cls, post_id: UUID, db: AsyncSession) -> None:
        await cls.delete_by_target(TargetType.POST, post_id, db=db)

    @classmethod
    async def delete_by_target(
        cls, target_type: TargetType | str, target_id: UUID, db: AsyncSession
    ) -> None:
        tv = _target_type_value(target_type)
        await db.execute(
            update(Report)
            .where(
                Report.target_type == tv,
                Report.target_id == target_id,
                _not_deleted(),
            )
            .values(deleted_at=utc_now())
        )

    @classmethod
    async def delete_by_comment_id(cls, comment_id: UUID, db: AsyncSession) -> None:
        await cls.delete_by_target(TargetType.COMMENT, comment_id, db=db)
