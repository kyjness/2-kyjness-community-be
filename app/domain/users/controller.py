# 사용자 비즈니스 로직. 프로필 조회·수정, 비밀번호 변경.
from sqlalchemy.orm import Session

from app.api.dependencies import CurrentUser
from app.auth.model import AuthModel
from app.common import ApiCode, raise_http_error, success_response
from app.core.security import hash_password, verify_password
from app.media.model import MediaModel
from app.users.model import UsersModel
from app.users.schema import UpdatePasswordRequest, UpdateUserRequest, UserAvailabilityQuery, UserProfileResponse


def check_availability(query: UserAvailabilityQuery, db: Session) -> dict:
    data = {}
    if query.email:
        data["emailAvailable"] = not UsersModel.email_exists(query.email, db=db)
    if query.nickname:
        data["nicknameAvailable"] = not UsersModel.nickname_exists(query.nickname, db=db)
    return success_response(ApiCode.OK, data)


def get_me(user: CurrentUser) -> dict:
    data = UserProfileResponse.model_validate(user).model_dump(by_alias=True)
    return success_response(ApiCode.USER_RETRIEVED, data)


def update_me(
    user: CurrentUser,
    data: UpdateUserRequest,
    db: Session,
) -> dict:
    dump = data.model_dump(exclude_unset=True)
    if "nickname" in dump and dump["nickname"] != user.nickname and UsersModel.nickname_exists(dump["nickname"], db=db):
        raise_http_error(409, ApiCode.NICKNAME_ALREADY_EXISTS)
    if "profile_image_id" in dump and dump["profile_image_id"] is not None:
        if MediaModel.get_image_by_id(dump["profile_image_id"], db=db) is None:
            raise_http_error(400, ApiCode.INVALID_REQUEST)
    with db.begin():
        if "profile_image_id" in dump:
            old_id = user.profile_image_id
            if not UsersModel.update_profile_image_id(user.id, dump["profile_image_id"], db=db):
                raise_http_error(500, ApiCode.INTERNAL_SERVER_ERROR)
            if old_id:
                MediaModel.decrement_ref_count(old_id, db=db)
            if dump["profile_image_id"] is not None:
                MediaModel.increment_ref_count(dump["profile_image_id"], db=db)
        if "nickname" in dump and not UsersModel.update_nickname(user.id, dump["nickname"], db=db):
            raise_http_error(500, ApiCode.INTERNAL_SERVER_ERROR)
    return success_response(ApiCode.USER_UPDATED)


def update_password(
    user: CurrentUser,
    data: UpdatePasswordRequest,
    db: Session,
) -> dict:
    hashed = UsersModel.get_password_hash(user.id, db=db)
    if not hashed or not verify_password(data.current_password, hashed):
        raise_http_error(401, ApiCode.UNAUTHORIZED)
    new_hashed = hash_password(data.new_password)
    if not UsersModel.update_password(user.id, new_hashed, db=db):
        raise_http_error(500, ApiCode.INTERNAL_SERVER_ERROR)
    return success_response(ApiCode.PASSWORD_UPDATED)


def delete_me(user: CurrentUser, db: Session) -> None:
    profile_image_id = user.profile_image_id
    AuthModel.revoke_sessions_for_user(user.id, db=db)
    if not UsersModel.delete_user(user.id, db=db):
        raise_http_error(500, ApiCode.INTERNAL_SERVER_ERROR)
    if profile_image_id is not None:
        MediaModel.decrement_ref_count(profile_image_id, db=db)
