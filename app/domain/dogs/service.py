# 강아지 프로필 비즈니스 로직. 순수 데이터/커스텀 예외. Full-Async.
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import (
    ForbiddenException,
    InternalServerErrorException,
    NotFoundException,
)
from app.db import utc_now
from app.dogs.model import DogProfilesModel
from app.dogs.schema import DogProfileUpsertItem
from app.users.model import UsersModel
from app.users.schema import UserProfileResponse


class DogService:
    @classmethod
    async def upsert_dog_profile(
        cls,
        owner_id: str,
        items: list[dict | DogProfileUpsertItem],
        db: AsyncSession,
    ) -> None:
        """강아지 목록 전체 교체(생성/수정/삭제). 대표 강아지 설정은 한 트랜잭션 내 원자적."""
        existing_ids = await DogProfilesModel.get_ids_by_owner_id(owner_id, db=db)
        update_ids: list[str] = []
        create_rows: list[dict[str, object]] = []
        update_rows: list[dict[str, object]] = []
        representative_existing_id: str | None = None
        representative_new_index: int | None = None

        for raw in items:
            item: DogProfileUpsertItem = DogProfileUpsertItem.model_validate(raw)
            touch_dog_image = "profile_image_id" in item.model_fields_set
            gender_value = str(getattr(item.gender, "value", item.gender))
            if item.id is None:
                create_rows.append(
                    {
                        "name": item.name,
                        "breed": item.breed,
                        "gender": gender_value,
                        "birth_date": item.birth_date,
                        "profile_image_id": item.profile_image_id,
                        "is_representative": item.is_representative,
                    }
                )
                if item.is_representative:
                    representative_new_index = len(create_rows) - 1
                    representative_existing_id = None
            else:
                update_ids.append(item.id)
                update_rows.append(
                    {
                        "dog_id": item.id,
                        "name": item.name,
                        "breed": item.breed,
                        "gender": gender_value,
                        "birth_date": item.birth_date,
                        "profile_image_id": item.profile_image_id,
                        "touch_profile_image": touch_dog_image,
                        "is_representative": item.is_representative,
                        "updated_at": utc_now(),
                    }
                )
                if item.is_representative:
                    representative_existing_id = item.id
                    representative_new_index = None

        owned_update_ids = await DogProfilesModel.get_owned_ids_in(owner_id, update_ids, db=db)
        if len(owned_update_ids) != len(set(update_ids)):
            raise ForbiddenException()

        if update_rows:
            await DogProfilesModel.bulk_update_by_owner(owner_id, update_rows, db=db)

        created = await DogProfilesModel.create_many(owner_id, create_rows, db=db)

        requested_ids: set[str] = set(update_ids)
        requested_ids.update(d.id for d in created)

        delete_ids = list(existing_ids - requested_ids)
        if delete_ids:
            await DogProfilesModel.bulk_delete_by_owner_ids(owner_id, delete_ids, db=db)

        representative_id: str | None = representative_existing_id
        if representative_new_index is not None:
            if 0 <= representative_new_index < len(created):
                representative_id = created[representative_new_index].id
            else:
                representative_id = None
        if representative_id and requested_ids:
            await DogProfilesModel.set_representative(owner_id, representative_id, db=db)

    @classmethod
    async def set_representative_dog(
        cls, owner_id: str, dog_id: str, db: AsyncSession
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
