# app/auth/auth_controller.py
"""인증 비즈니스 로직. 입력 형식 검증은 Pydantic + core.validators, 에러는 core.response."""

import logging
from typing import Optional

from app.auth.auth_model import AuthModel
from app.core.response import success_response, raise_http_error
from app.core.validators import validate_password_format, validate_nickname_format, validate_profile_image_url

logger = logging.getLogger(__name__)


def signup(
    email: str,
    password: str,
    password_confirm: str,
    nickname: str,
    profile_image_url: Optional[str] = None,
):
    if not validate_password_format(password):
        raise_http_error(400, "INVALID_PASSWORD_FORMAT")
    if password != password_confirm:
        raise_http_error(400, "PASSWORD_MISMATCH")
    if " " in nickname or not validate_nickname_format(nickname):
        raise_http_error(400, "INVALID_NICKNAME_FORMAT")
    if not validate_profile_image_url(profile_image_url):
        raise_http_error(400, "INVALID_PROFILEIMAGEURL")
    if AuthModel.email_exists(email):
        raise_http_error(409, "EMAIL_ALREADY_EXISTS")
    if AuthModel.nickname_exists(nickname):
        raise_http_error(409, "NICKNAME_ALREADY_EXISTS")
    AuthModel.create_user(email, password, nickname, profile_image_url)
    return success_response("SIGNUP_SUCCESS")


def login(email: str, password: str):
    if not validate_password_format(password):
        raise_http_error(400, "INVALID_PASSWORD_FORMAT")
    user = AuthModel.find_user_by_email(email)
    if not user:
        logger.warning("Login failed: User not found")
        raise_http_error(401, "INVALID_CREDENTIALS")
    if not AuthModel.verify_password(user["userId"], password):
        logger.warning("Login failed: Invalid password")
        raise_http_error(401, "INVALID_CREDENTIALS")
    session_id = AuthModel.create_token(user["userId"])
    return success_response("LOGIN_SUCCESS", {
        "userId": user["userId"],
        "email": user["email"],
        "nickname": user["nickname"],
        "authToken": session_id,
        "profileImage": user["profileImageUrl"],
    })


def logout(session_id: Optional[str]):
    AuthModel.revoke_token(session_id)
    return success_response("LOGOUT_SUCCESS")


def get_me(user_id: int):
    user = AuthModel.find_user_by_id(user_id)
    if not user:
        raise_http_error(401, "UNAUTHORIZED")
    return success_response("AUTH_SUCCESS", {
        "userId": user["userId"],
        "email": user["email"],
        "nickname": user["nickname"],
        "profileImageUrl": user["profileImageUrl"],
    })
