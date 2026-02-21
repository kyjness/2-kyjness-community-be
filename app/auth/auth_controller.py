# app/auth/auth_controller.py
"""인증 비즈니스 로직. 입력 형식 검증은 DTO(Pydantic)에서 수행, 컨트롤러는 검증된 값만 처리."""

from typing import Optional

from app.auth.auth_model import AuthModel
from app.auth.auth_schema import SignUpRequest, LoginRequest, LoginResponse, SessionUserResponse
from app.core.codes import ApiCode
from app.core.response import success_response, raise_http_error
from app.media.media_model import MediaModel
from app.users.users_model import UsersModel


def signup(data: SignUpRequest):
    if UsersModel.email_exists(data.email):
        raise_http_error(409, ApiCode.EMAIL_ALREADY_EXISTS)
    if UsersModel.nickname_exists(data.nickname):
        raise_http_error(409, ApiCode.NICKNAME_ALREADY_EXISTS)
    profile_image_url = None
    if data.profileImageId:
        profile_image_url = MediaModel.get_url_by_id(data.profileImageId)
    UsersModel.create_user(data.email, data.password, data.nickname, profile_image_url)
    return success_response(ApiCode.SIGNUP_SUCCESS)


def login(data: LoginRequest):
    """쿠키-세션 방식 로그인. 세션 ID는 응답 body에 넣지 않고, 라우트에서 Set-Cookie로만 전달 (JWT 아님)."""
    user = UsersModel.find_user_by_email(data.email)
    if not user:
        raise_http_error(401, ApiCode.EMAIL_NOT_FOUND, "존재하지 않는 이메일입니다")
    if not UsersModel.verify_password(user["userId"], data.password):
        raise_http_error(401, ApiCode.INVALID_CREDENTIALS)
    session_id = AuthModel.create_session(user["userId"])
    payload = LoginResponse(
        userId=user["userId"],
        email=user["email"],
        nickname=user["nickname"],
        profileImageUrl=user["profileImageUrl"],
    ).model_dump()
    return success_response(ApiCode.LOGIN_SUCCESS, payload), session_id


def logout(session_id: Optional[str]):
    AuthModel.revoke_session(session_id)
    return success_response(ApiCode.LOGOUT_SUCCESS)


def get_me(user_id: int):
    """세션 검증용. 최소 4개 필드만 반환. 프로필 전체는 GET /users/me."""
    user = UsersModel.get_user_summary(user_id)
    if not user:
        raise_http_error(401, ApiCode.UNAUTHORIZED)
    data = SessionUserResponse(**user).model_dump()
    return success_response(ApiCode.AUTH_SUCCESS, data)

