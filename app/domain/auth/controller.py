# 인증 비즈니스 로직. 회원가입·로그인(JWT)·로그아웃·리프레시.
from __future__ import annotations

from typing import Optional

from redis.asyncio import Redis
from sqlalchemy.orm import Session

from app.auth.schema import (
    AccessTokenData,
    LoginRequest,
    LoginSuccessData,
    SignUpRequest,
    SessionUserResponse,
)
from app.common import ApiCode, ApiResponse, UserStatus, raise_http_error
from app.api.dependencies import CurrentUser
from app.core.security import create_access_token, create_refresh_token, verify_password, verify_refresh_token
from app.media.model import MediaModel
from app.users.model import UsersModel

_REFRESH_KEY_PREFIX = "rt:"


def signup_user(data: SignUpRequest, db: Session) -> ApiResponse[None]:
    if UsersModel.email_exists(data.email, db=db):
        raise_http_error(409, ApiCode.EMAIL_ALREADY_EXISTS)
    if UsersModel.nickname_exists(data.nickname, db=db):
        raise_http_error(409, ApiCode.NICKNAME_ALREADY_EXISTS)
    has_image = data.profile_image_id is not None
    has_token = bool(data.signup_token)
    if has_image != has_token:
        raise_http_error(400, ApiCode.MISSING_REQUIRED_FIELD)
    profile_image_id = None
    if has_image and has_token:
        if MediaModel.verify_signup_token(data.profile_image_id, data.signup_token, db=db) is None:
            raise_http_error(400, ApiCode.SIGNUP_IMAGE_TOKEN_INVALID)
        profile_image_id = data.profile_image_id
    from app.core.security import hash_password
    hashed = hash_password(data.password)
    created = UsersModel.create_user(
        data.email,
        hashed,
        data.nickname,
        profile_image_id=profile_image_id,
        db=db,
    )
    if profile_image_id is not None:
        MediaModel.attach_signup_image(profile_image_id, created.id, db=db)
    return ApiResponse(code=ApiCode.SIGNUP_SUCCESS.value, data=None)


def login_user(data: LoginRequest, db: Session) -> tuple[ApiResponse[LoginSuccessData], str, str, int]:
    user = UsersModel.get_user_by_email(data.email, db=db)
    if not user:
        raise_http_error(401, ApiCode.INVALID_CREDENTIALS, "이메일 또는 비밀번호가 일치하지 않습니다")
    if not UserStatus.is_active_value(user.status):
        raise_http_error(403, ApiCode.FORBIDDEN, UserStatus.inactive_message_ko(user.status))
    if not verify_password(data.password, user.password):
        raise_http_error(401, ApiCode.INVALID_CREDENTIALS, "이메일 또는 비밀번호가 일치하지 않습니다")
    access_token = create_access_token(sub=user.id)
    refresh_token = create_refresh_token(sub=user.id)
    data_payload = LoginSuccessData(
        id=user.id,
        email=user.email,
        nickname=user.nickname,
        status=user.status,
        profile_image_id=user.profile_image_id,
        profile_image_url=user.profile_image_url,
        access_token=access_token,
    )
    return (
        ApiResponse(code=ApiCode.LOGIN_SUCCESS.value, data=data_payload),
        access_token,
        refresh_token,
        user.id,
    )


async def logout_user(refresh_token: Optional[str], redis: Optional[Redis]) -> ApiResponse[None]:
    if not refresh_token:
        return ApiResponse(code=ApiCode.LOGOUT_SUCCESS.value, data=None)
    try:
        payload = verify_refresh_token(refresh_token)
        user_id = payload.get("sub")
        if user_id is not None and redis:
            await redis.delete(f"{_REFRESH_KEY_PREFIX}{user_id}")
    except Exception:
        pass
    return ApiResponse(code=ApiCode.LOGOUT_SUCCESS.value, data=None)


async def revoke_refresh_for_user(user_id: int, redis: Optional[Redis]) -> None:
    """비밀번호 변경·회원 탈퇴 시 Refresh Token 무효화."""
    if redis:
        await redis.delete(f"{_REFRESH_KEY_PREFIX}{user_id}")


async def refresh_tokens(
    refresh_token: Optional[str], redis: Optional[Redis], db: Session
) -> tuple[ApiResponse[AccessTokenData], str]:
    if not refresh_token:
        raise_http_error(401, ApiCode.UNAUTHORIZED)
    payload = verify_refresh_token(refresh_token)
    user_id = int(payload["sub"])
    if redis:
        stored = await redis.get(f"{_REFRESH_KEY_PREFIX}{user_id}")
        if stored is None or stored != refresh_token:
            raise_http_error(401, ApiCode.UNAUTHORIZED)
    user = UsersModel.get_user_by_id(user_id, db=db)
    if not user:
        raise_http_error(401, ApiCode.UNAUTHORIZED)
    if not UserStatus.is_active_value(user.status):
        raise_http_error(401, ApiCode.UNAUTHORIZED, UserStatus.inactive_message_ko(user.status))
    new_access = create_access_token(sub=user_id)
    return (
        ApiResponse(code=ApiCode.AUTH_SUCCESS.value, data=AccessTokenData(access_token=new_access)),
        new_access,
    )


def get_session_user(user: CurrentUser) -> ApiResponse[SessionUserResponse]:
    return ApiResponse(
        code=ApiCode.AUTH_SUCCESS.value,
        data=SessionUserResponse.model_validate(user),
    )
