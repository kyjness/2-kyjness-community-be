# 강아지 프로필 비즈니스 로직. 순수 데이터/커스텀 예외. Full-Async.
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import (
    ForbiddenException,
    InternalServerErrorException,
    NotFoundException,
)
from app.dogs.model import DogProfilesModel
from app.dogs.schema import DogProfileUpsertItem
from app.media.model import MediaModel
from app.users.model import UsersModel
from app.users.schema import UserProfileResponse


class DogService:
    @classmethod
    async def upsert_dog_profile(
        cls,
        owner_id: int,
        items: list[dict | DogProfileUpsertItem],
        db: AsyncSession,
        to_decrement: list[int] | None = None,
    ) -> None:
        """강아지 목록 전체 교체(생성/수정/삭제). 대표 강아지 설정은 한 트랜잭션 내 원자적."""
        if to_decrement is None:
            to_decrement = []
        existing_ids = {d.id for d in await DogProfilesModel.get_by_owner_id(owner_id, db=db)}
        requested_ids: set[int] = set()
        representative_id: int | None = None

        for raw in items:
            item: DogProfileUpsertItem = DogProfileUpsertItem.model_validate(raw)
            if item.id is None:
                dog = await DogProfilesModel.create(
                    owner_id=owner_id,
                    name=item.name,
                    breed=item.breed,
                    gender=item.gender.value,
                    birth_date=item.birth_date,
                    profile_image_id=item.profile_image_id,
                    is_representative=item.is_representative,
                    db=db,
                )
                if item.profile_image_id:
                    await MediaModel.increment_ref_count(item.profile_image_id, db=db)
                requested_ids.add(dog.id)
                if item.is_representative:
                    representative_id = dog.id
            else:
                if await DogProfilesModel.get_by_id(item.id, owner_id, db=db) is None:
                    raise ForbiddenException()
                requested_ids.add(item.id)
                if item.is_representative:
                    representative_id = item.id
                old = await DogProfilesModel.get_by_id(item.id, owner_id, db=db)
                if old and old.profile_image_id != item.profile_image_id:
                    if old.profile_image_id:
                        to_decrement.append(old.profile_image_id)
                    if item.profile_image_id:
                        await MediaModel.increment_ref_count(item.profile_image_id, db=db)
                await DogProfilesModel.update(
                    item.id,
                    owner_id,
                    db=db,
                    name=item.name,
                    breed=item.breed,
                    gender=item.gender.value,
                    birth_date=item.birth_date,
                    profile_image_id=item.profile_image_id,
                    is_representative=item.is_representative,
                )

        for did in existing_ids - requested_ids:
            dog = await DogProfilesModel.get_by_id(did, owner_id, db=db)
            if dog and dog.profile_image_id:
                to_decrement.append(dog.profile_image_id)
            await DogProfilesModel.delete(did, owner_id, db=db)

        if representative_id and requested_ids:
            await DogProfilesModel.set_representative(owner_id, representative_id, db=db)

    @classmethod
    async def set_representative_dog(
        cls, owner_id: int, dog_id: int, db: AsyncSession
    ) -> UserProfileResponse:
        """대표 강아지 설정. dog_id가 해당 owner_id 소유가 아니면 NotFoundException. 반환: 갱신된 사용자 프로필."""
        async with db.begin():
            dog = await DogProfilesModel.get_by_id(dog_id, owner_id, db=db)
            if dog is None:
                raise NotFoundException()
            if not await DogProfilesModel.set_representative(owner_id, dog_id, db=db):
                raise InternalServerErrorException()
            user = await UsersModel.get_user_by_id_with_dogs(owner_id, db=db)
            if not user:
                raise InternalServerErrorException()
            return UserProfileResponse.model_validate(user)
