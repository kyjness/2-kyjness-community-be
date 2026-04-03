import asyncio
import uuid

import pytest
from app.common.codes import ApiCode
from app.main import app
from app.users.model import User
from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.asyncio


async def test_signup_success(client: AsyncClient, db_session: AsyncSession):
    payload = {
        "email": "testdog@example.com",
        "password": "StrongPassword123!",
        "nickname": "테스트퍼피",
    }

    response = await client.post("/v1/auth/signup", json=payload)

    assert response.status_code in (200, 201)

    stmt = select(User).where(User.email == payload["email"])
    result = await db_session.execute(stmt)
    db_user = result.scalar_one_or_none()
    assert db_user is not None
    assert isinstance(db_user.id, uuid.UUID)
    assert db_user.password != payload["password"]


async def test_signup_duplicate_email(client: AsyncClient):
    payload = {
        "email": "duplicate@example.com",
        "password": "StrongPassword123!",
        "nickname": "먼저가입한퍼피",
    }
    await client.post("/v1/auth/signup", json=payload)

    response = await client.post("/v1/auth/signup", json=payload)
    assert response.status_code == 409


async def test_login_and_refresh_token(client: AsyncClient):
    signup_payload = {
        "email": "login@example.com",
        "password": "LoginPassword123!",
        "nickname": "로그인유저",
    }
    await client.post("/v1/auth/signup", json=signup_payload)

    login_payload = {
        "email": signup_payload["email"],
        "password": signup_payload["password"],
    }
    response = await client.post("/v1/auth/login", json=login_payload)

    assert response.status_code == 200
    data = response.json()
    token_data = data.get("data", data)
    access_token = token_data.get("accessToken") or token_data.get("access_token")
    assert access_token is not None


_CONCURRENT_REFRESH_REQUESTS = 10


async def _post_refresh(client: AsyncClient) -> Response:
    """동시 호출 단위: 동일 클라이언트 쿠키(리프레시 토큰)로 /auth/refresh POST."""
    return await client.post("/v1/auth/refresh")


async def test_concurrent_refresh_tokens_lua_cas(client: AsyncClient):
    """
    동일 리프레시 토큰으로 N회 동시 갱신 시 Lua CAS로 정확히 1건만 성공하고 나머지는 401.

    Redis(RTR 저장소)가 없으면 refresh 자체가 전부 실패하므로 스킵한다.
    """
    if getattr(app.state, "redis", None) is None:
        pytest.skip("Redis 미연결·REDIS_URL 없음: RTR Lua CAS 동시성 검증 생략")

    # --- Given: 고유 유저 + 로그인으로 리프레시 쿠키 1개 확보 ---
    suffix = uuid.uuid4().hex[:12]
    signup_payload = {
        "email": f"concurrent_refresh_{suffix}@example.com",
        "password": "ConcurrentRefresh123!",
        "nickname": f"동시갱신{suffix[:6]}",
    }
    signup_res = await client.post("/v1/auth/signup", json=signup_payload)
    assert signup_res.status_code in (200, 201)

    login_res = await client.post(
        "/v1/auth/login",
        json={"email": signup_payload["email"], "password": signup_payload["password"]},
    )
    assert login_res.status_code == 200

    # --- When: 동일 쿠키를 실은 N개 요청을 한 번에 전송 ---
    responses: list[Response] = list(
        await asyncio.gather(*(_post_refresh(client) for _ in range(_CONCURRENT_REFRESH_REQUESTS)))
    )

    # --- Then: 200 정확히 1, 나머지 전부 401 + API 코드 일치 ---
    status_codes = [r.status_code for r in responses]
    assert status_codes.count(200) == 1, f"기대: 성공 1건, 실제 분포: {status_codes}"
    assert status_codes.count(401) == _CONCURRENT_REFRESH_REQUESTS - 1

    losers = [r for r in responses if r.status_code == 401]
    for r in losers:
        body = r.json()
        assert body.get("code") == ApiCode.UNAUTHORIZED.value

    winners = [r for r in responses if r.status_code == 200]
    assert len(winners) == 1
    win_json = winners[0].json()
    data = win_json.get("data") or {}
    assert data.get("accessToken") or data.get("access_token")
