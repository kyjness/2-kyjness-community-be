# 이미지 업로드 정책. purpose 검증, 매직바이트 포맷 판별, 청크 읽기, 저장(스레드).
# 커스텀 예외 사용 → 전역 handler가 400 응답 처리.
import asyncio
import uuid
from typing import Literal

from fastapi import UploadFile

from app.common.exceptions import (
    FileSizeExceededException,
    InvalidFileTypeException,
    InvalidImageFileException,
    InvalidRequestException,
    MissingRequiredFieldException,
)
from app.core.config import settings
from app.infra.storage import storage_save

ImagePurpose = Literal["signup", "profile", "post"]
IMAGE_PURPOSES: tuple[ImagePurpose, ...] = ("signup", "profile", "post")


def validate_purpose(purpose: ImagePurpose) -> None:
    if purpose not in IMAGE_PURPOSES:
        raise InvalidRequestException()


def sniff_image_type(content_start: bytes) -> tuple[str, str]:
    JPEG_HEADER = b"\xff\xd8\xff"
    PNG_HEADER = b"\x89PNG\r\n\x1a\n"

    if len(content_start) < 3:
        raise InvalidImageFileException()
    if content_start[:3] == JPEG_HEADER:
        return "image/jpeg", "jpg"
    if len(content_start) >= 8 and content_start[:8] == PNG_HEADER:
        return "image/png", "png"
    if len(content_start) >= 12 and content_start[:4] == b"RIFF" and content_start[8:12] == b"WEBP":
        return "image/webp", "webp"
    raise InvalidImageFileException()


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
            raise FileSizeExceededException()
        buf.extend(chunk)
    if not buf:
        raise InvalidImageFileException()
    return bytes(buf)


def _generate_key(purpose: ImagePurpose, ext: str) -> str:
    filename = f"{uuid.uuid4().hex}.{ext}"
    return f"{purpose}/{filename}"


async def save_image_for_media(
    file: UploadFile | None,
    purpose: ImagePurpose = "post",
    allowed_types: list[str] | None = None,
    max_size: int | None = None,
) -> tuple[str, str, str, int]:
    validate_purpose(purpose)
    if not file:
        raise MissingRequiredFieldException()
    if max_size is None:
        max_size = settings.MAX_FILE_SIZE
    types = allowed_types or settings.ALLOWED_IMAGE_TYPES
    allowed_set = set(types)

    content = await read_limited(file, max_size)
    SNIFF_HEADER_SIZE = 12
    header = content[:SNIFF_HEADER_SIZE]
    ct, ext = sniff_image_type(header)
    if ct not in allowed_set:
        raise InvalidFileTypeException()

    key = _generate_key(purpose, ext)
    url = await asyncio.to_thread(storage_save, key, content, ct)
    return key, url, ct, len(content)
