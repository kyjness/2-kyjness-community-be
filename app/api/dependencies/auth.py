# 인증 의존성. Authorization Bearer 검증 → CurrentUser. Full-Async.

import hashlib
from typing import Any, cast

import jwt
from fastapi import Depends, Request
from pydantic import Field
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.common import BaseSchema, UserStatus, UtcDatetime
from app.common.exceptions import ForbiddenException, UnauthorizedException
from app.core.ids import is_valid_ulid_str
from app.core.security import verify_access_token
from app.db import utc_now
from app.users.model import UsersModel

from .db import get_slave_db


class CurrentUser(BaseSchema):
    id: str = Field(..., description="사용자 ID (ULID)")
    email: str = ""
    nickname: str = ""
    role: str | None = Field(default="USER", description="USER|ADMIN")
    profile_image_id: str | None = None
    profile_image_url: str | None = None
    created_at: UtcDatetime = Field(default_factory=utc_now)


def _bearer_token(request: Request) -> str | None:
    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        return None
    return auth[7:].strip() or None


def _sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


async def _ensure_not_blacklisted(token: str, request: Request) -> None:
    """Access Token 블랙리스트(로그아웃) 선검사. Redis 장애 시 Fail-open(가용성 우선)."""
    redis_raw = getattr(request.app.state, "redis", None)
    if not isinstance(redis_raw, Redis):
        return
    key = f"blacklist:{_sha256_hex(token)}"
    try:
        redis = cast(Any, redis_raw)
        if await redis.get(key) is not None:
            raise UnauthorizedException(message="인증 토큰이 유효하지 않습니다.")
    except UnauthorizedException:
        raise
    except Exception:
        # Redis 장애로 인해 블랙리스트 확인 불가: 서비스 가용성 우선(Fail-open)
        return


async def get_current_user_optional(
    request: Request,
    db: AsyncSession = Depends(get_slave_db),
) -> CurrentUser | None:
    token = _bearer_token(request)
    if not token:
        return None
    await _ensure_not_blacklisted(token, request)
    try:
        payload = verify_access_token(token)
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None
    sub = payload.get("sub")
    if sub is None:
        return None
    if not isinstance(sub, str) or not is_valid_ulid_str(sub):
        return None
    user_id = sub
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
    await _ensure_not_blacklisted(token, request)
    try:
        payload = verify_access_token(token)
    except jwt.ExpiredSignatureError:
        raise UnauthorizedException(message="인증 토큰이 유효하지 않습니다.")
    except jwt.InvalidTokenError:
        raise UnauthorizedException(message="인증 토큰이 유효하지 않습니다.")
    sub = payload.get("sub")
    if sub is None:
        raise UnauthorizedException(message="인증 토큰이 유효하지 않습니다.")
    if not isinstance(sub, str) or not is_valid_ulid_str(sub):
        raise UnauthorizedException(message="인증 토큰이 유효하지 않습니다.")
    user_id = sub
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
