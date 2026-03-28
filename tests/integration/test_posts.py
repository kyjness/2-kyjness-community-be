import pytest
from app.core.ids import new_ulid_str
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


def _token_from_login(res_json: dict) -> str:
    token_data = res_json.get("data", res_json)
    t = token_data.get("accessToken") or token_data.get("access_token")
    if not t:
        raise AssertionError("로그인 응답에 accessToken이 없습니다.")
    return t


async def setup_auth_user(client: AsyncClient, email: str, nickname: str) -> dict[str, str]:
    payload = {"email": email, "password": "TestPassword123!", "nickname": nickname}
    await client.post("/v1/auth/signup", json=payload)
    login_res = await client.post(
        "/v1/auth/login",
        json={"email": email, "password": payload["password"]},
    )
    assert login_res.status_code == 200, login_res.text
    token = _token_from_login(login_res.json())
    return {"Authorization": f"Bearer {token}"}


async def test_create_and_get_post(client: AsyncClient):
    headers = await setup_auth_user(client, "post_user@example.com", "포스트퍼피")
    post_payload = {"title": "강아지 사료 추천", "content": "어떤 사료가 좋을까요?"}
    idem = {"X-Idempotency-Key": new_ulid_str()}

    create_res = await client.post("/v1/posts", json=post_payload, headers={**headers, **idem})
    assert create_res.status_code == 201, create_res.text

    body = create_res.json()
    post_id = body.get("data", {}).get("id") or body.get("id")
    assert post_id is not None

    get_res = await client.get(f"/v1/posts/{post_id}")
    assert get_res.status_code == 200
    data = get_res.json().get("data", get_res.json())
    assert data.get("title") == post_payload["title"]


async def test_search_posts_gin_index(client: AsyncClient):
    headers = await setup_auth_user(client, "search_user@example.com", "검색퍼피")
    idem1 = {"X-Idempotency-Key": new_ulid_str()}
    idem2 = {"X-Idempotency-Key": new_ulid_str()}
    await client.post(
        "/v1/posts",
        json={"title": "맛있는 카보불닭 레시피", "content": "내용"},
        headers={**headers, **idem1},
    )
    await client.post(
        "/v1/posts",
        json={"title": "우리집 강아지 자랑", "content": "내용"},
        headers={**headers, **idem2},
    )

    search_res = await client.get("/v1/posts", params={"q": "불닭"})
    assert search_res.status_code == 200
    payload = search_res.json().get("data", search_res.json())
    items = payload.get("items", [])
    assert len(items) >= 1
    assert "불닭" in (items[0].get("title") or "")
