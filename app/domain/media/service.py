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
_JOB_LOCK_SWEEP_UNUSED = "lock:media-sweep"
_JOB_LOCK_SIGNUP_CLEANUP = "lock:media-signup-cleanup"
_JOB_LOCK_TTL_SECONDS = 600


async def _release_job_lock(redis: Any, *, lock_key: str, lock_value: str) -> None:
    """락 소유자만 해제(compare-and-delete)."""
    try:
        await redis.eval(
            "if redis.call('GET', KEYS[1]) == ARGV[1] then "
            "return redis.call('DEL', KEYS[1]) else return 0 end",
            1,
            lock_key,
            lock_value,
        )
    except Exception as e:
        # TTL 기반 자동 해제를 신뢰하고, 실패 시 경고만 남긴다.
        logger.warning("job lock release failed key=%s err=%s", lock_key, e)


async def _try_acquire_job_lock(
    redis: Redis | None,
    *,
    lock_key: str,
    ttl_seconds: int,
) -> tuple[bool, str | None]:
    """잡 락 획득 시도. 실패(이미 점유)면 조용히 skip하도록 (False, None) 반환."""
    if redis is None:
        # Redis 미사용 환경은 단일 노드 개발 모드로 간주하고 작업을 진행한다.
        return True, None
    try:
        r = cast(Any, redis)
        lock_value = secrets.token_urlsafe(24)
        acquired = bool(await r.set(lock_key, lock_value, nx=True, ex=ttl_seconds))
        return acquired, (lock_value if acquired else None)
    except Exception as e:
        # 스케줄러 작업의 보수적 가용성: Redis 장애 시 락 없이 진행.
        logger.warning("job lock unavailable key=%s fallback_without_lock err=%s", lock_key, e)
        return True, None


class MediaService:
    @classmethod
    async def issue_upload_token(cls, image_id: str, redis: Redis | None) -> str:
        if redis is None:
            raise InternalServerErrorException("Redis unavailable for upload token issuance.")
        token = secrets.token_urlsafe(32)
        key = f"{_UPLOAD_TOKEN_KEY_PREFIX}{token}"
        # Token이 소유권 검증/첨부 단회성임을 보장하기 위해 TTL로 제한.
        r = cast(Any, redis)
        await r.set(key, str(image_id), ex=settings.SIGNUP_IMAGE_TOKEN_TTL_SECONDS)
        return token

    @classmethod
    async def verify_upload_token(cls, token: str, redis: Redis | None) -> str | None:
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
            if isinstance(image_id_raw, bytes):
                image_id = image_id_raw.decode("utf-8")
            elif isinstance(image_id_raw, str):
                image_id = image_id_raw
            else:
                return None
            return image_id or None
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
        user_id: str,
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
    async def delete_image(cls, image_id: str, user_id: str, db: AsyncSession) -> None:
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
    async def sweep_unused_images(cls, db: AsyncSession, redis: Redis | None = None) -> int:
        """24시간 이상 경과 + users/dog_profiles/post_images 어디에도 연결되지 않은 이미지 정리."""
        acquired, lock_value = await _try_acquire_job_lock(
            redis,
            lock_key=_JOB_LOCK_SWEEP_UNUSED,
            ttl_seconds=_JOB_LOCK_TTL_SECONDS,
        )
        if not acquired:
            logger.info("skip sweep_unused_images: lock already held")
            return 0
        r = cast(Any, redis) if redis is not None else None
        try:
            batch_size = settings.MEDIA_SWEEP_UNUSED_BATCH_SIZE
            total_deleted = 0

            while True:
                # 1) 짧은 조회 트랜잭션: 배치 단위로 orphan 확보(대량 시 긴 락·단일 DELETE 완화).
                async with db.begin():
                    orphan_images = await MediaModel.get_orphan_images_older_than(
                        older_than_hours=24,
                        db=db,
                        limit=batch_size,
                    )

                if not orphan_images:
                    break

                # 2) 스토리지 I/O는 DB 트랜잭션 밖에서 수행.
                deletable_ids: list[str] = []
                for img in orphan_images:
                    try:
                        await asyncio.to_thread(storage_delete, img.file_key)
                        deletable_ids.append(img.id)
                    except Exception as e:
                        logger.warning(
                            "Sweep storage delete failed image_id=%s file_key=%s: %s",
                            img.id,
                            img.file_key,
                            e,
                        )

                if not deletable_ids:
                    logger.warning(
                        "sweep_unused_images: batch had %s row(s) but no storage delete succeeded; "
                        "stopping this run to avoid a tight loop",
                        len(orphan_images),
                    )
                    break

                # 3) 짧은 삭제 트랜잭션: 성공한 id만 DB에서 제거.
                async with db.begin():
                    n = await MediaModel.delete_images_by_ids(deletable_ids, db=db)
                    total_deleted += n

                if len(orphan_images) < batch_size:
                    break

            return total_deleted
        finally:
            if lock_value and r is not None:
                await _release_job_lock(
                    r,
                    lock_key=_JOB_LOCK_SWEEP_UNUSED,
                    lock_value=lock_value,
                )

    @classmethod
    async def cleanup_expired_signup_images(
        cls, db: AsyncSession, *, task_id: str, redis: Redis | None = None
    ) -> tuple[int, list[str]]:
        acquired, lock_value = await _try_acquire_job_lock(
            redis,
            lock_key=_JOB_LOCK_SIGNUP_CLEANUP,
            ttl_seconds=_JOB_LOCK_TTL_SECONDS,
        )
        if not acquired:
            logger.info("skip cleanup_expired_signup_images task_id=%s: lock already held", task_id)
            return 0, []
        r = cast(Any, redis) if redis is not None else None
        try:
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
        finally:
            if lock_value and r is not None:
                await _release_job_lock(
                    r,
                    lock_key=_JOB_LOCK_SIGNUP_CLEANUP,
                    lock_value=lock_value,
                )
