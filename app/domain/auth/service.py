# 인증 비즈니스 로직. 순수 데이터 반환·커스텀 예외. Redis 연동 캡슐화. Full-Async.
# 멀티 디바이스: Redis Set(rt:{user_id})에 토큰 해시를 멤버로 저장. SADD/SISMEMBER/SREM 사용.
from __future__ import annotations

import hashlib
import logging

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.schema import (
    AccessTokenData,
    LoginRequest,
    LoginSuccessData,
    SignUpRequest,
)
from app.common.enums import UserStatus
from app.common.exceptions import (
    EmailAlreadyExistsException,
    ForbiddenException,
    InvalidCredentialsException,
    MissingRequiredFieldException,
    NicknameAlreadyExistsException,
    SignupImageTokenInvalidException,
    UnauthorizedException,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
    verify_refresh_token,
)
from app.media.model import MediaModel
from app.media.service import MediaService
from app.users.model import UsersModel

logger = logging.getLogger(__name__)

_REFRESH_KEY_PREFIX = "rt:"


def _refresh_token_hash(token: str) -> str:
    """Refresh 토큰을 Set 멤버로 저장할 때 사용하는 고정 길이 해시. 동일 토큰은 항상 동일 해시."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class AuthService:
    @classmethod
    async def signup(cls, data: SignUpRequest, db: AsyncSession) -> None:
        has_image = data.profile_image_id is not None
        has_token = bool(data.signup_token)
        if has_image != has_token:
            raise MissingRequiredFieldException()
        hashed = hash_password(data.password)
        async with db.begin():
            if await UsersModel.email_exists(data.email, db=db):
                raise EmailAlreadyExistsException()
            if await UsersModel.nickname_exists(data.nickname, db=db):
                raise NicknameAlreadyExistsException()
            profile_image_id = None
            if has_image and has_token:
                if (
                    await MediaService.verify_signup_token(
                        data.profile_image_id, data.signup_token, db=db
                    )
                    is None
                ):
                    raise SignupImageTokenInvalidException()
                profile_image_id = data.profile_image_id
            created = await UsersModel.create_user(
                data.email,
                hashed,
                data.nickname,
                profile_image_id=profile_image_id,
                db=db,
            )
            if profile_image_id is not None:
                await MediaModel.attach_signup_image(profile_image_id, created.id, db=db)

    @classmethod
    async def login(
        cls,
        data: LoginRequest,
        db: AsyncSession,
        redis: Redis | None = None,
        refresh_ttl_seconds: int = 0,
    ) -> tuple[LoginSuccessData, str]:
        async with db.begin():
            user = await UsersModel.get_user_by_email(data.email, db=db)
            if not user:
                raise InvalidCredentialsException()
            if not UserStatus.is_active_value(user.status):
                raise ForbiddenException()
            if not verify_password(data.password, user.password):
                raise InvalidCredentialsException()
            access_token = create_access_token(sub=user.id)
            refresh_token = create_refresh_token(sub=user.id)
            payload = LoginSuccessData(
                id=user.id,
                email=user.email,
                nickname=user.nickname,
                status=user.status,
                profile_image_id=user.profile_image_id,
                profile_image_url=user.profile_image_url,
                access_token=access_token,
            )
        if redis and refresh_ttl_seconds > 0:
            key = f"{_REFRESH_KEY_PREFIX}{payload.id}"
            await redis.sadd(key, _refresh_token_hash(refresh_token))
            await redis.expire(key, refresh_ttl_seconds)
        return (payload, refresh_token)

    @classmethod
    async def logout(
        cls,
        refresh_token: str | None,
        redis: Redis | None = None,
    ) -> None:
        if not refresh_token:
            return
        try:
            payload = verify_refresh_token(refresh_token)
            user_id = payload.get("sub")
            if user_id is not None and redis:
                key = f"{_REFRESH_KEY_PREFIX}{user_id}"
                await redis.srem(key, _refresh_token_hash(refresh_token))
        except Exception as e:
            logger.warning(
                "Logout: refresh token revoke failed or invalid token (user_id from payload). %s",
                e,
                exc_info=False,
            )

    @classmethod
    async def revoke_refresh_for_user(cls, user_id: int, redis: Redis | None = None) -> None:
        if redis:
            await redis.delete(f"{_REFRESH_KEY_PREFIX}{user_id}")

    @classmethod
    async def refresh_tokens(
        cls,
        refresh_token: str | None,
        redis: Redis | None,
        db: AsyncSession,
    ) -> AccessTokenData:
        if not refresh_token:
            raise UnauthorizedException()
        payload = verify_refresh_token(refresh_token)
        user_id = int(payload["sub"])
        if redis:
            key = f"{_REFRESH_KEY_PREFIX}{user_id}"
            is_member = await redis.sismember(key, _refresh_token_hash(refresh_token))
            if not is_member:
                raise UnauthorizedException()
        async with db.begin():
            user = await UsersModel.get_user_by_id(user_id, db=db)
            if not user:
                raise UnauthorizedException()
            if not UserStatus.is_active_value(user.status):
                raise UnauthorizedException()
        new_access = create_access_token(sub=user_id)
        return AccessTokenData(access_token=new_access)
