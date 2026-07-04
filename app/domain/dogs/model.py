# 강아지 프로필 CRUD. 대표 강아지 설정은 한 트랜잭션 내 원자적 처리. AsyncSession.

from uuid import UUID

from sqlalchemy import bindparam, case, delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.db.base_class import utc_now
from app.domain.users.model import DogProfile


class DogProfilesModel:
    @classmethod
    async def get_by_id(cls, dog_id: UUID, owner_id: UUID, db: AsyncSession) -> DogProfile | None:
        stmt = (
            select(DogProfile)
            .where(DogProfile.id == dog_id, DogProfile.owner_id == owner_id)
            .options(joinedload(DogProfile.profile_image))
        )
        result = await db.execute(stmt)
        return result.scalars().one_or_none()

    @classmethod
    async def get_ids_by_owner_id(cls, owner_id: UUID, db: AsyncSession) -> set[UUID]:
        result = await db.execute(select(DogProfile.id).where(DogProfile.owner_id == owner_id))
        return set(result.scalars().all())

    @classmethod
    async def get_owned_ids_in(
        cls, owner_id: UUID, dog_ids: list[UUID], db: AsyncSession
    ) -> set[UUID]:
        if not dog_ids:
            return set()
        result = await db.execute(
            select(DogProfile.id).where(
                DogProfile.owner_id == owner_id,
                DogProfile.id.in_(dog_ids),
            )
        )
        return set(result.scalars().all())

    @classmethod
    async def create_many(
        cls,
        owner_id: UUID,
        rows: list[dict[str, object]],
        *,
        db: AsyncSession,
    ) -> list[DogProfile]:
        if not rows:
            return []
        now = utc_now()
        dogs = [
            DogProfile(
                owner_id=owner_id,
                name=str(r["name"]),
                breed=str(r["breed"]),
                gender=str(r["gender"]),
                birth_date=r["birth_date"],
                profile_image_id=r.get("profile_image_id"),
                is_representative=bool(r.get("is_representative", False)),
                created_at=now,
                updated_at=now,
            )
            for r in rows
        ]
        db.add_all(dogs)
        await db.flush()
        return dogs

    @classmethod
    async def bulk_update_by_owner(
        cls,
        owner_id: UUID,
        rows: list[dict[str, object]],
        *,
        db: AsyncSession,
    ) -> int:
        if not rows:
            return 0
        stmt = (
            update(DogProfile)
            .where(
                DogProfile.owner_id == owner_id,
                DogProfile.id == bindparam("dog_id"),
            )
            .values(
                name=bindparam("name"),
                breed=bindparam("breed"),
                gender=bindparam("gender"),
                birth_date=bindparam("birth_date"),
                is_representative=bindparam("is_representative"),
                profile_image_id=case(
                    (bindparam("touch_profile_image"), bindparam("profile_image_id")),
                    else_=DogProfile.profile_image_id,
                ),
                updated_at=bindparam("updated_at"),
            )
            .returning(DogProfile.id)
        )
        result = await db.execute(stmt, rows)
        return len(list(result.scalars().all()))

    @classmethod
    async def bulk_delete_by_owner_ids(
        cls, owner_id: UUID, dog_ids: list[UUID], db: AsyncSession
    ) -> int:
        if not dog_ids:
            return 0
        result = await db.execute(
            delete(DogProfile)
            .where(DogProfile.owner_id == owner_id, DogProfile.id.in_(dog_ids))
            .returning(DogProfile.id)
        )
        return len(list(result.scalars().all()))

    @classmethod
    async def set_representative(cls, owner_id: UUID, dog_id: UUID, db: AsyncSession) -> bool:
        """해당 유저의 대표 강아지를 dog_id로 설정. 기존 대표 해제 후 설정을 한 트랜잭션 내 원자적으로 수행."""
        await db.execute(
            update(DogProfile)
            .where(DogProfile.owner_id == owner_id)
            .values(is_representative=False)
        )
        r = await db.execute(
            update(DogProfile)
            .where(DogProfile.id == dog_id, DogProfile.owner_id == owner_id)
            .values(is_representative=True, updated_at=utc_now())
            .returning(DogProfile.id)
        )
        return r.scalar_one_or_none() is not None
