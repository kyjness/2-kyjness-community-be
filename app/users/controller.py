from sqlalchemy.orm import Session

from app.auth.model import AuthModel
from app.common import ApiCode, raise_http_error, success_response
from app.core.dependencies import CurrentUser
from app.media.model import MediaModel
from app.users.model import UsersModel
from app.users.schema import UpdatePasswordRequest, UpdateUserRequest, UserAvailabilityQuery, UserProfileResponse
from app.core.security import hash_password, verify_password


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


def update_me(user: CurrentUser, data: UpdateUserRequest, db: Session) -> dict:
    if data.nickname is not None and user.nickname != data.nickname and UsersModel.nickname_exists(data.nickname, db=db):
        raise_http_error(409, ApiCode.NICKNAME_ALREADY_EXISTS)
    profile_image_url = None
    if data.profile_image_id is not None:
        profile_image_url = MediaModel.get_url_by_id(data.profile_image_id, db=db)
        if profile_image_url is None:
            raise_http_error(400, ApiCode.INVALID_REQUEST)
    if data.nickname is not None and not UsersModel.update_nickname(user.id, data.nickname, db=db):
        raise_http_error(500, ApiCode.INTERNAL_SERVER_ERROR)
    if profile_image_url is not None:
        if user.profile_image_url:
            MediaModel.withdraw_by_url(user.profile_image_url, db=db)
        if not UsersModel.update_profile_image_url(user.id, profile_image_url, db=db):
            raise_http_error(500, ApiCode.INTERNAL_SERVER_ERROR)
    return success_response(ApiCode.USER_UPDATED)


def update_password(user: CurrentUser, data: UpdatePasswordRequest, db: Session) -> dict:
    hashed = UsersModel.get_password_hash(user.id, db=db)
    if not hashed or not verify_password(data.current_password, hashed):
        raise_http_error(401, ApiCode.UNAUTHORIZED)
    new_hashed = hash_password(data.new_password)
    if not UsersModel.update_password(user.id, new_hashed, db=db):
        raise_http_error(500, ApiCode.INTERNAL_SERVER_ERROR)
    return success_response(ApiCode.PASSWORD_UPDATED)


def withdraw_me(user: CurrentUser, db: Session) -> None:
    AuthModel.revoke_sessions_for_user(user.id, db=db)
    if not UsersModel.withdraw_user(user.id, db=db):
        raise_http_error(500, ApiCode.INTERNAL_SERVER_ERROR)
