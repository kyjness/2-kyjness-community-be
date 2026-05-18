# 로컬/S3 파일 스토리지. STORAGE_BACKEND에 따라 분기.
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from starlette.concurrency import run_in_threadpool

from app.core.config import settings
from app.core.ids import new_ulid_str

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
UPLOAD_DIR = PROJECT_ROOT / "upload"

_s3_client = None

_MEDIA_PREFIX = "media/"
PENDING_KEY_PREFIX = "pending/"
PRESIGNED_MAX_BYTES = 10 * 1024 * 1024
PRESIGNED_POST_EXPIRES_SECONDS = 900
_PENDING_KEY_RE = re.compile(
    r"^pending/[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}/[\w.\-]+$"
)


def _strip_redundant_media_prefixes(key: str) -> str:
    """DB/호출부에 media/ 가 중복·혼입돼도 S3 키·공개 URL에서 한 번만 쓰이도록 본문 경로만 남김."""
    k = (key or "").strip().lstrip("/")
    while k.startswith(_MEDIA_PREFIX):
        k = k[len(_MEDIA_PREFIX) :].lstrip("/")
    return k


def _s3_object_key(key: str) -> str:
    body = _strip_redundant_media_prefixes(key)
    if not body:
        raise ValueError("storage key must not be empty")
    return f"{_MEDIA_PREFIX}{body}"


def _get_s3_client():
    """S3 클라이언트 Lazy-loading. 인증 정보 누락 시 ValueError."""
    global _s3_client
    if _s3_client is not None:
        return _s3_client
    if (
        not settings.S3_BUCKET_NAME
        or not settings.AWS_ACCESS_KEY_ID
        or not settings.AWS_SECRET_ACCESS_KEY
    ):
        raise ValueError(
            "S3_BUCKET_NAME, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY must be set when STORAGE_BACKEND=s3"
        )
    import boto3

    kwargs: dict = {
        "region_name": settings.AWS_REGION,
        "aws_access_key_id": settings.AWS_ACCESS_KEY_ID,
        "aws_secret_access_key": settings.AWS_SECRET_ACCESS_KEY,
    }
    if settings.S3_ENDPOINT_URL:
        kwargs["endpoint_url"] = settings.S3_ENDPOINT_URL
    _s3_client = boto3.client("s3", **kwargs)
    return _s3_client


def storage_save(key: str, content: bytes, content_type: str) -> str:
    if settings.STORAGE_BACKEND == "s3":
        return _s3_save(key, content, content_type)
    return _local_save(key, content, content_type)


def storage_delete(key: str) -> None:
    if settings.STORAGE_BACKEND == "s3":
        _s3_delete(key)
    else:
        _local_delete(key)


def _be_base_url() -> str:
    raw = (settings.BE_API_URL or "").strip()
    if "," in raw:
        raw = raw.split(",")[0].strip()
    return raw or "http://127.0.0.1:8000"


def build_url(key: str) -> str:
    if settings.STORAGE_BACKEND == "s3":
        path_under_media = _strip_redundant_media_prefixes(key)
        if settings.S3_PUBLIC_BASE_URL:
            base = settings.S3_PUBLIC_BASE_URL.rstrip("/")
            return f"{base}/{path_under_media}"
        return (
            f"https://{settings.S3_BUCKET_NAME}.s3.{settings.AWS_REGION}.amazonaws.com/"
            f"{_s3_object_key(key)}"
        )
    base = _be_base_url().rstrip("/")
    return f"{base}/upload/{key}"


def _s3_save(key: str, content: bytes, content_type: str) -> str:
    client = _get_s3_client()
    s3_key = _s3_object_key(key)
    client.put_object(
        Bucket=settings.S3_BUCKET_NAME,
        Key=s3_key,
        Body=content,
        ContentType=content_type,
    )
    # 반환되는 URL은 기존 로직(build_url)을 그대로 타서 https://도메인/media/키 형태가 됩니다.
    return build_url(key)


def _s3_delete(key: str) -> None:
    client = _get_s3_client()
    client.delete_object(Bucket=settings.S3_BUCKET_NAME, Key=_s3_object_key(key))


