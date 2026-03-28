import pytest
from app.users.model import User
from httpx import AsyncClient
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
    assert len(db_user.id) == 26
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
