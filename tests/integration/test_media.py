import uuid
from datetime import timedelta

import pytest
from app.api.dependencies.client import _idempotency_fingerprint, _lock_redis_key
from app.common.codes import ApiCode
from app.core.config import settings
from app.core.ids import parse_public_id_value
from app.db.base_class import utc_now
from app.domain.media.model import Image
from app.main import app
from httpx import AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.asyncio

_TEST_PW = "MediaTestPW123!"
# 최소 유효 PNG: sniff_image_type이 매직바이트로 image/png 판별(뒤는 패딩).
_PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


def _auth_header(login_json: dict) -> dict[str, str]:
    data = login_json.get("data", login_json)
    token = data.get("accessToken") or data.get("access_token")
    assert token, "accessToken 없음"
    return {"Authorization": f"Bearer {token}"}


def _png_files() -> dict:
    return {"image": ("x.png", _PNG_BYTES, "image/png")}


async def _signup_login(client: AsyncClient, email: str, nickname: str) -> dict:
    await client.post(
        "/v1/auth/signup", json={"email": email, "password": _TEST_PW, "nickname": nickname}
    )
    res = await client.post("/v1/auth/login", json={"email": email, "password": _TEST_PW})
    assert res.status_code == 200
    return res.json()


async def test_media_upload_idempotency_replays_same_result(client: AsyncClient):
    """동일 X-Idempotency-Key로 두 번 업로드 → 두 번째는 첫 응답을 재생(같은 이미지 id, 부작용 1회)."""
    if getattr(app.state, "redis", None) is None:
        pytest.skip("Redis 미연결: 멱등성 캐시 재생 검증 생략")

    login = await _signup_login(client, "media-idem@example.com", "미디어멱등")
    headers = {**_auth_header(login), "X-Idempotency-Key": uuid.uuid4().hex}

    first = await client.post(
        "/v1/media/images", params={"purpose": "post"}, headers=headers, files=_png_files()
    )
    assert first.status_code == 201, first.text
    second = await client.post(
        "/v1/media/images", params={"purpose": "post"}, headers=headers, files=_png_files()
    )
    assert second.status_code == 201, second.text

    assert first.json()["data"]["id"] == second.json()["data"]["id"], (
        "재시도가 새 업로드를 만들면 안 된다(멱등성 위반)"
    )


async def test_media_upload_conflict_when_key_inflight(client: AsyncClient):
    """같은 키 처리가 진행 중(락 보유)이면 두 번째 요청은 409로 거절된다."""
    if getattr(app.state, "redis", None) is None:
        pytest.skip("Redis 미연결: in-flight 락 충돌 검증 생략")

    login = await _signup_login(client, "media-conflict@example.com", "미디어충돌")
    key = uuid.uuid4().hex
    headers = {**_auth_header(login), "X-Idempotency-Key": key}

    # 다른 요청이 처리 중인 상태를 재현: 동일 fingerprint의 락 키를 선점.
    user_uuid = parse_public_id_value(login["data"]["id"])
    fp = _idempotency_fingerprint((str(user_uuid), "post"), key)
    await app.state.redis.set(_lock_redis_key("media:upload", fp), "1", nx=True, ex=60)

    res = await client.post(
        "/v1/media/images", params={"purpose": "post"}, headers=headers, files=_png_files()
    )
    assert res.status_code == 409, res.text
    assert res.json().get("code") == ApiCode.CONFLICT.value


async def test_cleanup_keeps_records_when_storage_delete_fails(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    """스토리지 삭제 실패 이미지는 DB 레코드를 보존(고아 방지)하고, 성공분만 삭제된다(#1)."""
    old = utc_now() - timedelta(days=1)
    sfx = uuid.uuid4().hex[:8]
    ok_key, fail_key = f"cleanup-ok-{sfx}", f"cleanup-fail-{sfx}"
    ok = Image(
        file_key=ok_key, file_url="u1", content_type="image/png", size=1,
        uploader_id=None, created_at=old,
    )
    fail = Image(
        file_key=fail_key, file_url="u2", content_type="image/png", size=1,
        uploader_id=None, created_at=old,
    )
    db_session.add_all([ok, fail])
    await db_session.commit()

    def fake_storage_delete(file_key: str) -> None:
        if file_key == fail_key:
            raise RuntimeError("storage down")

    monkeypatch.setattr("app.domain.media.service.storage_delete", fake_storage_delete)

    from app.domain.media.service import MediaService

    try:
        deleted, failed = await MediaService.cleanup_expired_signup_images(
            db_session, task_id="test", redis=None
        )
        assert deleted >= 1
        assert fail_key in failed

        remaining = (
            await db_session.execute(
                select(Image.file_key).where(Image.file_key.in_([ok_key, fail_key]))
            )
        ).scalars().all()
        # 삭제 실패분만 남고, 성공분은 제거됨.
        assert set(remaining) == {fail_key}
    finally:
        # 남긴 만료-orphan 행이 다른 테스트로 새지 않도록 정리.
        await db_session.execute(delete(Image).where(Image.file_key.in_([ok_key, fail_key])))
        await db_session.commit()


async def test_cleanup_advances_past_failing_head(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    """id 앞머리의 스토리지 실패 이미지가 뒤쪽 정상 이미지를 굶기지 않는다(keyset 전진)."""
    # 배치 1로 좁혀, '실패 머리 → 정상 꼬리'를 서로 다른 배치로 강제.
    monkeypatch.setattr(settings, "MEDIA_CLEANUP_BATCH_SIZE", 1)
    old = utc_now() - timedelta(days=1)
    sfx = uuid.uuid4().hex[:8]
    a = Image(
        file_key=f"cleanup-a-{sfx}", file_url="u", content_type="image/png", size=1,
        uploader_id=None, created_at=old,
    )
    b = Image(
        file_key=f"cleanup-b-{sfx}", file_url="u", content_type="image/png", size=1,
        uploader_id=None, created_at=old,
    )
    db_session.add_all([a, b])
    await db_session.flush()  # uuid7 PK 확정
    # 작은 id를 '실패 머리'로: 실패분이 앞머리에 있어도 커서가 전진해 꼬리에 도달함을 검증.
    head, tail = sorted((a, b), key=lambda x: x.id)
    await db_session.commit()

    def fake_storage_delete(file_key: str) -> None:
        if file_key == head.file_key:
            raise RuntimeError("storage down")

    monkeypatch.setattr("app.domain.media.service.storage_delete", fake_storage_delete)

    from app.domain.media.service import MediaService

    try:
        deleted, failed = await MediaService.cleanup_expired_signup_images(
            db_session, task_id="test", redis=None
        )
        assert deleted >= 1
        assert head.file_key in failed

        remaining = (
            await db_session.execute(
                select(Image.file_key).where(Image.file_key.in_([head.file_key, tail.file_key]))
            )
        ).scalars().all()
        # 실패한 머리는 남고, 커서가 그 뒤로 전진해 꼬리(정상)는 삭제됨.
        assert set(remaining) == {head.file_key}
    finally:
        await db_session.execute(
            delete(Image).where(Image.file_key.in_([head.file_key, tail.file_key]))
        )
        await db_session.commit()
