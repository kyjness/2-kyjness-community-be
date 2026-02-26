import logging
import threading

from app.core.config import settings
from app.core.database import get_connection


def run_once() -> None:
    try:
        from app.auth.model import AuthModel
        AuthModel.cleanup_expired_sessions()
    except Exception as e:
        logging.getLogger(__name__).warning("Session cleanup failed: %s", e)
    try:
        from app.media.model import MediaModel
        with get_connection() as db:
            MediaModel.cleanup_expired_signup_images(db, ttl_seconds=settings.SIGNUP_IMAGE_TOKEN_TTL_SECONDS)
    except Exception as e:
        logging.getLogger(__name__).warning("Signup image cleanup failed: %s", e)


def run_loop(stop_event: threading.Event) -> None:
    interval = max(60, settings.SESSION_CLEANUP_INTERVAL)
    while True:
        run_once()
        if stop_event.wait(timeout=interval):
            break
    run_once()
