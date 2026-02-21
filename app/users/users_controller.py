# app/users/users_controller.py
"""사용자 관련 비즈니스 로직. 입력 형식 검증은 DTO(Pydantic)에서 수행, 컨트롤러는 검증된 값만 처리."""

from app.auth.auth_model import AuthModel
from app.users.users_model import UsersModel
from app.users.users_schema import UserProfileResponse, UpdateUserRequest, UpdatePasswordRequest
from app.core.codes import ApiCode
from app.core.response import success_response, raise_http_error


def check_availability(query) -> dict:
    """이메일·닉네임 가용 여부. 요청한 항목만 검사해 반환. 사용자 정보 노출 없음."""
    data = {}
    if query.email:
        data["emailAvailable"] = not UsersModel.email_exists(query.email)
    if query.nickname:
        data["nicknameAvailable"] = not UsersModel.nickname_exists(query.nickname)
    return success_response(ApiCode.OK, data)


def get_user_profile(user_id: int):
    """내 프로필 조회. createdAt 포함. GET /users/me 전용."""
    user = UsersModel.get_user_by_id(user_id)
    if not user:
        raise_http_error(404, ApiCode.USER_NOT_FOUND)
    data = UserProfileResponse(**user).model_dump()
    return success_response(ApiCode.USER_RETRIEVED, data)


def update_user(user_id: int, data: UpdateUserRequest):
    """내 정보 수정. /users/me 전용. DTO 통째로 받음. profileImageId는 미리 업로드한 이미지 id."""
    if data.nickname is not None:
        current_user = UsersModel.get_user_by_id(user_id)
        if not current_user:
            raise_http_error(404, ApiCode.USER_NOT_FOUND)
        if current_user["nickname"] != data.nickname:
            if UsersModel.nickname_exists(data.nickname):
                raise_http_error(409, ApiCode.NICKNAME_ALREADY_EXISTS)
            if not UsersModel.update_nickname(user_id, data.nickname):
                raise_http_error(500, ApiCode.INTERNAL_SERVER_ERROR)
    if data.profileImageId is not None:
        profile_image_url = UsersModel.resolve_image_url(data.profileImageId)
        if profile_image_url is None:
            raise_http_error(400, ApiCode.INVALID_REQUEST)
        UsersModel.soft_delete_old_profile_image(user_id)
        if not UsersModel.update_profile_image_url(user_id, profile_image_url):
            raise_http_error(500, ApiCode.INTERNAL_SERVER_ERROR)
    return success_response(ApiCode.USER_UPDATED)


def update_password(user_id: int, data: UpdatePasswordRequest):
    """비밀번호 변경. /users/me 전용. DTO 통째로 받음. 형식 검증은 DTO에서 완료."""
    user = UsersModel.get_user_by_id(user_id)
    if not user:
        raise_http_error(404, ApiCode.USER_NOT_FOUND)
    if not UsersModel.verify_password(user_id, data.currentPassword):
        raise_http_error(401, ApiCode.UNAUTHORIZED)
    if not UsersModel.update_password(user_id, data.newPassword):
        raise_http_error(500, ApiCode.INTERNAL_SERVER_ERROR)
    return success_response(ApiCode.PASSWORD_UPDATED)


def withdraw_user(user_id: int):
    """회원 탈퇴. /users/me 전용. 성공 시 반환 없음(route에서 204 반환), 실패 시 예외."""
    user = UsersModel.get_user_by_id(user_id)
    if not user:
        raise_http_error(404, ApiCode.USER_NOT_FOUND)
    AuthModel.revoke_sessions_for_user(user_id)
    if not UsersModel.delete_user(user_id):
        raise_http_error(500, ApiCode.INTERNAL_SERVER_ERROR)
