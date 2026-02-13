# app/users/users_controller.py
"""사용자 관련 비즈니스 로직. 입력 형식 검증은 DTO(Pydantic)에서 수행, 컨트롤러는 검증된 값만 처리."""

from typing import Optional

from fastapi import UploadFile

from app.users.users_model import UsersModel
from app.auth.auth_model import AuthModel
from app.core.response import success_response, raise_http_error
from app.core.file_upload import save_profile_image


async def upload_profile_image(user_id: int, profile_image: Optional[UploadFile]):
    """
    프로필 이미지 업로드. /users/me 전용.
    검증·저장·URL 생성은 file_upload.save_profile_image에서 처리. 컨트롤러는 권한·DB만.
    """
    user = UsersModel.get_user_by_id(user_id)
    if not user:
        raise_http_error(404, "USER_NOT_FOUND")

    profile_image_url = await save_profile_image(profile_image)

    if not UsersModel.update_profile_image_url(user_id, profile_image_url):
        raise_http_error(500, "INTERNAL_SERVER_ERROR")
    return success_response("PROFILE_IMAGE_UPLOADED", {"profileImageUrl": profile_image_url})


def check_user_exists(query):
    """REST: users 리소스 존재 여부 조회. DTO에서 이미 email|nickname 정확히 하나 검증됨."""
    if query.email:
        exists = AuthModel.email_exists(query.email)
        return success_response("OK", {"exists": exists})
    exists = AuthModel.nickname_exists(query.nickname)
    return success_response("OK", {"exists": exists})


def get_user(user_id: int):
    """내 프로필 리소스 조회. createdAt 포함. /users/me 전용."""
    user = UsersModel.get_user_by_id(user_id)
    if not user:
        raise_http_error(404, "USER_NOT_FOUND")
    return success_response("USER_RETRIEVED", user)


def update_user(
    user_id: int,
    nickname: Optional[str] = None,
    profile_image_url: Optional[str] = None,
):
    """내 정보 수정. /users/me 전용. DTO에서 필수·닉네임 형식 검증 완료."""
    if nickname is not None:
        current_user = UsersModel.get_user_by_id(user_id)
        if not current_user:
            raise_http_error(404, "USER_NOT_FOUND")
        if current_user["nickname"] != nickname:
            if AuthModel.nickname_exists(nickname):
                raise_http_error(409, "NICKNAME_ALREADY_EXISTS")
            if not UsersModel.update_nickname(user_id, nickname):
                raise_http_error(500, "INTERNAL_SERVER_ERROR")
    if profile_image_url is not None:
        # profileImageUrl 형식 검증은 DTO(UpdateUserRequest)에서 완료
        if not UsersModel.update_profile_image_url(user_id, profile_image_url):
            raise_http_error(500, "INTERNAL_SERVER_ERROR")
    return success_response("USER_UPDATED")


def update_password(user_id: int, current_password: str, new_password: str):
    """비밀번호 변경. /users/me 전용. DTO에서 비밀번호 형식 검증 완료."""
    user = UsersModel.get_user_by_id(user_id)
    if not user:
        raise_http_error(404, "USER_NOT_FOUND")
    if not AuthModel.verify_password(user_id, current_password):
        raise_http_error(401, "UNAUTHORIZED")
    if not UsersModel.update_password(user_id, new_password):
        raise_http_error(500, "INTERNAL_SERVER_ERROR")
    return success_response("PASSWORD_UPDATED")


def withdraw_user(user_id: int):
    """회원 탈퇴. /users/me 전용. 성공 시 success_response, 실패 시 예외."""
    user = UsersModel.get_user_by_id(user_id)
    if not user:
        raise_http_error(404, "USER_NOT_FOUND")
    if not UsersModel.delete_user(user_id):
        raise_http_error(500, "INTERNAL_SERVER_ERROR")
    return success_response("USER_DELETED", None)
