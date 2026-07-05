"""ADR 0010 — 실제 S3 API 경로를 MinIO에 태워 검증.

S3_ENDPOINT_URL/S3_BUCKET_NAME이 없으면 skip → 로컬 pytest는 건너뛰고, CI(bitnami/minio 서비스 +
S3_* env)에서 실행된다. local 디스크 백엔드가 가리던 presign·copy 승격·키 프리픽스·path-style
주소를 dev/CI가 비로소 자동 검증한다.
"""

import asyncio

import httpx
import pytest
from app.core.config import settings
from app.core.ids import new_uuid7
from app.infra import storage

pytestmark = pytest.mark.skipif(
    not settings.S3_ENDPOINT_URL or not settings.S3_BUCKET_NAME,
    reason="MinIO(S3_ENDPOINT_URL·S3_BUCKET_NAME) 미설정 — 로컬 skip, CI에서 실행",
)

_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


@pytest.fixture(autouse=True)
def _reset_s3_client():
    # 싱글턴 클라이언트를 리셋해 각 테스트가 현재 설정으로 다시 만들게 한다.
    storage._s3_client = None
    yield
    storage._s3_client = None


def _get_object(key: str) -> bytes:
    client = storage._get_s3_client()
    obj = client.get_object(Bucket=settings.S3_BUCKET_NAME, Key=storage._s3_object_key(key))
    return obj["Body"].read()


def test_storage_save_and_delete_roundtrip():
    # 경로 ②(직접 multipart)가 쓰는 put_object → 저장·삭제가 MinIO에서 동작하는지.
    key = f"post/{new_uuid7()}.png"
    url = storage.storage_save(key, _PNG, "image/png")
    # 공개 URL 경로는 실제 저장 키(media/ 프리픽스 포함)로 끝나야 리졸브된다 — 베이스가 /media를
    # 빠뜨리면(예: .../puppytalk) URL이 media/ 없이 나와 404. 이 불변식으로 회귀를 막는다.
    assert url.endswith(storage._s3_object_key(key)), url
    assert _get_object(key) == _PNG

    storage.storage_delete(key)
    with pytest.raises(Exception):
        _get_object(key)


def test_presigned_post_upload_then_promote():
    # 경로 ①(presigned 직접 업로드): presign 발급 → 실제 업로드 → head → promote(copy+delete).
    pending_key = f"pending/{new_uuid7()}/test.png"
    url, fields, key = asyncio.run(storage.issue_presigned_post(pending_key, "image/png"))
    assert key == pending_key

    resp = httpx.post(url, data=fields, files={"file": ("test.png", _PNG, "image/png")})
    assert resp.status_code in (200, 201, 204), resp.text

    meta = asyncio.run(storage.head_pending_object(pending_key))
    assert int(meta["ContentLength"]) == len(_PNG)

    dest_key, size, content_type = asyncio.run(storage.promote_pending_object(pending_key, "post"))
    assert size == len(_PNG)
    assert content_type == "image/png"
    assert dest_key.startswith("post/") and dest_key.endswith(".png")
    assert _get_object(dest_key) == _PNG

    # 승격 후 pending 원본은 삭제됐다.
    with pytest.raises(Exception):
        _get_object(pending_key)

    storage.storage_delete(dest_key)
