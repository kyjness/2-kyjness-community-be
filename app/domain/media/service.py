# 미디어 비즈니스 로직. 순수 데이터 반환·커스텀 예외. HTTP·ApiResponse 없음. Full-Async.
from __future__ import annotations

import asyncio
import hmac
import logging
from datetime import datetime, timedelta, timezone

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import (
    ImageInUseException,
    ImageNotFoundException,
    InvalidRequestException,
)
from app.core.config import settings
from app.core.security import hash_token
from app.db import utc_now
from app.infra.storage import storage_delete
from app.media.model import MediaModel
from app.media.schema import ImageUploadResponse, SignupImageUploadData
from app.media.image_policy import save_image_for_media

logger = logging.getLogger(__name__)


class MediaService:
    @classmethod
    async def upload_image_for_signup(
        cls, file: UploadFile, db: AsyncSession
    ) -> SignupImageUploadData:
        file_key, file_url, content_type, size = await save_image_for_media(
            file, purpose="signup"
        )
        try:
            async with db.begin():
                expires_at = utc_now() + timedelta(
                    seconds=settings.SIGNUP_IMAGE_TOKEN_TTL_SECONDS
                )
                image, signup_token = await MediaModel.create_signup_image(
                    file_key=file_key,
                    file_url=file_url,
                    content_type=content_type,
                    size=size,
                    expires_at=expires_at,
                    db=db,
                )
            return SignupImageUploadData(
                id=image.id,
                file_url=image.file_url,
                signup_token=signup_token,
            )
        except Exception:
            try:
                await asyncio.to_thread(storage_delete, file_key)
            except Exception as rollback_e:
                logger.warning(
                    "Rollback storage delete failed after signup image DB error file_key=%s: %s",
                    file_key,
                    rollback_e,
                )
            raise

    @classmethod
    async def upload_image(
        cls,
        file: UploadFile,
        user_id: int,
        purpose: str,
        db: AsyncSession,
    ) -> ImageUploadResponse:
        if purpose not in ("profile", "post"):
            raise InvalidRequestException()
        file_key, file_url, content_type, size = await save_image_for_media(
            file, purpose=purpose
        )
        try:
            async with db.begin():
                image = await MediaModel.create_image(
                    file_key=file_key,
                    file_url=file_url,
                    content_type=content_type,
                    size=size,
                    uploader_id=user_id,
                    db=db,
                )
                return ImageUploadResponse.model_validate(image)
        except Exception:
            try:
                await asyncio.to_thread(storage_delete, file_key)
            except Exception as rollback_e:
                logger.warning(
                    "Rollback storage delete failed after create_image DB error file_key=%s: %s",
                    file_key,
                    rollback_e,
                )
            raise

    @classmethod
    async def verify_signup_token(cls, image_id: int, token: str, db: AsyncSession):
        image = await MediaModel.get_signup_image(image_id, db)
        if not image or image.uploader_id is not None:
            return None
        expected_hash = hash_token(token)
        if not hmac.compare_digest(image.signup_token_hash or "", expected_hash):
            return None
        if image.signup_expires_at is None:
            return None
        now = utc_now()
        expires_at = image.signup_expires_at
        if isinstance(expires_at, datetime) and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at <= now:
            return None
        return image

    @classmethod
    async def delete_image(cls, image_id: int, user_id: int, db: AsyncSession) -> None:
        file_key = None
        async with db.begin():
            image = await MediaModel.get_image_by_id(image_id, db=db)
            if not image or image.uploader_id != user_id:
                raise ImageNotFoundException()
            if image.ref_count > 0:
                raise ImageInUseException()
            file_key = image.file_key
            await MediaModel.delete_image_record(image, db=db)
        if file_key:
            await asyncio.to_thread(storage_delete, file_key)

    @classmethod
    async def decrement_ref_count(cls, image_id: int, db: AsyncSession) -> None:
        async def _run(session: AsyncSession):
            image = await MediaModel.decrement_ref_count(image_id, db=session)
            if image is None:
                return None
            if image.ref_count <= 0:
                file_key = image.file_key
                await MediaModel.delete_image_record(image, db=session)
                return file_key
            return None

        file_key_to_delete = None
        if db.in_transaction():
            file_key_to_delete = await _run(db)
        else:
            async with db.begin():
                file_key_to_delete = await _run(db)
        if file_key_to_delete:
            try:
                await asyncio.to_thread(storage_delete, file_key_to_delete)
            except Exception as e:
                logger.warning(
                    "Image file delete failed image_id=%s file_key=%s: %s",
                    image_id,
                    file_key_to_delete,
                    e,
                )

    @classmethod
    async def cleanup_expired_signup_images(
        cls, db: AsyncSession, *, task_id: str
    ) -> tuple[int, list[str]]:
        failed_file_keys: list[str] = []
        async with db.begin():
            rows = await MediaModel.get_expired_signup_images(db=db)
            if not rows:
                return 0, []
            for img in rows:
                try:
                    await asyncio.to_thread(storage_delete, img.file_key)
                except Exception as e:
                    logger.warning(
                        "Signup image storage delete failed task_id=%s image_id=%s file_key=%s: %s",
                        task_id,
                        img.id,
                        img.file_key,
                        e,
                        exc_info=True,
                    )
                    failed_file_keys.append(img.file_key)
                await MediaModel.delete_image_record(img, db=db)
        return len(rows), failed_file_keys
