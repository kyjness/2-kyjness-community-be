# 비밀번호 해시·검증(bcrypt), JWT Access/Refresh 토큰 생성·검증.
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt

from app.core.config import settings


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(
            password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except (ValueError, TypeError):
        return False


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(sub: int) -> str:
    """sub=user_id. ACCESS_TOKEN_EXPIRE_SECONDS 후 만료. JWT spec에 따라 sub는 문자열로 저장."""
    expire = _now_utc() + timedelta(seconds=settings.ACCESS_TOKEN_EXPIRE_SECONDS)
    payload = {"sub": str(sub), "exp": expire, "iat": _now_utc(), "type": "access"}
    return jwt.encode(
        payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
    )


def create_refresh_token(sub: int) -> str:
    """sub=user_id. REFRESH_TOKEN_EXPIRE_DAYS 후 만료. Redis rt:{user_id}에 저장해 무효화 가능. JWT spec에 따라 sub는 문자열로 저장."""
    expire = _now_utc() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {"sub": str(sub), "exp": expire, "iat": _now_utc(), "type": "refresh"}
    return jwt.encode(
        payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
    )


def verify_access_token(token: str) -> dict[str, Any]:
    """만료/서명 실패 시 ExpiredSignatureError 또는 InvalidTokenError."""
    payload = jwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
    )
    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("invalid token type")
    return payload


def verify_refresh_token(token: str) -> dict[str, Any]:
    """type=refresh 검사. 만료/서명 실패 시 예외."""
    payload = jwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
    )
    if payload.get("type") != "refresh":
        raise jwt.InvalidTokenError("invalid token type")
    return payload
