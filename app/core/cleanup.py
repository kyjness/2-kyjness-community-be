# 만료 세션·회원가입용 이미지 TTL 정리. run_once + run_loop(주기 스레드).
import logging
import threading

from app.core.config import settings
from app.db import get_connection


def run_once() -> None:
    try:
        from app.auth.model import AuthModel
        AuthModel.cleanup_expired_sessions()
    except Exception as e:
        logging.getLogger(__name__).warning("Session cleanup failed: %s", e)
    try:
        from app.media.model import MediaModel
        with get_connection() as db:
            deleted_count, failed_file_keys = MediaModel.cleanup_expired_signup_images(db)
        if failed_file_keys:
            logging.getLogger(__name__).warning(
                "Signup image cleanup: %s rows soft-deleted, %s storage delete failed (retry later): %s",
                deleted_count,
                len(failed_file_keys),
                failed_file_keys,
            )
    except Exception as e:
        logging.getLogger(__name__).warning("Signup image cleanup failed: %s", e)


def run_loop(stop_event: threading.Event) -> None:
    interval = max(60, settings.SESSION_CLEANUP_INTERVAL)
    while True:
        run_once()
        if stop_event.wait(timeout=interval):
            break
    run_once()
