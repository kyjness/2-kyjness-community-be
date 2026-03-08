# 로컬/S3 파일 스토리지. STORAGE_BACKEND에 따라 분기.
from pathlib import Path

from app.core.config import settings

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
UPLOAD_DIR = PROJECT_ROOT / "upload"

_s3_client = None


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

    _s3_client = boto3.client(
        "s3",
        region_name=settings.AWS_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    )
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
        if settings.S3_PUBLIC_BASE_URL:
            base = settings.S3_PUBLIC_BASE_URL.rstrip("/")
            return f"{base}/{key}"
        return f"https://{settings.S3_BUCKET_NAME}.s3.{settings.AWS_REGION}.amazonaws.com/{key}"
    base = _be_base_url().rstrip("/")
    return f"{base}/upload/{key}"


def _s3_save(key: str, content: bytes, content_type: str) -> str:
    client = _get_s3_client()
    client.put_object(
        Bucket=settings.S3_BUCKET_NAME,
        Key=key,
        Body=content,
        ContentType=content_type,
    )
    return build_url(key)


def _s3_delete(key: str) -> None:
    client = _get_s3_client()
    client.delete_object(Bucket=settings.S3_BUCKET_NAME, Key=key)


def _local_save(key: str, content: bytes, content_type: str) -> str:
    filepath = UPLOAD_DIR / key
    filepath.parent.mkdir(parents=True, exist_ok=True)
    filepath.write_bytes(content)
    return build_url(key)


def _local_delete(key: str) -> None:
    filepath = UPLOAD_DIR / key
    if filepath.exists():
        filepath.unlink(missing_ok=True)
