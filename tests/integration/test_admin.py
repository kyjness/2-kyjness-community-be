import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.asyncio

# SignUpRequest: PasswordStr 8~20자
_TEST_PW = "AdminTestPW123!"


def _auth_header(login_json: dict) -> dict[str, str]:
    token_data = login_json.get("data", login_json)
    token = token_data.get("accessToken") or token_data.get("access_token")
    assert token, "accessToken 없음"
    return {"Authorization": f"Bearer {token}"}


async def test_admin_access_denied_for_normal_user(client: AsyncClient, db_session: AsyncSession):
    payload = {"email": "normal@example.com", "password": _TEST_PW, "nickname": "일반유저"}
    await client.post("/v1/auth/signup", json=payload)
    login_res = await client.post(
        "/v1/auth/login",
        json={"email": payload["email"], "password": payload["password"]},
    )
    assert login_res.status_code == 200
    headers = _auth_header(login_res.json())

    res = await client.get("/v1/admin/reported-posts", headers=headers)
    assert res.status_code == 403


async def test_admin_access_success(client: AsyncClient, db_session: AsyncSession):
    payload = {"email": "admin@example.com", "password": _TEST_PW, "nickname": "관리자"}
    await client.post("/v1/auth/signup", json=payload)

    await db_session.execute(
        text("UPDATE users SET role = 'ADMIN' WHERE email = :email"),
        {"email": payload["email"]},
    )
    await db_session.commit()

    login_res = await client.post(
        "/v1/auth/login",
        json={"email": payload["email"], "password": payload["password"]},
    )
    assert login_res.status_code == 200
    headers = _auth_header(login_res.json())

    res = await client.get("/v1/admin/reported-posts", headers=headers)
    assert res.status_code == 200
