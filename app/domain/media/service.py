# 미디어 비즈니스 로직. 순수 데이터 반환·커스텀 예외. HTTP·ApiResponse 없음. Full-Async.
from __future__ import annotations

import asyncio
import logging
import secrets
from typing import Any, cast

from fastapi import UploadFile
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import (
    ImageNotFoundException,
    InternalServerErrorException,
    InvalidRequestException,
)
from app.core.config import settings
from app.infra.storage import storage_delete
from app.media.image_policy import save_image_for_media
from app.media.model import MediaModel
from app.media.schema import ImageUploadResponse, SignupImageUploadData

logger = logging.getLogger(__name__)

_UPLOAD_TOKEN_KEY_PREFIX = "upload_token:"


class MediaService:
    @classmethod
    async def issue_upload_token(cls, image_id: int, redis: Redis | None) -> str:
        if redis is None:
            raise InternalServerErrorException("Redis unavailable for upload token issuance.")
        token = secrets.token_urlsafe(32)
        key = f"{_UPLOAD_TOKEN_KEY_PREFIX}{token}"
        # Token이 소유권 검증/첨부 단회성임을 보장하기 위해 TTL로 제한.
        r = cast(Any, redis)
        await r.set(key, str(image_id), ex=settings.SIGNUP_IMAGE_TOKEN_TTL_SECONDS)
        return token

    @classmethod
    async def verify_upload_token(cls, token: str, redis: Redis | None) -> int | None:
        if not token or redis is None:
            return None
        key = f"{_UPLOAD_TOKEN_KEY_PREFIX}{token}"
        try:
            r = cast(Any, redis)
            image_id_raw = await r.get(key)
            if image_id_raw is None:
                return None
            # 사용 즉시 토큰 폐기(단일 사용). 경쟁 상황은 DB 첨부 조건(uploader_id is None)로 안전하게 처리.
            await r.delete(key)
            return int(image_id_raw)
        except Exception as e:
            logger.warning("verify_upload_token redis error: %s", e)
            return None

    @classmethod
    async def upload_image_for_signup(
        cls, file: UploadFile, db: AsyncSession, redis: Redis | None
    ) -> SignupImageUploadData:
        file_key, file_url, content_type, size = await save_image_for_media(file, purpose="signup")
        image = None
        try:
            async with db.begin():
                image = await MediaModel.create_temp_image(
                    file_key=file_key,
                    file_url=file_url,
                    content_type=content_type,
                    size=size,
                    db=db,
                )
            signup_token = await cls.issue_upload_token(image.id, redis=redis)
            return SignupImageUploadData(
                id=image.id,
                file_url=image.file_url,
                signup_token=signup_token,
            )
        except Exception:
            try:
                if image is not None:
                    async with db.begin():
                        await MediaModel.delete_images_by_ids([image.id], db=db)
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
        file_key, file_url, content_type, size = await save_image_for_media(file, purpose=purpose)
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
    async def delete_image(cls, image_id: int, user_id: int, db: AsyncSession) -> None:
        file_key = None
        async with db.begin():
            image = await MediaModel.get_image_by_id(image_id, db=db)
            if not image or image.uploader_id != user_id:
                raise ImageNotFoundException()
            file_key = image.file_key
            await MediaModel.delete_image_record(image, db=db)
        if file_key:
            await asyncio.to_thread(storage_delete, file_key)

    @classmethod
    async def sweep_unused_images(cls, db: AsyncSession) -> int:
        """24시간 이상 경과 + users/dog_profiles/post_images 어디에도 연결되지 않은 이미지 정리."""
        # 1) 조회 트랜잭션: orphan 이미지를 스냅샷으로 확보(네트워크 I/O는 트랜잭션 밖에서 수행).
        async with db.begin():
            orphan_images = await MediaModel.get_orphan_images_older_than(
                older_than_hours=24, db=db
            )

        if not orphan_images:
            return 0

        # 2) I/O 작업: DB 락/트랜잭션을 오래 물고 있지 않기 위해 storage_delete는 트랜잭션 밖에서 수행.
        deletable_ids: list[int] = []
        for img in orphan_images:
            try:
                await asyncio.to_thread(storage_delete, img.file_key)
                deletable_ids.append(img.id)
            except Exception as e:
                # 루프는 계속 진행: 단일 이미지 실패가 전체 스윕을 중단하지 않도록.
                logger.warning(
                    "Sweep storage delete failed image_id=%s file_key=%s: %s",
                    img.id,
                    img.file_key,
                    e,
                )

        if not deletable_ids:
            return 0

        # 3) 삭제 트랜잭션: DB에 레코드 일괄 삭제(네트워크 I/O 없음).
        async with db.begin():
            return await MediaModel.delete_images_by_ids(deletable_ids, db=db)

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
