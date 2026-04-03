# 인증 의존성. Authorization Bearer 검증 → CurrentUser. Full-Async.

from typing import Any, cast

import jwt
from fastapi import Depends, Request
from pydantic import Field
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.common import BaseSchema, OptionalPublicId, PublicId, UserStatus, UtcDatetime
from app.common.exceptions import ForbiddenException, UnauthorizedException
from app.core.ids import jwt_sub_to_uuid
from app.core.security import access_jti_blacklist_redis_key, verify_access_token
from app.db import utc_now
from app.users.model import UsersModel

from .db import get_slave_db


class CurrentUser(BaseSchema):
    id: PublicId = Field(..., description="사용자 공개 ID (Base62)")
    email: str = ""
    nickname: str = ""
    role: str | None = Field(default="USER", description="USER|ADMIN")
    profile_image_id: OptionalPublicId = None
    profile_image_url: str | None = None
    created_at: UtcDatetime = Field(default_factory=utc_now)


def _bearer_token(request: Request) -> str | None:
    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        return None
    return auth[7:].strip() or None


async def _ensure_jti_not_blacklisted(jti: str, request: Request) -> None:
    """Access Token jti 블랙리스트(로그아웃). Redis 장애 시 Fail-open."""
    redis_raw = getattr(request.app.state, "redis", None)
    if not isinstance(redis_raw, Redis):
        return
    key = access_jti_blacklist_redis_key(jti)
    try:
        redis = cast(Any, redis_raw)
        if await redis.get(key) is not None:
            raise UnauthorizedException(message="인증 토큰이 유효하지 않습니다.")
    except UnauthorizedException:
        raise
    except Exception:
        return


async def get_current_user_optional(
    request: Request,
    db: AsyncSession = Depends(get_slave_db),
) -> CurrentUser | None:
    token = _bearer_token(request)
    if not token:
        return None
    try:
        payload = verify_access_token(token)
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None
    jti = payload.get("jti")
    if isinstance(jti, str) and jti.strip():
        try:
            await _ensure_jti_not_blacklisted(jti.strip(), request)
        except UnauthorizedException:
            return None
    sub = payload.get("sub")
    if sub is None:
        return None
    if not isinstance(sub, str):
        return None
    try:
        user_id = jwt_sub_to_uuid(sub)
    except ValueError:
        return None
    async with db.begin():
        user = await UsersModel.get_user_by_id(user_id, db=db)
        if not user or not UserStatus.is_active_value(user.status):
            return None
        return CurrentUser.model_validate(user)


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_slave_db),
) -> CurrentUser:
    token = _bearer_token(request)
    if not token:
        raise UnauthorizedException(message="로그인이 필요합니다.")
    try:
        payload = verify_access_token(token)
    except jwt.ExpiredSignatureError:
        raise UnauthorizedException(message="인증 토큰이 유효하지 않습니다.")
    except jwt.InvalidTokenError:
        raise UnauthorizedException(message="인증 토큰이 유효하지 않습니다.")
    jti = payload.get("jti")
    if isinstance(jti, str) and jti.strip():
        await _ensure_jti_not_blacklisted(jti.strip(), request)
    sub = payload.get("sub")
    if sub is None:
        raise UnauthorizedException(message="인증 토큰이 유효하지 않습니다.")
    if not isinstance(sub, str):
        raise UnauthorizedException(message="인증 토큰이 유효하지 않습니다.")
    try:
        user_id = jwt_sub_to_uuid(sub)
    except ValueError:
        raise UnauthorizedException(message="인증 토큰이 유효하지 않습니다.") from None
    async with db.begin():
        user = await UsersModel.get_user_by_id(user_id, db=db)
        if not user:
            raise UnauthorizedException(message="인증 토큰이 유효하지 않습니다.")
        if not UserStatus.is_active_value(user.status):
            raise ForbiddenException(message=UserStatus.inactive_message_ko(user.status))
        return CurrentUser.model_validate(user)


async def get_current_admin(
    current_user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    if getattr(current_user, "role", None) != "ADMIN":
        raise ForbiddenException(message="관리자 권한이 필요합니다.")
    return current_user
