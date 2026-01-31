# app/users/users_controller.py
"""사용자 관련 비즈니스 로직. 권한은 Route 의존성(require_same_user), 검증·응답은 core 사용."""

from typing import Optional

from fastapi import UploadFile

from app.users.users_model import UsersModel
from app.auth.auth_model import AuthModel
from app.core.config import settings
from app.core.response import success_response, raise_http_error
from app.core.validators import validate_nickname_format, validate_password_format, validate_profile_image_url
from app.core.file_upload import validate_image_upload, PROFILE_ALLOWED_TYPES, MAX_FILE_SIZE


async def upload_profile_image(user_id: int, profile_image: Optional[UploadFile]):
    """프로필 이미지 업로드. 권한은 Route(require_same_user)에서 검사."""
    if not profile_image:
        raise_http_error(400, "MISSING_REQUIRED_FIELD")
    await validate_image_upload(profile_image, PROFILE_ALLOWED_TYPES, MAX_FILE_SIZE)
    user = UsersModel.get_user_by_id(user_id)
    if not user:
        raise_http_error(404, "USER_NOT_FOUND")
    file_extension = "jpg"
    profile_image_url = f"{settings.BE_API_URL}/public/image/profile/{user_id}.{file_extension}"
    if not UsersModel.update_profile_image_url(user_id, profile_image_url):
        raise_http_error(500, "INTERNAL_SERVER_ERROR")
    return success_response("PROFILE_IMAGE_UPLOADED", {"profileImageUrl": profile_image_url})


def check_email(email: Optional[str]):
    if not email or not isinstance(email, str) or not email.strip():
        raise_http_error(400, "MISSING_REQUIRED_FIELD")
    is_available = not AuthModel.email_exists(email)
    return success_response("EMAIL_AVAILABLE", {"available": is_available})


def check_nickname(nickname: Optional[str]):
    if not nickname or not isinstance(nickname, str) or not nickname.strip():
        raise_http_error(400, "MISSING_REQUIRED_FIELD")
    if not validate_nickname_format(nickname):
        raise_http_error(400, "INVALID_NICKNAME_FORMAT")
    if AuthModel.nickname_exists(nickname):
        raise_http_error(409, "NICKNAME_ALREADY_EXISTS")
    return success_response("NICKNAME_AVAILABLE", {"available": True})


def get_user(user_id: int):
    """내 정보 조회. 권한은 Route(require_same_user)에서 검사."""
    user = UsersModel.get_user_by_id(user_id)
    if not user:
        raise_http_error(404, "USER_NOT_FOUND")
    return success_response("USER_RETRIEVED", user)


def update_user(
    user_id: int,
    nickname: Optional[str] = None,
    profile_image_url: Optional[str] = None,
):
    """내 정보 수정. 권한은 Route(require_same_user)에서 검사."""
    if nickname is None and profile_image_url is None:
        raise_http_error(400, "MISSING_REQUIRED_FIELD")
    if nickname is not None:
        if " " in nickname or not validate_nickname_format(nickname):
            raise_http_error(400, "INVALID_NICKNAME_FORMAT")
        current_user = UsersModel.get_user_by_id(user_id)
        if not current_user:
            raise_http_error(404, "USER_NOT_FOUND")
        if current_user["nickname"] != nickname:
            if AuthModel.nickname_exists(nickname):
                raise_http_error(409, "NICKNAME_ALREADY_EXISTS")
            if not UsersModel.update_nickname(user_id, nickname):
                raise_http_error(500, "INTERNAL_SERVER_ERROR")
    if profile_image_url is not None:
        if not validate_profile_image_url(profile_image_url):
            raise_http_error(400, "INVALID_PROFILEIMAGEURL")
        if not UsersModel.update_profile_image_url(user_id, profile_image_url):
            raise_http_error(500, "INTERNAL_SERVER_ERROR")
    return success_response("USER_UPDATED")


def update_password(user_id: int, current_password: str, new_password: str):
    """비밀번호 변경. 권한은 Route(require_same_user)에서 검사."""
    if not validate_password_format(current_password):
        raise_http_error(400, "INVALID_CURRENTPASSWORD_FORMAT")
    if not validate_password_format(new_password):
        raise_http_error(400, "INVALID_NEWPASSWORD_FORMAT")
    user = UsersModel.get_user_by_id(user_id)
    if not user:
        raise_http_error(404, "USER_NOT_FOUND")
    if not AuthModel.verify_password(user_id, current_password):
        raise_http_error(401, "UNAUTHORIZED")
    if not UsersModel.update_password(user_id, new_password):
        raise_http_error(500, "INTERNAL_SERVER_ERROR")
    return success_response("PASSWORD_UPDATED")


def withdraw_user(user_id: int):
    """회원 탈퇴. 권한은 Route(require_same_user)에서 검사."""
    user = UsersModel.get_user_by_id(user_id)
    if not user:
        raise_http_error(404, "USER_NOT_FOUND")
    if not UsersModel.delete_user(user_id):
        raise_http_error(500, "INTERNAL_SERVER_ERROR")
    return None
