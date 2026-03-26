# 만료된 회원가입용 임시 이미지 정리. Full-Async: run_once 비동기, run_loop_async(lifespan).
# HTTP request가 없으므로 실행마다 task_id(UUID)를 발급해 로그 상관관계에 사용.
import asyncio
import logging
import uuid

from app.core.config import settings
from app.db import get_connection

log = logging.getLogger(__name__)


async def run_once() -> None:
    task_id = str(uuid.uuid4())
    log.info("cleanup_start task_id=%s", task_id)

    # 1) 회원가입 임시 이미지 정리
    try:
        from app.media.service import MediaService

        async with get_connection() as db:
            deleted_count, failed_file_keys = await MediaService.cleanup_expired_signup_images(
                db, task_id=task_id
            )
        if failed_file_keys:
            log.warning(
                "signup_image_cleanup_partial task_id=%s deleted_count=%s storage_delete_failed=%s keys=%s",
                task_id,
                deleted_count,
                len(failed_file_keys),
                failed_file_keys,
            )
            log.warning("[S3_DELETE_RETRY_NEEDED] task_id=%s keys=%s", task_id, failed_file_keys)
        elif deleted_count:
            log.info("signup_image_cleanup_done task_id=%s deleted_count=%s", task_id, deleted_count)
    except Exception as e:
        log.warning("signup_image_cleanup_failed task_id=%s error=%s", task_id, e)

    # 2) 게시글 작성 중 이탈 등으로 남은 고아 이미지(24h+) 정리
    try:
        from app.media.service import MediaService

        async with get_connection() as db:
            deleted = await MediaService.sweep_unused_images(db)
        if deleted:
            log.info("orphan_post_image_cleanup_done task_id=%s deleted_count=%s", task_id, deleted)
    except Exception as e:
        log.warning("orphan_post_image_cleanup_failed task_id=%s error=%s", task_id, e)

    # 3) 탈퇴 유저 파기(30일 경과 하드 삭제, 청크 단위)
    try:
        from app.users.service import UserService

        async with get_connection() as db:
            deleted_users = await UserService.purge_withdrawn_users(older_than_days=30, db=db)
        if deleted_users:
            log.info("withdrawn_user_purge_done task_id=%s deleted_count=%s", task_id, deleted_users)
    except Exception as e:
        log.warning("withdrawn_user_purge_failed task_id=%s error=%s", task_id, e)


async def run_loop_async(stop_event: asyncio.Event) -> None:
    interval = max(60, settings.SIGNUP_IMAGE_CLEANUP_INTERVAL)
    while not stop_event.is_set():
        await run_once()
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=float(interval))
        except TimeoutError:
            pass  # Intended: interval elapsed, run cleanup again
