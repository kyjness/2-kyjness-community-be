# app/users/controller.py

from app.auth.model import AuthModel
from app.users.model import UsersModel
from app.media.model import MediaModel
from app.core.database import get_connection
from app.core.security import hash_password, verify_password
from app.users.schema import UserProfileResponse, UpdateUserRequest, UpdatePasswordRequest, UserAvailabilityQuery
from app.core.codes import ApiCode
from app.core.response import success_response, raise_http_error


def check_availability(query: UserAvailabilityQuery) -> dict:
    data = {}
    if query.email:
        data["emailAvailable"] = not UsersModel.email_exists(query.email)
    if query.nickname:
        data["nicknameAvailable"] = not UsersModel.nickname_exists(query.nickname)
    return success_response(ApiCode.OK, data)

def get_me(user_id: int):
    row = UsersModel.find_user_by_id(user_id)
    if not row:
        raise_http_error(404, ApiCode.USER_NOT_FOUND)
    data = UserProfileResponse.model_validate(row).model_dump(by_alias=True)
    return success_response(ApiCode.USER_RETRIEVED, data)

def update_me(user_id: int, data: UpdateUserRequest):
    current = UsersModel.find_user_by_id(user_id)
    if not current:
        raise_http_error(404, ApiCode.USER_NOT_FOUND)
    if data.nickname is not None and current["nickname"] != data.nickname:
        if UsersModel.nickname_exists(data.nickname):
            raise_http_error(409, ApiCode.NICKNAME_ALREADY_EXISTS)
    if data.profileImageId is not None:
        profile_image_url = MediaModel.get_url_by_id(data.profileImageId)
        if profile_image_url is None:
            raise_http_error(400, ApiCode.INVALID_REQUEST)
    with get_connection() as conn:
        if data.nickname is not None:
            if not UsersModel.update_nickname(user_id, data.nickname, conn=conn):
                raise_http_error(500, ApiCode.INTERNAL_SERVER_ERROR)
        if data.profileImageId is not None:
            if current.get("profile_image_url"):
                MediaModel.withdraw_by_url(current["profile_image_url"], conn=conn)
            if not UsersModel.update_profile_image_url(
                user_id, profile_image_url, conn=conn
            ):
                raise_http_error(500, ApiCode.INTERNAL_SERVER_ERROR)
        conn.commit()
    return success_response(ApiCode.USER_UPDATED)

def update_password(user_id: int, data: UpdatePasswordRequest):
    if not UsersModel.find_user_by_id(user_id):
        raise_http_error(404, ApiCode.USER_NOT_FOUND)
    hashed = UsersModel.get_password_hash(user_id)
    if not hashed or not verify_password(data.currentPassword, hashed):
        raise_http_error(401, ApiCode.UNAUTHORIZED)
    new_hashed = hash_password(data.newPassword)
    if not UsersModel.update_password(user_id, new_hashed):
        raise_http_error(500, ApiCode.INTERNAL_SERVER_ERROR)
    return success_response(ApiCode.PASSWORD_UPDATED)

def withdraw_me(user_id: int):
    if not UsersModel.find_user_by_id(user_id):
        raise_http_error(404, ApiCode.USER_NOT_FOUND)
    with get_connection() as conn:
        AuthModel.revoke_sessions_for_user(user_id, conn=conn)
        if not UsersModel.withdraw_user(user_id, conn=conn):
            raise_http_error(500, ApiCode.INTERNAL_SERVER_ERROR)
        conn.commit()
