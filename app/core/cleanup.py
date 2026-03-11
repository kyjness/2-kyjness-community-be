# 만료 세션·회원가입용 이미지 TTL 정리. Full-Async: run_once 비동기, run_loop_async(lifespan).
import asyncio
import logging

from app.core.config import settings
from app.db import get_connection

log = logging.getLogger(__name__)


async def run_once() -> None:
    try:
        from app.media.service import MediaService

        async with get_connection() as db:
            (
                deleted_count,
                failed_file_keys,
            ) = await MediaService.cleanup_expired_signup_images(db)
        if failed_file_keys:
            log.warning(
                "Signup image cleanup: %s rows soft-deleted, %s storage delete failed (retry later): %s",
                deleted_count,
                len(failed_file_keys),
                failed_file_keys,
            )
            log.warning("[S3_DELETE_RETRY_NEEDED] keys: %s", failed_file_keys)
    except Exception as e:
        log.warning("Signup image cleanup failed: %s", e)


async def run_loop_async(stop_event: asyncio.Event) -> None:
    interval = max(60, settings.SESSION_CLEANUP_INTERVAL)
    while not stop_event.is_set():
        await run_once()
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=float(interval))
        except TimeoutError:
            pass  # Intended: interval elapsed, run cleanup again
