import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from app.core.config import settings
from app.core.ids import uuid_to_base62
from app.core.security import create_access_token, hash_password, verify_password
from ulid import ULID


@pytest.mark.anyio
async def test_password_hashing():
    plain_password = "SecurePassword123!"
    hashed_password = await hash_password(plain_password)

    assert plain_password != hashed_password
    assert (await verify_password(plain_password, hashed_password)) is True
    assert (await verify_password("WrongPassword123!", hashed_password)) is False


def test_create_access_token():
    sub = uuid.uuid4()
    token = create_access_token(sub)
    decoded = jwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
    )
    assert decoded.get("sub") == uuid_to_base62(sub)
    assert decoded.get("type") == "access"
    assert "exp" in decoded
    jti = decoded.get("jti")
    assert isinstance(jti, str)
    ULID.from_str(jti)  # 유효한 ULID면 예외 없이 파싱된다


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


@pytest.mark.anyio
async def test_legacy_fallback_single_verify_when_pepper_empty(monkeypatch):
    """빈 PASSWORD_PEPPER면 verify_password를 1회만 호출한다(이중 bcrypt 방지, #9)."""
    from app.core import security

    calls = 0

    async def fake_verify(password: str, hashed: str) -> bool:
        nonlocal calls
        calls += 1
        return False

    monkeypatch.setattr(security.settings, "PASSWORD_PEPPER", "")
    monkeypatch.setattr(security, "verify_password", fake_verify)

    result = await security.verify_password_with_legacy_fallback("pw", "hashed")
    assert result is False
    assert calls == 1


@pytest.mark.anyio
async def test_legacy_fallback_tries_pepper_then_plain(monkeypatch):
    """PASSWORD_PEPPER 설정 시 pepper 검증 실패하면 평문으로 폴백한다(순서·최대 2회)."""
    from app.core import security

    seen: list[str] = []

    async def fake_verify(password: str, hashed: str) -> bool:
        seen.append(password)
        return password == "pw"  # 평문만 통과, pepper 붙은 입력은 실패

    monkeypatch.setattr(security.settings, "PASSWORD_PEPPER", "PEP")
    monkeypatch.setattr(security, "verify_password", fake_verify)

    result = await security.verify_password_with_legacy_fallback("pw", "hashed")
    assert result is True
    assert seen == ["pwPEP", "pw"]
