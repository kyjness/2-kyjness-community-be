# app/core/file_upload.py
"""파일 업로드 인프라: 검증, 저장, URL 생성. local | S3. 실제 API는 app.media에서 제공."""

import uuid
from pathlib import Path
from typing import List, Optional

from fastapi import UploadFile

from app.core.config import settings
from app.core.codes import ApiCode
from app.core.response import raise_http_error

MAX_FILE_SIZE = settings.MAX_FILE_SIZE

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
UPLOAD_DIR = PROJECT_ROOT / "upload"
# 저장 서브폴더: profile(회원 프로필), post(게시글 이미지). images 폴더는 사용하지 않음.
VALID_UPLOAD_FOLDERS = ("profile", "post")


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
    """이미지 검증: 존재·Content-Type·크기만. 확장자는 제한하지 않음."""
    if not file:
        raise_http_error(400, ApiCode.MISSING_REQUIRED_FIELD)

    if file.content_type not in allowed_types:
        raise_http_error(400, ApiCode.INVALID_FILE_TYPE)

    content = await file.read()
    if not content:
        raise_http_error(400, ApiCode.INVALID_IMAGE_FILE)

    if len(content) > max_size:
        raise_http_error(400, ApiCode.FILE_SIZE_EXCEEDED)

    return content


def _safe_extension(filename: Optional[str], content_type: str) -> str:
    """파일명에서 확장자 추출. 없거나 비정상이면 content_type 기준으로 반환."""
    if filename and "." in filename:
        ext = filename.lower().split(".")[-1].strip()
        if ext and len(ext) <= 5 and ext.isalnum():
            return ext
    if "png" in content_type:
        return "png"
    return "jpg"


async def save_image_for_media(
    file: Optional[UploadFile],
    allowed_types: Optional[List[str]] = None,
    max_size: int = MAX_FILE_SIZE,
    folder: str = "post",
) -> tuple[str, str, str, int]:
    """
    이미지 검증 후 저장. (file_key, file_url, content_type, size) 반환.
    folder: "profile"(회원 프로필) | "post"(게시글). 메타 저장은 media.controller에서 수행.
    """
    if folder not in VALID_UPLOAD_FOLDERS:
        folder = "post"
    types = allowed_types or settings.ALLOWED_IMAGE_TYPES
    content = await _validate_image(file, allowed_types=types, max_size=max_size)
    ext = _safe_extension(file.filename if file else None, file.content_type or "")
    filename = f"{uuid.uuid4().hex}.{ext}"
    ct = file.content_type or "image/jpeg"
    key = f"{folder}/{filename}"
    if settings.STORAGE_BACKEND == "s3":
        url = _s3_upload(key, content, ct)
    else:
        subdir = UPLOAD_DIR / folder
        subdir.mkdir(parents=True, exist_ok=True)
        filepath = subdir / filename
        filepath.write_bytes(content)
        url = f"{settings.BE_API_URL}/upload/{folder}/{filename}"
    return key, url, ct, len(content)
