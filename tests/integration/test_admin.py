import pytest
from app.core.config import settings
from app.db.base_class import utc_now
from app.domain.comments.model import Comment
from app.domain.posts.model import Post
from app.domain.reports.model import Report
from app.domain.users.model import User
from app.main import app
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.asyncio

# SignUpRequest: PasswordStr 8~20자
_TEST_PW = "AdminTestPW123!"


def _auth_header(login_json: dict) -> dict[str, str]:
    token_data = login_json.get("data", login_json)
    token = token_data.get("accessToken") or token_data.get("access_token")
    assert token, "accessToken 없음"
    return {"Authorization": f"Bearer {token}"}


async def _admin_headers(client: AsyncClient, db: AsyncSession, email: str, nickname: str) -> dict:
    await client.post(
        "/v1/auth/signup", json={"email": email, "password": _TEST_PW, "nickname": nickname}
    )
    await db.execute(text("UPDATE users SET role = 'ADMIN' WHERE email = :email"), {"email": email})
    await db.commit()
    res = await client.post("/v1/auth/login", json={"email": email, "password": _TEST_PW})
    assert res.status_code == 200, res.text
    return _auth_header(res.json())


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
    # refresh 회전(RTR)은 Redis 저장소 위에서만 동작한다(refresh_tokens가 redis 없으면 401).
    # 다른 RTR 테스트와 동일하게 Redis 미연결 시 스킵한다.
    if getattr(app.state, "redis", None) is None:
        pytest.skip("Redis 미연결: refresh 토큰 무효화(#8) 검증 생략")
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


async def test_reported_feed_interleaves_and_paginates(
    client: AsyncClient, db_session: AsyncSession
):
    """신고된 게시글·댓글이 report_count DESC 단일 피드로 interleave되고, 페이지 경계가 정확하다(#5).

    공유 DB(테스트 간 정리 없음) 오염과 무관하도록 큰 report_count로 피드 상단을 점유시켜
    상대 순서·페이지 경계·중복 없음을 검증한다.
    """
    headers = await _admin_headers(client, db_session, "feed-admin@example.com", "피드관리자")

    # 콘텐츠 작성자 준비 → id 확보
    await client.post(
        "/v1/auth/signup",
        json={"email": "feed-author@example.com", "password": _TEST_PW, "nickname": "피드작성자"},
    )
    author_id = (
        await db_session.execute(select(User.id).where(User.email == "feed-author@example.com"))
    ).scalar_one()

    now = utc_now()
    host = Post(
        user_id=author_id,
        title="피드 호스트 글",
        content="본문",
        report_count=0,
        created_at=now,
        updated_at=now,
    )
    p_high = Post(
        user_id=author_id,
        title="많이 신고된 글",
        content="P본문",
        report_count=9001,
        created_at=now,
        updated_at=now,
    )
    p_low = Post(
        user_id=author_id,
        title="적게 신고된 글",
        content="P본문2",
        report_count=8998,
        created_at=now,
        updated_at=now,
    )
    db_session.add_all([host, p_high, p_low])
    await db_session.flush()  # host.id 확정(댓글 FK)
    c_high = Comment(
        post_id=host.id,
        author_id=author_id,
        content="많이 신고된 댓글",
        report_count=9000,
        created_at=now,
        updated_at=now,
    )
    c_mid = Comment(
        post_id=host.id,
        author_id=author_id,
        content="중간 댓글",
        report_count=8999,
        created_at=now,
        updated_at=now,
    )
    db_session.add_all([c_high, c_mid])
    await db_session.flush()
    # 집계(last_reported_at·reasons) 경로도 태운다.
    for tt, tid in (("POST", p_high.id), ("COMMENT", c_high.id)):
        db_session.add(
            Report(
                reporter_id=author_id, target_type=tt, target_id=tid, reason="스팸", created_at=now
            )
        )
    await db_session.commit()

    # 상단 4건 = 내가 심은 것, report_count DESC로 interleave: POST, COMMENT, COMMENT, POST
    res = await client.get("/v1/admin/reported-posts?page=1&size=4", headers=headers)
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    top = data["items"][:4]
    assert [i["reportCount"] for i in top] == [9001, 9000, 8999, 8998]
    assert [i["targetType"] for i in top] == ["POST", "COMMENT", "COMMENT", "POST"]
    assert data["total"] >= 4
    # 댓글 항목은 호스트 글 제목을 단다.
    assert top[1]["title"] == "피드 호스트 글"

    # 페이지 경계: size=2 두 페이지가 겹치지 않고 순서가 이어진다(500 cap·인메모리 슬라이스 회귀 방지).
    r1 = (await client.get("/v1/admin/reported-posts?page=1&size=2", headers=headers)).json()[
        "data"
    ]
    r2 = (await client.get("/v1/admin/reported-posts?page=2&size=2", headers=headers)).json()[
        "data"
    ]
    ids1 = [i["id"] for i in r1["items"]]
    ids2 = [i["id"] for i in r2["items"]]
    assert [i["reportCount"] for i in r1["items"]] == [9001, 9000]
    assert [i["reportCount"] for i in r2["items"]] == [8999, 8998]
    assert set(ids1).isdisjoint(ids2)
    assert r1["hasMore"] is True
