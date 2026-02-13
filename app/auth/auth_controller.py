# app/auth/auth_controller.py
"""인증 비즈니스 로직. 입력 형식 검증은 DTO(Pydantic)에서 수행, 컨트롤러는 검증된 값만 처리."""

import logging
from typing import Optional

from app.auth.auth_model import AuthModel
from app.core.response import success_response, raise_http_error

logger = logging.getLogger(__name__)


def signup(
    email: str,
    password: str,
    nickname: str,
    profile_image_url: Optional[str] = None,
):
    # 비밀번호·닉네임·profileImageUrl 형식 검증은 DTO(SignUpRequest)에서 완료
    if AuthModel.email_exists(email):
        raise_http_error(409, "EMAIL_ALREADY_EXISTS")
    if AuthModel.nickname_exists(nickname):
        raise_http_error(409, "NICKNAME_ALREADY_EXISTS")
    AuthModel.create_user(email, password, nickname, profile_image_url)
    return success_response("SIGNUP_SUCCESS")


def login(email: str, password: str):
    """쿠키-세션 방식 로그인. 세션 ID는 응답 body에 넣지 않고, 라우트에서 Set-Cookie로만 전달 (JWT 아님)."""
    # 비밀번호 형식 검증은 DTO(LoginRequest)에서 완료
    user = AuthModel.find_user_by_email(email)
    if not user:
        logger.warning("Login failed: User not found")
        raise_http_error(401, "INVALID_CREDENTIALS")
    if not AuthModel.verify_password(user["userId"], password):
        logger.warning("Login failed: Invalid password")
        raise_http_error(401, "INVALID_CREDENTIALS")
    session_id = AuthModel.create_session(user["userId"])
    response_body = success_response("LOGIN_SUCCESS", {
        "userId": user["userId"],
        "email": user["email"],
        "nickname": user["nickname"],
        "profileImageUrl": user["profileImageUrl"],
    })
    return response_body, session_id


def logout(session_id: Optional[str]):
    AuthModel.revoke_session(session_id)
    return success_response("LOGOUT_SUCCESS")

def get_me(user_id: int):
    """세션 검증용. 최소 4개 필드만 반환. 프로필 전체는 GET /users/me."""
    user = AuthModel.get_user_minimal_for_session(user_id)
    if not user:
        raise_http_error(401, "UNAUTHORIZED")
    return success_response("AUTH_SUCCESS", user)

