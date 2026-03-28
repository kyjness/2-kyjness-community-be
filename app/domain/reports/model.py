# 신고 테이블 접근. Report ORM은 app.users.model에 정의됨.
from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import TargetType
from app.db.base_class import utc_now
from app.users.model import Report

# PostgreSQL IN (...)·파라미터·응답 메모리 폭주 완화 (관리자 신고 목록 등 대량 ID)
REPORT_BULK_IN_CHUNK = 200


def _not_deleted():
    return Report.deleted_at.is_(None)


def _target_type_value(v: TargetType | str) -> str:
    return v.value if isinstance(v, TargetType) else v


def _chunk_ids(ids: list[str], size: int) -> list[list[str]]:
    if not ids:
        return []
    return [ids[i : i + size] for i in range(0, len(ids), size)]


class ReportsModel:
    @classmethod
    async def create_report(
        cls,
        reporter_id: str,
        target_type: TargetType | str,
        target_id: str,
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
    async def get_last_reported_at(cls, post_id: str, db: AsyncSession) -> datetime | None:
        return await cls.get_last_reported_at_for_target(TargetType.POST, post_id, db=db)

    @classmethod
    async def get_last_reported_at_for_target(
        cls, target_type: TargetType | str, target_id: str, db: AsyncSession
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
    async def get_reasons_for_post(cls, post_id: str, db: AsyncSession) -> list[str]:
        return await cls.get_reasons_for_target(TargetType.POST, post_id, db=db)

    @classmethod
    async def get_reasons_for_target(
        cls, target_type: TargetType | str, target_id: str, db: AsyncSession
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
        target_ids: list[str],
        db: AsyncSession,
    ) -> dict[str, datetime]:
        """삭제되지 않은 신고 기준 target_id별 max(created_at). IN은 청크 분할."""
        if not target_ids:
            return {}
        tv = _target_type_value(target_type)
        out: dict[str, datetime] = {}
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
        target_ids: list[str],
        db: AsyncSession,
    ) -> dict[str, list[str]]:
        """target_id별 reason 목록(created_at 오름차순). 빈 reason은 제외 — 단건 get_reasons_for_target과 동일."""
        if not target_ids:
            return {}
        tv = _target_type_value(target_type)
        agg: defaultdict[str, list[str]] = defaultdict(list)
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
    async def delete_by_post_id(cls, post_id: str, db: AsyncSession) -> None:
        await cls.delete_by_target(TargetType.POST, post_id, db=db)

    @classmethod
    async def delete_by_target(
        cls, target_type: TargetType | str, target_id: str, db: AsyncSession
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
    async def delete_by_comment_id(cls, comment_id: str, db: AsyncSession) -> None:
        await cls.delete_by_target(TargetType.COMMENT, comment_id, db=db)