def require_s3_direct_upload() -> None:
    """Presigned POST·확정 API는 S3 백엔드에서만 사용."""
    if settings.STORAGE_BACKEND != "s3":
        raise ValueError("Direct S3 upload requires STORAGE_BACKEND=s3")


def is_valid_pending_file_key(file_key: str) -> bool:
    k = (file_key or "").strip().lstrip("/")
    return bool(_PENDING_KEY_RE.fullmatch(k))


def _generate_presigned_post_sync(file_key: str, content_type: str) -> dict[str, Any]:
    require_s3_direct_upload()
    client = _get_s3_client()
    s3_key = _s3_object_key(file_key)
    return client.generate_presigned_post(
        Bucket=settings.S3_BUCKET_NAME,
        Key=s3_key,
        Fields={"Content-Type": content_type},
        Conditions=[
            {"Content-Type": content_type},
            ["content-length-range", 1, PRESIGNED_MAX_BYTES],
        ],
        ExpiresIn=PRESIGNED_POST_EXPIRES_SECONDS,
    )


async def issue_presigned_post(
    file_key: str,
    content_type: str,
) -> tuple[str, dict[str, str], str]:
    """Presigned POST(url, fields) 발급. boto3 동기 호출은 스레드풀로 오프로딩."""
    payload = await run_in_threadpool(_generate_presigned_post_sync, file_key, content_type)
    fields = {str(k): str(v) for k, v in payload["fields"].items()}
    return str(payload["url"]), fields, file_key


def _head_pending_object_sync(file_key: str) -> dict[str, Any]:
    require_s3_direct_upload()
    if not is_valid_pending_file_key(file_key):
        raise ValueError("invalid pending file_key")
    client = _get_s3_client()
    return client.head_object(Bucket=settings.S3_BUCKET_NAME, Key=_s3_object_key(file_key))


def _promote_pending_object_sync(pending_key: str, dest_purpose: str) -> tuple[str, int, str]:
    """pending/ 객체를 영구 purpose 경로로 copy 후 삭제."""
    require_s3_direct_upload()
    if not is_valid_pending_file_key(pending_key):
        raise ValueError("invalid pending file_key")
    if dest_purpose not in ("signup", "profile", "post"):
        raise ValueError("invalid dest purpose")

    meta = _head_pending_object_sync(pending_key)
    size = int(meta.get("ContentLength") or 0)
    if size < 1 or size > PRESIGNED_MAX_BYTES:
        raise ValueError("object size out of allowed range")
    content_type = str(meta.get("ContentType") or "")
    if not content_type:
        raise ValueError("missing content type")

    ext = _ext_from_content_type(content_type)
    dest_key = f"{dest_purpose}/{new_ulid_str()}.{ext}"
    bucket = settings.S3_BUCKET_NAME
    client = _get_s3_client()
    client.copy_object(
        Bucket=bucket,
        Key=_s3_object_key(dest_key),
        CopySource={"Bucket": bucket, "Key": _s3_object_key(pending_key)},
        ContentType=content_type,
        MetadataDirective="REPLACE",
    )
    client.delete_object(Bucket=bucket, Key=_s3_object_key(pending_key))
    return dest_key, size, content_type


def _ext_from_content_type(content_type: str) -> str:
    mapping = {
        "image/jpeg": "jpg",
        "image/png": "png",
        "image/webp": "webp",
    }
    ext = mapping.get(content_type.split(";")[0].strip().lower())
    if not ext:
        raise ValueError("unsupported content type")
    return ext


async def head_pending_object(file_key: str) -> dict[str, Any]:
    return await run_in_threadpool(_head_pending_object_sync, file_key)


async def promote_pending_object(pending_key: str, dest_purpose: str) -> tuple[str, int, str]:
    return await run_in_threadpool(_promote_pending_object_sync, pending_key, dest_purpose)


def _local_save(key: str, content: bytes, content_type: str) -> str:
    filepath = UPLOAD_DIR / key
    filepath.parent.mkdir(parents=True, exist_ok=True)
    filepath.write_bytes(content)
    return build_url(key)


def _local_delete(key: str) -> None:
    filepath = UPLOAD_DIR / key
    if filepath.exists():
        filepath.unlink(missing_ok=True)
