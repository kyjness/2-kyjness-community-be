# 사용자 비즈니스 로직. 프로필 조회·수정, 비밀번호 변경.
from __future__ import annotations

from sqlalchemy.orm import Session

from app.api.dependencies import CurrentUser
from app.common import ApiCode, ApiResponse, raise_http_error
from app.core.security import hash_password, verify_password
from app.media.model import MediaModel
from app.users.model import UsersModel, DogProfilesModel
from app.users.schema import (
    AvailabilityData,
    DogProfileUpsertItem,
    UpdatePasswordRequest,
    UpdateUserRequest,
    UserAvailabilityQuery,
    UserProfileResponse,
)


def check_availability(query: UserAvailabilityQuery, db: Session) -> ApiResponse[AvailabilityData]:
    data = AvailabilityData(
        email_available=not UsersModel.email_exists(query.email, db=db) if query.email else None,
        nickname_available=not UsersModel.nickname_exists(query.nickname, db=db) if query.nickname else None,
    )
    return ApiResponse(code=ApiCode.OK.value, data=data)


def get_me(user: CurrentUser, db: Session) -> ApiResponse[UserProfileResponse]:
    user_with_dogs = UsersModel.get_user_by_id_with_dogs(user.id, db=db)
    if not user_with_dogs:
        raise_http_error(401, ApiCode.UNAUTHORIZED)
    return ApiResponse(
        code=ApiCode.USER_RETRIEVED.value,
        data=UserProfileResponse.model_validate(user_with_dogs),
    )


def update_me(
    user: CurrentUser,
    data: UpdateUserRequest,
    db: Session,
) -> ApiResponse[UserProfileResponse]:
    dump = data.model_dump(exclude_unset=True)
    if "nickname" in dump and dump["nickname"] != user.nickname and UsersModel.nickname_exists(dump["nickname"], db=db):
        raise_http_error(409, ApiCode.NICKNAME_ALREADY_EXISTS)

    # 프론트에서 보낸 명시적 플래그(clearProfileImage)를 확인하여 null 누락 문제를 우회합니다.
    if (
        dump.get("clear_profile_image") is True
        or ("profile_image_id" in dump and dump["profile_image_id"] is None)
    ):
        old_id = user.profile_image_id
        if not UsersModel.update_profile_image_id(user.id, None, db=db):
            raise_http_error(500, ApiCode.INTERNAL_SERVER_ERROR)
        if old_id:
            MediaModel.decrement_ref_count(old_id, db=db)
    elif dump.get("profile_image_id"):
        if MediaModel.get_image_by_id(dump["profile_image_id"], db=db) is None:
            raise_http_error(400, ApiCode.INVALID_REQUEST)
        old_id = user.profile_image_id
        if not UsersModel.update_profile_image_id(user.id, dump["profile_image_id"], db=db):
            raise_http_error(500, ApiCode.INTERNAL_SERVER_ERROR)
        if old_id:
            MediaModel.decrement_ref_count(old_id, db=db)
        MediaModel.increment_ref_count(dump["profile_image_id"], db=db)

    if "nickname" in dump and not UsersModel.update_nickname(user.id, dump["nickname"], db=db):
        raise_http_error(500, ApiCode.INTERNAL_SERVER_ERROR)

    _sync_user_dogs(user.id, dump.get("dogs", []), db=db)

    # 플러시가 아닌 커밋으로 DB 영구 저장을 확정합니다.
    db.commit()
    user_updated = UsersModel.get_user_by_id_with_dogs(user.id, db=db)
    if not user_updated:
        raise_http_error(500, ApiCode.INTERNAL_SERVER_ERROR)
    db.refresh(user_updated)
    return ApiResponse(
        code=ApiCode.USER_UPDATED.value,
        data=UserProfileResponse.model_validate(user_updated),
    )


def _sync_user_dogs(user_id: int, items: list, db: Session) -> None:
    existing_ids = {d.id for d in DogProfilesModel.get_by_owner_id(user_id, db=db)}
    requested_ids = set()
    representative_id = None

    for raw in items:
        item = raw if isinstance(raw, DogProfileUpsertItem) else DogProfileUpsertItem.model_validate(raw)
        if item.id is None:
            dog = DogProfilesModel.create(
                owner_id=user_id,
                name=item.name,
                breed=item.breed,
                gender=item.gender.value,
                birth_date=item.birth_date,
                profile_image_id=item.profile_image_id,
                is_representative=item.is_representative,
                db=db,
            )
            if item.profile_image_id:
                MediaModel.increment_ref_count(item.profile_image_id, db=db)
            requested_ids.add(dog.id)
            if item.is_representative:
                representative_id = dog.id
        else:
            requested_ids.add(item.id)
            if item.is_representative:
                representative_id = item.id
            old = DogProfilesModel.get_by_id(item.id, user_id, db=db)
            if old and old.profile_image_id != item.profile_image_id:
                if old.profile_image_id:
                    MediaModel.decrement_ref_count(old.profile_image_id, db=db)
                if item.profile_image_id:
                    MediaModel.increment_ref_count(item.profile_image_id, db=db)
            DogProfilesModel.update(
                item.id,
                user_id,
                db=db,
                name=item.name,
                breed=item.breed,
                gender=item.gender.value,
                birth_date=item.birth_date,
                profile_image_id=item.profile_image_id,
                is_representative=item.is_representative,
            )

    for did in existing_ids - requested_ids:
        dog = DogProfilesModel.get_by_id(did, user_id, db=db)
        if dog and dog.profile_image_id:
            MediaModel.decrement_ref_count(dog.profile_image_id, db=db)
        DogProfilesModel.delete(did, user_id, db=db)

    if representative_id and requested_ids:
        DogProfilesModel.set_representative(user_id, representative_id, db=db)


def update_password(
    user: CurrentUser,
    data: UpdatePasswordRequest,
    db: Session,
) -> ApiResponse[None]:
    hashed = UsersModel.get_password_hash(user.id, db=db)
    if not hashed or not verify_password(data.current_password, hashed):
        raise_http_error(401, ApiCode.UNAUTHORIZED)
    new_hashed = hash_password(data.new_password)
    if not UsersModel.update_password(user.id, new_hashed, db=db):
        raise_http_error(500, ApiCode.INTERNAL_SERVER_ERROR)
    return ApiResponse(code=ApiCode.PASSWORD_UPDATED.value, data=None)


def delete_me(user: CurrentUser, db: Session) -> None:
    profile_image_id = user.profile_image_id
    if not UsersModel.delete_user(user.id, db=db):
        raise_http_error(500, ApiCode.INTERNAL_SERVER_ERROR)
    if profile_image_id is not None:
        MediaModel.decrement_ref_count(profile_image_id, db=db)
