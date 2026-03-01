# 로컬/S3 파일 업로드. STORAGE_BACKEND에 따라 저장소 분기.
from pathlib import Path

from app.core.config import settings

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
UPLOAD_DIR = PROJECT_ROOT / "upload"


def storage_save(key: str, content: bytes, content_type: str) -> str:
    if settings.STORAGE_BACKEND == "s3":
        return _s3_save(key, content, content_type)
    return _local_save(key, content, content_type)


def storage_delete(key: str) -> None:
    if settings.STORAGE_BACKEND == "s3":
        _s3_delete(key)
    else:
        _local_delete(key)


def build_url(key: str) -> str:
    if settings.STORAGE_BACKEND == "s3":
        if settings.S3_PUBLIC_BASE_URL:
            base = settings.S3_PUBLIC_BASE_URL.rstrip("/")
            return f"{base}/{key}"
        return f"https://{settings.S3_BUCKET_NAME}.s3.{settings.AWS_REGION}.amazonaws.com/{key}"
    return f"{settings.BE_API_URL}/upload/{key}"


def _s3_save(key: str, content: bytes, content_type: str) -> str:
    import boto3
    if not settings.S3_BUCKET_NAME or not settings.AWS_ACCESS_KEY_ID or not settings.AWS_SECRET_ACCESS_KEY:
        raise ValueError(
            "S3_BUCKET_NAME, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY must be set when STORAGE_BACKEND=s3"
        )
    client = boto3.client(
        "s3",
        region_name=settings.AWS_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    )
    client.put_object(
        Bucket=settings.S3_BUCKET_NAME,
        Key=key,
        Body=content,
        ContentType=content_type,
    )
    return build_url(key)


def _s3_delete(key: str) -> None:
    import boto3
    if not settings.S3_BUCKET_NAME or not settings.AWS_ACCESS_KEY_ID or not settings.AWS_SECRET_ACCESS_KEY:
        raise ValueError(
            "S3_BUCKET_NAME, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY must be set when STORAGE_BACKEND=s3"
        )
    client = boto3.client(
        "s3",
        region_name=settings.AWS_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    )
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
