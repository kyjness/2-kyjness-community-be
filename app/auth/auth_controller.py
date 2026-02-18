# app/auth/auth_controller.py
"""인증 비즈니스 로직. 입력 형식 검증은 DTO(Pydantic)에서 수행, 컨트롤러는 검증된 값만 처리."""

import logging
from typing import Optional

from app.auth.auth_model import AuthModel
from app.auth.auth_schema import SignUpRequest, LoginRequest, LoginData, MeData
from app.core.codes import ApiCode
from app.core.response import success_response, raise_http_error
from app.media.media_model import MediaModel

logger = logging.getLogger(__name__)


def signup(data: SignUpRequest):
    if AuthModel.email_exists(data.email):
        raise_http_error(409, ApiCode.EMAIL_ALREADY_EXISTS)
    if AuthModel.nickname_exists(data.nickname):
        raise_http_error(409, ApiCode.NICKNAME_ALREADY_EXISTS)
    profile_image_url = None
    if data.profileImageId:
        profile_image_url = MediaModel.get_url_by_id(data.profileImageId)
        if not profile_image_url:
            raise_http_error(400, ApiCode.INVALID_REQUEST)
    AuthModel.create_user(data.email, data.password, data.nickname, profile_image_url)
    return success_response(ApiCode.SIGNUP_SUCCESS)


def login(data: LoginRequest):
    """쿠키-세션 방식 로그인. 세션 ID는 응답 body에 넣지 않고, 라우트에서 Set-Cookie로만 전달 (JWT 아님)."""
    user = AuthModel.find_user_by_email(data.email)
    if not user:
        logger.warning("Login failed: User not found")
        raise_http_error(401, ApiCode.INVALID_CREDENTIALS)
    if not AuthModel.verify_password(user["userId"], data.password):
        logger.warning("Login failed: Invalid password")
        raise_http_error(401, ApiCode.INVALID_CREDENTIALS)
    session_id = AuthModel.create_session(user["userId"])
    data = LoginData(
        userId=user["userId"],
        email=user["email"],
        nickname=user["nickname"],
        profileImageUrl=user["profileImageUrl"],
    ).model_dump()
    return success_response(ApiCode.LOGIN_SUCCESS, data), session_id


def logout(session_id: Optional[str]):
    AuthModel.revoke_session(session_id)
    return success_response(ApiCode.LOGOUT_SUCCESS)


def get_me(user_id: int):
    """세션 검증용. 최소 4개 필드만 반환. 프로필 전체는 GET /users/me."""
    user = AuthModel.get_user_minimal_for_session(user_id)
    if not user:
        raise_http_error(401, ApiCode.UNAUTHORIZED)
    data = MeData(**user).model_dump()
    return success_response(ApiCode.AUTH_SUCCESS, data)

