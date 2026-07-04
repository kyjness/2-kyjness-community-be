import pytest
from app.core.config import settings
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


async def test_suspend_revokes_refresh_token(client: AsyncClient, db_session: AsyncSession):
    """정지되면 기존 refresh 토큰이 무효화된다(#8)."""
    cookie_name = settings.REFRESH_TOKEN_COOKIE_NAME

    # 대상 유저 가입·로그인 → 공개 id + refresh 쿠키 확보
    target = {"email": "suspend-target@example.com", "password": _TEST_PW, "nickname": "정지대상"}
    await client.post("/v1/auth/signup", json=target)
    login_res = await client.post(
        "/v1/auth/login",
        json={"email": target["email"], "password": target["password"]},
    )
    assert login_res.status_code == 200
    target_id = login_res.json()["data"]["id"]
    refresh_cookie = login_res.cookies.get(cookie_name)
    assert refresh_cookie, "refresh 쿠키 없음"

    # 정지 전에는 refresh 성공 — 이후 401이 '정지 때문'임을 증명(쿠키 자체는 유효)
    client.cookies.clear()
    before = await client.post("/v1/auth/refresh", cookies={cookie_name: refresh_cookie})
    assert before.status_code == 200
    refresh_cookie = before.cookies.get(cookie_name) or refresh_cookie

    # 관리자 생성·승격·로그인
    admin = {"email": "suspender-admin@example.com", "password": _TEST_PW, "nickname": "정지관리자"}
    await client.post("/v1/auth/signup", json=admin)
    await db_session.execute(
        text("UPDATE users SET role = 'ADMIN' WHERE email = :email"),
        {"email": admin["email"]},
    )
    await db_session.commit()
    admin_login = await client.post(
        "/v1/auth/login",
        json={"email": admin["email"], "password": admin["password"]},
    )
    headers = _auth_header(admin_login.json())

    # 정지 실행
    suspend_res = await client.patch(f"/v1/admin/users/{target_id}/suspend", headers=headers)
    assert suspend_res.status_code == 200

    # 정지 후에는 기존 refresh 토큰이 무효화되어 401
    client.cookies.clear()
    after = await client.post("/v1/auth/refresh", cookies={cookie_name: refresh_cookie})
    assert after.status_code == 401
