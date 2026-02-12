# app/core/file_upload.py
"""파일 업로드: 검증, 저장, URL 생성. 프로필/게시글 이미지·비디오. local | S3 지원."""

import uuid
from pathlib import Path
from typing import List, Optional

from fastapi import UploadFile

from app.core.config import settings
from app.core.response import raise_http_error

PROFILE_ALLOWED_TYPES = ["image/jpeg", "image/jpg"]
POST_ALLOWED_TYPES = settings.ALLOWED_IMAGE_TYPES
POST_VIDEO_ALLOWED_TYPES = settings.ALLOWED_VIDEO_TYPES
MAX_FILE_SIZE = settings.MAX_FILE_SIZE
MAX_VIDEO_SIZE = settings.MAX_VIDEO_SIZE

# 프로젝트 루트 기준 upload 폴더 (STORAGE_BACKEND=local 시, main.py에서 StaticFiles 마운트)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
UPLOAD_PROFILE_DIR = PROJECT_ROOT / "upload" / "image" / "profile"
UPLOAD_POST_DIR = PROJECT_ROOT / "upload" / "image" / "post"
UPLOAD_VIDEO_DIR = PROJECT_ROOT / "upload" / "video" / "post"


def _s3_upload(key: str, content: bytes, content_type: str) -> str:
    """S3에 업로드 후 공개 URL 반환. STORAGE_BACKEND=s3 일 때만 호출."""
    import boto3
    if not settings.S3_BUCKET_NAME or not settings.AWS_ACCESS_KEY_ID or not settings.AWS_SECRET_ACCESS_KEY:
        raise ValueError("S3_BUCKET_NAME, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY must be set when STORAGE_BACKEND=s3")

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
    if settings.S3_PUBLIC_BASE_URL:
        base = settings.S3_PUBLIC_BASE_URL.rstrip("/")
        return f"{base}/{key}"
    return f"https://{settings.S3_BUCKET_NAME}.s3.{settings.AWS_REGION}.amazonaws.com/{key}"


async def _validate_image(
    file: Optional[UploadFile],
    allowed_types: List[str],
    max_size: int = MAX_FILE_SIZE,
) -> bytes:
    """이미지 검증: 존재·Content-Type·크기·확장자. bytes 반환."""
    if not file:
        raise_http_error(400, "MISSING_REQUIRED_FIELD")

    if file.content_type not in allowed_types:
        raise_http_error(400, "INVALID_FILE_TYPE")

    content = await file.read()
    if not content:
        raise_http_error(400, "INVALID_IMAGE_FILE")

    if len(content) > max_size:
        raise_http_error(400, "FILE_SIZE_EXCEEDED")

    if file.filename:
        ext = file.filename.lower().split(".")[-1] if "." in file.filename else ""
        if ext not in ["jpg", "jpeg", "png"]:
            raise_http_error(400, "INVALID_FILE_TYPE")

    return content


async def validate_image_upload(
    file: Optional[UploadFile],
    allowed_types: List[str],
    max_size: int = MAX_FILE_SIZE,
) -> bytes:
    """
    이미지 업로드 검증만 수행 (게시글 등 다른 용도에서 재사용).
    검증+저장+URL이 필요하면 save_profile_image 사용.
    """
    return await _validate_image(file, allowed_types, max_size)


async def save_profile_image(file: Optional[UploadFile]) -> str:
    """
    프로필 이미지: 검증 + 저장 + URL 반환.
    STORAGE_BACKEND=local → upload/image/profile, s3 → S3 버킷 image/profile/
    """
    content = await _validate_image(
        file,
        allowed_types=PROFILE_ALLOWED_TYPES,
        max_size=MAX_FILE_SIZE,
    )

    filename = f"{uuid.uuid4().hex}.jpg"
    if settings.STORAGE_BACKEND == "s3":
        key = f"image/profile/{filename}"
        return _s3_upload(key, content, "image/jpeg")
    UPLOAD_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    filepath = UPLOAD_PROFILE_DIR / filename
    filepath.write_bytes(content)
    return f"{settings.BE_API_URL}/upload/image/profile/{filename}"


async def save_post_image(post_id: int, file: Optional[UploadFile]) -> str:
    """
    게시글 이미지: 검증 + 저장 + URL 반환.
    STORAGE_BACKEND=local → upload/image/post, s3 → S3 버킷 image/post/
    """
    content = await _validate_image(
        file,
        allowed_types=POST_ALLOWED_TYPES,
        max_size=MAX_FILE_SIZE,
    )

    ext = "jpg"
    if file.filename and "." in file.filename:
        ext = file.filename.lower().split(".")[-1]
        if ext not in ("jpg", "jpeg", "png"):
            ext = "jpg"
    filename = f"{post_id}_{uuid.uuid4().hex}.{ext}"
    content_type = "image/jpeg" if ext in ("jpg", "jpeg") else "image/png"

    if settings.STORAGE_BACKEND == "s3":
        key = f"image/post/{filename}"
        return _s3_upload(key, content, content_type)
    UPLOAD_POST_DIR.mkdir(parents=True, exist_ok=True)
    filepath = UPLOAD_POST_DIR / filename
    filepath.write_bytes(content)
    return f"{settings.BE_API_URL}/upload/image/post/{filename}"


async def _validate_video(
    file: Optional[UploadFile],
    allowed_types: List[str],
    max_size: int = MAX_VIDEO_SIZE,
) -> bytes:
    """비디오 검증: 존재·Content-Type·크기·확장자. bytes 반환."""
    if not file:
        raise_http_error(400, "MISSING_REQUIRED_FIELD")
    if file.content_type not in allowed_types:
        raise_http_error(400, "INVALID_FILE_TYPE")
    content = await file.read()
    if not content:
        raise_http_error(400, "INVALID_VIDEO_FILE")
    if len(content) > max_size:
        raise_http_error(400, "FILE_SIZE_EXCEEDED")
    if file.filename:
        ext = file.filename.lower().split(".")[-1] if "." in file.filename else ""
        if ext not in ("mp4", "webm"):
            raise_http_error(400, "INVALID_FILE_TYPE")
    return content


async def save_post_video(post_id: int, file: Optional[UploadFile]) -> str:
    """
    게시글 비디오: 검증 + 저장 + URL 반환.
    STORAGE_BACKEND=local → upload/video/post, s3 → S3 버킷 video/post/
    """
    content = await _validate_video(
        file,
        allowed_types=POST_VIDEO_ALLOWED_TYPES,
        max_size=MAX_VIDEO_SIZE,
    )
    ext = "mp4"
    if file.filename and "." in file.filename:
        e = file.filename.lower().split(".")[-1]
        if e in ("mp4", "webm"):
            ext = e
    content_type = "video/mp4" if ext == "mp4" else "video/webm"
    filename = f"{post_id}_{uuid.uuid4().hex}.{ext}"

    if settings.STORAGE_BACKEND == "s3":
        key = f"video/post/{filename}"
        return _s3_upload(key, content, content_type)
    UPLOAD_VIDEO_DIR.mkdir(parents=True, exist_ok=True)
    filepath = UPLOAD_VIDEO_DIR / filename
    filepath.write_bytes(content)
    return f"{settings.BE_API_URL}/upload/video/post/{filename}"
