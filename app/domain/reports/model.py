# 신고 테이블 접근. Report ORM은 app.users.model에 정의됨.
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import TargetType
from app.db import utc_now
from app.users.model import Report


def _not_deleted():
    return Report.deleted_at.is_(None)


def _target_type_value(v: TargetType | str) -> str:
    return v.value if isinstance(v, TargetType) else v


class ReportsModel:
    @classmethod
    async def create_report(
        cls,
        reporter_id: int,
        target_type: TargetType | str,
        target_id: int,
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
    async def get_last_reported_at(cls, post_id: int, db: AsyncSession) -> datetime | None:
        return await cls.get_last_reported_at_for_target(TargetType.POST, post_id, db=db)

    @classmethod
    async def get_last_reported_at_for_target(
        cls, target_type: TargetType | str, target_id: int, db: AsyncSession
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
    async def get_reasons_for_post(cls, post_id: int, db: AsyncSession) -> list[str]:
        return await cls.get_reasons_for_target(TargetType.POST, post_id, db=db)

    @classmethod
    async def get_reasons_for_target(
        cls, target_type: TargetType | str, target_id: int, db: AsyncSession
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
    async def delete_by_post_id(cls, post_id: int, db: AsyncSession) -> None:
        await cls.delete_by_target(TargetType.POST, post_id, db=db)

    @classmethod
    async def delete_by_target(
        cls, target_type: TargetType | str, target_id: int, db: AsyncSession
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
    async def delete_by_comment_id(cls, comment_id: int, db: AsyncSession) -> None:
        await cls.delete_by_target(TargetType.COMMENT, comment_id, db=db)
