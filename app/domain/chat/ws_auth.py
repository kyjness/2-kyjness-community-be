# WebSocket 쿼리 ?token= Access JWT 검증. HTTP Depends와 동일한 sub·jti 블랙리스트 규칙.
from __future__ import annotations

import logging
from typing import Any, cast
from uuid import UUID

import jwt
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.websockets import WebSocket

from app.common.enums import UserStatus
from app.common.exceptions import ForbiddenException, UnauthorizedException
from app.core.ids import jwt_sub_to_uuid
from app.core.security import access_jti_blacklist_redis_key, verify_access_token
from app.users.model import UsersModel

log = logging.getLogger(__name__)


async def _jti_blacklisted(redis_raw: Any, jti: str) -> bool:
    if not isinstance(redis_raw, Redis):
        return False
    key = access_jti_blacklist_redis_key(jti)
    try:
        r = cast(Any, redis_raw)
        return await r.get(key) is not None
    except Exception:
        log.warning("chat ws jti redis 조회 실패(Fail-open)", exc_info=True)
        return False


async def authenticate_chat_websocket(websocket: WebSocket, db: AsyncSession) -> UUID:
    """성공 시 user_id(UUID). 실패 시 UnauthorizedException/ForbiddenException."""
    token = (websocket.query_params.get("token") or "").strip()
    if not token:
        raise UnauthorizedException(message="인증 토큰이 필요합니다.")
    try:
        payload = verify_access_token(token)
    except jwt.ExpiredSignatureError:
        raise UnauthorizedException(message="인증 토큰이 만료되었습니다.") from None
    except jwt.InvalidTokenError:
        raise UnauthorizedException(message="인증 토큰이 유효하지 않습니다.") from None
    jti = payload.get("jti")
    if isinstance(jti, str) and jti.strip():
        app = websocket.scope.get("app")
        redis_raw = getattr(app.state, "redis", None) if app is not None else None
        if await _jti_blacklisted(redis_raw, jti.strip()):
            raise UnauthorizedException(message="인증 토큰이 유효하지 않습니다.")
    sub = payload.get("sub")
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
    return user_id
