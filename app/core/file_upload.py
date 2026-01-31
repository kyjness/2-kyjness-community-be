# app/core/file_upload.py
"""파일 업로드 정책·검증 공통 (라우터/컨트롤러에서 분리)."""

from typing import List, Optional
from fastapi import UploadFile

from app.core.response import raise_http_error
from app.core.config import settings

PROFILE_ALLOWED_TYPES = ["image/jpeg", "image/jpg"]
POST_ALLOWED_TYPES = settings.ALLOWED_IMAGE_TYPES
MAX_FILE_SIZE = settings.MAX_FILE_SIZE


def _magic_jpeg(content: bytes) -> bool:
    return len(content) >= 2 and content[:2] == b"\xff\xd8"


def _magic_png(content: bytes) -> bool:
    return len(content) >= 8 and content[:8] == b"\x89PNG\r\n\x1a\n"


async def validate_image_upload(
    file: Optional[UploadFile],
    allowed_types: List[str],
    max_size: int = MAX_FILE_SIZE,
) -> bytes:
    """이미지 업로드 검증. 통과 시 본문 bytes 반환, 실패 시 raise_http_error."""
    if not file:
        raise_http_error(400, "MISSING_REQUIRED_FIELD")
    if file.content_type not in allowed_types:
        raise_http_error(400, "INVALID_FILE_TYPE")
    content = await file.read()
    if not content:
        raise_http_error(400, "INVALID_IMAGE_FILE")
    if len(content) > max_size:
        raise_http_error(400, "FILE_SIZE_EXCEEDED")
    if "jpeg" in (file.content_type or "") or "jpg" in (file.content_type or ""):
        if not _magic_jpeg(content):
            raise_http_error(400, "UNSUPPORTED_IMAGE_FORMAT")
    elif file.content_type == "image/png":
        if not _magic_png(content):
            raise_http_error(400, "UNSUPPORTED_IMAGE_FORMAT")
    return content
