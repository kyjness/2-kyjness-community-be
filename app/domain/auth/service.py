# 인증 비즈니스 로직. 순수 데이터 반환·커스텀 예외. Redis 연동 캡슐화. Full-Async.
from __future__ import annotations

import logging
from typing import Optional

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


class AuthService:
    @classmethod
    async def signup(cls, data: SignUpRequest, db: AsyncSession) -> None:
        has_image = data.profile_image_id is not None
        has_token = bool(data.signup_token)
        if has_image != has_token:
            raise MissingRequiredFieldException()
        profile_image_id = None
        async with db.begin():
            if await UsersModel.email_exists(data.email, db=db):
                raise EmailAlreadyExistsException()
            if await UsersModel.nickname_exists(data.nickname, db=db):
                raise NicknameAlreadyExistsException()
        if has_image and has_token:
            if (
                await MediaService.verify_signup_token(
                    data.profile_image_id, data.signup_token, db=db
                )
                is None
            ):
                raise SignupImageTokenInvalidException()
            profile_image_id = data.profile_image_id
        hashed = hash_password(data.password)
        async with db.begin():
            created = await UsersModel.create_user(
                data.email,
                hashed,
                data.nickname,
                profile_image_id=profile_image_id,
                db=db,
            )
            if profile_image_id is not None:
                await MediaModel.attach_signup_image(
                    profile_image_id, created.id, db=db
                )

    @classmethod
    async def login(
        cls,
        data: LoginRequest,
        db: AsyncSession,
        redis: Optional[Redis] = None,
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
            await redis.set(
                f"{_REFRESH_KEY_PREFIX}{payload.id}",
                refresh_token,
                ex=refresh_ttl_seconds,
            )
        return (payload, refresh_token)

    @classmethod
    async def logout(
        cls,
        refresh_token: Optional[str],
        redis: Optional[Redis] = None,
    ) -> None:
        if not refresh_token:
            return
        try:
            payload = verify_refresh_token(refresh_token)
            user_id = payload.get("sub")
            if user_id is not None and redis:
                await redis.delete(f"{_REFRESH_KEY_PREFIX}{user_id}")
        except Exception as e:
            logger.warning(
                "Logout: refresh token revoke failed or invalid token (user_id from payload). %s",
                e,
                exc_info=False,
            )

    @classmethod
    async def revoke_refresh_for_user(
        cls, user_id: int, redis: Optional[Redis] = None
    ) -> None:
        if redis:
            await redis.delete(f"{_REFRESH_KEY_PREFIX}{user_id}")

    @classmethod
    async def refresh_tokens(
        cls,
        refresh_token: Optional[str],
        redis: Optional[Redis],
        db: AsyncSession,
    ) -> AccessTokenData:
        if not refresh_token:
            raise UnauthorizedException()
        payload = verify_refresh_token(refresh_token)
        user_id = int(payload["sub"])
        if redis:
            stored = await redis.get(f"{_REFRESH_KEY_PREFIX}{user_id}")
            if stored is None or stored != refresh_token:
                raise UnauthorizedException()
        async with db.begin():
            user = await UsersModel.get_user_by_id(user_id, db=db)
            if not user:
                raise UnauthorizedException()
            if not UserStatus.is_active_value(user.status):
                raise UnauthorizedException()
        new_access = create_access_token(sub=user_id)
        return AccessTokenData(access_token=new_access)
