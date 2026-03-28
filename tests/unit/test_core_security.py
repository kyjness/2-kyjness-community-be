from datetime import UTC, datetime, timedelta

import jwt
import pytest
from app.core.config import settings
from app.core.security import create_access_token, hash_password, verify_password


def test_password_hashing():
    plain_password = "SecurePassword123!"
    hashed_password = hash_password(plain_password)

    assert plain_password != hashed_password
    assert verify_password(plain_password, hashed_password) is True
    assert verify_password("WrongPassword123!", hashed_password) is False


def test_create_access_token():
    sub = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
    token = create_access_token(sub)
    decoded = jwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
    )
    assert decoded.get("sub") == sub
    assert decoded.get("type") == "access"
    assert "exp" in decoded


def test_expired_jwt_token():
    sub = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
    past = datetime.now(UTC) - timedelta(seconds=10)
    payload = {"sub": sub, "exp": past, "iat": past, "type": "access"}
    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

    with pytest.raises(jwt.ExpiredSignatureError):
        jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
