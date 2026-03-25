# 인증 비즈니스 로직. 순수 데이터 반환·커스텀 예외. Redis 연동 캡슐화. Full-Async.
# Redis 기반 Refresh Token 저장 + Access Token 블랙리스트(로그아웃). Full-Async.
from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime
from typing import Any, cast

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

_USER_REFRESH_KEY_PREFIX = "user_refresh:"
_BLACKLIST_KEY_PREFIX = "blacklist:"


def _sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _user_refresh_key(user_id: int) -> str:
    return f"{_USER_REFRESH_KEY_PREFIX}{user_id}"


def _blacklist_key(access_token: str) -> str:
    # 토큰 원문을 키로 쓰지 않음(메모리/로그/관측 표면 최소화)
    return f"{_BLACKLIST_KEY_PREFIX}{_sha256_hex(access_token)}"


def _refresh_token_digest(refresh_token: str) -> str:
    return _sha256_hex(refresh_token)


def _remaining_ttl_seconds_from_access_payload(payload: dict) -> int:
    exp = payload.get("exp")
    now = datetime.now(UTC)
    if isinstance(exp, int):
        exp_dt = datetime.fromtimestamp(exp, UTC)
    elif isinstance(exp, datetime):
        exp_dt = exp if exp.tzinfo is not None else exp.replace(tzinfo=UTC)
    else:
        return 0
    return max(0, int((exp_dt - now).total_seconds()))


class AuthService:
    @classmethod
    async def signup(
        cls, data: SignUpRequest, db: AsyncSession, redis: Redis | None = None
    ) -> None:
        has_token = bool(data.signup_token)
        if data.profile_image_id is not None and not has_token:
            # validator: profile_image_id만 단독 전달은 허용하지 않음.
            raise MissingRequiredFieldException()
        hashed = hash_password(data.password)
        async with db.begin():
            if await UsersModel.email_exists(data.email, db=db):
                raise EmailAlreadyExistsException()
            if await UsersModel.nickname_exists(data.nickname, db=db):
                raise NicknameAlreadyExistsException()
            profile_image_id = None
            if has_token:
                image_id_from_token = await MediaService.verify_upload_token(
                    data.signup_token or "", redis=redis
                )
                if image_id_from_token is None:
                    raise SignupImageTokenInvalidException()
                if (
                    data.profile_image_id is not None
                    and data.profile_image_id != image_id_from_token
                ):
                    raise SignupImageTokenInvalidException()
                profile_image_id = image_id_from_token
            created = await UsersModel.create_user(
                data.email,
                hashed,
                data.nickname,
                profile_image_id=profile_image_id,
                db=db,
            )
            if profile_image_id is not None:
                attached = await MediaModel.attach_signup_image(profile_image_id, created.id, db=db)
                if not attached:
                    # 토큰 경쟁/재사용 등으로 인해 DB 첨부가 실패한 경우.
                    raise SignupImageTokenInvalidException()

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
        # Refresh Token은 user_refresh:{user_id}에 단일 값으로 저장 (RTR 전제).
        if redis is not None and refresh_ttl_seconds > 0:
            r = cast(Any, redis)
            await r.set(
                _user_refresh_key(payload.id),
                _refresh_token_digest(refresh_token),
                ex=refresh_ttl_seconds,
            )
        return (payload, refresh_token)

    @classmethod
    async def logout(
        cls,
        *,
        user_id: int,
        refresh_token: str | None,
        access_token: str,
        access_payload: dict,
        redis: Redis | None = None,
    ) -> None:
        # 운영 관점: 로그아웃은 블랙리스트/refresh 폐기가 핵심이므로 Redis 없이는 실패시키는 편이 안전.
        if redis is None:
            raise UnauthorizedException(
                message="로그아웃을 처리할 수 없습니다. 잠시 후 다시 시도하세요."
            )

        # 1) access token 블랙리스트 등록(남은 TTL만큼).
        ttl = _remaining_ttl_seconds_from_access_payload(access_payload)
        if ttl > 0:
            await cast(Any, redis).set(_blacklist_key(access_token), "logout", ex=ttl)

        # 2) refresh token 폐기(회전 전제이므로 user_id 키 삭제).
        await cast(Any, redis).delete(_user_refresh_key(int(user_id)))

    @classmethod
    async def revoke_refresh_for_user(cls, user_id: int, redis: Redis | None = None) -> None:
        if redis:
            await cast(Any, redis).delete(_user_refresh_key(user_id))

    @classmethod
    async def refresh_tokens(
        cls,
        refresh_token: str | None,
        redis: Redis | None,
        db: AsyncSession,
        refresh_ttl_seconds: int,
    ) -> tuple[AccessTokenData, str]:
        if not refresh_token:
            raise UnauthorizedException()
        payload = verify_refresh_token(refresh_token)
        user_id = int(payload["sub"])
        # RTR: Redis에 저장된 refresh_token과 정확히 일치해야 함. 검증 후 새 refresh로 교체.
        if redis is None:
            raise UnauthorizedException(
                message="인증을 갱신할 수 없습니다. 잠시 후 다시 시도하세요."
            )
        r = cast(Any, redis)
        stored_digest = await r.get(_user_refresh_key(user_id))
        if stored_digest is None or stored_digest != _refresh_token_digest(refresh_token):
            raise UnauthorizedException()
        async with db.begin():
            user = await UsersModel.get_user_by_id(user_id, db=db)
            if not user:
                raise UnauthorizedException()
            if not UserStatus.is_active_value(user.status):
                raise UnauthorizedException()
        new_access = create_access_token(sub=user_id)
        new_refresh = create_refresh_token(sub=user_id)
        if refresh_ttl_seconds > 0:
            await r.set(
                _user_refresh_key(user_id),
                _refresh_token_digest(new_refresh),
                ex=refresh_ttl_seconds,
            )
        return AccessTokenData(access_token=new_access), new_refresh
