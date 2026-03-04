# 만료 세션·회원가입용 이미지 TTL 정리. asyncio 전용: run_once(동기), run_loop_async(lifespan).
import asyncio
import logging

from app.core.config import settings
from app.db import get_connection

log = logging.getLogger(__name__)


def run_once() -> None:
    try:
        from app.auth.model import AuthModel
        AuthModel.cleanup_expired_sessions()
    except Exception as e:
        log.warning("Session cleanup failed: %s", e)
    try:
        from app.media.model import MediaModel
        with get_connection() as db:
            deleted_count, failed_file_keys = MediaModel.cleanup_expired_signup_images(db)
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
        await asyncio.to_thread(run_once)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=float(interval))
        except asyncio.TimeoutError:
            pass
    run_once()
