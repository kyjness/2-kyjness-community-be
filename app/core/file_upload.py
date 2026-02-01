# app/core/file_upload.py
"""파일 업로드: 검증, 저장, URL 생성. 프로필/게시글 이미지 정책."""

import uuid
from pathlib import Path
from typing import List, Optional

from fastapi import UploadFile

from app.core.config import settings
from app.core.response import raise_http_error

PROFILE_ALLOWED_TYPES = ["image/jpeg", "image/jpg"]
POST_ALLOWED_TYPES = settings.ALLOWED_IMAGE_TYPES
MAX_FILE_SIZE = settings.MAX_FILE_SIZE

# 프로젝트 루트 기준 public 폴더 (main.py에서 StaticFiles 마운트)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PUBLIC_PROFILE_DIR = PROJECT_ROOT / "public" / "image" / "profile"
PUBLIC_POST_DIR = PROJECT_ROOT / "public" / "image" / "post"


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
    - 타입/크기 검증
    - uuid 파일명으로 public/image/profile에 저장
    - 접근 가능한 profileImageUrl 반환
    """
    content = await _validate_image(
        file,
        allowed_types=PROFILE_ALLOWED_TYPES,
        max_size=MAX_FILE_SIZE,
    )

    PUBLIC_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}.jpg"
    filepath = PUBLIC_PROFILE_DIR / filename

    filepath.write_bytes(content)

    profile_image_url = f"{settings.BE_API_URL}/public/image/profile/{filename}"
    return profile_image_url


async def save_post_image(post_id: int, file: Optional[UploadFile]) -> str:
    """
    게시글 이미지: 검증 + 저장 + URL 반환.
    - 타입/크기 검증
    - uuid 파일명으로 public/image/post에 저장
    """
    content = await _validate_image(
        file,
        allowed_types=POST_ALLOWED_TYPES,
        max_size=MAX_FILE_SIZE,
    )

    PUBLIC_POST_DIR.mkdir(parents=True, exist_ok=True)
    ext = "jpg"
    if file.filename and "." in file.filename:
        ext = file.filename.lower().split(".")[-1]
        if ext not in ("jpg", "jpeg", "png"):
            ext = "jpg"
    filename = f"{post_id}_{uuid.uuid4().hex}.{ext}"
    filepath = PUBLIC_POST_DIR / filename

    filepath.write_bytes(content)

    file_url = f"{settings.BE_API_URL}/public/image/post/{filename}"
    return file_url
