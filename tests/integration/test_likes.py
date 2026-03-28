import uuid

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

_TEST_PW = "LikeTestPW123!"


def _auth_header(login_json: dict) -> dict[str, str]:
    token_data = login_json.get("data", login_json)
    token = token_data.get("accessToken") or token_data.get("access_token")
    assert token
    return {"Authorization": f"Bearer {token}"}


async def setup_post_and_headers(client: AsyncClient) -> tuple[dict[str, str], str]:
    payload = {"email": "liker@example.com", "password": _TEST_PW, "nickname": "좋아요퍼피"}
    await client.post("/v1/auth/signup", json=payload)
    login_res = await client.post(
        "/v1/auth/login",
        json={"email": payload["email"], "password": payload["password"]},
    )
    assert login_res.status_code == 200
    headers = _auth_header(login_res.json())

    post_res = await client.post(
        "/v1/posts",
        json={"title": "좋아요 테스트", "content": "내용"},
        headers={**headers, "X-Idempotency-Key": str(uuid.uuid4())},
    )
    assert post_res.status_code == 201, post_res.text
    body = post_res.json()
    post_id = body.get("data", {}).get("id") or body.get("id")
    assert post_id
    return headers, post_id


async def test_like_post_then_unlike(client: AsyncClient):
    headers, post_id = await setup_post_and_headers(client)

    like_res = await client.post(f"/v1/likes/posts/{post_id}", headers=headers)
    assert like_res.status_code == 200

    unlike_res = await client.delete(f"/v1/likes/posts/{post_id}", headers=headers)
    assert unlike_res.status_code == 200
