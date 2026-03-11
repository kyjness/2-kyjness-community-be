# 신고 테이블 접근. Report ORM은 app.users.model에 정의됨.
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.users.model import Report


class ReportsModel:
    @classmethod
    async def report_exists(
        cls,
        reporter_id: int,
        target_type: str,
        target_id: int,
        db: AsyncSession,
    ) -> bool:
        result = await db.execute(
            select(Report.id)
            .where(
                Report.reporter_id == reporter_id,
                Report.target_type == target_type,
                Report.target_id == target_id,
            )
            .limit(1)
        )
        return result.first() is not None

    @classmethod
    async def create_report(
        cls,
        reporter_id: int,
        target_type: str,
        target_id: int,
        reason: str | None,
        db: AsyncSession,
    ) -> None:
        from app.db import utc_now

        db.add(
            Report(
                reporter_id=reporter_id,
                target_type=target_type,
                target_id=target_id,
                reason=reason,
                status="PENDING",
                created_at=utc_now(),
            )
        )
        await db.flush()
