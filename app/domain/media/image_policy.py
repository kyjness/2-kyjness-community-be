# 이미지 업로드 정책. purpose 검증, 매직바이트 포맷 판별, 청크 읽기, 저장(스레드).
import asyncio
import uuid
from typing import List, Literal, Optional

from fastapi import UploadFile

from app.core.config import settings
from app.common import ApiCode, raise_http_error
from app.infra.storage import storage_save

ImagePurpose = Literal["signup", "profile", "post"]
IMAGE_PURPOSES: tuple[ImagePurpose, ...] = ("signup", "profile", "post")


def validate_purpose(purpose: ImagePurpose) -> None:
    if purpose not in IMAGE_PURPOSES:
        raise_http_error(400, ApiCode.INVALID_REQUEST)


def sniff_image_type(content_start: bytes) -> tuple[str, str]:
    JPEG_HEADER = b"\xff\xd8\xff"
    PNG_HEADER = b"\x89PNG\r\n\x1a\n"

    if len(content_start) < 3:
        raise_http_error(400, ApiCode.INVALID_IMAGE_FILE)
    if content_start[:3] == JPEG_HEADER:
        return "image/jpeg", "jpg"
    if len(content_start) >= 8 and content_start[:8] == PNG_HEADER:
        return "image/png", "png"
    if len(content_start) >= 12 and content_start[:4] == b"RIFF" and content_start[8:12] == b"WEBP":
        return "image/webp", "webp"
    raise_http_error(400, ApiCode.INVALID_IMAGE_FILE)


async def read_limited(file: UploadFile, max_bytes: int) -> bytes:
    CHUNK_SIZE = 64 * 1024
    buf = bytearray()
    total = 0
    while True:
        chunk = await file.read(CHUNK_SIZE)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise_http_error(400, ApiCode.FILE_SIZE_EXCEEDED)
        buf.extend(chunk)
    if not buf:
        raise_http_error(400, ApiCode.INVALID_IMAGE_FILE)
    return bytes(buf)


def _generate_key(purpose: ImagePurpose, ext: str) -> str:
    filename = f"{uuid.uuid4().hex}.{ext}"
    return f"{purpose}/{filename}"


async def save_image_for_media(
    file: Optional[UploadFile],
    purpose: ImagePurpose = "post",
    allowed_types: Optional[List[str]] = None,
    max_size: Optional[int] = None,
) -> tuple[str, str, str, int]:
    validate_purpose(purpose)
    if not file:
        raise_http_error(400, ApiCode.MISSING_REQUIRED_FIELD)
    if max_size is None:
        max_size = settings.MAX_FILE_SIZE
    types = allowed_types or settings.ALLOWED_IMAGE_TYPES
    allowed_set = set(types)

    content = await read_limited(file, max_size)
    SNIFF_HEADER_SIZE = 12
    header = content[:SNIFF_HEADER_SIZE]
    ct, ext = sniff_image_type(header)
    if ct not in allowed_set:
        raise_http_error(400, ApiCode.INVALID_FILE_TYPE)

    key = _generate_key(purpose, ext)
    url = await asyncio.to_thread(storage_save, key, content, ct)
    return key, url, ct, len(content)
