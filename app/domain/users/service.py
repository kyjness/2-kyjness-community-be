# 사용자 비즈니스 로직. 순수 데이터 반환·커스텀 예외. 이미지 ref_count는 서비스 내 처리. Full-Async.
from __future__ import annotations

from typing import List

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import (
    InternalServerErrorException,
    InvalidUserInfoException,
    NicknameAlreadyExistsException,
    UnauthorizedException,
)
from app.core.security import hash_password, verify_password
from app.media.model import MediaModel
from app.media.service import MediaService
from app.users.model import UsersModel
from app.users.schema import (
    AvailabilityData,
    UpdatePasswordRequest,
    UpdateUserRequest,
    UserAvailabilityQuery,
    UserProfileResponse,
)
from app.dogs.service import DogService


class UserService:
    @classmethod
    async def check_availability(
        cls, query: UserAvailabilityQuery, db: AsyncSession
    ) -> AvailabilityData:
        async with db.begin():
            return AvailabilityData(
                email_available=not await UsersModel.email_exists(query.email, db=db)
                if query.email
                else None,
                nickname_available=not await UsersModel.nickname_exists(
                    query.nickname, db=db
                )
                if query.nickname
                else None,
            )

    @classmethod
    async def get_user_profile(
        cls, user_id: int, db: AsyncSession
    ) -> UserProfileResponse:
        async with db.begin():
            user_with_dogs = await UsersModel.get_user_by_id_with_dogs(user_id, db=db)
            if not user_with_dogs:
                raise UnauthorizedException()
            return UserProfileResponse.model_validate(user_with_dogs)

    @classmethod
    async def update_user_profile(
        cls,
        user_id: int,
        data: UpdateUserRequest,
        db: AsyncSession,
    ) -> UserProfileResponse:
        async with db.begin():
            user = await UsersModel.get_user_by_id(user_id, db=db)
        if not user:
            raise UnauthorizedException()
        dump = data.model_dump(exclude_unset=True)
        async with db.begin():
            if (
                "nickname" in dump
                and dump["nickname"] != user.nickname
                and await UsersModel.nickname_exists(dump["nickname"], db=db)
            ):
                raise NicknameAlreadyExistsException()

        to_decrement: List[int] = []
        async with db.begin():
            user = await UsersModel.get_user_by_id(user_id, db=db)
            if not user:
                raise UnauthorizedException()
            if dump.get("clear_profile_image") is True or (
                "profile_image_id" in dump and dump["profile_image_id"] is None
            ):
                old_id = user.profile_image_id
                if not await UsersModel.update_profile_image_id(user_id, None, db=db):
                    raise InternalServerErrorException()
                if old_id:
                    to_decrement.append(old_id)
            elif dump.get("profile_image_id"):
                if (
                    await MediaModel.get_image_by_id(dump["profile_image_id"], db=db)
                    is None
                ):
                    raise InvalidUserInfoException()
                old_id = user.profile_image_id
                if not await UsersModel.update_profile_image_id(
                    user_id, dump["profile_image_id"], db=db
                ):
                    raise InternalServerErrorException()
                if old_id:
                    to_decrement.append(old_id)
                await MediaModel.increment_ref_count(dump["profile_image_id"], db=db)

            if "nickname" in dump and not await UsersModel.update_nickname(
                user_id, dump["nickname"], db=db
            ):
                raise InternalServerErrorException()

            if "dogs" in dump:
                await DogService.upsert_dog_profile(
                    user_id, dump["dogs"] or [], db=db, to_decrement=to_decrement
                )

            db.expire(user)
            user_updated = await UsersModel.get_user_by_id_with_dogs(user_id, db=db)
            if not user_updated:
                raise InternalServerErrorException()
            result = UserProfileResponse.model_validate(user_updated)
        for image_id in to_decrement:
            await MediaService.decrement_ref_count(image_id, db=db)
        return result

    @classmethod
    async def update_password(
        cls, user_id: int, data: UpdatePasswordRequest, db: AsyncSession
    ) -> None:
        async with db.begin():
            hashed = await UsersModel.get_password_hash(user_id, db=db)
        if not hashed or not verify_password(data.current_password, hashed):
            raise UnauthorizedException()
        if verify_password(data.new_password, hashed):
            raise InvalidUserInfoException(
                "기존 비밀번호와 동일한 비밀번호는 사용할 수 없습니다."
            )
        new_hashed = hash_password(data.new_password)
        async with db.begin():
            if not await UsersModel.update_password(user_id, new_hashed, db=db):
                raise InternalServerErrorException()

    @classmethod
    async def delete_user(cls, user_id: int, db: AsyncSession) -> None:
        async with db.begin():
            user = await UsersModel.get_user_by_id(user_id, db=db)
        if not user:
            raise InternalServerErrorException()
        profile_image_id = user.profile_image_id
        async with db.begin():
            if not await UsersModel.delete_user(user_id, db=db):
                raise InternalServerErrorException()
        if profile_image_id is not None:
            await MediaService.decrement_ref_count(profile_image_id, db=db)
